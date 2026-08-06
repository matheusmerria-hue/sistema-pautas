from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFileDialog, QComboBox,
    QScrollArea, QFrame, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt

from config import CANDIDATOS
from file_scanner import listar_arquivos_midia
from database import salvar_pauta
from theme import GLOBAL_STYLE
import os
import re



class CreatePautaWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Criar pauta")
        self.resize(1100, 750)

        self.caminho_pasta = ""
        self.take_widgets = []

        self.main_layout = QVBoxLayout(self)

        self.criar_cabecalho()
        self.criar_formulario()
        self.criar_area_arquivos()
        self.criar_botao_salvar()

        self.aplicar_estilo()

    def criar_cabecalho(self):
        title = QLabel("Criar pauta")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: bold;")

        subtitle = QLabel("Cadastre a pauta e comente apenas os takes importantes.")
        subtitle.setAlignment(Qt.AlignCenter)

        self.main_layout.addWidget(title)
        self.main_layout.addWidget(subtitle)

    def criar_formulario(self):
        form_box = QFrame()
        form_box.setObjectName("Card")

        layout = QVBoxLayout(form_box)

        self.input_nome = QLineEdit()
        self.input_nome.setPlaceholderText("Nome da pauta")

        self.input_data = QLineEdit()
        self.input_data.setPlaceholderText("Data da pauta. Ex: 22/06/2026")

        self.combo_candidato = QComboBox()
        self.combo_candidato.addItems(CANDIDATOS)

        self.input_descricao = QTextEdit()
        self.input_descricao.setPlaceholderText("Descrição inicial da pauta. Aproximadamente 150 caracteres.")
        self.input_descricao.setMaximumHeight(90)

        pasta_layout = QHBoxLayout()

        self.input_pasta = QLineEdit()
        self.input_pasta.setPlaceholderText("Nenhuma pasta selecionada")
        self.input_pasta.setReadOnly(True)

        btn_pasta = QPushButton("Selecionar pasta")
        btn_pasta.clicked.connect(self.selecionar_pasta)

        pasta_layout.addWidget(self.input_pasta)
        pasta_layout.addWidget(btn_pasta)

        layout.addWidget(QLabel("Nome da pauta"))
        layout.addWidget(self.input_nome)

        layout.addWidget(QLabel("Data da pauta"))
        layout.addWidget(self.input_data)

        layout.addWidget(QLabel("Candidato"))
        layout.addWidget(self.combo_candidato)

        layout.addWidget(QLabel("Descrição inicial"))
        layout.addWidget(self.input_descricao)

        layout.addWidget(QLabel("Pasta dos arquivos brutos"))
        layout.addLayout(pasta_layout)

        self.main_layout.addWidget(form_box)

    def criar_area_arquivos(self):
        title = QLabel("Arquivos encontrados")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        self.label_total = QLabel("Nenhum arquivo carregado.")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)

        self.scroll_area.setWidget(self.scroll_content)

        self.main_layout.addWidget(title)
        self.main_layout.addWidget(self.label_total)
        self.main_layout.addWidget(self.scroll_area)

    def criar_botao_salvar(self):
        self.btn_salvar = QPushButton("Salvar pauta")
        self.btn_salvar.setMinimumHeight(55)
        self.btn_salvar.clicked.connect(self.salvar)

        self.main_layout.addWidget(self.btn_salvar)

    def selecionar_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar pasta dos arquivos")

        if not pasta:
            return

        self.caminho_pasta = pasta
        self.input_pasta.setText(pasta)

        self.preencher_campos_pela_pasta(pasta)

        arquivos = listar_arquivos_midia(pasta)
        self.carregar_arquivos(arquivos)

    def carregar_arquivos(self, arquivos):
        self.take_widgets.clear()

        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        self.label_total.setText(f"{len(arquivos)} arquivo(s) encontrado(s).")

        for arquivo in arquivos:
            row = QFrame()
            row.setObjectName("TakeRow")

            layout = QHBoxLayout(row)

            nome = QLabel(arquivo["nome_arquivo"])
            nome.setMinimumWidth(220)

            comentario = QLineEdit()
            comentario.setPlaceholderText("Comentário do take")
            tags = QLineEdit()
            tags.setPlaceholderText("Tags. Ex: agro, saúde, abraço")
            importante = QCheckBox("Importante")

            layout.addWidget(nome)
            layout.addWidget(comentario, stretch=1)
            layout.addWidget(tags, stretch=1)
            layout.addWidget(importante)
            

            self.scroll_layout.addWidget(row)

            self.take_widgets.append({
                "arquivo": arquivo,
                "comentario_widget": comentario,
                "tags_widget": tags,
                "importante_widget": importante
                
            })

        self.scroll_layout.addStretch()

    def salvar(self):
        nome = self.input_nome.text().strip()
        data = self.input_data.text().strip()
        candidato = self.combo_candidato.currentText()
        descricao = self.input_descricao.toPlainText().strip()

        if not nome:
            QMessageBox.warning(self, "Atenção", "Preencha o nome da pauta.")
            return

        if not self.caminho_pasta:
            QMessageBox.warning(self, "Atenção", "Selecione a pasta dos arquivos.")
            return

        takes = []

        for item in self.take_widgets:
            comentario = item["comentario_widget"].text().strip()
            tags = item["tags_widget"].text().strip()
            importante = item["importante_widget"].isChecked()

            takes.append({
                "nome_arquivo": item["arquivo"]["nome_arquivo"],
                "caminho_arquivo": item["arquivo"]["caminho_arquivo"],
                "comentario": comentario,
                "tags": tags,
                "importante": importante
            })

        salvar_pauta(
            nome_pauta=nome,
            data_pauta=data,
            candidato=candidato,
            descricao=descricao,
            caminho_pasta=self.caminho_pasta,
            takes=takes
        )

        QMessageBox.information(self, "Sucesso", "Pauta salva com sucesso!")

    def preencher_campos_pela_pasta(self, pasta):
        partes = pasta.replace("\\", "/").split("/")

        pasta_pauta = None

        for parte in reversed(partes):
            if re.match(r"^\d{4}-\d{2}-\d{2}\s*-\s*.+$", parte):
                pasta_pauta = parte
                break

        if pasta_pauta:
            padrao = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s*-\s*(.+)$", pasta_pauta)

            if padrao:
                ano, mes, dia, nome_pauta = padrao.groups()

                if not self.input_data.text().strip():
                    self.input_data.setText(f"{dia}/{mes}/{ano}")

                if not self.input_nome.text().strip():
                    self.input_nome.setText(nome_pauta.strip())

            indice = partes.index(pasta_pauta)
            caminho_base_pauta = "/".join(partes[:indice + 1])
        else:
            caminho_base_pauta = pasta

        caminho_desc = os.path.join(caminho_base_pauta, "desc.txt")

        if os.path.exists(caminho_desc):
            try:
                with open(caminho_desc, "r", encoding="utf-8") as arquivo:
                    descricao = arquivo.read().strip()
            except UnicodeDecodeError:
                with open(caminho_desc, "r", encoding="latin-1") as arquivo:
                    descricao = arquivo.read().strip()

            if descricao and not self.input_descricao.toPlainText().strip():
                self.input_descricao.setPlainText(descricao)

    def aplicar_estilo(self):
        self.setStyleSheet(GLOBAL_STYLE)
