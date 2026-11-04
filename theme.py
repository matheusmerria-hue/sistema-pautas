APP_VERSION = "v1.0"
APP_SUBTITLE = "Busca audiovisual inteligente"
APP_TEAM = "Núcleo de Produção"

FONT_FAMILY = "Segoe UI"

COLORS = {
    "bg": "#0B1018",
    "sidebar": "#0E1623",
    "surface": "#121C2A",
    "surface_raised": "#172334",
    "surface_hover": "#1B2A3E",
    "primary": "#3977E6",
    "primary_hover": "#4B88F2",
    "primary_pressed": "#2D62C2",
    "admin": "#B45309",
    "danger": "#C2413A",
    "success": "#2FA66A",
    "warning": "#D79A2B",
    "text": "#EAF0F7",
    "text_secondary": "#B6C2D1",
    "muted": "#8291A5",
    "border": "#253449",
    "focus": "#6EA1FF",
}

# Shared spacing and sizing tokens used by the Python layouts.
SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
SIZES = {"field_height": 42, "button_height": 42, "radius": 10, "card_radius": 14}

GLOBAL_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "{FONT_FAMILY}";
    font-size: 14px;
}}
QLabel {{ background: transparent; }}
QToolTip {{
    color: {COLORS['text']}; background: {COLORS['surface_raised']};
    border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 6px;
}}
QFrame#Sidebar {{
    background: {COLORS['sidebar']}; border: none;
    border-right: 1px solid {COLORS['border']};
}}
QFrame#Card, QFrame#PautaCard, QFrame#AcervoPautaItem, QFrame#TakeRow {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: {SIZES['card_radius']}px;
}}
QFrame#PautaCard:hover, QFrame#AcervoPautaItem:hover, QFrame#TakeRow:hover {{
    background: {COLORS['surface_hover']}; border-color: #3A506C;
}}
QPushButton {{
    min-height: {SIZES['button_height']}px;
    background: {COLORS['primary']}; color: #F7FAFF;
    border: 1px solid {COLORS['primary']}; border-radius: {SIZES['radius']}px;
    padding: 0 16px; font-weight: 600;
}}
QPushButton:hover {{ background: {COLORS['primary_hover']}; border-color: {COLORS['primary_hover']}; }}
QPushButton:pressed {{ background: {COLORS['primary_pressed']}; border-color: {COLORS['primary_pressed']}; }}
QPushButton:focus {{ border: 2px solid {COLORS['focus']}; }}
QPushButton:disabled {{ background: #182231; color: #617087; border-color: #253044; }}
QPushButton#SecondaryButton, QPushButton#SmallButton, QPushButton#PautaActionButton {{
    background: {COLORS['surface_raised']}; color: {COLORS['text_secondary']};
    border-color: #31435A;
}}
QPushButton#SecondaryButton:hover, QPushButton#SmallButton:hover, QPushButton#PautaActionButton:hover {{
    background: {COLORS['surface_hover']}; color: {COLORS['text']}; border-color: #4A607C;
}}
QPushButton#AdminButton {{ background: {COLORS['admin']}; border-color: {COLORS['admin']}; }}
QPushButton#DeleteButton {{
    min-height: 36px; background: transparent; color: #F29A94;
    border: 1px solid #7E3837; border-radius: 9px; padding: 0 12px; font-weight: 600;
}}
QPushButton#DeleteButton:hover {{ background: #3A2023; color: #FFD1CD; border-color: {COLORS['danger']}; }}
QPushButton#SmallButton, QPushButton#PautaActionButton {{ min-height: 34px; padding: 0 12px; font-size: 13px; }}
QLineEdit, QTextEdit, QComboBox {{
    min-height: {SIZES['field_height']}px; background: #0E1723; color: {COLORS['text']};
    border: 1px solid #304158; border-radius: {SIZES['radius']}px;
    padding: 0 12px; selection-background-color: {COLORS['primary']};
}}
QTextEdit {{ padding: 10px 12px; }}
QLineEdit:hover, QTextEdit:hover, QComboBox:hover {{ border-color: #445A76; }}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border: 2px solid {COLORS['focus']}; }}
QLineEdit:read-only {{ background: #111A27; color: {COLORS['muted']}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{
    background: {COLORS['surface_raised']}; color: {COLORS['text']};
    border: 1px solid {COLORS['border']}; selection-background-color: {COLORS['primary']};
}}
QCheckBox {{ spacing: 8px; color: {COLORS['text_secondary']}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid #4B607A; border-radius: 5px; background: #0E1723; }}
QCheckBox::indicator:checked {{ background: {COLORS['primary']}; border-color: {COLORS['focus']}; }}
QCheckBox:focus {{ color: {COLORS['text']}; }}
QScrollArea, QScrollArea > QWidget > QWidget, QWidget#SearchResultsArea, QWidget#AcervoScrollContent {{
    border: none; background: {COLORS['bg']};
}}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #34455B; min-height: 32px; border-radius: 5px; }}
QScrollBar::handle:vertical:hover {{ background: #4A607A; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QLabel#PageTitle {{ font-size: 30px; font-weight: 700; color: {COLORS['text']}; }}
QLabel#PageSubtitle, QLabel#SectionSubtitle, QLabel#PautaMeta, QLabel#PautaPath, QLabel#EmptyText {{ color: {COLORS['muted']}; }}
QLabel#SectionTitle {{ font-size: 20px; font-weight: 700; }}
QLabel#FieldLabel, QLabel#PautaSectionTitle {{ color: {COLORS['text_secondary']}; font-size: 13px; font-weight: 600; }}
QLabel#PautaTitle {{ font-size: 18px; font-weight: 700; }}
QLabel#PautaDescription {{ color: {COLORS['text_secondary']}; }}
QLabel#EmptyText {{ padding: 28px; font-size: 14px; }}
QPushButton#HistoryChip, QPushButton#SegmentButton, QPushButton#SegmentButtonActive {{
    min-height: 30px; border-radius: 15px; padding: 0 12px; font-size: 13px; font-weight: 600;
}}
QPushButton#HistoryChip, QPushButton#SegmentButton {{
    background: {COLORS['sidebar']}; color: {COLORS['muted']}; border-color: {COLORS['border']};
}}
QPushButton#HistoryChip:hover, QPushButton#SegmentButton:hover {{ background: {COLORS['surface_hover']}; color: {COLORS['text']}; }}
QPushButton#SegmentButtonActive {{ background: {COLORS['primary']}; color: white; border-color: {COLORS['primary']}; }}
QLabel#AcervoPautaTitulo {{ font-size: 15px; font-weight: 600; }}
QLabel#AcervoPautaMeta {{ color: {COLORS['muted']}; font-size: 13px; }}
QPushButton#StatusDot_a_editar, QPushButton#StatusDot_em_producao, QPushButton#StatusDot_finalizada {{
    min-width: 12px; max-width: 12px; min-height: 12px; max-height: 12px;
    padding: 0; border: 2px solid transparent; border-radius: 6px;
}}
QPushButton#StatusDot_a_editar {{ background: #5B9AF4; }}
QPushButton#StatusDot_em_producao {{ background: {COLORS['warning']}; }}
QPushButton#StatusDot_finalizada {{ background: {COLORS['success']}; }}
QPushButton#StatusDot_a_editar:hover, QPushButton#StatusDot_em_producao:hover, QPushButton#StatusDot_finalizada:hover {{ border-color: {COLORS['text']}; }}
QLabel#CardStatusDot_a_editar {{ color: #5B9AF4; }}
QLabel#CardStatusDot_em_producao {{ color: {COLORS['warning']}; }}
QLabel#CardStatusDot_finalizada {{ color: {COLORS['success']}; }}
QDialog, QMessageBox {{ background: {COLORS['bg']}; color: {COLORS['text']}; }}
QDialog QWidget, QMessageBox QWidget {{ color: {COLORS['text']}; }}
QToolButton {{ background: transparent; color: {COLORS['text_secondary']}; border: none; padding: 6px 2px; font-weight: 600; text-align: left; }}
QToolButton:hover {{ color: {COLORS['text']}; }}
"""
