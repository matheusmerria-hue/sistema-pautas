import csv
import json
from pathlib import Path
from database import get_connection


def exportar_json(caminho_saida):
    conn = get_connection()
    conn.row_factory = None
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM pautas
        WHERE IFNULL(excluida, 0) = 0
        ORDER BY data_pauta DESC, id DESC
    """)

    colunas_pautas = [desc[0] for desc in cursor.description]
    pautas_rows = cursor.fetchall()

    dados = []

    for pauta_row in pautas_rows:
        pauta = dict(zip(colunas_pautas, pauta_row))

        cursor.execute("""
            SELECT *
            FROM takes
            WHERE pauta_id = ?
            ORDER BY nome_arquivo ASC
        """, (pauta["id"],))

        colunas_takes = [desc[0] for desc in cursor.description]
        takes_rows = cursor.fetchall()

        pauta["takes"] = [
            dict(zip(colunas_takes, take_row))
            for take_row in takes_rows
        ]

        dados.append(pauta)

    conn.close()

    caminho_saida = Path(caminho_saida)

    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def exportar_csv(caminho_saida):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.id AS pauta_id,
            p.nome_pauta,
            p.data_pauta,
            p.candidato,
            p.descricao_inicial,
            p.caminho_pasta,
            t.id AS take_id,
            t.nome_arquivo,
            t.caminho_arquivo,
            t.comentario,
            t.marcado_como_importante
        FROM pautas p
        LEFT JOIN takes t ON t.pauta_id = p.id
        WHERE IFNULL(p.excluida, 0) = 0
        ORDER BY p.data_pauta DESC, p.id DESC, t.nome_arquivo ASC
    """)

    colunas = [desc[0] for desc in cursor.description]
    linhas = cursor.fetchall()

    conn.close()

    caminho_saida = Path(caminho_saida)

    with open(caminho_saida, "w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.writer(arquivo, delimiter=";")
        writer.writerow(colunas)
        writer.writerows(linhas)




def exportar_resultados_json(caminho_saida, resultados):
    import json

    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultados, arquivo, ensure_ascii=False, indent=4)


def exportar_resultados_csv(caminho_saida, resultados):
    import csv

    with open(caminho_saida, "w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.writer(arquivo, delimiter=";")

        writer.writerow([
            "pauta_id",
            "nome_pauta",
            "data_pauta",
            "candidato",
            "descricao",
            "caminho_pasta",
            "take_id",
            "nome_arquivo",
            "comentario",
            "favorito",
            "caminho_arquivo"
        ])

        for item in resultados:
            pauta = item["pauta"]

            for take in item["takes"]:
                writer.writerow([
                    pauta.get("id"),
                    pauta.get("nome_pauta"),
                    pauta.get("data_pauta"),
                    pauta.get("candidato"),
                    pauta.get("descricao_inicial"),
                    pauta.get("caminho_pasta"),
                    take.get("id"),
                    take.get("nome_arquivo"),
                    take.get("comentario"),
                    take.get("favorito"),
                    take.get("caminho_arquivo")
                ])