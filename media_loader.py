import logging
import os
import weakref
from collections import OrderedDict, deque

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot, Qt
from PySide6.QtGui import QPixmap

from thumbnailer import carregar_midia


LOGGER = logging.getLogger(__name__)
METRICS_ENABLED = os.getenv("SISTEMA_PAUTAS_THUMB_METRICS") == "1"


class _WorkerSignals(QObject):
    concluido = Signal(str, str, object, object)
    falhou = Signal(str, str)


class _MediaWorker(QRunnable):
    def __init__(self, chave, caminho):
        super().__init__()
        self.chave = chave
        self.caminho = caminho
        self.signals = _WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            thumbnail, info, metricas = carregar_midia(self.caminho)
            self.signals.concluido.emit(
                self.chave, thumbnail or "", info, metricas
            )
        except Exception as erro:
            self.signals.falhou.emit(self.chave, str(erro))


class MediaLoader(QObject):
    """Fila limitada, deduplicada e cancelável para mídia visível."""

    def __init__(self, parent=None, max_workers=2, memory_limit=64):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(max_workers)
        self.memory_limit = memory_limit
        self.generation = 0
        self._queue = deque()
        self._requests = {}
        self._running = set()
        self._workers = {}
        self._pixmaps = OrderedDict()
        self.metrics = {
            "solicitadas": 0,
            "iniciadas": 0,
            "cache_disco": 0,
            "cache_memoria": 0,
            "duplicadas": 0,
            "canceladas": 0,
            "erros": 0,
        }

    def nova_geracao(self):
        self.generation += 1
        self.metrics["canceladas"] += len(self._queue)
        for chave, _ in self._queue:
            if chave not in self._running:
                self._requests.pop(chave, None)
        self._queue.clear()
        for chave, inscritos in list(self._requests.items()):
            self._requests[chave] = [
                item for item in inscritos if item[1] == self.generation
            ]
        return self.generation

    def solicitar(self, caminho, receptor, generation):
        if generation != self.generation:
            return

        chave = os.path.normcase(os.path.abspath(os.path.normpath(caminho)))
        self.metrics["solicitadas"] += 1
        inscrito = (weakref.ref(receptor), generation)

        if chave in self._requests:
            self._requests[chave].append(inscrito)
            self.metrics["duplicadas"] += 1
            return

        self._requests[chave] = [inscrito]
        self._queue.append((chave, caminho))
        self._iniciar_disponiveis()

    def _iniciar_disponiveis(self):
        while self._queue and len(self._running) < self.pool.maxThreadCount():
            chave, caminho = self._queue.popleft()
            worker = _MediaWorker(chave, caminho)
            worker.signals.concluido.connect(self._concluido)
            worker.signals.falhou.connect(self._falhou)
            self._workers[chave] = worker
            self._running.add(chave)
            self.metrics["iniciadas"] += 1
            self.pool.start(worker)

    @Slot(str, str, object, object)
    def _concluido(self, chave, thumb_path, info, metricas):
        pixmap = None
        if thumb_path:
            pixmap = self._pixmaps.pop(thumb_path, None)
            if pixmap is not None:
                self.metrics["cache_memoria"] += 1
            else:
                carregado = QPixmap(thumb_path)
                if not carregado.isNull():
                    pixmap = carregado.scaled(
                        190, 107, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self._pixmaps[thumb_path] = pixmap
                    while len(self._pixmaps) > self.memory_limit:
                        self._pixmaps.popitem(last=False)
            if pixmap is not None:
                self._pixmaps[thumb_path] = pixmap

        if metricas.get("cache_hit"):
            self.metrics["cache_disco"] += 1
        self._finalizar(chave, pixmap, info, None)

        if METRICS_ENABLED:
            LOGGER.info("thumbnail concluída: %s %s", chave, metricas)

    @Slot(str, str)
    def _falhou(self, chave, mensagem):
        self.metrics["erros"] += 1
        self._finalizar(chave, None, None, mensagem)
        if METRICS_ENABLED:
            LOGGER.warning("thumbnail falhou: %s: %s", chave, mensagem)

    def _finalizar(self, chave, pixmap, info, erro):
        inscritos = self._requests.pop(chave, [])
        self._running.discard(chave)
        self._workers.pop(chave, None)

        for referencia, generation in inscritos:
            receptor = referencia()
            if receptor is None or generation != self.generation:
                continue
            if erro:
                receptor.aplicar_erro_midia(erro)
            else:
                receptor.aplicar_midia(pixmap, info)

        self._iniciar_disponiveis()

    def encerrar(self):
        self.nova_geracao()
        self.pool.clear()
