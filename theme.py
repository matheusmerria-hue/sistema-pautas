APP_VERSION = "v1.0"
APP_SUBTITLE = "Busca audiovisual inteligente"
APP_TEAM = "Núcleo de Produção"

FONT_FAMILY = "Manrope"

COLORS = {
    "bg": "#0B0F17",
    "sidebar": "#101826",
    "card": "#151B26",
    "card_hover": "#1E293B",
    "primary": "#2D6CDF",
    "primary_hover": "#3F7FF0",
    "admin": "#C2410C",
    "danger": "#B3261E",
    "text": "#F8FAFC",
    "muted": "#94A3B8",
    "border": "#263244"
}

GLOBAL_STYLE = f"""
QMainWindow {{
    background-color: #0B0F17;
    color: #F8FAFC;
    font-family: Manrope;
    font-size: 15px;
}}

QWidget {{
    color: #F8FAFC;
    font-family: Manrope;
    font-size: 15px;
}}

QLabel {{
    color: #F8FAFC;
    background-color: transparent;
}}

QFrame#Sidebar {{
    background-color: #101826;
    border-right: 1px solid #263244;
}}

QFrame#Card {{
    background-color: #151B26;
    border: 1px solid #263244;
    border-radius: 16px;
}}

QPushButton {{
    background-color: #2D6CDF;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px;
    font: 700 15px "Segoe UI";
}}

QPushButton:hover {{
    background-color: #3F7FF0;
}}

QPushButton#SecondaryButton {{
    background-color: #151B26;
    border: 1px solid #263244;
}}

QPushButton#SecondaryButton:hover {{
    background-color: #1E293B;
}}

QPushButton#AdminButton {{
    background-color: #C2410C;
}}


QPushButton#DeleteButton {{
    background-color: #B3261E;
    color: white;
    border: 1px solid #B3261E;
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#DeleteButton:hover {{
    background-color: #C93A2F;
    border: 1px solid #E25A4F;
}}

QPushButton#DeleteButton:pressed {{
    background-color: #941E17;
}}

QLineEdit, QTextEdit, QComboBox {{
    background-color: #151B26;
    color: #F8FAFC;
    border: 1px solid #263244;
    border-radius: 10px;
    padding: 10px;
}}

QScrollArea {{
    border: none;
}}

QPushButton#HistoryChip {{
    background-color: #101826;
    border: 1px solid #263244;
    border-radius: 16px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#HistoryChip:hover {{
    background-color: #1E293B;
}}

QFrame#TakeRow {{
    background-color: #111827;
    border: 1px solid #243044;
    border-radius: 16px;
    margin: 6px 0px;
}}

QFrame#TakeRow:hover {{
    background-color: #141F2F;
    border: 1px solid #2D6CDF;
}}

QPushButton#SmallButton {{
    background-color: #1E293B;
    color: #CBD5E1;
    border: 1px solid #334155;
    border-radius: 9px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 700;
    min-width: 86px;
}}

QPushButton#SmallButton:hover {{
    background-color: #263449;
    color: #F8FAFC;
    border: 1px solid #475569;
}}

QPushButton#SmallButton:pressed {{
    background-color: #172033;
}}

QFrame#PautaCard {{
    background-color: #111827;
    border: 1px solid #243044;
    border-radius: 16px;
    margin: 10px 0px 18px 0px;
}}

QFrame#PautaCard:hover {{
    background-color: #162033;
    border: 1px solid #3B4A63;
}}

QLabel#PautaTitle {{
    color: #F8FAFC;
    font-size: 18px;
    font-weight: 800;
}}

QLabel#PautaDescription {{
    color: #CBD5E1;
    font-size: 14px;
}}

QLabel#PautaPath {{
    color: #94A3B8;
    font-size: 13px;
}}

QLabel#PautaSectionTitle {{
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 700;
}}

QLabel#EmptyText {{
    color: #94A3B8;
    font-size: 14px;
}}

QPushButton#PautaActionButton {{
    background-color: #2D6CDF;
    color: white;
    border: none;
    border-radius: 9px;
    padding: 9px 13px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#PautaActionButton:hover {{
    background-color: #3B7AF0;
}}


QLabel#PautaTitle {{
    color: #F8FAFC;
    font-size: 20px;
    font-weight: 800;
}}

QLabel#PautaMeta {{
    color: #94A3B8;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton#PautaActionButton {{
    background-color: #1E293B;
    color: #CBD5E1;
    border: 1px solid #334155;
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#PautaActionButton:hover {{
    background-color: #263449;
    color: #F8FAFC;
    border: 1px solid #475569;
}}

QFrame#PautaCard QWidget#PautaInfoWidget {{
    background-color: transparent;
    border: none;
}}

QFrame#PautaCard {{
    background-color: #111827;
    border: 1px solid #243044;
    border-radius: 16px;
    margin: 10px 0px 18px 0px;
}}

QFrame#PautaCard > QWidget {{
    background-color: transparent;
    border: none;
}}

QWidget#PautaInfoWidget {{
    background-color: transparent;
    border: none;
}}

QDialog {{
    background-color: #121212;
    color: white;
}}

QDialog QWidget {{
    background-color: transparent;
    color: white;
}}

QWidget#SearchResultsArea {{
    background-color: #0B0F17;
}}

QScrollArea {{
    border: none;
    background-color: #0B0F17;
}}

QScrollArea > QWidget > QWidget {{
    background-color: #0B0F17;
}}

QLabel#SectionTitle {{
    color: #F8FAFC;
    font-size: 22px;
    font-weight: 800;
}}

QLabel#SectionSubtitle {{
    color: #94A3B8;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 8px;
}}

QPushButton#SegmentButton,
QPushButton#SegmentButtonActive {{
    border-radius: 999px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#SegmentButton {{
    background-color: #101826;
    color: #94A3B8;
    border: 1px solid #263244;
}}

QPushButton#SegmentButton:hover {{
    background-color: #1E293B;
    color: #F8FAFC;
}}

QPushButton#SegmentButtonActive {{
    background-color: #2D6CDF;
    color: white;
    border: 1px solid #2D6CDF;
}}

QFrame#AcervoPautaItem {{
    background-color: #101826;
    border: 1px solid #263244;
    border-radius: 12px;
}}

QFrame#AcervoPautaItem:hover {{
    background-color: #162033;
    border: 1px solid #3B4A63;
}}

QLabel#AcervoPautaTitulo {{
    color: #F8FAFC;
    font-size: 15px;
    font-weight: 800;
}}

QLabel#AcervoPautaMeta {{
    color: #94A3B8;
    font-size: 13px;
    font-weight: 500;
}}

QLabel#StatusDot_a_editar {{
    color: #60A5FA;
    font-size: 18px;
    font-weight: 900;
}}

QLabel#StatusDot_em_producao {{
    color: #F59E0B;
    font-size: 18px;
    font-weight: 900;
}}

QLabel#StatusDot_finalizada {{
    color: #22C55E;
    font-size: 18px;
    font-weight: 900;
}}

QScrollArea#AcervoScroll {{
    background-color: transparent;
    border: none;
}}

QWidget#AcervoScrollContent {{
    background-color: transparent;
}}

QPushButton#StatusDot_a_editar {{
    background-color: #60A5FA;
    border: none;
    border-radius: 6px;
    padding: 0px;
    min-width: 12px;
    max-width: 12px;
    min-height: 12px;
    max-height: 12px;
}}

QPushButton#StatusDot_em_producao {{
    background-color: #EF4444;
    border: none;
    border-radius: 6px;
    padding: 0px;
    min-width: 12px;
    max-width: 12px;
    min-height: 12px;
    max-height: 12px;
}}

QPushButton#StatusDot_finalizada {{
    background-color: #22C55E;
    border: none;
    border-radius: 6px;
    padding: 0px;
    min-width: 12px;
    max-width: 12px;
    min-height: 12px;
    max-height: 12px;
}}

QPushButton#StatusDot_a_editar:hover,
QPushButton#StatusDot_em_producao:hover,
QPushButton#StatusDot_finalizada:hover {{
    border: 2px solid #F8FAFC;
}}

QLabel#CardStatusDot_a_editar {{
    color: #60A5FA;
    font-size: 16px;
    font-weight: 900;
}}

QLabel#CardStatusDot_em_producao {{
    color: #EF4444;
    font-size: 16px;
    font-weight: 900;
}}

QLabel#CardStatusDot_finalizada {{
    color: #22C55E;
    font-size: 16px;
    font-weight: 900;
}}

"""