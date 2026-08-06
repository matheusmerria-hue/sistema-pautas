import os
import html
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QScrollArea, QFrame, QCheckBox,
    QMessageBox, QDialog, QTextEdit, QFileDialog, QToolButton, QLayout
)
from database import (
    buscar_pautas,
    excluir_pauta,
    atualizar_pauta,
    alternar_favorito_take,
    salvar_busca,
    obter_historico_buscas,
    alternar_favorito_pauta
)
from PySide6.QtGui import QGuiApplication

from PySide6.QtCore import (
     Qt,
     QTimer,
     Slot
 )





from config import CANDIDATOS
from exporter import exportar_resultados_json, exportar_resultados_csv
from media_loader import MediaLoader
from theme import GLOBAL_STYLE, SPACING

class SearchPautaWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Buscar pautas")
        self.resize(1100, 750)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSizeConstraint(QLayout.SetNoConstraint)
        self.main_layout.setContentsMargins(SPACING["xxl"], SPACING["xl"], SPACING["xxl"], SPACING["xl"])
        self.main_layout.setSpacing(SPACING["md"])
        self.resultados_exportaveis = []
        self.media_loader = MediaLoader(self)
        self.media_generation = self.media_loader.generation
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(500)
        self.search_timer.timeout.connect(self.executar_busca_instantanea)

        self.criar_cabecalho()
        self.criar_filtros()
        self.criar_area_resultados()
        self.aplicar_estilo()
        self.atualizar_historico()

    def closeEvent(self, event):
        self.media_loader.encerrar()
        super().closeEvent(event)

    def criar_cabecalho(self):
        title = QLabel("Buscar pautas")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Busque por pauta, candidato, data, arquivo ou comentário dos takes.")
        subtitle.setObjectName("PageSubtitle")

        self.main_layout.addWidget(title)
        self.main_layout.addWidget(subtitle)

    def criar_filtros(self):
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        linha_1 = QHBoxLayout()

        self.input_palavra = QLineEdit()
        self.input_palavra.setPlaceholderText("Palavra-chave")
        self.input_palavra.textChanged.connect(self.agendar_busca)

        self.combo_candidato = QComboBox()
        self.combo_candidato.addItem("Todos")
        self.combo_candidato.addItems(CANDIDATOS)

        linha_1.addWidget(self.input_palavra, stretch=3)
        linha_1.addWidget(self.combo_candidato, stretch=1)

        linha_2 = QHBoxLayout()
        linha_2.setSpacing(12)

        linha_opcoes = QVBoxLayout()
        linha_opcoes.setSpacing(8)

        linha_acoes = QHBoxLayout()
        linha_acoes.setSpacing(10)

        self.input_data_inicial = QLineEdit()
        self.input_data_inicial.setPlaceholderText("Data inicial (AAAA-MM-DD)")

        self.input_data_final = QLineEdit()
        self.input_data_final.setPlaceholderText("Data final (AAAA-MM-DD)")

        self.check_somente_comentados = QCheckBox("Mostrar somente takes comentados")
        self.check_somente_favoritos = QCheckBox("Mostrar somente takes favoritos")
        self.check_somente_pautas_favoritas = QCheckBox("Somente pautas favoritas")

        self.check_somente_comentados.setChecked(True)

        self.combo_candidato.currentIndexChanged.connect(self.agendar_busca)
        self.check_somente_comentados.stateChanged.connect(self.agendar_busca)
        self.check_somente_favoritos.stateChanged.connect(self.agendar_busca)
        self.check_somente_pautas_favoritas.stateChanged.connect(self.agendar_busca)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(lambda: self.executar_busca())

        self.btn_exportar_resultado = QPushButton("Exportar resultado")
        self.btn_exportar_resultado.setObjectName("SecondaryButton")
        self.btn_exportar_resultado.clicked.connect(self.exportar_resultado_busca)
        self.btn_exportar_resultado.setEnabled(False)

        linha_2.addWidget(self.input_data_inicial)
        linha_2.addWidget(self.input_data_final)
        linha_opcoes.addWidget(self.check_somente_comentados)
        linha_opcoes.addWidget(self.check_somente_favoritos)
        linha_opcoes.addWidget(self.check_somente_pautas_favoritas)
        linha_acoes.addStretch()
        linha_acoes.addWidget(self.btn_buscar)
        linha_acoes.addWidget(self.btn_exportar_resultado)

        layout.addLayout(linha_1)
        layout.addLayout(linha_2)
        layout.addLayout(linha_opcoes)
        layout.addLayout(linha_acoes)

        self.card_historico = QFrame()
        self.card_historico.setObjectName("Card")

        historico_layout = QVBoxLayout(self.card_historico)
        historico_layout.setContentsMargins(12, 8, 12, 8)

        self.btn_toggle_historico = QToolButton()
        self.btn_toggle_historico.setText("▼ Últimas buscas")
        self.btn_toggle_historico.setCheckable(True)
        self.btn_toggle_historico.setChecked(False)
        self.btn_toggle_historico.clicked.connect(self.alternar_historico)
        self.btn_toggle_historico.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                color: #F8FAFC;
                border: none;
                font-size: 15px;
                font-weight: bold;
                text-align: left;
            }
        """)

        historico_layout.addWidget(self.btn_toggle_historico)

        self.historico_content = QWidget()
        self.lista_historico = QHBoxLayout(self.historico_content)
        self.lista_historico.setContentsMargins(0, 6, 0, 0)
        self.lista_historico.setSpacing(8)

        self.historico_content.setVisible(False)

        historico_layout.addWidget(self.historico_content)

        layout.addWidget(self.card_historico)

        self.main_layout.addWidget(card)

    def criar_area_resultados(self):
        self.resultados_titulo = QLabel("Resultados")
        self.resultados_titulo.setObjectName("SectionTitle")
        self.resultados_titulo.setVisible(False)

        self.resultados_info = QLabel("Nenhuma busca realizada.")
        self.resultados_info.setObjectName("SectionSubtitle")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("SearchResultsArea")

        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(2, 10, 8, 0)
        self.scroll_layout.setSpacing(14)

        self.scroll_area.setWidget(self.scroll_content)

        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.resultados_titulo)
        self.main_layout.addWidget(self.resultados_info)
        self.main_layout.addSpacing(8)
        self.main_layout.addWidget(self.scroll_area)


    def executar_busca(self, salvar_no_historico=True):
        self.btn_buscar.setText("Buscando...")
        self.btn_buscar.setEnabled(False)

        try:
            palavra = self.input_palavra.text().strip()

            if salvar_no_historico and palavra:
                salvar_busca(palavra)

            resultados = buscar_pautas(
                palavra_chave=palavra,
                data_inicial=self.input_data_inicial.text().strip(),
                data_final=self.input_data_final.text().strip(),
                candidato=self.combo_candidato.currentText(),
                somente_pautas_favoritas=self.check_somente_pautas_favoritas.isChecked()
            )

            self.carregar_resultados(resultados)
            self.atualizar_historico()
        except Exception as erro:
            QMessageBox.critical(
                self,
                "Erro na busca",
                f"Não foi possível concluir a busca:\n\n{erro}"
            )
        finally:
            self.btn_buscar.setText("Buscar")
            self.btn_buscar.setEnabled(True)


    def carregar_resultados(self, resultados):
        self.media_generation = self.media_loader.nova_geracao()

        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total_pautas_visiveis = 0
        total_takes_visiveis = 0
        self.resultados_exportaveis = []

        palavra = self.input_palavra.text().strip()

        if not resultados:
            self.resultados_titulo.setVisible(True)
            self.resultados_info.setText("Nenhum resultado encontrado.")
            self.btn_exportar_resultado.setEnabled(False)

            aviso = QLabel("Nenhum resultado encontrado.")
            aviso.setObjectName("EmptyText")
            self.scroll_layout.addWidget(aviso)
            return

        for item in resultados:
            card = PautaCard(
                pauta=item["pauta"],
                takes=item["takes"],
                somente_comentados=self.check_somente_comentados.isChecked(),
                somente_favoritos=self.check_somente_favoritos.isChecked(),
                palavra_chave=palavra,
                media_loader=self.media_loader,
                media_generation=self.media_generation
            )

            if card.sem_takes_visiveis:
                card.deleteLater()
                continue

            total_pautas_visiveis += 1
            total_takes_visiveis += card.total_takes_visiveis

            self.resultados_exportaveis.append({
                "pauta": item["pauta"],
                "takes": card.takes_visiveis
            })

            self.scroll_layout.addWidget(card)

        if total_pautas_visiveis == 0:
            self.resultados_titulo.setVisible(True)
            self.resultados_info.setText("Nenhum resultado encontrado com os filtros atuais.")
            self.btn_exportar_resultado.setEnabled(False)

            aviso = QLabel("Nenhum resultado encontrado com os filtros atuais.")
            aviso.setObjectName("EmptyText")
            self.scroll_layout.addWidget(aviso)
            return

        self.resultados_titulo.setVisible(True)
        self.resultados_info.setText(
            f"{total_takes_visiveis} takes • {total_pautas_visiveis} pautas"
        )

        self.btn_exportar_resultado.setEnabled(True)
        self.scroll_layout.addStretch()


    def aplicar_estilo(self):
        self.setStyleSheet(GLOBAL_STYLE)
    

    def exportar_resultado_busca(self):
        if not self.resultados_exportaveis:
            QMessageBox.warning(
                self,
                "Nada para exportar",
                "Faça uma busca antes de exportar."
            )
            return

        caminho_saida, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar resultado da busca",
            "resultado_busca",
            "JSON (*.json);;CSV (*.csv)"
        )

        if not caminho_saida:
            return

        try:
            if caminho_saida.lower().endswith(".json"):
                exportar_resultados_json(caminho_saida, self.resultados_exportaveis)

            elif caminho_saida.lower().endswith(".csv"):
                exportar_resultados_csv(caminho_saida, self.resultados_exportaveis)

            else:
                caminho_saida += ".json"
                exportar_resultados_json(caminho_saida, self.resultados_exportaveis)

            QMessageBox.information(
                self,
                "Exportação concluída",
                f"Resultado exportado com sucesso:\n\n{caminho_saida}"
            )

        except Exception as erro:
            QMessageBox.critical(
                self,
                "Erro ao exportar",
                f"Não foi possível exportar o resultado:\n\n{erro}"
            )

    def atualizar_historico(self):
        while self.lista_historico.count():
            item = self.lista_historico.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        historico = obter_historico_buscas()

        self.btn_toggle_historico.setText(
            f"▼ Últimas buscas ({len(historico)})"
        )

        for termo in historico:
            btn = QPushButton(termo)
            btn.setObjectName("HistoryChip")
            btn.setMaximumWidth(160)
            btn.setMinimumHeight(32)

            btn.clicked.connect(
                lambda checked=False, t=termo:
                self.reutilizar_busca(t)
            )

            self.lista_historico.addWidget(btn)

        self.lista_historico.addStretch()


    def reutilizar_busca(self, termo):
        self.input_palavra.setText(termo)
        self.search_timer.stop()
        self.executar_busca()

    def alternar_historico(self):
        aberto = self.btn_toggle_historico.isChecked()

        self.historico_content.setVisible(aberto)
        self.btn_toggle_historico.setText(
            "▲ Últimas buscas" if aberto else "▼ Últimas buscas"
        )

    def agendar_busca(self):
        self.search_timer.start()


    def executar_busca_instantanea(self):
        self.executar_busca(salvar_no_historico=False)


class PautaCard(QFrame):
    def __init__(
        self,
        pauta,
        takes,
        somente_comentados=True,
        somente_favoritos=False,
        palavra_chave="",
        media_loader=None,
        media_generation=0
    ):
        super().__init__()

        self.pauta = pauta
        self.takes = takes
        self.somente_comentados = somente_comentados
        self.somente_favoritos = somente_favoritos
        self.palavra_chave = palavra_chave.lower().strip()
        self.media_loader = media_loader
        self.media_generation = media_generation

        self.takes_visiveis = []
        self.total_takes_visiveis = 0
        self.sem_takes_visiveis = False

        self.expandido = False
        self.detalhes_criados = False

        self.setObjectName("PautaCard")
        self.setCursor(Qt.PointingHandCursor)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 18, 20, 18)
        self.layout.setSpacing(14)

        # Faz somente os filtros de texto/banco.
        # Nenhuma thumbnail é criada neste momento.
        self.preparar_takes_visiveis()

        self.criar_header()

        # O widget existe desde o início, mas seu conteúdo pesado
        # só será criado quando o usuário abrir o card.
        self.detalhes_widget = QWidget()
        self.detalhes_widget.setVisible(False)
        self.layout.addWidget(self.detalhes_widget)


    def preparar_takes_visiveis(self):
        """
        Aplica os mesmos filtros da versão anterior, porém sem criar TakeRow.

        Isso é importante porque outras partes da tela podem consultar:
        - self.total_takes_visiveis
        - self.sem_takes_visiveis

        logo depois que o PautaCard é criado.
        """
        takes_filtrados = list(self.takes)

        if self.somente_comentados:
            takes_filtrados = [
                take for take in takes_filtrados
                if (take.get("comentario") or "").strip()
            ]

        if self.somente_favoritos:
            takes_filtrados = [
                take for take in takes_filtrados
                if int(take.get("favorito") or 0) == 1
            ]

        if self.palavra_chave:
            termo = self.palavra_chave

            takes_com_termo = [
                take for take in takes_filtrados
                if termo in (take.get("comentario") or "").lower()
                or termo in (take.get("nome_arquivo") or "").lower()
                or termo in (take.get("tags") or "").lower()
            ]

            # Mantém exatamente o comportamento anterior:
            # só substitui a lista quando algum take contém o termo.
            if takes_com_termo:
                takes_filtrados = takes_com_termo

        self.takes_visiveis = takes_filtrados
        self.total_takes_visiveis = len(takes_filtrados)
        self.sem_takes_visiveis = not bool(takes_filtrados)


    def criar_header(self):
        linha = QHBoxLayout()
        linha.setSpacing(12)

        info_widget = QWidget()
        info_widget.setObjectName("PautaInfoWidget")
        info_widget.setStyleSheet(
            "background: transparent; border: none;"
        )

        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(3)

        titulo = QLabel(self.pauta["nome_pauta"])
        titulo.setObjectName("PautaTitle")

        meta = QLabel(
            f"{self.pauta['data_pauta']} • "
            f"{self.pauta['candidato']}"
        )
        meta.setObjectName("PautaMeta")

        info_layout.addWidget(titulo)
        info_layout.addWidget(meta)

        self.btn_favorita_pauta = QPushButton(
            "⭐"
            if int(self.pauta.get("favorita") or 0) == 1
            else "☆"
        )
        self.btn_favorita_pauta.setObjectName(
            "PautaActionButton"
        )
        self.btn_favorita_pauta.setMaximumWidth(55)
        self.btn_favorita_pauta.clicked.connect(
            self.alternar_favorita_pauta
        )

        self.btn_editar = QPushButton("Editar")
        self.btn_editar.setObjectName(
            "PautaActionButton"
        )
        self.btn_editar.setMaximumWidth(100)
        self.btn_editar.clicked.connect(
            self.abrir_edicao
        )

        self.btn_excluir = QPushButton("Excluir")
        self.btn_excluir.setMaximumWidth(100)
        self.btn_excluir.setObjectName(
            "DeleteButton"
        )
        self.btn_excluir.clicked.connect(
            self.confirmar_exclusao
        )

        linha.addWidget(info_widget, stretch=1)
        linha.addWidget(self.btn_favorita_pauta)
        linha.addWidget(self.btn_editar)
        linha.addWidget(self.btn_excluir)

        self.layout.addLayout(linha)


    def criar_detalhes(self):
        """
        Só é chamado na primeira vez em que o usuário abre o card.

        É neste momento que TakeRow será criado e, consequentemente,
        gerar_thumbnail() e obter_info_video() poderão ser chamados.
        """
        if self.detalhes_criados:
            return

        detalhes_layout = QVBoxLayout(
            self.detalhes_widget
        )
        detalhes_layout.setContentsMargins(
            0, 8, 0, 0
        )
        detalhes_layout.setSpacing(10)

        descricao = QLabel(
            f"Descrição: "
            f"{self.pauta.get('descricao_inicial') or ''}"
        )
        descricao.setObjectName(
            "PautaDescription"
        )
        descricao.setWordWrap(True)

        caminho = QLabel(
            f"Pasta: "
            f"{self.pauta.get('caminho_pasta') or ''}"
        )
        caminho.setObjectName("PautaPath")
        caminho.setWordWrap(True)

        takes_label = QLabel("Takes")
        takes_label.setObjectName(
            "PautaSectionTitle"
        )

        detalhes_layout.addWidget(descricao)
        detalhes_layout.addWidget(caminho)
        detalhes_layout.addSpacing(4)
        detalhes_layout.addWidget(takes_label)

        if self.sem_takes_visiveis:
            vazio = QLabel(
                "Nenhum take encontrado com os filtros atuais."
            )
            vazio.setObjectName("EmptyText")
            detalhes_layout.addWidget(vazio)

        else:
            for take in self.takes_visiveis:
                take["_termo_busca"] = (
                    self.palavra_chave
                )

                row = TakeRow(
                    take,
                    self.media_loader,
                    self.media_generation
                )
                detalhes_layout.addWidget(row)

        self.detalhes_criados = True


    def alternar_favorita_pauta(self):
        favorita_atual = (
            int(self.pauta.get("favorita") or 0) == 1
        )
        nova_favorita = not favorita_atual

        alternar_favorito_pauta(
            self.pauta["id"],
            nova_favorita
        )

        self.pauta["favorita"] = (
            1 if nova_favorita else 0
        )

        self.btn_favorita_pauta.setText(
            "⭐" if nova_favorita else "☆"
        )


    def alternar_expandir(self):
        vai_expandir = not self.expandido

        # Só cria os TakeRow na primeira abertura.
        if (
            vai_expandir
            and not self.detalhes_criados
        ):
            self.criar_detalhes()

        self.expandido = vai_expandir
        self.detalhes_widget.setVisible(
            self.expandido
        )


    def mousePressEvent(self, event):
        # Mantém o comportamento atual:
        # clicar no card inteiro abre ou fecha os detalhes.
        if event.button() == Qt.LeftButton:
            self.alternar_expandir()


    def abrir_edicao(self):
        popup = EditPautaPopup(
            self.pauta,
            self.takes
        )

        if popup.exec():
            QMessageBox.information(
                self,
                "Atualizado",
                "Pauta atualizada com sucesso. "
                "Faça a busca novamente para ver "
                "os dados atualizados."
            )


    def confirmar_exclusao(self):
        resposta = QMessageBox.question(
            self,
            "Excluir pauta",
            "Tem certeza que deseja remover da "
            "visualização a pauta:"
            f"\n\n{self.pauta['nome_pauta']}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if resposta != QMessageBox.Yes:
            return

        excluir_pauta(
            self.pauta["id"]
        )

        self.setParent(None)
        self.deleteLater()


class TakeRow(QFrame):
    def __init__(self, take, media_loader, media_generation):
        super().__init__()

        self.take = take
        self.media_loader = media_loader
        self.media_generation = media_generation
        self.media_solicitada = False

        self.setObjectName("TakeRow")
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(16)

        # ====================================================
        # THUMBNAIL
        # ====================================================

        self.thumb_label = QLabel(
            "Carregando..."
        )
        self.thumb_label.setFixedSize(
            190,
            107
        )
        self.thumb_label.setAlignment(
            Qt.AlignCenter
        )
        self.thumb_label.setStyleSheet("""
            QLabel {
                background-color: #0B0F17;
                border: 1px solid #263244;
                border-radius: 12px;
                color: #64748B;
                font-size: 13px;
            }
        """)

        # ====================================================
        # INFORMAÇÕES DO TAKE
        # ====================================================

        info_widget = QWidget()

        info_layout = QVBoxLayout(
            info_widget
        )
        info_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )
        info_layout.setSpacing(7)

        nome = QLabel(
            take["nome_arquivo"]
        )
        nome.setWordWrap(True)
        nome.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: 700;
                color: #F8FAFC;
            }
        """)

        self.detalhes_video = QLabel(
            "⏱ Carregando informações..."
        )
        self.detalhes_video.setStyleSheet("""
            QLabel {
                color: #94A3B8;
                font-size: 13px;
                font-weight: 500;
            }
        """)

        status_take = (
            take.get("status_take")
            or "talvez"
        )

        status_map = {
            "usar": (
                "USAR",
                "#15803D"
            ),
            "talvez": (
                "TALVEZ",
                "#A16207"
            ),
            "ignorar": (
                "IGNORAR",
                "#B91C1C"
            ),
        }

        status_texto, status_cor = status_map.get(
            status_take,
            status_map["talvez"]
        )

        status_label = QLabel(
            status_texto
        )
        status_label.setFixedWidth(82)
        status_label.setAlignment(
            Qt.AlignCenter
        )
        status_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                background-color: {status_cor};
                border-radius: 999px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }}
        """)

        comentario_texto = (
            take.get("comentario")
            or ""
        )

        comentario = QLabel(
            self.destacar_termo(
                comentario_texto
            )
        )
        comentario.setWordWrap(True)
        comentario.setTextFormat(
            Qt.RichText
        )
        comentario.setStyleSheet("""
            QLabel {
                color: #CBD5E1;
                font-size: 14px;
                line-height: 1.4;
            }
        """)

        tags_texto = (
            take.get("tags")
            or ""
        )

        info_layout.addWidget(nome)
        info_layout.addWidget(
            self.detalhes_video
        )
        info_layout.addWidget(
            status_label
        )
        info_layout.addWidget(
            comentario
        )

        if tags_texto:
            tags_label = QLabel(
                "  ".join(
                    f"#{tag.strip()}"
                    for tag in tags_texto.split(",")
                    if tag.strip()
                )
            )

            tags_label.setWordWrap(True)
            tags_label.setStyleSheet("""
                QLabel {
                    color: #60A5FA;
                    font-size: 13px;
                    font-weight: 600;
                }
            """)

            info_layout.addWidget(
                tags_label
            )

        info_layout.addStretch()

        # ====================================================
        # BOTÕES
        # ====================================================

        botoes_widget = QWidget()

        botoes_layout = QVBoxLayout(
            botoes_widget
        )
        botoes_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )
        botoes_layout.setSpacing(8)

        self.btn_favorito = QPushButton(
            "⭐ Favorito"
            if int(take.get("favorito") or 0) == 1
            else "☆ Favoritar"
        )
        self.btn_favorito.setObjectName(
            "SmallButton"
        )
        self.btn_favorito.clicked.connect(
            self.alternar_favorito
        )

        btn_abrir_arquivo = QPushButton(
            "Abrir"
        )
        btn_abrir_arquivo.setObjectName(
            "SmallButton"
        )
        btn_abrir_arquivo.clicked.connect(
            self.abrir_arquivo
        )

        btn_copiar = QPushButton(
            "Copiar"
        )
        btn_copiar.setObjectName(
            "SmallButton"
        )
        btn_copiar.clicked.connect(
            self.copiar_caminho
        )

        btn_abrir = QPushButton(
            "Pasta"
        )
        btn_abrir.setObjectName(
            "SmallButton"
        )
        btn_abrir.clicked.connect(
            self.abrir_pasta
        )

        botoes_layout.addWidget(
            self.btn_favorito
        )
        botoes_layout.addWidget(
            btn_abrir_arquivo
        )
        botoes_layout.addWidget(
            btn_copiar
        )
        botoes_layout.addWidget(
            btn_abrir
        )
        botoes_layout.addStretch()

        layout.addWidget(
            self.thumb_label
        )
        layout.addWidget(
            info_widget,
            stretch=1
        )
        layout.addWidget(
            botoes_widget
        )

        self.mousePressEvent = (
            self.abrir_popup
        )

        # A mídia só é solicitada quando a linha realmente for pintada.


    def iniciar_carregamento_midia(self):
        if self.media_solicitada or self.media_loader is None:
            return

        self.media_solicitada = True
        caminho = self.take.get(
            "caminho_arquivo",
            ""
        )

        self.media_loader.solicitar(
            caminho,
            self,
            self.media_generation
        )


    def paintEvent(self, event):
        self.iniciar_carregamento_midia()
        super().paintEvent(event)


    @Slot(object, object)
    def aplicar_midia(
        self,
        pixmap,
        info_video
    ):
        if pixmap is not None:
            if not pixmap.isNull():
                self.thumb_label.setText("")
                self.thumb_label.setPixmap(pixmap)
            else:
                self.mostrar_sem_thumbnail()
        else:
            self.mostrar_sem_thumbnail()

        if info_video:
            self.detalhes_video.setText(
                f"⏱ {info_video['duracao']}  •  "
                f"{info_video['fps']} fps  •  "
                f"{info_video['resolucao']}"
            )
        else:
            self.detalhes_video.setText(
                "⏱ Duração indisponível"
            )

    @Slot(str)
    def aplicar_erro_midia(
        self,
        mensagem
    ):
        self.mostrar_sem_thumbnail()

        self.detalhes_video.setText(
            "⏱ Informações indisponíveis"
        )

    def mostrar_sem_thumbnail(self):
        self.thumb_label.clear()
        self.thumb_label.setText(
            "Sem thumbnail"
        )
        self.thumb_label.setAlignment(
            Qt.AlignCenter
        )


    def alternar_favorito(self):
        favorito_atual = (
            int(
                self.take.get("favorito")
                or 0
            ) == 1
        )

        novo_favorito = (
            not favorito_atual
        )

        alternar_favorito_take(
            self.take["id"],
            novo_favorito
        )

        self.take["favorito"] = (
            1 if novo_favorito else 0
        )

        self.btn_favorito.setText(
            "⭐ Favorito"
            if novo_favorito
            else "☆ Favoritar"
        )


    def copiar_caminho(self):
        clipboard = (
            QGuiApplication.clipboard()
        )

        clipboard.setText(
            self.take["caminho_arquivo"]
        )


    def abrir_pasta(self):
        caminho = self.take[
            "caminho_arquivo"
        ]

        if os.path.exists(caminho):
            os.startfile(
                os.path.dirname(caminho)
            )
        else:
            QMessageBox.warning(
                self,
                "Arquivo não encontrado",
                "O caminho deste arquivo "
                "não existe mais."
            )


    def abrir_popup(self, event):
        popup = TakePopup(
            self.take
        )
        popup.exec()


    def destacar_termo(
        self,
        texto
    ):
        termo = self.take.get(
            "_termo_busca",
            ""
        ).strip()

        if not termo:
            return html.escape(
                texto
            )

        texto_seguro = html.escape(
            texto
        )
        termo_seguro = html.escape(
            termo
        )

        padrao = re.compile(
            re.escape(
                termo_seguro
            ),
            re.IGNORECASE
        )

        return padrao.sub(
            lambda m: (
                "<span style='"
                "background-color:#FACC15; "
                "color:#0B0F17; "
                "padding:2px 4px; "
                "border-radius:4px; "
                "font-weight:700;'>"
                f"{m.group(0)}"
                "</span>"
            ),
            texto_seguro
        )


    def abrir_arquivo(self):
        caminho = self.take[
            "caminho_arquivo"
        ]

        if os.path.exists(caminho):
            os.startfile(
                caminho
            )
        else:
            QMessageBox.warning(
                self,
                "Arquivo não encontrado",
                "O caminho deste arquivo "
                "não existe mais."
            )


class TakePopup(QDialog):
    def __init__(self, take):
        super().__init__()

        self.take = take

        self.setWindowTitle(take["nome_arquivo"])
        self.resize(700, 400)

        layout = QVBoxLayout(self)

        nome = QLabel(take["nome_arquivo"])
        nome.setStyleSheet("font-size: 22px; font-weight: bold;")

        comentario = QTextEdit()
        comentario.setReadOnly(True)
        comentario.setText(take.get("comentario") or "")
        tags = QLineEdit()
        tags.setText(take.get("tags") or "")
        tags.setPlaceholderText("Tags. Ex: agro, saúde, abraço")

        caminho = QLabel(take["caminho_arquivo"])
        caminho.setWordWrap(True)

        botoes = QHBoxLayout()

        btn_copiar = QPushButton("Copiar caminho")
        btn_copiar.clicked.connect(self.copiar_caminho)

        btn_abrir = QPushButton("Abrir pasta")
        btn_abrir.clicked.connect(self.abrir_pasta)

        botoes.addWidget(btn_copiar)
        botoes.addWidget(btn_abrir)

        layout.addWidget(nome)
        layout.addWidget(QLabel("Comentário completo:"))
        layout.addWidget(comentario)
        layout.addWidget(QLabel("Caminho completo:"))
        layout.addWidget(caminho)
        layout.addLayout(botoes)
        
        self.setStyleSheet(GLOBAL_STYLE)

    def copiar_caminho(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.take["caminho_arquivo"])

    def abrir_pasta(self):
        caminho = self.take["caminho_arquivo"]

        if os.path.exists(caminho):
            os.startfile(os.path.dirname(caminho))
        else:
            QMessageBox.warning(self, "Arquivo não encontrado", "O caminho deste arquivo não existe mais.")






class EditPautaPopup(QDialog):
    def __init__(self, pauta, takes):
        super().__init__()

        self.pauta = pauta
        self.takes = takes
        self.take_widgets = []

        self.setWindowTitle("Editar pauta")
        self.resize(1150, 720)

        layout = QVBoxLayout(self)

        titulo = QLabel("Editar pauta")
        titulo.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.input_nome = QLineEdit()
        self.input_nome.setText(pauta.get("nome_pauta") or "")

        self.input_data = QLineEdit()
        self.input_data.setText(pauta.get("data_pauta") or "")

        self.combo_candidato = QComboBox()
        self.combo_candidato.addItems(CANDIDATOS)

        candidato_atual = pauta.get("candidato") or ""
        index = self.combo_candidato.findText(candidato_atual)
        if index >= 0:
            self.combo_candidato.setCurrentIndex(index)

        self.input_descricao = QTextEdit()
        self.input_descricao.setText(pauta.get("descricao_inicial") or "")
        self.input_descricao.setMaximumHeight(90)

        layout.addWidget(titulo)

        layout.addWidget(QLabel("Nome da pauta"))
        layout.addWidget(self.input_nome)

        layout.addWidget(QLabel("Data da pauta"))
        layout.addWidget(self.input_data)

        layout.addWidget(QLabel("Candidato"))
        layout.addWidget(self.combo_candidato)

        layout.addWidget(QLabel("Descrição"))
        layout.addWidget(self.input_descricao)

        layout.addWidget(QLabel("Takes"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        for take in takes:
            row = QFrame()
            row.setObjectName("TakeRow")

            row_layout = QHBoxLayout(row)

            nome = QLabel(take["nome_arquivo"])
            nome.setMinimumWidth(180)

            comentario = QLineEdit()
            comentario.setText(take.get("comentario") or "")
            comentario.setPlaceholderText("Comentário do take")

            tags = QLineEdit()
            tags.setText(take.get("tags") or "")
            tags.setPlaceholderText("Tags. Ex: agro, saúde, abraço")

            importante = QCheckBox("Importante")
            importante.setChecked(bool(take.get("marcado_como_importante")))

            status = QComboBox()
            status.addItems(["usar", "talvez", "ignorar"])

            status_atual = take.get("status_take") or "talvez"
            index_status = status.findText(status_atual)
            if index_status >= 0:
                status.setCurrentIndex(index_status)

            row_layout.addWidget(nome)
            row_layout.addWidget(comentario, stretch=2)
            row_layout.addWidget(tags, stretch=1)
            row_layout.addWidget(importante)
            row_layout.addWidget(status)

            scroll_layout.addWidget(row)

            self.take_widgets.append({
                "id": take["id"],
                "comentario_widget": comentario,
                "tags_widget": tags,
                "importante_widget": importante,
                "status_widget": status
            })

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)

        layout.addWidget(scroll)

        btn_salvar = QPushButton("Salvar alterações")
        btn_salvar.clicked.connect(self.salvar_alteracoes)

        layout.addWidget(btn_salvar)

        self.setStyleSheet(GLOBAL_STYLE)

    def salvar_alteracoes(self):
        nome = self.input_nome.text().strip()
        data = self.input_data.text().strip()
        candidato = self.combo_candidato.currentText()
        descricao = self.input_descricao.toPlainText().strip()

        if not nome:
            QMessageBox.warning(self, "Atenção", "Preencha o nome da pauta.")
            return

        takes_atualizados = []

        for item in self.take_widgets:
            takes_atualizados.append({
                "id": item["id"],
                "comentario": item["comentario_widget"].text().strip(),
                "tags": item["tags_widget"].text().strip(),
                "importante": item["importante_widget"].isChecked(),
                "status_take": item["status_widget"].currentText()
            })

        atualizar_pauta(
            pauta_id=self.pauta["id"],
            nome_pauta=nome,
            data_pauta=data,
            candidato=candidato,
            descricao=descricao,
            takes=takes_atualizados
        )

        self.accept()









