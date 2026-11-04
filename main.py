import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QFont

from database import init_database
from ui.ui_home import HomeWindow
from ui.ui_search import SearchPautaWindow
from user_config import MODO
from theme import FONT_FAMILY


def main():
    init_database()

    app = QApplication(sys.argv)
    app.setApplicationName("Sistema de Pautas")
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setWindowIcon(QIcon("assets/icons/logo.ico"))

    if MODO == "LEITURA":
        window = SearchPautaWindow()
    else:
        window = HomeWindow()

    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
