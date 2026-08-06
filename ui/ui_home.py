from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QStackedWidget,
    QFileDialog,
    QMessageBox,
    QScrollArea
)
from PySide6.QtCore import Qt, QSize
from exporter import exportar_json, exportar_csv
from ui.ui_create import CreatePautaWindow
from ui.ui_search import SearchPautaWindow
from user_config import MODO
from theme import GLOBAL_STYLE, APP_VERSION, APP_SUBTITLE, APP_TEAM
from database import listar_pautas_acervo, atualizar_status_pauta
from config import CANDIDATOS
from PySide6.QtGui import QIcon




class HomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.filtro_acervo_atual = "Todos"
        self.filtro_status_acervo = "Todos"
        self.filtro_periodo_acervo = "Todos"
        self.setWindowTitle("Sistema de Pautas Audiovisuais")
        self.resize(1200, 760)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.sidebar_aberta = True

        self.pages = QStackedWidget()

        self.dashboard_page = self.criar_dashboard_page()
        self.create_page = CreatePautaWindow()
        self.search_page = SearchPautaWindow()

        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.create_page)
        self.pages.addWidget(self.search_page)

        self.sidebar = self.criar_sidebar()

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.pages, stretch=1)

        self.setCentralWidget(root)
        self.setStyleSheet(GLOBAL_STYLE)

    def criar_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(280)

        layout = QVBoxLayout(sidebar)
        self.sidebar_layout = layout
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(16)

        self.btn_toggle_sidebar = QPushButton("")
        self.btn_toggle_sidebar.setObjectName("SecondaryButton")
        self.btn_toggle_sidebar.setFixedHeight(42)
        self.configurar_botao_sidebar(
            self.btn_toggle_sidebar,
            "",
            "assets/icons/menu.svg"
        )
        self.btn_toggle_sidebar.clicked.connect(self.alternar_sidebar)
        layout.addWidget(self.btn_toggle_sidebar)

        self.logo = QLabel("SP")
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setFixedSize(64, 64)
        self.logo.setStyleSheet("""
            QLabel {
                background-color: #2D6CDF;
                border-radius: 18px;
                font-size: 26px;
                font-weight: bold;
            }
        """)

        self.sidebar_title = QLabel("SISTEMA\nDE PAUTAS")
        self.sidebar_title.setStyleSheet("font-size: 26px; font-weight: bold;")

        self.sidebar_subtitle = QLabel(APP_SUBTITLE)
        self.sidebar_subtitle.setStyleSheet("color: #94A3B8; font-size: 14px;")

        layout.addWidget(self.logo)
        layout.addSpacing(8)
        layout.addWidget(self.sidebar_title)
        layout.addWidget(self.sidebar_subtitle)
        layout.addSpacing(32)

        self.btn_dashboard = QPushButton()
        self.btn_dashboard.setObjectName("SecondaryButton")
        self.configurar_botao_sidebar(
            self.btn_dashboard,
            "Dashboard",
            "assets/icons/dashboard.svg"
        )
        self.btn_dashboard.clicked.connect(self.mostrar_dashboard)
        layout.addWidget(self.btn_dashboard)

        if MODO == "ADMIN":
            self.btn_criar = QPushButton()
            self.btn_criar.setObjectName("AdminButton")
            self.configurar_botao_sidebar(
                self.btn_criar,
                "Nova pauta",
                "assets/icons/add.svg"
            )
            self.btn_criar.clicked.connect(self.mostrar_criar)
            layout.addWidget(self.btn_criar)

        self.btn_buscar = QPushButton()
        self.configurar_botao_sidebar(
            self.btn_buscar,
            "Pesquisar acervo",
            "assets/icons/search.svg"
        )
        self.btn_buscar.clicked.connect(self.mostrar_busca)
        layout.addWidget(self.btn_buscar)

        self.btn_exportar = QPushButton()
        self.btn_exportar.setObjectName("SecondaryButton")
        self.configurar_botao_sidebar(
            self.btn_exportar,
            "Exportar dados",
            "assets/icons/export.svg"
        )
        self.btn_exportar.clicked.connect(self.exportar_dados)
        layout.addWidget(self.btn_exportar)

        layout.addStretch()

        self.mode_label = QLabel(f"Modo: {MODO}")
        self.mode_label.setStyleSheet("color: #94A3B8;")

        self.version_label = QLabel(f"{APP_VERSION} • {APP_TEAM}")
        self.version_label.setStyleSheet("color: #94A3B8; font-size: 12px;")

        layout.addWidget(self.mode_label)
        layout.addWidget(self.version_label)

        return sidebar

    def criar_dashboard_page(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(22)

        header_title = QLabel("Acervo")
        header_title.setStyleSheet("font-size: 34px; font-weight: bold;")

        header_subtitle = QLabel("Organize e acompanhe suas pautas por status, responsável e período.")
        header_subtitle.setStyleSheet("color: #94A3B8; font-size: 16px;")

        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)

        pautas = listar_pautas_acervo(
            candidato=self.filtro_acervo_atual,
            periodo=self.filtro_periodo_acervo,
            status=self.filtro_status_acervo
        )

        total_a_editar = len([p for p in pautas if (p.get("status_pauta") or "a_editar") == "a_editar"])
        total_em_producao = len([p for p in pautas if (p.get("status_pauta") or "") == "em_producao"])
        total_finalizadas = len([p for p in pautas if (p.get("status_pauta") or "") == "finalizada"])

        status_row = QHBoxLayout()
        status_row.setSpacing(12)

        status_row.addWidget(self.criar_card_stat("A editar", total_a_editar))
        status_row.addWidget(self.criar_card_stat("Em produção", total_em_producao))
        status_row.addWidget(self.criar_card_stat("Finalizadas", total_finalizadas))

        layout.addLayout(status_row)

        filtros_row = QHBoxLayout()
        filtros_row.setSpacing(12)

        responsavel_card = QFrame()
        responsavel_card.setObjectName("Card")
        responsavel_card.setMaximumHeight(58)

        responsavel_layout = QHBoxLayout(responsavel_card)
        responsavel_layout.setContentsMargins(16, 12, 16, 12)
        responsavel_layout.setSpacing(10)

        responsavel_label = QLabel("Responsável")
        responsavel_label.setStyleSheet("color: #94A3B8; font-size: 14px; font-weight: 600;")

        responsavel_layout.addWidget(responsavel_label)
        responsavel_layout.addSpacing(10)

        responsavel_layout.addWidget(
            self.criar_segment_button(
                "Todos",
                self.filtro_acervo_atual == "Todos",
                lambda: self.selecionar_filtro_acervo("candidato", "Todos")
            )
        )

        for candidato in CANDIDATOS:
            responsavel_layout.addWidget(
                self.criar_segment_button(
                    candidato,
                    self.filtro_acervo_atual == candidato,
                    lambda checked=False, c=candidato: self.selecionar_filtro_acervo("candidato", c)
                )
            )

        responsavel_layout.addStretch()

        periodo_card = QFrame()
        periodo_card.setObjectName("Card")
        periodo_card.setMaximumHeight(58)

        periodo_layout = QHBoxLayout(periodo_card)
        periodo_layout.setContentsMargins(16, 12, 16, 12)
        periodo_layout.setSpacing(10)

        periodo_label = QLabel("Período")
        periodo_label.setStyleSheet("color: #94A3B8; font-size: 14px; font-weight: 600;")

        periodo_layout.addWidget(periodo_label)
        periodo_layout.addSpacing(10)

        for periodo in ["Todos", "Hoje", "7 dias", "30 dias"]:
            periodo_layout.addWidget(
                self.criar_segment_button(
                    periodo,
                    self.filtro_periodo_acervo == periodo,
                    lambda checked=False, p=periodo: self.selecionar_filtro_acervo("periodo", p)
                )
            )

        periodo_layout.addStretch()

        filtros_row.addWidget(responsavel_card, stretch=2)
        filtros_row.addWidget(periodo_card, stretch=1)

        layout.addLayout(filtros_row)

        lista_card = QFrame()
        lista_card.setObjectName("Card")

        lista_layout = QVBoxLayout(lista_card)
        lista_layout.setContentsMargins(18, 18, 18, 18)
        lista_layout.setSpacing(12)

        lista_header = QHBoxLayout()

        lista_titulo = QLabel("Pautas")
        lista_titulo.setStyleSheet("font-size: 22px; font-weight: bold;")

        lista_total = QLabel(f"{len(pautas)} pauta(s) encontradas")
        lista_total.setStyleSheet("color: #94A3B8; font-size: 14px;")

        lista_header.addWidget(lista_titulo)
        lista_header.addStretch()
        lista_header.addWidget(lista_total)

        lista_layout.addLayout(lista_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("AcervoScroll")

        scroll_content = QWidget()
        scroll_content.setObjectName("AcervoScrollContent")

        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        if not pautas:
            vazio = QLabel("Nenhuma pauta encontrada com os filtros atuais.")
            vazio.setStyleSheet("color: #94A3B8; font-size: 14px;")
            scroll_layout.addWidget(vazio)
        else:
            for pauta in pautas:
                scroll_layout.addWidget(self.criar_pauta_acervo_item(pauta))

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        lista_layout.addWidget(scroll)

        layout.addWidget(lista_card, stretch=1)

        return content

    def alternar_status_pauta(self, pauta):
        status_atual = pauta.get("status_pauta") or "a_editar"

        proximo_status = {
            "a_editar": "em_producao",
            "em_producao": "finalizada",
            "finalizada": "a_editar"
        }

        novo_status = proximo_status.get(status_atual, "a_editar")

        atualizar_status_pauta(pauta["id"], novo_status)

        self.dashboard_page.deleteLater()
        self.dashboard_page = self.criar_dashboard_page()
        self.pages.insertWidget(0, self.dashboard_page)
        self.pages.setCurrentWidget(self.dashboard_page)

    def criar_card_stat(self, titulo, valor):
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(130)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)

        header = QHBoxLayout()
        header.setSpacing(8)

        status_map = {
            "A editar": "a_editar",
            "Em produção": "em_producao",
            "Finalizadas": "finalizada",
        }

        if titulo in status_map:
            bolinha = QLabel("●")
            bolinha.setObjectName(f"CardStatusDot_{status_map[titulo]}")
            header.addWidget(bolinha)

        label_titulo = QLabel(titulo)
        label_titulo.setStyleSheet("color: #94A3B8; font-size: 14px;")

        header.addWidget(label_titulo)
        header.addStretch()

        label_valor = QLabel(str(valor))
        label_valor.setStyleSheet("font-size: 34px; font-weight: bold;")

        layout.addLayout(header)
        layout.addStretch()
        layout.addWidget(label_valor)

        return card

    def mostrar_dashboard(self):
        self.dashboard_page.deleteLater()
        self.dashboard_page = self.criar_dashboard_page()
        self.pages.insertWidget(0, self.dashboard_page)
        self.pages.setCurrentWidget(self.dashboard_page)

    def mostrar_criar(self):
        self.pages.setCurrentWidget(self.create_page)

    def mostrar_busca(self):
        self.pages.setCurrentWidget(self.search_page)

    def alternar_sidebar(self):
        self.sidebar_aberta = not self.sidebar_aberta

        if self.sidebar_aberta:
            self.sidebar.setFixedWidth(280)

            self.logo.setVisible(True)
            self.sidebar_title.setVisible(True)
            self.sidebar_subtitle.setVisible(True)
            self.mode_label.setVisible(True)
            self.version_label.setVisible(True)

            self.btn_dashboard.setText("Dashboard")

            if MODO == "ADMIN":
                self.btn_criar.setText("Nova pauta")

            self.btn_buscar.setText("Pesquisar acervo")
            self.btn_exportar.setText("Exportar dados")

        else:
            self.sidebar.setFixedWidth(76)

            self.logo.setVisible(False)
            self.sidebar_title.setVisible(False)
            self.sidebar_subtitle.setVisible(False)
            self.mode_label.setVisible(False)
            self.version_label.setVisible(False)

            self.btn_dashboard.setText("")

            if MODO == "ADMIN":
                self.btn_criar.setText("")

            self.btn_buscar.setText("")
            self.btn_exportar.setText("")

    def exportar_dados(self):
        caminho_base, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar banco de dados",
            "backup_pautas",
            "JSON (*.json);;CSV (*.csv)"
        )

        if not caminho_base:
            return

        try:
            if caminho_base.lower().endswith(".json"):
                exportar_json(caminho_base)

            elif caminho_base.lower().endswith(".csv"):
                exportar_csv(caminho_base)

            else:
                caminho_base = caminho_base + ".json"
                exportar_json(caminho_base)

            QMessageBox.information(
                self,
                "Exportação concluída",
                f"Dados exportados com sucesso:\n\n{caminho_base}"
            )

        except Exception as erro:
            QMessageBox.critical(
                self,
                "Erro ao exportar",
                f"Não foi possível exportar os dados:\n\n{erro}"
            )

    def configurar_botao_sidebar(self, botao, texto, icone):
        botao.setText(texto)
        botao.setIcon(QIcon(icone))
        botao.setIconSize(QSize(22, 22))
        botao.setMinimumHeight(46)


    def selecionar_filtro_acervo(self, tipo, valor):
        if tipo == "status":
            self.filtro_status_acervo = valor

        elif tipo == "candidato":
            self.filtro_acervo_atual = valor

        elif tipo == "periodo":
            self.filtro_periodo_acervo = valor

        self.dashboard_page.deleteLater()
        self.dashboard_page = self.criar_dashboard_page()
        self.pages.insertWidget(0, self.dashboard_page)
        self.pages.setCurrentWidget(self.dashboard_page)


    def criar_segment_button(self, texto, ativo, callback):
        botao = QPushButton(texto)
        botao.setObjectName("SegmentButtonActive" if ativo else "SegmentButton")
        botao.clicked.connect(callback)
        return botao


    def criar_pauta_acervo_item(self, pauta):
        item = QFrame()
        item.setObjectName("AcervoPautaItem")

        layout = QHBoxLayout(item)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        status = pauta.get("status_pauta") or "a_editar"

        status_icone = {
            "a_editar": "●",
            "em_producao": "●",
            "finalizada": "●",
        }.get(status, "●")

        status_label = QPushButton()
        status_label.setObjectName(f"StatusDot_{status}")
        status_label.setFixedSize(18, 18)
        status_label.setCursor(Qt.PointingHandCursor)
        status_label.clicked.connect(lambda: self.alternar_status_pauta(pauta))

        info = QVBoxLayout()
        info.setSpacing(3)

        nome = QLabel(pauta.get("nome_pauta") or "Sem nome")
        nome.setObjectName("AcervoPautaTitulo")

        meta = QLabel(f"{pauta.get('data_pauta') or ''} • {pauta.get('candidato') or ''}")
        meta.setObjectName("AcervoPautaMeta")

        info.addWidget(nome)
        info.addWidget(meta)

        layout.addWidget(status_label)
        layout.addLayout(info, stretch=1)

        return item



















































