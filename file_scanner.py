from pathlib import Path
from config import EXTENSOES_VALIDAS


def listar_arquivos_midia(caminho_pasta):
    pasta = Path(caminho_pasta)

    if not pasta.exists() or not pasta.is_dir():
        return []

    arquivos = []

    # Apenas arquivos da pasta selecionada.
    # Não entra em subpastas.
    for arquivo in pasta.iterdir():
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_VALIDAS:
            arquivos.append({
                "nome_arquivo": arquivo.name,
                "caminho_arquivo": str(arquivo)
            })

    return sorted(arquivos, key=lambda item: item["nome_arquivo"].lower())