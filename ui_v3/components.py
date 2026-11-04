from PySide6.QtCore import Qt,QTimer,QPropertyAnimation,QEasingCurve,Signal,Slot
from PySide6.QtGui import QColor,QPainter,QKeySequence,QShortcut
from PySide6.QtWidgets import QWidget,QFrame,QLabel,QPushButton,QHBoxLayout,QVBoxLayout,QLineEdit,QDialog,QGraphicsOpacityEffect

def txt(value,role=None,wrap=False):
    w=QLabel(value); w.setWordWrap(wrap)
    if role:w.setObjectName(role)
    return w
def btn(value,kind=None,tip=None):
    w=QPushButton(value); w.setCursor(Qt.PointingHandCursor)
    if kind:w.setProperty("kind",kind)
    if tip:w.setToolTip(tip)
    return w
def rule():
    w=QFrame(); w.setFixedHeight(1); w.setStyleSheet("background:#173036"); return w
def panel(raised=False):
    w=QFrame(); w.setObjectName("Raised" if raised else "Panel"); return w

class Status(QLabel):
    def __init__(self,value):
        super().__init__(value); palette={"ENTRADA":("#234047","#8AAEB2"),"TRIAGEM":("#3B351B","#E8C866"),"CORTE":("#123B42","#43E4D7"),"PRONTO":("#173925","#72DA95"),"USAR":("#173925","#72DA95"),"TALVEZ":("#3B351B","#E8C866"),"IGNORAR":("#3B1C20","#F08D91")}; bg,fg=palette.get(value,("#17363B","#9AB6B8")); self.setStyleSheet(f"background:{bg};color:{fg};border-radius:3px;padding:2px 6px;font-size:9px;font-weight:800;letter-spacing:.5px"); self.setFixedHeight(18)

class Thumb(QWidget):
    def __init__(self,seed=0,large=False):
        super().__init__(); self.seed=seed; self.setFixedSize(176,99) if large else self.setFixedSize(72,41)
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); r=self.rect(); bases=[("#123238","#1D5960"),("#213136","#3F5559"),("#16352E","#27614F")]; a,b=bases[self.seed%3]; p.fillRect(r,QColor(a)); p.setPen(Qt.NoPen); p.setBrush(QColor(b)); p.drawEllipse(-r.width()//5,r.height()//3,r.width()*3//4,r.height()); p.setBrush(QColor("#102126")); p.drawRect(r.width()*2//3,0,r.width()//3,r.height()); p.setPen(QColor("#6E9B9E")); p.drawText(r,Qt.AlignCenter,"▶")

class MediaThumb(QLabel):
    def __init__(self,path,loader,generation,size=(72,41)):
        super().__init__("···"); self.path=path; self.loader=loader; self.generation=generation; self.setAlignment(Qt.AlignCenter); self.setFixedSize(*size); self.setStyleSheet("background:#102A2F;color:#587B80;border-radius:4px")
    def paintEvent(self,e):
        if self.loader and self.path and self.property("requested") is None:
            self.setProperty("requested",True); self.loader.solicitar(self.path,self,self.generation)
        super().paintEvent(e)
    @Slot(object,object)
    def aplicar_midia(self,pixmap,info):
        if pixmap and not pixmap.isNull(): self.setText(""); self.setPixmap(pixmap.scaled(self.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation))
        else: self.setText("SEM MÍDIA")
        self.setToolTip(" · ".join(str(info.get(k,"")) for k in ("duracao","fps","resolucao")) if info else "Mídia indisponível")
    @Slot(str)
    def aplicar_erro_midia(self,message): self.setText("ERRO"); self.setToolTip(message)

class SelectableRow(QFrame):
    clicked=Signal(object)
    def __init__(self,data,index=0,take_count=None,thumb=None):
        super().__init__(); self.setMinimumHeight(58); self.data=data; self.setObjectName("Row"); self.setProperty("selected",False); self.setCursor(Qt.PointingHandCursor); r=QHBoxLayout(self); r.setContentsMargins(10,8,8,8); r.setSpacing(10); r.addWidget(thumb or Thumb(index)); info=QVBoxLayout(); info.setSpacing(3); info.addWidget(txt(data["title"],"Item")); info.addWidget(txt(f'{data["owner"]}  ·  {data["date"]}',"Meta")); r.addLayout(info,1); side=QVBoxLayout(); side.setAlignment(Qt.AlignRight); side.addWidget(Status(data["status"]),alignment=Qt.AlignRight)
        self.setFixedHeight(58)
        if take_count is not None: side.addWidget(txt(f'{take_count} takes',"Meta"),alignment=Qt.AlignRight)
        r.addLayout(side)
    def mousePressEvent(self,e): self.clicked.emit(self.data)
    def select(self,on): self.setProperty("selected",on); self.style().unpolish(self); self.style().polish(self)

class Toast(QFrame):
    def __init__(self,parent,message):
        super().__init__(parent); self.setObjectName("Raised"); r=QHBoxLayout(self); r.setContentsMargins(12,9,12,9); r.addWidget(txt("●","Accent")); r.addWidget(txt(message,"Item")); self.adjustSize(); self.move(parent.width()-self.width()-18,parent.height()-self.height()-18); self.show(); self.raise_(); QTimer.singleShot(2400,self.deleteLater)

class Confirm(QDialog):
    def __init__(self,parent,title,body,danger=False):
        super().__init__(parent); self.setModal(True); self.setFixedWidth(400); self.setStyleSheet("QDialog{background:#102429;border:1px solid #2C555D}"); l=QVBoxLayout(self); l.setContentsMargins(20,18,20,16); l.setSpacing(12); l.addWidget(txt(title,"Title")); l.addWidget(txt(body,"Meta",True)); l.addWidget(rule()); r=QHBoxLayout(); r.addStretch(); c=btn("Cancelar","flat"); ok=btn("Excluir" if danger else "Confirmar","danger" if danger else "accent"); c.clicked.connect(self.reject); ok.clicked.connect(self.accept); r.addWidget(c); r.addWidget(ok); l.addLayout(r)

class CommandPalette(QDialog):
    navigate=Signal(int)
    def __init__(self,parent):
        super().__init__(parent,Qt.FramelessWindowHint|Qt.Dialog); self.setModal(True); self.setFixedSize(520,390); self.setStyleSheet("QDialog{background:#102429;border:1px solid #34717A;border-radius:9px}"); l=QVBoxLayout(self); l.setContentsMargins(10,10,10,10); l.setSpacing(5); self.search=QLineEdit(); self.search.setPlaceholderText("Digite um comando ou destino…"); self.search.setMinimumHeight(39); l.addWidget(self.search); l.addWidget(txt("AÇÕES RÁPIDAS","Micro")); self.actions=[]
        for name,key,idx in (("Ir para Central de trabalho","Ctrl 1",0),("Pesquisar no acervo","Ctrl F",1),("Criar nova pauta","Ctrl N",2),("Abrir Design Lab","Ctrl 4",3),("Alternar inspector","Ctrl I",-2)):
            b=btn(name,"flat"); b.setMinimumHeight(38); b.setText(name+"                                      "+key); b.clicked.connect(lambda _,x=idx:self.choose(x)); l.addWidget(b); self.actions.append((b,name))
        l.addStretch(); l.addWidget(txt("↑↓ navegar   Enter executar   Esc fechar","Meta")); self.search.textChanged.connect(self.filter)
    def showEvent(self,e): super().showEvent(e); self.search.clear(); self.search.setFocus()
    def filter(self,q):
        for b,n in self.actions:b.setVisible(q.lower() in n.lower())
    def choose(self,idx):
        self.navigate.emit(idx)
        self.accept()
