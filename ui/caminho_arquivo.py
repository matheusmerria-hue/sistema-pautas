import os
import json
import shutil

# Arquivo JSON com os resultados
ARQUIVO_JSON = "resultado_busca.json"

# Pasta onde todos os vídeos serão copiados
PASTA_DESTINO = r"D:\VANDER\AGENDA VANDER\2026-07-16 - ABRAÇOS_CUMPRIMENTOS_CONVERSAS"

os.makedirs(PASTA_DESTINO, exist_ok=True)

with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
    dados = json.load(f)

copiados = 0
erros = 0

for pauta in dados:
    for take in pauta["takes"]:
        origem = take["caminho_arquivo"]

        if os.path.exists(origem):
            destino = os.path.join(PASTA_DESTINO, os.path.basename(origem))
            shutil.copy2(origem, destino)
            print(f"✔ Copiado: {os.path.basename(origem)}")
            copiados += 1
        else:
            print(f"✖ Não encontrado: {origem}")
            erros += 1

print("\n========================")
print(f"Copiados: {copiados}")
print(f"Erros: {erros}")