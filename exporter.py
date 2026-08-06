import csv
import json
from pathlib import Path
from database import get_connection


def exportar_json(caminho_saida):
    conn = get_connection()
    try:
        conn.row_factory = None
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM pautas
            WHERE IFNULL(excluida, 0) = 0
            ORDER BY data_pauta DESC, id DESC
        """)
        colunas_pautas = [desc[0] for desc in cursor.description]
        dados = [dict(zip(colunas_pautas, row)) for row in cursor.fetchall()]

        takes_por_pauta = {pauta["id"]: [] for pauta in dados}
        if takes_por_pauta:
            cursor.execute("""
                SELECT t.*
                FROM takes t
                JOIN pautas p ON p.id = t.pauta_id
                WHERE IFNULL(p.excluida, 0) = 0
                ORDER BY t.pauta_id, t.nome_arquivo ASC
            """)
            colunas_takes = [desc[0] for desc in cursor.description]
            for row in cursor.fetchall():
                take = dict(zip(colunas_takes, row))
                takes_por_pauta[take["pauta_id"]].append(take)

        for pauta in dados:
            pauta["takes"] = takes_por_pauta[pauta["id"]]
    finally:
        conn.close()

    caminho_saida = Path(caminho_saida)

    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)


def exportar_csv(caminho_saida):
    conn = get_connection()
    try:
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
    finally:
        conn.close()

    caminho_saida = Path(caminho_saida)

    with open(caminho_saida, "w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.writer(arquivo, delimiter=";")
        writer.writerow(colunas)
        writer.writerows(linhas)




def exportar_resultados_json(caminho_saida, resultados):
    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultados, arquivo, ensure_ascii=False, indent=4)


def exportar_resultados_csv(caminho_saida, resultados):
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
