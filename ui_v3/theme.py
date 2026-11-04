ACCENT="#19D3C5"
QSS=r"""
*{font-family:"Segoe UI Variable","Segoe UI",Arial,sans-serif;font-size:12px;color:#DCE8E8}
QMainWindow,QWidget#Root,QWidget#Stage{background:#071014}
QWidget#Rail{background:#06191C;border-right:1px solid #123137}
QWidget#WorkspaceBar{background:#0A171B;border-bottom:1px solid #173036}
QWidget#Master{background:#0B1519;border-right:1px solid #183238}
QWidget#Inspector{background:#0C1A1E;border-left:1px solid #183238}
QFrame#Panel{background:#0D1D21;border-radius:7px}
QFrame#Raised{background:#12272B;border:1px solid #214047;border-radius:8px}
QFrame#Row{background:transparent;border-bottom:1px solid #142B30}
QFrame#Row:hover{background:#10252A}
QFrame#Row[selected="true"]{background:#103237;border-left:2px solid #19D3C5}
QLabel#Logo{background:#19D3C5;color:#031315;border-radius:7px;font-weight:900;font-size:16px}
QLabel#Title{font-size:19px;font-weight:700;color:#F0FAFA}
QLabel#Section{font-size:13px;font-weight:700;color:#F0FAFA}
QLabel#Item{font-size:12px;font-weight:650;color:#EAF5F5}
QLabel#Meta{font-size:11px;color:#789397}
QLabel#Micro{font-size:9px;font-weight:750;color:#5F7F83;letter-spacing:1px}
QLabel#Accent{color:#19D3C5;font-weight:700}
QPushButton{min-height:29px;padding:0 10px;background:#12272B;border:1px solid #24434A;border-radius:5px;font-weight:600}
QPushButton:hover{background:#173238;border-color:#32616A} QPushButton:pressed{background:#0B2024;padding-top:1px}
QPushButton[kind="accent"]{background:#19D3C5;color:#041315;border:0} QPushButton[kind="accent"]:hover{background:#43E4D7}
QPushButton[kind="flat"]{background:transparent;border:0;color:#89A4A7} QPushButton[kind="flat"]:hover{background:#10272C;color:#EAF7F6}
QPushButton[kind="rail"]{background:transparent;border:0;padding:0;color:#789397;font-size:17px} QPushButton[kind="rail"]:hover{background:#102A2F;color:#DFFFFB} QPushButton[kind="rail"]:checked{background:#12383C;color:#19D3C5;border-left:2px solid #19D3C5}
QPushButton[kind="tab"]{background:transparent;border:0;border-radius:0;color:#6F8B8F;padding:0 13px} QPushButton[kind="tab"]:checked{color:#EAF7F6;border-bottom:2px solid #19D3C5}
QPushButton[kind="danger"]{background:#32191C;color:#FF9B9D;border-color:#5A282D}
QLineEdit,QTextEdit,QComboBox{background:#071519;border:1px solid #254249;border-radius:5px;padding:5px 8px;selection-background-color:#167C76}
QLineEdit{min-height:21px} QLineEdit:focus,QTextEdit:focus,QComboBox:focus{border-color:#19D3C5}
QComboBox{min-height:21px} QComboBox::drop-down{width:22px;border:0} QComboBox QAbstractItemView{background:#102429;border:1px solid #285058;selection-background-color:#155158;padding:4px}
QCheckBox{spacing:6px;color:#A5B9BA} QCheckBox::indicator{width:14px;height:14px;border:1px solid #3C5A60;border-radius:3px;background:#081519} QCheckBox::indicator:checked{background:#19D3C5;border-color:#19D3C5}
QScrollArea{border:0;background:transparent} QScrollArea>QWidget>QWidget{background:transparent}
QScrollBar:vertical{background:transparent;width:8px;margin:1px} QScrollBar::handle:vertical{background:#27464C;min-height:30px;border-radius:3px} QScrollBar::handle:vertical:hover{background:#39636B} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
QMenu{background:#102429;border:1px solid #285058;padding:5px} QMenu::item{padding:7px 24px 7px 9px;border-radius:4px} QMenu::item:selected{background:#164149}
QToolTip{background:#163036;color:#EAF7F6;border:1px solid #32616A;padding:5px}
QSplitter::handle{background:#173238} QSplitter::handle:hover{background:#19D3C5}
"""
