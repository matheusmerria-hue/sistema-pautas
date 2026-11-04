import sys
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QStackedWidget,QStyle
from .theme import QSS
from .components import label, button, Modal
from .screens import HomePage, SearchPage, EditorPage, ShowcasePage


class AppShell(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Pautas — UI V2 · Protótipo visual"); self.resize(1366,768); self.setMinimumSize(1100,680)
        root=QWidget(); root.setObjectName("Canvas"); row=QHBoxLayout(root); row.setContentsMargins(0,0,0,0); row.setSpacing(0); self.setCentralWidget(root)
        self.sidebar=QWidget(); self.sidebar.setObjectName("Sidebar"); self.sidebar.setFixedWidth(218); side=QVBoxLayout(self.sidebar); side.setContentsMargins(12,14,12,14); side.setSpacing(5)
        brand=QHBoxLayout(); mark=QLabel("P"); mark.setAlignment(Qt.AlignCenter); mark.setFixedSize(30,30); mark.setStyleSheet("background:#7C6EF6;color:white;border-radius:7px;font-size:15px;font-weight:800;"); brand.addWidget(mark); names=QVBoxLayout(); names.setSpacing(0); names.addWidget(label("PAUTAS","Brand")); names.addWidget(label("ACERVO AUDIOVISUAL","Caption")); brand.addLayout(names); brand.addStretch(); side.addLayout(brand); side.addSpacing(18)
        side.addWidget(label("ESPAÇO DE TRABALHO","Eyebrow")); self.nav=[]
        style=self.style(); items=[("Visão geral",QStyle.SP_ComputerIcon),("Pesquisar",QStyle.SP_FileDialogContentsView),("Nova pauta",QStyle.SP_FileDialogNewFolder),("UI Showcase",QStyle.SP_DesktopIcon)]
        for i,(name,ico) in enumerate(items):
            b=QPushButton(name); b.setProperty("nav","true"); b.setCheckable(True); b.setAutoExclusive(True); b.setIcon(style.standardIcon(ico)); b.setIconSize(QSize(16,16)); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(lambda _,x=i:self.navigate(x)); b.setToolTip(name); side.addWidget(b); self.nav.append(b)
        side.addStretch(); side.addWidget(label("FERRAMENTAS","Eyebrow")); settings=QPushButton("Configurações"); settings.setProperty("nav","true"); settings.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView)); settings.clicked.connect(lambda:Modal(self,"Configurações","Painel demonstrativo. Nenhuma preferência será persistida.").exec()); side.addWidget(settings)
        user=QFrame(); user.setObjectName("Raised"); ur=QHBoxLayout(user); ur.setContentsMargins(9,8,9,8); avatar=QLabel("MS"); avatar.setAlignment(Qt.AlignCenter); avatar.setFixedSize(29,29); avatar.setStyleSheet("background:#293240;border-radius:14px;color:#C4BDFF;font-weight:700;"); ur.addWidget(avatar); uv=QVBoxLayout(); uv.setSpacing(0); uv.addWidget(label("Modo administrador","ItemTitle")); uv.addWidget(label("Protótipo local · MOCK","Caption")); ur.addLayout(uv,1); side.addWidget(user); row.addWidget(self.sidebar)
        workspace=QWidget(); work=QVBoxLayout(workspace); work.setContentsMargins(0,0,0,0); work.setSpacing(0)
        top=QWidget(); top.setObjectName("Topbar"); tr=QHBoxLayout(top); tr.setContentsMargins(18,7,16,7); crumb=label("Pautas  /  Visão geral","Muted"); self.crumb=crumb; tr.addWidget(crumb); tr.addStretch(); command=button("⌕  Buscar   Ctrl K","ghost","Busca rápida"); command.clicked.connect(lambda:self.navigate(1)); tr.addWidget(command); helpb=button("?","ghost","Ajuda"); helpb.setFixedWidth(32); tr.addWidget(helpb); work.addWidget(top)
        self.pages=QStackedWidget(); self.pages.addWidget(HomePage(self.navigate)); self.pages.addWidget(SearchPage(self.navigate)); self.pages.addWidget(EditorPage(self.navigate)); self.pages.addWidget(ShowcasePage(self.navigate)); work.addWidget(self.pages,1); row.addWidget(workspace,1); self.navigate(0)
    def navigate(self,index):
        self.pages.setCurrentIndex(index); [b.setChecked(i==index) for i,b in enumerate(self.nav)]; self.crumb.setText("Pautas  /  "+["Visão geral","Pesquisar acervo","Nova pauta","UI Showcase"][index])


def main():
    app=QApplication.instance() or QApplication(sys.argv); app.setApplicationName("Pautas UI V2"); app.setStyle("Fusion"); app.setFont(QFont("Segoe UI",9)); app.setStyleSheet(QSS)
    window=AppShell(); window.show(); return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
