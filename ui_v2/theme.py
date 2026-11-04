COLORS = {
    "canvas": "#0C0F14", "sidebar": "#10141B", "surface": "#151A22",
    "raised": "#1B212B", "hover": "#222A36", "border": "#293240",
    "text": "#F2F5F9", "muted": "#929EAE", "faint": "#667181",
    "accent": "#7C6EF6", "accent_hover": "#8D81FA", "accent_soft": "#292548",
    "green": "#48C78E", "green_soft": "#17362D", "amber": "#E7B75F",
    "amber_soft": "#392E1C", "red": "#EF6A78", "red_soft": "#3B2028",
    "blue": "#62A8F7", "blue_soft": "#1B3048",
}

QSS = r"""
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; color: #F2F5F9; }
QMainWindow, QWidget#Canvas { background: #0C0F14; }
QWidget#Sidebar { background: #10141B; border-right: 1px solid #202733; }
QWidget#Topbar { background: #0F1319; border-bottom: 1px solid #202733; }
QWidget#Surface, QFrame#Surface { background: #151A22; border: 1px solid #242C38; border-radius: 9px; }
QFrame#Raised { background: #1B212B; border: 1px solid #293240; border-radius: 9px; }
QFrame#ListRow { background: transparent; border-bottom: 1px solid #202733; }
QFrame#ListRow:hover { background: #191F28; }
QLabel#Brand { font-size: 15px; font-weight: 700; }
QLabel#Eyebrow { color: #7C6EF6; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QLabel#PageTitle { font-size: 21px; font-weight: 650; }
QLabel#SectionTitle { font-size: 14px; font-weight: 650; }
QLabel#ItemTitle { font-size: 13px; font-weight: 600; }
QLabel#Muted { color: #929EAE; }
QLabel#Caption { color: #667181; font-size: 11px; }
QLabel#Metric { font-size: 24px; font-weight: 650; }
QLabel#Required { color: #EF6A78; }
QPushButton { min-height: 32px; padding: 0 12px; background: #1B212B; border: 1px solid #303A49; border-radius: 6px; font-weight: 600; }
QPushButton:hover { background: #222A36; border-color: #3D4858; }
QPushButton:pressed { background: #171C24; padding-top: 1px; }
QPushButton:focus { border: 1px solid #7C6EF6; }
QPushButton:disabled { color: #596371; background: #151A22; border-color: #252C36; }
QPushButton[variant="primary"] { background: #7C6EF6; border-color: #7C6EF6; color: white; }
QPushButton[variant="primary"]:hover { background: #8D81FA; }
QPushButton[variant="ghost"] { background: transparent; border-color: transparent; color: #AAB4C2; }
QPushButton[variant="ghost"]:hover { background: #202630; color: #F2F5F9; }
QPushButton[variant="danger"] { background: #3B2028; border-color: #65303A; color: #FF9DA7; }
QPushButton[nav="true"] { background: transparent; border: 0; border-radius: 6px; text-align: left; color: #929EAE; padding-left: 14px; }
QPushButton[nav="true"]:hover { background: #191F28; color: #E5E9EF; }
QPushButton[nav="true"]:checked { background: #25233A; color: #FFFFFF; border-left: 3px solid #7C6EF6; padding-left: 11px; }
QLineEdit, QTextEdit, QComboBox { background: #11161D; border: 1px solid #303A49; border-radius: 6px; padding: 6px 9px; selection-background-color: #7C6EF6; }
QLineEdit { min-height: 22px; }
QLineEdit:hover, QTextEdit:hover, QComboBox:hover { border-color: #465266; }
QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1px solid #7C6EF6; }
QLineEdit[error="true"] { border-color: #EF6A78; }
QComboBox { min-height: 22px; padding-right: 24px; }
QComboBox::drop-down { width: 24px; border: 0; }
QComboBox QAbstractItemView { background: #1B212B; border: 1px solid #303A49; selection-background-color: #292548; padding: 4px; }
QCheckBox { spacing: 7px; color: #C6CED9; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #475466; background: #11161D; }
QCheckBox::indicator:checked { background: #7C6EF6; border-color: #7C6EF6; }
QScrollArea, QScrollArea > QWidget > QWidget { border: 0; background: transparent; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #384252; min-height: 28px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #505C6E; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 9px; }
QScrollBar::handle:horizontal { background: #384252; min-width: 28px; border-radius: 3px; }
QToolTip { background: #252C37; color: #F2F5F9; border: 1px solid #3A4555; padding: 6px 8px; border-radius: 5px; }
QMenu { background: #1B212B; border: 1px solid #303A49; padding: 5px; }
QMenu::item { padding: 7px 26px 7px 10px; border-radius: 4px; }
QMenu::item:selected { background: #292548; }
QTabBar::tab { color: #929EAE; padding: 8px 12px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #F2F5F9; border-bottom-color: #7C6EF6; }
QTabWidget::pane { border: 0; }
"""
