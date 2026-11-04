import hashlib
import json
import os
import threading
import time
from pathlib import Path

import cv2


# Cache local de cada computador.
# Exemplo:
# C:\Users\USUARIO\AppData\Local\SistemaPautas\cache
LOCAL_APP_DATA = os.getenv("LOCALAPPDATA")

if LOCAL_APP_DATA:
    CACHE_DIR = Path(LOCAL_APP_DATA) / "SistemaPautas" / "cache"
else:
    CACHE_DIR = Path.home() / ".sistemapautas" / "cache"

THUMB_DIR = CACHE_DIR / "thumbnails"
INFO_DIR = CACHE_DIR / "video_info"

CACHE_VERSION = "2"
THUMB_SIZE = (320, 180)

THUMB_DIR.mkdir(parents=True, exist_ok=True)
INFO_DIR.mkdir(parents=True, exist_ok=True)


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mxf",
    ".avi",
    ".mkv",
    ".wmv",
    ".m4v"
}

VIDEO_TIMEOUT_MS = 5000


def _abrir_video(caminho: Path):
    parametros = []
    for propriedade in ("CAP_PROP_OPEN_TIMEOUT_MSEC", "CAP_PROP_READ_TIMEOUT_MSEC"):
        valor = getattr(cv2, propriedade, None)
        if valor is not None:
            parametros.extend([valor, VIDEO_TIMEOUT_MS])

    if parametros:
        cap = cv2.VideoCapture(str(caminho), cv2.CAP_ANY, parametros)
        if cap.isOpened():
            return cap
        cap.release()

    return cv2.VideoCapture(str(caminho))


def _gerar_identificador(caminho: Path):
    """
    Cria uma identificação baseada em:
    - caminho do arquivo;
    - tamanho;
    - data da última alteração.

    Se o vídeo for substituído ou alterado, uma nova thumbnail será criada.
    """
    try:
        stat = caminho.stat()

        caminho_normalizado = os.path.normcase(
            os.path.abspath(
                os.path.normpath(str(caminho))
            )
        )

        assinatura = (
            f"{CACHE_VERSION}|{THUMB_SIZE[0]}x{THUMB_SIZE[1]}|"
            f"{caminho_normalizado}|"
            f"{stat.st_size}|"
            f"{stat.st_mtime_ns}|{caminho.suffix.lower()}"
        )

        return hashlib.md5(
            assinatura.encode("utf-8", errors="ignore")
        ).hexdigest()

    except OSError:
        return None


def _formatar_duracao(duracao):
    duracao = max(0, int(duracao))

    horas = duracao // 3600
    minutos = (duracao % 3600) // 60
    segundos = duracao % 60

    return f"{horas:02}:{minutos:02}:{segundos:02}"


def _salvar_info(info_path: Path, info: dict):
    arquivo_temporario = info_path.with_name(
        f"{info_path.stem}.{os.getpid()}.{threading.get_ident()}.tmp"
    )

    try:
        arquivo_temporario.write_text(
            json.dumps(
                info,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        os.replace(
            arquivo_temporario,
            info_path
        )

    except OSError:
        try:
            arquivo_temporario.unlink(missing_ok=True)
        except OSError:
            pass


def _ler_info(info_path: Path):
    try:
        info = json.loads(
            info_path.read_text(encoding="utf-8")
        )

        campos_obrigatorios = {
            "duracao",
            "fps",
            "resolucao"
        }

        if campos_obrigatorios.issubset(info):
            return info

    except (
        OSError,
        json.JSONDecodeError,
        TypeError
    ):
        pass

    return None


def _obter_caminhos_cache(caminho: Path):
    identificador = _gerar_identificador(caminho)

    if not identificador:
        return None, None

    thumb_path = THUMB_DIR / f"{identificador}.jpg"
    info_path = INFO_DIR / f"{identificador}.json"

    return thumb_path, info_path


def _coletar_info(cap):
    fps = float(
        cap.get(cv2.CAP_PROP_FPS) or 0
    )

    frames = float(
        cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    )

    largura = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
    )

    altura = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
    )

    if fps <= 0:
        fps = 25.0

    duracao = (
        frames / fps
        if frames > 0
        else 0
    )

    return {
        "duracao": _formatar_duracao(duracao),
        "fps": round(fps, 2),
        "resolucao": (
            f"{largura}x{altura}"
            if largura > 0 and altura > 0
            else "Indisponível"
        )
    }


def gerar_thumbnail(caminho_arquivo, segundo=2):
    caminho = Path(caminho_arquivo)

    if not caminho.is_file():
        return None

    if caminho.suffix.lower() not in VIDEO_EXTENSIONS:
        return None

    thumb_path, info_path = _obter_caminhos_cache(
        caminho
    )

    if not thumb_path or not info_path:
        return None

    # A thumbnail já existe localmente:
    # não abre novamente o vídeo do servidor.
    if (
        thumb_path.is_file()
        and thumb_path.stat().st_size > 0
    ):
        return str(thumb_path)

    cap = _abrir_video(caminho)

    if not cap.isOpened():
        cap.release()
        return None

    try:
        info = _coletar_info(cap)

        fps = float(
            cap.get(cv2.CAP_PROP_FPS) or 0
        )

        if fps <= 0:
            fps = 25.0

        frame_number = max(
            0,
            int(fps * float(segundo))
        )

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            frame_number
        )

        sucesso, frame = cap.read()

        # Vídeos muito curtos ou codecs que não aceitam
        # bem o salto direto: tenta o primeiro frame.
        if not sucesso or frame is None:
            cap.set(
                cv2.CAP_PROP_POS_FRAMES,
                0
            )
            sucesso, frame = cap.read()

        if not sucesso or frame is None:
            return None

        frame = cv2.resize(
            frame,
            THUMB_SIZE,
            interpolation=cv2.INTER_AREA
        )

        thumb_temporaria = thumb_path.with_name(
            f"{thumb_path.stem}.{os.getpid()}."
            f"{threading.get_ident()}.tmp.jpg"
        )

        gravou = cv2.imwrite(
            str(thumb_temporaria),
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 85]
        )

        if not gravou:
            thumb_temporaria.unlink(
                missing_ok=True
            )
            return None

        os.replace(
            thumb_temporaria,
            thumb_path
        )

        # Aproveita a mesma abertura do vídeo para salvar
        # duração, FPS e resolução.
        _salvar_info(
            info_path,
            info
        )

        return str(thumb_path)

    finally:
        cap.release()


def obter_info_video(caminho_arquivo):
    caminho = Path(caminho_arquivo)

    if not caminho.is_file():
        return None

    if caminho.suffix.lower() not in VIDEO_EXTENSIONS:
        return None

    _, info_path = _obter_caminhos_cache(
        caminho
    )

    if not info_path:
        return None

    # Depois do primeiro acesso, lê somente o JSON local.
    if info_path.is_file():
        info_cache = _ler_info(info_path)

        if info_cache:
            return info_cache

    cap = _abrir_video(caminho)

    if not cap.isOpened():
        cap.release()
        return None

    try:
        info = _coletar_info(cap)

        _salvar_info(
            info_path,
            info
        )

        return info

    finally:
        cap.release()


def obter_pasta_cache():
    return str(CACHE_DIR)


def carregar_midia(caminho_arquivo):
    """Carrega thumbnail e metadados, retornando métricas observáveis."""
    inicio = time.perf_counter()
    caminho = Path(caminho_arquivo)
    thumb_path, info_path = _obter_caminhos_cache(caminho)

    cache_hit = bool(
        thumb_path
        and info_path
        and thumb_path.is_file()
        and thumb_path.stat().st_size > 0
        and info_path.is_file()
        and _ler_info(info_path)
    )

    inicio_thumbnail = time.perf_counter()
    thumbnail = gerar_thumbnail(caminho)
    tempo_thumbnail = time.perf_counter() - inicio_thumbnail

    inicio_info = time.perf_counter()
    info = obter_info_video(caminho)
    tempo_info = time.perf_counter() - inicio_info

    return thumbnail, info, {
        "cache_hit": cache_hit,
        "tempo_thumbnail_ms": round(tempo_thumbnail * 1000, 2),
        "tempo_info_ms": round(tempo_info * 1000, 2),
        "tempo_total_ms": round((time.perf_counter() - inicio) * 1000, 2),
    }
