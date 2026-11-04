from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QHBoxLayout,
    QVBoxLayout, QLineEdit, QDialog, QGraphicsOpacityEffect, QApplication)

from .theme import COLORS


def label(text, role=None, wrap=False):
    w = QLabel(text)
    if role: w.setObjectName(role)
    w.setWordWrap(wrap)
    return w


def button(text, variant="secondary", tooltip=None):
    w = QPushButton(text)
    w.setProperty("variant", variant)
    w.setCursor(Qt.PointingHandCursor)
    if tooltip: w.setToolTip(tooltip)
    return w


def surface(layout=None, raised=False):
    w = QFrame(); w.setObjectName("Raised" if raised else "Surface")
    if layout: w.setLayout(layout)
    return w


def divider():
    w = QFrame(); w.setFixedHeight(1); w.setStyleSheet("background:#242C38;border:0;")
    return w


class StatusBadge(QLabel):
    def __init__(self, text):
        super().__init__(text)
        colors = {"Finalizada":("#17362D","#6DDBAA"), "Em produção":("#1B3048","#82BCFF"),
                  "A editar":("#392E1C","#F1C978"), "Usar":("#17362D","#6DDBAA"),
                  "Talvez":("#392E1C","#F1C978"), "Ignorar":("#3B2028","#FF9DA7")}
        bg, fg = colors.get(text, ("#292548", "#A99FFF"))
        self.setStyleSheet(f"background:{bg};color:{fg};border-radius:5px;padding:3px 7px;font-size:11px;font-weight:600;")
        self.setSizePolicy(self.sizePolicy().Policy.Fixed, self.sizePolicy().Policy.Fixed)


class Toggle(QWidget):
    def __init__(self, checked=False):
        super().__init__(); self.checked = checked; self.setFixedSize(34, 19); self.setCursor(Qt.PointingHandCursor)
    def mousePressEvent(self, e):
        self.checked = not self.checked; self.update()
    def paintEvent(self, e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen); p.setBrush(QColor(COLORS["accent"] if self.checked else "#3A4351")); p.drawRoundedRect(self.rect(),9,9)
        p.setBrush(QColor("white")); x=18 if self.checked else 3; p.drawEllipse(x,3,13,13)


class SearchInput(QLineEdit):
    def __init__(self, placeholder="Buscar..."):
        super().__init__(); self.setPlaceholderText(placeholder); self.setClearButtonEnabled(True); self.setMinimumHeight(36)


class Modal(QDialog):
    def __init__(self, parent, title, body, destructive=False):
        super().__init__(parent); self.setModal(True); self.setWindowTitle(title); self.setFixedWidth(420)
        lay=QVBoxLayout(self); lay.setContentsMargins(22,20,22,18); lay.setSpacing(14)
        lay.addWidget(label(title,"PageTitle")); lay.addWidget(label(body,"Muted",True)); lay.addWidget(divider())
        row=QHBoxLayout(); row.addStretch(); cancel=button("Cancelar","ghost"); ok=button("Excluir" if destructive else "Confirmar", "danger" if destructive else "primary")
        cancel.clicked.connect(self.reject); ok.clicked.connect(self.accept); row.addWidget(cancel); row.addWidget(ok); lay.addLayout(row)
        self.setStyleSheet("QDialog{background:#1B212B;border:1px solid #354052;}")


class Toast(QFrame):
    def __init__(self, parent, text, kind="success"):
        super().__init__(parent); self.setObjectName("Raised")
        row=QHBoxLayout(self); row.setContentsMargins(13,10,13,10)
        dot=QLabel("●"); dot.setStyleSheet(f"color:{COLORS['green'] if kind=='success' else COLORS['red']};")
        row.addWidget(dot); row.addWidget(label(text,"ItemTitle")); self.adjustSize()
        self.move(max(16,parent.width()-self.width()-24), max(16,parent.height()-self.height()-24)); self.show(); self.raise_()
        effect=QGraphicsOpacityEffect(self); self.setGraphicsEffect(effect)
        anim=QPropertyAnimation(effect,b"opacity",self); anim.setDuration(180); anim.setStartValue(0); anim.setEndValue(1); anim.setEasingCurve(QEasingCurve.OutCubic); anim.start()
        self._anim=anim; QTimer.singleShot(2600,self.deleteLater)


class Skeleton(QFrame):
    def __init__(self, width=160):
        super().__init__(); self.setFixedSize(width,12); self.setStyleSheet("background:#28303C;border-radius:5px;")


class EmptyState(QWidget):
    def __init__(self, action):
        super().__init__(); lay=QVBoxLayout(self); lay.setAlignment(Qt.AlignCenter); lay.setSpacing(8)
        icon=QLabel("○"); icon.setAlignment(Qt.AlignCenter); icon.setStyleSheet("font-size:32px;color:#667181;")
        lay.addWidget(icon); lay.addWidget(label("Nenhuma pauta encontrada","SectionTitle"),alignment=Qt.AlignCenter)
        lay.addWidget(label("Ajuste os filtros ou crie uma nova pauta.","Muted"),alignment=Qt.AlignCenter); lay.addWidget(button(action,"primary"),alignment=Qt.AlignCenter)
