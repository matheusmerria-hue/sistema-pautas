import sqlite3
from datetime import datetime
from config import DB_PATH
import re
import json
import unicodedata
from functools import wraps
from contextlib import closing
from collections import Counter


# ==========================================================
# CONEXÃO COM O BANCO DE DADOS
# ==========================================================

def get_connection():
    """
    Abre a conexão com o banco SQLite.

    Caso a pasta onde o banco ficará salvo ainda não exista,
    ela será criada automaticamente.
    """

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.create_function("normalizar", 1, normalizar, deterministic=True)
    return conn


def normalizar(valor):
    texto = " ".join((valor or "").split()).casefold()
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if not unicodedata.combining(c))


def compat_cliente(func):
    """Aceita o antigo argumento nomeado durante a transição das integrações."""
    @wraps(func)
    def call(*args, **kwargs):
        if "candidato" in kwargs:
            legado = kwargs.pop("candidato")
            kwargs.setdefault("cliente", "" if legado == "Todos" else legado)
        return func(*args, **kwargs)
    return call


def resolver_cliente(conn, cliente):
    cliente = " ".join((cliente or "").split())
    if not cliente:
        conn.close()
        raise ValueError("Preencha o nome do cliente.")
    row = conn.execute(
        "SELECT cliente FROM pautas WHERE normalizar(cliente) = ? ORDER BY id LIMIT 1",
        (normalizar(cliente),)
    ).fetchone()
    return row[0] if row else cliente


def listar_clientes():
    """Nomes disponíveis para busca, sem duplicatas de caixa/espaços/acentos."""
    with closing(get_connection()) as conn:
        rows = conn.execute("""
            SELECT cliente FROM pautas
            WHERE IFNULL(excluida, 0) = 0
              AND TRIM(IFNULL(cliente, '')) != ''
            ORDER BY id
        """)
        nomes = {}
        for (nome,) in rows:
            nome = " ".join(nome.split())
            nomes.setdefault(normalizar(nome), nome)
    return sorted(nomes.values(), key=normalizar)


# ==========================================================
# CRIAÇÃO / ATUALIZAÇÃO DA ESTRUTURA DO BANCO
# ==========================================================

def init_database():
    """
    Cria as tabelas necessárias para o sistema funcionar.

    Também adiciona colunas novas caso o banco já exista
    em uma versão antiga.
    """

    conn = get_connection()
    cursor = conn.cursor()

    # Backup consistente antes de qualquer mudança no banco legado.
    colunas = {r[1] for r in cursor.execute("PRAGMA table_info(pautas)")}
    if "candidato" in colunas and "cliente" not in colunas:
        backup = DB_PATH.with_name(DB_PATH.name + ".antes-clientes-" +
                                   datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".bak")
        with closing(sqlite3.connect(backup)) as destino:
            conn.backup(destino)
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor.execute("ALTER TABLE pautas RENAME COLUMN candidato TO cliente")
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            raise

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_buscas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            termo TEXT NOT NULL,
            data_busca TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pautas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_pauta TEXT NOT NULL,
            data_pauta TEXT,
            cliente TEXT NOT NULL,
            descricao_inicial TEXT,
            caminho_pasta TEXT NOT NULL,
            data_criacao TEXT NOT NULL,
            data_atualizacao TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS takes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pauta_id INTEGER NOT NULL,
            nome_arquivo TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            comentario TEXT,
            marcado_como_importante INTEGER DEFAULT 0,
            FOREIGN KEY (pauta_id) REFERENCES pautas(id)
        )
    """)

    cursor.execute("PRAGMA table_info(pautas)")
    colunas_pautas = [coluna[1] for coluna in cursor.fetchall()]

    if "excluida" not in colunas_pautas:
        cursor.execute("""
            ALTER TABLE pautas ADD COLUMN excluida INTEGER DEFAULT 0
        """)

    if "favorita" not in colunas_pautas:
        cursor.execute("""
            ALTER TABLE pautas ADD COLUMN favorita INTEGER DEFAULT 0
        """)

    if "status_pauta" not in colunas_pautas:
        cursor.execute("ALTER TABLE pautas ADD COLUMN status_pauta TEXT DEFAULT 'a_editar'")

    if "filtros" not in {r[1] for r in cursor.execute("PRAGMA table_info(historico_buscas)")}:
        cursor.execute("ALTER TABLE historico_buscas ADD COLUMN filtros TEXT NOT NULL DEFAULT '{}'")

    cursor.execute("PRAGMA table_info(takes)")
    colunas_takes = [coluna[1] for coluna in cursor.fetchall()]

    if "favorito" not in colunas_takes:
        cursor.execute("""
            ALTER TABLE takes ADD COLUMN favorito INTEGER DEFAULT 0
        """)

    if "tags" not in colunas_takes:
        cursor.execute("""
            ALTER TABLE takes ADD COLUMN tags TEXT
        """)

    if "status_take" not in colunas_takes:
        cursor.execute("""
            ALTER TABLE takes ADD COLUMN status_take TEXT DEFAULT 'talvez'
        """)

    conn.commit()
    conn.close()

    from smart_locate import init_storage
    init_storage()


# ==========================================================
# SALVAR NOVA PAUTA
# ==========================================================

@compat_cliente
def salvar_pauta(nome_pauta, data_pauta, cliente="", descricao="", caminho_pasta="", takes=()):
    """
    Salva uma nova pauta no banco.

    Depois de salvar a pauta, salva também todos os takes
    relacionados a ela.
    """

    conn = get_connection()
    cliente = resolver_cliente(conn, cliente)
    cursor = conn.cursor()

    agora = datetime.now().isoformat(timespec="seconds")

    # Salva os dados principais da pauta
    cursor.execute("""
        INSERT INTO pautas (
            nome_pauta,
            data_pauta,
            cliente,
            descricao_inicial,
            caminho_pasta,
            data_criacao,
            data_atualizacao
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        nome_pauta,
        data_pauta,
        cliente,
        descricao,
        caminho_pasta,
        agora,
        agora
    ))

    # Pega o ID da pauta recém-criada
    pauta_id = cursor.lastrowid

    # Salva cada take vinculado à pauta
    for take in takes:
        cursor.execute("""
            INSERT INTO takes (
                pauta_id,
                nome_arquivo,
                caminho_arquivo,
                comentario,
                tags,
                marcado_como_importante
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            pauta_id,
            take["nome_arquivo"],
            take["caminho_arquivo"],
            take.get("comentario", ""),
            take.get("tags", ""),
            1 if take.get("importante") else 0
        ))

    conn.commit()
    conn.close()


@compat_cliente
def listar_pautas_acervo(cliente="", periodo="Todos", status="Todos"):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(pautas)")
    colunas = [coluna[1] for coluna in cursor.fetchall()]

    if "status_pauta" not in colunas:
        cursor.execute("""
            ALTER TABLE pautas
            ADD COLUMN status_pauta TEXT DEFAULT 'a_editar'
        """)
        conn.commit()

    data_sql = """
        CASE
            WHEN data_pauta LIKE '__/__/____'
            THEN date(substr(data_pauta, 7, 4) || '-' || substr(data_pauta, 4, 2) || '-' || substr(data_pauta, 1, 2))
            ELSE date(data_pauta)
        END
    """

    query = """
        SELECT *
        FROM pautas
        WHERE IFNULL(excluida, 0) = 0
    """

    params = []

    if normalizar(cliente):
        query += " AND instr(normalizar(cliente), ?) > 0"
        params.append(normalizar(cliente))

    if status != "Todos":
        query += " AND IFNULL(status_pauta, 'a_editar') = ?"
        params.append(status)

    if periodo == "Hoje":
        query += f" AND {data_sql} = date('now')"

    elif periodo == "7 dias":
        query += f" AND {data_sql} >= date('now', '-7 days')"

    elif periodo == "30 dias":
        query += f" AND {data_sql} >= date('now', '-30 days')"

    query += f"""
        ORDER BY {data_sql} DESC, id DESC
    """

    cursor.execute(query, params)
    pautas = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return pautas
# ==========================================================
# BUSCAR PAUTAS
# ==========================================================

@compat_cliente
def buscar_pautas(
    palavra_chave="",
    data_inicial="",
    data_final="",
    cliente="",
    somente_pautas_favoritas=False
):
    """
    Busca pautas no banco.

    Permite filtrar por:
    - palavra-chave
    - data inicial
    - data final
    - cliente
    - somente pautas favoritas
    """

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT DISTINCT
            p.*
        FROM pautas p
        LEFT JOIN takes t ON t.pauta_id = p.id
        WHERE 1 = 1
        AND IFNULL(p.excluida, 0) = 0
    """

    params = []

    if somente_pautas_favoritas:
        query += " AND IFNULL(p.favorita, 0) = 1"

    if palavra_chave:
        query += """
            AND (
                p.nome_pauta LIKE ?
                OR p.descricao_inicial LIKE ?
                OR p.data_pauta LIKE ?
                OR instr(normalizar(p.cliente), normalizar(?)) > 0
                OR t.nome_arquivo LIKE ?
                OR t.comentario LIKE ?
                OR t.tags LIKE ?
            )
        """
        termo = f"%{palavra_chave}%"
        params.extend([termo, termo, termo, palavra_chave, termo, termo, termo])

    data_sql = "CASE WHEN p.data_pauta LIKE '__/__/____' THEN substr(p.data_pauta,7,4)||'-'||substr(p.data_pauta,4,2)||'-'||substr(p.data_pauta,1,2) ELSE p.data_pauta END"
    if data_inicial:
        query += f" AND {data_sql} >= ?"
        params.append(data_inicial[6:10] + '-' + data_inicial[3:5] + '-' + data_inicial[:2] if re.fullmatch(r'\d{2}/\d{2}/\d{4}', data_inicial) else data_inicial)

    if data_final:
        query += f" AND {data_sql} <= ?"
        params.append(data_final[6:10] + '-' + data_final[3:5] + '-' + data_final[:2] if re.fullmatch(r'\d{2}/\d{2}/\d{4}', data_final) else data_final)

    if normalizar(cliente):
        query += " AND instr(normalizar(p.cliente), ?) > 0"
        params.append(normalizar(cliente))

    query += " ORDER BY p.data_pauta DESC, p.id DESC"

    cursor.execute(query, params)
    pautas = cursor.fetchall()

    pautas_por_id = {pauta["id"]: [] for pauta in pautas}

    pauta_ids = tuple(pautas_por_id)
    for inicio in range(0, len(pauta_ids), 900):
        lote_ids = pauta_ids[inicio:inicio + 900]
        placeholders = ",".join("?" for _ in lote_ids)
        cursor.execute("""
            SELECT *
            FROM takes
            WHERE pauta_id IN ({})
            ORDER BY
                pauta_id,
                CASE
                    WHEN comentario IS NOT NULL AND comentario != '' THEN 0
                    ELSE 1
                END,
                marcado_como_importante DESC,
                nome_arquivo ASC
        """.format(placeholders), lote_ids)

        for take in cursor.fetchall():
            pautas_por_id[take["pauta_id"]].append(dict(take))

    resultado = [
        {
            "pauta": dict(pauta),
            "takes": pautas_por_id[pauta["id"]]
        }
        for pauta in pautas
    ]

    conn.close()
    return resultado

def atualizar_status_pauta(pauta_id, status_pauta):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pautas
        SET status_pauta = ?
        WHERE id = ?
    """, (status_pauta, pauta_id))

    conn.commit()
    conn.close()
# ==========================================================
# EXCLUIR PAUTA — SOFT DELETE
# ==========================================================

def excluir_pauta(pauta_id):
    """
    Marca uma pauta como excluída.

    A pauta não é apagada de verdade.
    Apenas recebe excluida = 1.
    """

    conn = get_connection()
    cursor = conn.cursor()

    agora = datetime.now().isoformat(timespec="seconds")

    cursor.execute("""
        UPDATE pautas
        SET excluida = 1,
            data_atualizacao = ?
        WHERE id = ?
    """, (agora, pauta_id))

    conn.commit()
    conn.close()


# ==========================================================
# OBTER UMA PAUTA ESPECÍFICA COM SEUS TAKES
# ==========================================================

def obter_pauta_com_takes(pauta_id):
    """
    Busca uma única pauta pelo ID.

    Retorna a pauta e todos os takes vinculados a ela.
    Usado principalmente na tela de edição.
    """

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Busca os dados principais da pauta
    cursor.execute("""
        SELECT *
        FROM pautas
        WHERE id = ?
    """, (pauta_id,))

    pauta = cursor.fetchone()

    # Busca os takes da pauta
    cursor.execute("""
        SELECT *
        FROM takes
        WHERE pauta_id = ?
        ORDER BY nome_arquivo ASC
    """, (pauta_id,))

    takes = cursor.fetchall()

    conn.close()

    if not pauta:
        return None

    return {
        "pauta": dict(pauta),
        "takes": [dict(take) for take in takes]
    }


# ==========================================================
# ATUALIZAR PAUTA EXISTENTE
# ==========================================================

@compat_cliente
def atualizar_pauta(pauta_id, nome_pauta, data_pauta, cliente="", descricao="", takes=()):
    conn = get_connection()
    cliente = resolver_cliente(conn, cliente)
    cursor = conn.cursor()

    agora = datetime.now().isoformat(timespec="seconds")

    # Atualiza os dados principais da pauta
    cursor.execute("""
        UPDATE pautas
        SET nome_pauta = ?,
            data_pauta = ?,
            cliente = ?,
            descricao_inicial = ?,
            data_atualizacao = ?
        WHERE id = ?
    """, (
        nome_pauta,
        data_pauta,
        cliente,
        descricao,
        agora,
        pauta_id
    ))

    # Atualiza os takes vinculados
    for take in takes:
        cursor.execute("""
            UPDATE takes
            SET comentario = ?,
                tags = ?,
                marcado_como_importante = ?,
                status_take = ?
            WHERE id = ? AND pauta_id = ?
        """, (
            take["comentario"],
            take.get("tags", ""),
            1 if take["importante"] else 0,
            take.get("status_take", "talvez"),
            take["id"], pauta_id
        ))

    conn.commit()
    conn.close()


# ==========================================================
# ESTATÍSTICAS DO SISTEMA
# ==========================================================

@compat_cliente
def obter_estatisticas(cliente=""):
    conn = get_connection()
    cursor = conn.cursor()

    filtro = "WHERE IFNULL(p.excluida, 0) = 0"
    params = []

    if normalizar(cliente):
        filtro += " AND instr(normalizar(p.cliente), ?) > 0"
        params.append(normalizar(cliente))

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM pautas p
        {filtro}
    """, params)
    total_pautas = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM takes t
        JOIN pautas p ON p.id = t.pauta_id
        {filtro}
    """, params)
    total_takes = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM takes t
        JOIN pautas p ON p.id = t.pauta_id
        {filtro}
        AND TRIM(IFNULL(t.comentario, '')) != ''
    """, params)
    takes_comentados = cursor.fetchone()[0]

    cursor.execute("""
        SELECT cliente, COUNT(*)
        FROM pautas
        WHERE IFNULL(excluida, 0) = 0
        GROUP BY cliente
    """)
    pautas_por_cliente = dict(cursor.fetchall())

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM pautas p
        {filtro}
        AND date(p.data_criacao) >= date('now', '-7 days')
    """, params)
    pautas_ultimos_7_dias = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT p.nome_pauta, p.data_pauta
        FROM pautas p
        {filtro}
        ORDER BY p.id DESC
        LIMIT 1
    """, params)
    ultima = cursor.fetchone()

    conn.close()

    return {
        "total_pautas": total_pautas,
        "total_takes": total_takes,
        "takes_comentados": takes_comentados,
        "pautas_por_cliente": pautas_por_cliente,
        "pautas_ultimos_7_dias": pautas_ultimos_7_dias,
        "ultima_pauta": ultima[0] if ultima else "Nenhuma pauta cadastrada",
        "ultima_data": ultima[1] if ultima else ""
    }


# ==========================================================
# FAVORITAR / DESFAVORITAR TAKE
# ==========================================================

def alternar_favorito_take(take_id, favorito):
    """
    Marca ou desmarca um take como favorito.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE takes
        SET favorito = ?
        WHERE id = ?
    """, (
        1 if favorito else 0,
        take_id
    ))

    conn.commit()
    conn.close()


# ==========================================================
# SALVAR HISTÓRICO DE BUSCA
# ==========================================================

def salvar_busca(termo, **filtros):
    """
    Salva um termo pesquisado no histórico.

    Buscas sem termo também são registradas quando possuem filtros.
    """

    termo = termo.strip()

    if not termo and not any(filtros.values()):
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO historico_buscas (
            termo,
            data_busca, filtros
        )
        VALUES (?, ?, ?)
    """, (
        termo,
        datetime.now().isoformat(),
        json.dumps(filtros, ensure_ascii=False, sort_keys=True)
    ))

    conn.commit()
    conn.close()


# ==========================================================
# OBTER HISTÓRICO DE BUSCAS
# ==========================================================

def obter_historico_buscas(limite=10, detalhado=False):
    """
    Retorna os últimos termos pesquisados.

    Não repete termos iguais.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT termo, filtros
        FROM historico_buscas
        GROUP BY termo, filtros
        ORDER BY MAX(id) DESC
        LIMIT ?
    """, (limite,))

    rows = cursor.fetchall()
    resultado = [{"termo": row[0], **json.loads(row[1] or '{}')} for row in rows] if detalhado else [row[0] for row in rows]

    conn.close()

    return resultado


# ==========================================================
# OBTER PALAVRAS MAIS FREQUENTES
# ==========================================================

@compat_cliente
def obter_top_palavras(limite=10, cliente=""):
    conn = get_connection()
    cursor = conn.cursor()

    filtro = "WHERE IFNULL(p.excluida, 0) = 0"
    params = []

    if normalizar(cliente):
        filtro += " AND instr(normalizar(p.cliente), ?) > 0"
        params.append(normalizar(cliente))

    cursor.execute(f"""
        SELECT 
            p.nome_pauta,
            p.descricao_inicial,
            t.nome_arquivo,
            t.comentario
        FROM pautas p
        LEFT JOIN takes t ON t.pauta_id = p.id
        {filtro}
    """, params)

    textos = []

    for nome_pauta, descricao, nome_arquivo, comentario in cursor.fetchall():
        textos.extend([
            nome_pauta or "",
            descricao or "",
            nome_arquivo or "",
            comentario or ""
        ])

    conn.close()

    texto_total = " ".join(textos).lower()
    palavras = re.findall(r"[a-záàâãéèêíïóôõöúçñ]{3,}", texto_total)

    ignorar = {
        "com", "para", "por", "dos", "das", "uma", "uns", "nas", "nos",
        "que", "não", "sim", "sobre", "take", "cena", "fala", "falas",
        "arquivo", "video", "vídeo", "audio", "áudio", "mp4", "mov",
        "mxf", "avi", "wav", "mp3", "cliente", "candidato", "candidata",
        "importante", "pauta", "pautas", "bruto", "brutos"
    }

    contador = Counter(
        palavra for palavra in palavras
        if palavra not in ignorar
    )

    return contador.most_common(limite)


def alternar_favorito_pauta(pauta_id, favorita):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pautas
        SET favorita = ?
        WHERE id = ?
    """, (
        1 if favorita else 0,
        pauta_id
    ))

    conn.commit()
    conn.close()
































