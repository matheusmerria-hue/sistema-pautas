import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QFont

from database import init_database
from theme import FONT_FAMILY


def main(network=False):
    if getattr(sys,'frozen',False):
        import os
        os.chdir(sys._MEIPASS)
    app = QApplication(sys.argv)
    app.setApplicationName("Sistema de Pautas")
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setWindowIcon(QIcon("assets/icons/logo.ico"))

    from network.desktop import connect,load_settings,install_monitor
    if network or load_settings().get('network'):
        if not connect():return 1
    init_database()
    from user_config import MODO
    from ui.ui_home import HomeWindow
    from ui.ui_search import SearchPautaWindow

    if MODO == "LEITURA":
        window = SearchPautaWindow()
    else:
        window = HomeWindow()

    window.showMaximized()
    install_monitor(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
