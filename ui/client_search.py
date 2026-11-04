"""Campo livre de busca com sugestões obtidas do acervo atual."""
from PySide6.QtCore import QStringListModel
from PySide6.QtWidgets import QCompleter, QLineEdit, QStyle

from database import listar_clientes, normalizar


class ClientSearchInput(QLineEdit):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setPlaceholderText("Digite o nome do cliente")
        self.setAccessibleName("Cliente")
        self.setToolTip("Digite parte do nome ou clique na seta para ver os clientes cadastrados.")
        self._model = QStringListModel(self)
        self._suggestions = QCompleter(self._model, self)
        self._suggestions.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._suggestions.setMaxVisibleItems(12)
        self.setCompleter(self._suggestions)
        self._suggestions.activated[str].connect(self.setText)
        self.clients_action = self.addAction(
            self.style().standardIcon(QStyle.SP_ArrowDown), QLineEdit.TrailingPosition
        )
        self.clients_action.setText("Ver clientes cadastrados")
        self.clients_action.setToolTip("Ver todos os clientes cadastrados")
        self.clients_action.triggered.connect(self.show_clients)
        self.textEdited.connect(self.filter_clients)

    def refresh_clients(self, term=""):
        term = normalizar(term)
        names = [name for name in listar_clientes() if term in normalizar(name)]
        self._model.setStringList(names)
        self._suggestions.setCompletionPrefix("")
        return names

    def filter_clients(self, text):
        if self.refresh_clients(text):
            self._suggestions.complete()
        else:
            self._suggestions.popup().hide()

    def show_clients(self):
        self.setFocus()
        if self.refresh_clients():
            self._suggestions.complete()
