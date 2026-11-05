import logging,sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QKeySequence,QShortcut
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QLabel,QHBoxLayout,QVBoxLayout,QStackedWidget
from media_loader import MediaLoader
from ui.ui_locate import allow_close
from .theme import QSS
from .components import txt,btn,CommandPalette
from .screens import Inspector,WorkCenter,SearchWorkspace,EditorWorkspace,DesignLab,report_error
from . import backend

class Workstation(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Pautas V3 — Mesa de Corte"); self.resize(1366,768); self.setMinimumSize(1080,660); self.media_loader=MediaLoader(self); self.media_generation=self.media_loader.generation
        root=QWidget(); root.setObjectName("Root"); line=QHBoxLayout(root); line.setContentsMargins(0,0,0,0); line.setSpacing(0); self.setCentralWidget(root); rail=QWidget(); rail.setObjectName("Rail"); rail.setFixedWidth(58); rl=QVBoxLayout(rail); rl.setContentsMargins(7,9,7,9); rl.setSpacing(6); logo=QLabel("P"); logo.setObjectName("Logo"); logo.setAlignment(Qt.AlignCenter); logo.setFixedSize(36,36); rl.addWidget(logo,alignment=Qt.AlignCenter); rl.addSpacing(13); self.nav=[]
        for i,(glyph,name,key) in enumerate((("⌂","Central","Ctrl+1"),("⌕","Pesquisar","Ctrl+F"),("＋","Nova pauta","Ctrl+N"),("◇","Design Lab","Ctrl+4"))):
            b=btn(glyph,"rail",f"{name} · {key}"); b.setFixedSize(43,40); b.setCheckable(True); b.setAutoExclusive(True); b.clicked.connect(lambda _,x=i:self.go(x)); rl.addWidget(b); self.nav.append(b)
        rl.addStretch(); command=btn("⌘","rail","Command Palette · Ctrl+K"); command.setFixedSize(43,40); command.clicked.connect(self.open_palette); rl.addWidget(command); line.addWidget(rail)
        work=QWidget(); wl=QVBoxLayout(work); wl.setContentsMargins(0,0,0,0); wl.setSpacing(0); tabs=QWidget(); tabs.setObjectName("WorkspaceBar"); tr=QHBoxLayout(tabs); tr.setContentsMargins(10,0,8,0); tr.addWidget(txt("WORKSPACES","Micro")); self.tab_buttons=[]
        for i,name in enumerate(("Central","Acervo","Edição","Design Lab")):
            b=btn(name,"tab"); b.setFixedHeight(37); b.setCheckable(True); b.setAutoExclusive(True); b.clicked.connect(lambda _,x=i:self.go(x)); tr.addWidget(b); self.tab_buttons.append(b)
        tr.addStretch(); self.inspector_btn=btn("Inspector  Ctrl I","flat"); self.inspector_btn.clicked.connect(self.toggle_inspector); tr.addWidget(self.inspector_btn); tr.addWidget(btn("Ctrl K","flat","Abrir Command Palette")); wl.addWidget(tabs)
        stage=QWidget(); stage.setObjectName("Stage"); sr=QHBoxLayout(stage); sr.setContentsMargins(0,0,0,0); sr.setSpacing(0); self.inspector=Inspector(); self.pages=QStackedWidget(); self.home=WorkCenter(self.inspector); self.search=SearchWorkspace(self.inspector); self.editor=EditorWorkspace(); self.lab=DesignLab(); [self.pages.addWidget(x) for x in (self.home,self.search,self.editor,self.lab)]; sr.addWidget(self.pages,1); sr.addWidget(self.inspector); wl.addWidget(stage,1); line.addWidget(work,1)
        self.home.new.clicked.connect(self.new_pauta); self.inspector.edit_requested.connect(self.edit_pauta); self.inspector.deleted.connect(self.refresh_all); self.editor.saved.connect(self.refresh_all); self.palette=CommandPalette(self); self.palette.navigate.connect(self.command); QShortcut(QKeySequence("Ctrl+K"),self,self.open_palette); QShortcut(QKeySequence("Ctrl+F"),self,lambda:self.go(1)); QShortcut(QKeySequence("Ctrl+N"),self,self.new_pauta); QShortcut(QKeySequence("Ctrl+I"),self,self.toggle_inspector); QShortcut(QKeySequence("Ctrl+1"),self,lambda:self.go(0)); QShortcut(QKeySequence("Ctrl+4"),self,lambda:self.go(3)); QShortcut(QKeySequence("Ctrl+S"),self,self.save_current); self.go(0)
    def go(self,index):
        self.pages.setCurrentIndex(index)
        for i,b in enumerate(self.nav):b.setChecked(i==index)
        for i,b in enumerate(self.tab_buttons):b.setChecked(i==index)
        self.inspector.setVisible(index in (0,1))
        if index==0:self.home.refresh()
        elif index==1:self.search.refresh(False)
    def new_pauta(self): self.editor.new(); self.go(2)
    def edit_pauta(self,pauta_id): self.editor.load(pauta_id); self.go(2)
    def save_current(self):
        if self.pages.currentIndex()==2:self.editor.save()
    def refresh_all(self):
        self.inspector.empty(); self.home.refresh(); self.search.refresh(False)
    def toggle_inspector(self):
        if self.pages.currentIndex() in (0,1):self.inspector.setVisible(not self.inspector.isVisible())
    def command(self,index):
        if index==-2:self.toggle_inspector()
        else:self.go(index)
    def open_palette(self):
        center=self.geometry().center(); self.palette.move(center.x()-self.palette.width()//2,center.y()-self.palette.height()//2); self.palette.exec()
    def closeEvent(self,event):
        from network.desktop import allow_network_close
        if not allow_network_close(self,event):return
        if not allow_close(self,event):return
        self.media_loader.encerrar(); self.media_loader.pool.waitForDone(6500); super().closeEvent(event)

def main(network=False):
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app=QApplication.instance() or QApplication(sys.argv)
    from network.desktop import connect,load_settings,install_monitor
    if network or load_settings().get('network'):
        if not connect():return 1
    try: backend.initialize()
    except Exception: logging.exception("Falha ao inicializar banco"); raise
    app.setApplicationName("Pautas V3"); app.setStyle("Fusion"); app.setFont(QFont("Segoe UI",9)); app.setStyleSheet(QSS); window=Workstation(); install_monitor(window); window.show(); return app.exec()
if __name__=="__main__": raise SystemExit(main())
