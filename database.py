import sqlite3
from datetime import datetime
from config import DB_PATH
import re
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
    return sqlite3.connect(DB_PATH)


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
            candidato TEXT NOT NULL,
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


# ==========================================================
# SALVAR NOVA PAUTA
# ==========================================================

def salvar_pauta(nome_pauta, data_pauta, candidato, descricao, caminho_pasta, takes):
    """
    Salva uma nova pauta no banco.

    Depois de salvar a pauta, salva também todos os takes
    relacionados a ela.
    """

    conn = get_connection()
    cursor = conn.cursor()

    agora = datetime.now().isoformat(timespec="seconds")

    # Salva os dados principais da pauta
    cursor.execute("""
        INSERT INTO pautas (
            nome_pauta,
            data_pauta,
            candidato,
            descricao_inicial,
            caminho_pasta,
            data_criacao,
            data_atualizacao
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        nome_pauta,
        data_pauta,
        candidato,
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


def listar_pautas_acervo(candidato="Todos", periodo="Todos", status="Todos"):
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

    if candidato != "Todos":
        query += " AND candidato = ?"
        params.append(candidato)

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

def buscar_pautas(
    palavra_chave="",
    data_inicial="",
    data_final="",
    candidato="Todos",
    somente_pautas_favoritas=False
):
    """
    Busca pautas no banco.

    Permite filtrar por:
    - palavra-chave
    - data inicial
    - data final
    - candidato
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
                OR p.candidato LIKE ?
                OR t.nome_arquivo LIKE ?
                OR t.comentario LIKE ?
                OR t.tags LIKE ?
            )
        """
        termo = f"%{palavra_chave}%"
        params.extend([termo, termo, termo, termo, termo, termo, termo])

    if data_inicial:
        query += " AND p.data_pauta >= ?"
        params.append(data_inicial)

    if data_final:
        query += " AND p.data_pauta <= ?"
        params.append(data_final)

    if candidato and candidato != "Todos":
        query += " AND p.candidato = ?"
        params.append(candidato)

    query += " ORDER BY p.data_pauta DESC, p.id DESC"

    cursor.execute(query, params)
    pautas = cursor.fetchall()

    resultado = []

    for pauta in pautas:
        cursor.execute("""
            SELECT *
            FROM takes
            WHERE pauta_id = ?
            ORDER BY
                CASE
                    WHEN comentario IS NOT NULL AND comentario != '' THEN 0
                    ELSE 1
                END,
                marcado_como_importante DESC,
                nome_arquivo ASC
        """, (pauta["id"],))

        takes = cursor.fetchall()

        resultado.append({
            "pauta": dict(pauta),
            "takes": [dict(take) for take in takes]
        })

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

def atualizar_pauta(pauta_id, nome_pauta, data_pauta, candidato, descricao, takes):
    conn = get_connection()
    cursor = conn.cursor()

    agora = datetime.now().isoformat(timespec="seconds")

    # Atualiza os dados principais da pauta
    cursor.execute("""
        UPDATE pautas
        SET nome_pauta = ?,
            data_pauta = ?,
            candidato = ?,
            descricao_inicial = ?,
            data_atualizacao = ?
        WHERE id = ?
    """, (
        nome_pauta,
        data_pauta,
        candidato,
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
            WHERE id = ?
        """, (
            take["comentario"],
            take.get("tags", ""),
            1 if take["importante"] else 0,
            take.get("status_take", "talvez"),
            take["id"]
        ))

    conn.commit()
    conn.close()


# ==========================================================
# ESTATÍSTICAS DO SISTEMA
# ==========================================================

def obter_estatisticas(candidato="Todos"):
    conn = get_connection()
    cursor = conn.cursor()

    filtro = "WHERE IFNULL(p.excluida, 0) = 0"
    params = []

    if candidato != "Todos":
        filtro += " AND p.candidato = ?"
        params.append(candidato)

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
        SELECT candidato, COUNT(*)
        FROM pautas
        WHERE IFNULL(excluida, 0) = 0
        GROUP BY candidato
    """)
    pautas_por_candidato = dict(cursor.fetchall())

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
        "pautas_por_candidato": pautas_por_candidato,
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

def salvar_busca(termo):
    """
    Salva um termo pesquisado no histórico.

    Termos vazios são ignorados.
    """

    termo = termo.strip()

    if not termo:
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO historico_buscas (
            termo,
            data_busca
        )
        VALUES (?, ?)
    """, (
        termo,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# ==========================================================
# OBTER HISTÓRICO DE BUSCAS
# ==========================================================

def obter_historico_buscas(limite=10):
    """
    Retorna os últimos termos pesquisados.

    Não repete termos iguais.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT termo
        FROM historico_buscas
        GROUP BY termo
        ORDER BY MAX(id) DESC
        LIMIT ?
    """, (limite,))

    resultado = [row[0] for row in cursor.fetchall()]

    conn.close()

    return resultado


# ==========================================================
# OBTER PALAVRAS MAIS FREQUENTES
# ==========================================================

def obter_top_palavras(limite=10, candidato="Todos"):
    conn = get_connection()
    cursor = conn.cursor()

    filtro = "WHERE IFNULL(p.excluida, 0) = 0"
    params = []

    if candidato != "Todos":
        filtro += " AND p.candidato = ?"
        params.append(candidato)

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
        "mxf", "avi", "wav", "mp3", "candidato", "candidata",
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
































    