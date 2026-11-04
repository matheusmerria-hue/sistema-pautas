import logging, os, re, traceback
from PySide6.QtCore import Qt,Signal,QTimer
from PySide6.QtWidgets import (QApplication,QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QScrollArea,QLineEdit,QTextEdit,QComboBox,QCheckBox,QMenu,QSplitter,QFileDialog,QMessageBox)
from media_loader import MediaLoader
from ui.client_search import ClientSearchInput
from ui.ui_locate import open_locator
from exporter import exportar_json,exportar_csv,exportar_resultados_json,exportar_resultados_csv
from .components import txt,btn,rule,panel,Status,Thumb,MediaThumb,SelectableRow,Toast,Confirm
from . import backend
LOGGER=logging.getLogger(__name__)

def scroll(widget):
    a=QScrollArea(); a.setWidgetResizable(True); a.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); a.setWidget(widget); return a
def clear(layout):
    while layout.count():
        i=layout.takeAt(0); w=i.widget()
        if w:w.deleteLater()
        elif i.layout():clear(i.layout())
def header(kicker,title,action=None):
    w=QWidget(); r=QHBoxLayout(w); r.setContentsMargins(14,10,14,9); t=QVBoxLayout(); t.setSpacing(1); t.addWidget(txt(kicker,"Micro")); t.addWidget(txt(title,"Title")); r.addLayout(t); r.addStretch()
    if action:r.addWidget(action)
    return w
def report_error(parent,title,error):
    LOGGER.exception(title); traceback.print_exc(); QMessageBox.critical(parent,title,f"Não foi possível concluir a operação.\n\n{error}")

class Inspector(QWidget):
    edit_requested=Signal(int); deleted=Signal()
    def __init__(self):
        super().__init__(); self.setObjectName("Inspector"); self.setMinimumWidth(255); self.setMaximumWidth(330); self.l=QVBoxLayout(self); self.l.setContentsMargins(14,13,14,14); self.l.setSpacing(9); self.current=None; self.empty()
    def reset(self): clear(self.l)
    def empty(self):
        self.reset(); self.current=None; self.l.addWidget(txt("INSPECTOR","Micro")); self.l.addStretch(); self.l.addWidget(txt("Nenhuma seleção","Section"),alignment=Qt.AlignCenter); self.l.addWidget(txt("Selecione uma pauta ou take para ver detalhes.","Meta",True),alignment=Qt.AlignCenter); self.l.addStretch()
    def show_pauta(self,p):
        self.reset(); self.current=p; detail=backend.detail(p["id"]); takes=detail["takes"] if detail else []; self.l.addWidget(txt("INSPECTOR / PAUTA","Micro")); self.l.addWidget(txt(p["title"],"Section",True)); self.l.addWidget(Status(p["status"]),alignment=Qt.AlignLeft); self.l.addWidget(rule())
        for k,v in (("CLIENTE",p["owner"]),("DATA",p["date"]),("PASTA",p.get("caminho_pasta") or "—"),("ATUALIZAÇÃO",p.get("data_atualizacao") or "—")):
            self.l.addWidget(txt(k,"Micro")); self.l.addWidget(txt(str(v),"Item",True))
        self.l.addWidget(rule()); self.l.addWidget(txt(p["desc"],"Meta",True)); self.l.addWidget(txt(f"TAKES · {len(takes)}","Micro"))
        for take in takes[:4]:
            line=QHBoxLayout(); line.addWidget(Status(backend.TAKE_LABEL.get(take.get("status_take") or "talvez","TALVEZ"))); name=btn(take.get("nome_arquivo") or "—","flat","Copiar caminho"); name.setStyleSheet("text-align:left"); name.clicked.connect(lambda _,path=take.get("caminho_arquivo") or "":QApplication.clipboard().setText(path)); line.addWidget(name,1); self.l.addLayout(line)
        if len(takes)>4:self.l.addWidget(txt(f"+ {len(takes)-4} takes no workspace de edição","Meta"))
        if not os.path.isdir(p.get("caminho_pasta") or ""):
            locate=btn("Localizar","flat"); locate.clicked.connect(lambda:open_locator(self.window(),pauta_id=p["id"])); self.l.addWidget(locate)
        for take in takes:
            if not os.path.isfile(take.get("caminho_arquivo") or ""):
                locate=btn("Localizar · "+(take.get("nome_arquivo") or "arquivo"),"flat"); locate.clicked.connect(lambda _,tid=take["id"]:open_locator(self.window(),take_id=tid)); self.l.addWidget(locate)
                break
        self.l.addStretch(); edit=btn("Abrir workspace de edição","accent"); edit.clicked.connect(lambda:self.edit_requested.emit(p["id"])); self.l.addWidget(edit)
        row=QHBoxLayout(); fav=btn("★ Favorita" if p.get("favorita") else "☆ Favoritar","flat"); fav.clicked.connect(lambda:self.toggle_favorite(fav)); delete=btn("Excluir…","danger"); delete.clicked.connect(self.confirm_delete); row.addWidget(fav); row.addWidget(delete); self.l.addLayout(row)
    def toggle_favorite(self,b):
        try: new=not bool(self.current.get("favorita")); backend.favorite_pauta(self.current["id"],new); self.current["favorita"]=int(new); b.setText("★ Favorita" if new else "☆ Favoritar"); Toast(self.window(),"Favorito atualizado")
        except Exception as e: report_error(self,"Erro ao favoritar",e)
    def confirm_delete(self):
        d=Confirm(self,"Excluir pauta?",f'“{self.current["title"]}” será removida das listagens. O sistema utiliza exclusão segura.',True)
        if d.exec():
            try: backend.delete(self.current["id"]); self.empty(); self.deleted.emit(); Toast(self.window(),"Pauta excluída")
            except Exception as e: report_error(self,"Erro ao excluir",e)

class WorkCenter(QWidget):
    open_editor=Signal(int)
    def __init__(self,inspector):
        super().__init__(); self.inspector=inspector; root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0); self.new=btn("＋ Nova pauta","accent"); root.addWidget(header("CENTRAL DE TRABALHO","Acervo operacional",self.new)); self.summary=QFrame(); self.summary.setObjectName("Panel"); self.sum_layout=QHBoxLayout(self.summary); root.addWidget(self.summary)
        split=QSplitter(Qt.Horizontal); master=QWidget(); master.setObjectName("Master"); ml=QVBoxLayout(master); ml.setContentsMargins(9,8,0,0); self.find=QLineEdit(); self.find.setPlaceholderText("Filtrar trabalhos recentes…"); ml.addWidget(self.find); self.holder=QWidget(); self.rows_layout=QVBoxLayout(self.holder); self.rows_layout.setContentsMargins(0,0,0,0); self.rows_layout.setSpacing(0); ml.addWidget(scroll(self.holder),1); split.addWidget(master)
        focus=QWidget(); fl=QVBoxLayout(focus); fl.setContentsMargins(14,12,14,14); fl.addWidget(txt("FLUXO REAL","Micro")); fl.addWidget(txt("Status do acervo","Section")); self.status_layout=QVBoxLayout(); fl.addLayout(self.status_layout); fl.addStretch(); split.addWidget(focus); split.setSizes([650,300]); root.addWidget(split,1); self.find.textChanged.connect(self.filter); self.rows=[]
    def refresh(self):
        try:
            records=backend.search(); pautas=[x["pauta"] for x in records]; stats=backend.stats(); clear(self.sum_layout); self.sum_layout.setContentsMargins(14,9,14,9); self.sum_layout.addWidget(txt(f'{stats["total_pautas"]} PAUTAS',"Accent")); self.sum_layout.addWidget(txt(f'{stats["total_takes"]} takes · {stats["takes_comentados"]} comentados',"Meta")); self.sum_layout.addStretch(); self.sum_layout.addWidget(txt(f'{stats["pautas_ultimos_7_dias"]} criadas nos últimos 7 dias',"Meta")); export=btn("Exportar acervo","flat"); export.clicked.connect(self.export_all); self.sum_layout.addWidget(export); clear(self.rows_layout); self.rows=[]
            for i,item in enumerate(records):
                p=item["pauta"]; takes=item["takes"]; thumb=MediaThumb(takes[0].get("caminho_arquivo"),self.window().media_loader,self.window().media_generation) if takes else None
                r=SelectableRow(p,i,len(takes),thumb); r.clicked.connect(lambda d,x=r:self.pick(d,x)); self.rows_layout.addWidget(r); self.rows.append(r)
            self.rows_layout.addStretch(); self.holder.setMinimumHeight(max(1,len(self.rows))*58); clear(self.status_layout)
            for value,label in (("a_editar","Triagem"),("em_producao","Em corte"),("finalizada","Finalizadas")):
                n=sum((p.get("status_pauta") or "a_editar")==value for p in pautas); q=QHBoxLayout(); q.addWidget(Status(backend.STATUS_LABEL[value])); q.addWidget(txt(label,"Item")); q.addStretch(); q.addWidget(txt(str(n),"Accent")); self.status_layout.addLayout(q)
        except Exception as e: report_error(self,"Erro ao carregar a Home",e)
    def pick(self,d,row):
        for r in self.rows:r.select(r is row)
        self.inspector.show_pauta(d)
    def filter(self,q):
        for r in self.rows:r.setVisible(q.lower() in (r.data["title"]+r.data["owner"]+r.data["desc"]).lower())
    def export_all(self):
        path,selected=QFileDialog.getSaveFileName(self,"Exportar banco de dados","backup_pautas","JSON (*.json);;CSV (*.csv)")
        if not path:return
        try:
            if selected.startswith("CSV") or path.lower().endswith(".csv"): exportar_csv(path if path.lower().endswith(".csv") else path+".csv")
            else: exportar_json(path if path.lower().endswith(".json") else path+".json")
            Toast(self.window(),"Acervo exportado com sucesso")
        except Exception as e: report_error(self,"Erro ao exportar",e)

class SearchWorkspace(QWidget):
    open_editor=Signal(int)
    def __init__(self,inspector):
        super().__init__(); self.inspector=inspector; root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0); root.addWidget(header("ACERVO","Pesquisa e recuperação de mídia")); filters=QWidget(); grid=QGridLayout(filters); grid.setContentsMargins(12,4,12,8); self.q=QLineEdit(); self.q.setPlaceholderText("Pesquisar pautas, falas, tags ou arquivos…"); self.owner=ClientSearchInput(); self.owner.setPlaceholderText("Digite o nome do cliente"); self.owner.setAccessibleName("Cliente"); self.owner.setToolTip("Cliente"); self.date_from=QLineEdit(); self.date_from.setPlaceholderText("Data inicial"); self.date_to=QLineEdit(); self.date_to.setPlaceholderText("Data final"); self.commented=QCheckBox("Somente comentados"); self.fav_takes=QCheckBox("Takes favoritos"); self.fav_pautas=QCheckBox("Pautas favoritas"); self.search_btn=btn("Pesquisar","accent"); self.clear_btn=btn("Limpar","flat"); grid.addWidget(self.q,0,0,1,3); client_box=QWidget(); client_layout=QVBoxLayout(client_box); client_layout.setContentsMargins(0,0,0,0); client_layout.addWidget(txt("Cliente","Micro")); client_layout.addWidget(self.owner); grid.addWidget(client_box,0,3); grid.addWidget(self.search_btn,0,4); grid.addWidget(self.date_from,1,0); grid.addWidget(self.date_to,1,1); grid.addWidget(self.commented,1,2); grid.addWidget(self.fav_takes,1,3); grid.addWidget(self.fav_pautas,1,4); root.addWidget(filters)
        info=QHBoxLayout(); info.setContentsMargins(12,4,12,5); self.count=txt("Carregando…","Meta"); info.addWidget(self.count); info.addStretch(); self.export_btn=btn("Exportar resultados","flat"); self.export_btn.setEnabled(False); self.export_btn.clicked.connect(self.export_results); info.addWidget(self.export_btn); info.addWidget(self.clear_btn); self.locate_btn=btn("Localizar arquivos perdidos","flat"); self.locate_btn.clicked.connect(lambda:open_locator(self.window())); info.addWidget(self.locate_btn); iw=QWidget(); iw.setLayout(info); root.addWidget(iw); self.history_box=QComboBox(); self.history_box.setToolTip("Restaurar busca e filtros"); self.history_box.activated.connect(self.restore_history); root.addWidget(self.history_box); self.load_history(); self.holder=QWidget(); self.rows_layout=QVBoxLayout(self.holder); self.rows_layout.setContentsMargins(0,0,0,0); self.rows_layout.setSpacing(0); root.addWidget(scroll(self.holder),1); self.rows=[]; self.results_export=[]; self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(350); self.timer.timeout.connect(lambda:self.refresh(False)); self.q.textChanged.connect(self.timer.start); self.owner.textChanged.connect(self.timer.start); self.commented.stateChanged.connect(lambda:self.refresh(False)); self.fav_takes.stateChanged.connect(lambda:self.refresh(False)); self.fav_pautas.stateChanged.connect(lambda:self.refresh(False)); self.date_from.editingFinished.connect(lambda:self.refresh(False)); self.date_to.editingFinished.connect(lambda:self.refresh(False)); self.search_btn.clicked.connect(lambda:self.refresh(True)); self.clear_btn.clicked.connect(self.clear_filters)
    def refresh(self,save_history=False):
        try:
            term=self.q.text().strip()
            if save_history:
                backend.save_search(term,cliente=self.owner.text().strip(),data_inicial=self.date_from.text().strip(),data_final=self.date_to.text().strip(),somente_pautas_favoritas=self.fav_pautas.isChecked(),somente_comentados=self.commented.isChecked(),somente_favoritos=self.fav_takes.isChecked()); self.load_history()
            results=backend.search(term,self.date_from.text().strip(),self.date_to.text().strip(),self.owner.text().strip(),self.fav_pautas.isChecked()); clear(self.rows_layout); self.rows=[]; self.results_export=[]; pauta_count=take_count=0
            for i,item in enumerate(results):
                takes=item["takes"]
                if self.commented.isChecked(): takes=[t for t in takes if (t.get("comentario") or "").strip()]
                if self.fav_takes.isChecked(): takes=[t for t in takes if int(t.get("favorito") or 0)==1]
                if (self.commented.isChecked() or self.fav_takes.isChecked()) and not takes: continue
                p=item["pauta"]; thumb=MediaThumb(takes[0].get("caminho_arquivo"),self.window().media_loader,self.window().media_generation) if takes else None; r=SelectableRow(p,i,len(takes),thumb); r.clicked.connect(lambda d,x=r:self.pick(d,x)); self.rows_layout.addWidget(r); self.rows.append(r); self.results_export.append({"pauta":p,"takes":takes}); pauta_count+=1; take_count+=len(takes)
            if not self.rows: self.rows_layout.addStretch(); self.rows_layout.addWidget(txt("Nenhum resultado com os filtros atuais.","Section"),alignment=Qt.AlignCenter); self.rows_layout.addWidget(txt("Limpe ou ajuste os filtros para continuar.","Meta"),alignment=Qt.AlignCenter)
            self.rows_layout.addStretch(); self.holder.setMinimumHeight(max(1,len(self.rows))*58); self.count.setText(f"{pauta_count} pautas · {take_count} takes"); self.export_btn.setEnabled(bool(self.results_export))
        except Exception as e: report_error(self,"Erro na pesquisa",e)
    def pick(self,d,row):
        for r in self.rows:r.select(r is row)
        self.inspector.show_pauta(d)
    def load_history(self):
        self.history_box.clear(); self.history_box.addItem("Últimas buscas", None)
        for entry in backend.history():
            label=" • ".join(filter(None,[entry["termo"],entry.get("cliente")])) or "Filtros"
            self.history_box.addItem(label,entry)
    def restore_history(self,index):
        entry=self.history_box.itemData(index)
        if not entry:return
        widgets=[self.q,self.owner,self.date_from,self.date_to,self.fav_pautas,self.commented,self.fav_takes]
        for w in widgets:w.blockSignals(True)
        try:
            self.q.setText(entry["termo"]); self.owner.setText(entry.get("cliente","")); self.date_from.setText(entry.get("data_inicial","")); self.date_to.setText(entry.get("data_final","")); self.fav_pautas.setChecked(entry.get("somente_pautas_favoritas",False)); self.commented.setChecked(entry.get("somente_comentados",False)); self.fav_takes.setChecked(entry.get("somente_favoritos",False))
        finally:
            for w in widgets:w.blockSignals(False)
        self.timer.stop(); self.refresh(False)
    def clear_filters(self):
        self.q.clear(); self.date_from.clear(); self.date_to.clear(); self.owner.clear(); self.commented.setChecked(False); self.fav_takes.setChecked(False); self.fav_pautas.setChecked(False); self.refresh(False)
    def export_results(self):
        path,selected=QFileDialog.getSaveFileName(self,"Exportar resultados","resultado_busca","JSON (*.json);;CSV (*.csv)")
        if not path:return
        try:
            if selected.startswith("CSV") or path.lower().endswith(".csv"): exportar_resultados_csv(path if path.lower().endswith(".csv") else path+".csv",self.results_export)
            else: exportar_resultados_json(path if path.lower().endswith(".json") else path+".json",self.results_export)
            Toast(self.window(),"Resultados exportados")
        except Exception as e: report_error(self,"Erro ao exportar",e)

class TakeEditorRow(QFrame):
    def __init__(self,take,loader,generation,new=False):
        super().__init__(); self.setMinimumHeight(58); self.take=take; self.setObjectName("Row"); self.new=new; r=QHBoxLayout(self); r.setContentsMargins(8,6,8,6); r.addWidget(MediaThumb(take.get("caminho_arquivo"),loader,generation)); v=QVBoxLayout(); v.addWidget(txt(take.get("nome_arquivo") or "—","Item")); self.comment=QLineEdit(take.get("comentario") or ""); self.comment.setPlaceholderText("Comentário"); v.addWidget(self.comment); r.addLayout(v,2); self.tags=QLineEdit(take.get("tags") or ""); self.tags.setPlaceholderText("Tags"); r.addWidget(self.tags,1); self.important=QCheckBox("Importante"); self.important.setChecked(bool(take.get("marcado_como_importante"))); r.addWidget(self.important); self.favorite=QCheckBox("★"); self.favorite.setToolTip("Take favorito"); self.favorite.setChecked(bool(take.get("favorito"))); self.favorite.setEnabled(not new); r.addWidget(self.favorite); self.status=QComboBox(); self.status.addItems(["usar","talvez","ignorar"]); self.status.setCurrentText(take.get("status_take") or "talvez"); self.status.setEnabled(not new); r.addWidget(self.status); more=btn("•••","flat","Ações do arquivo"); menu=QMenu(more); menu.addAction("Abrir arquivo",self.open_file); menu.addAction("Abrir pasta",self.open_folder); menu.addAction("Copiar caminho",lambda:QApplication.clipboard().setText(take.get("caminho_arquivo") or "")); more.clicked.connect(lambda:menu.exec(more.mapToGlobal(more.rect().bottomLeft()))); r.addWidget(more)
        if not os.path.isfile(take.get("caminho_arquivo") or ""):
            locate=btn("Localizar","flat"); locate.clicked.connect(lambda:open_locator(self.window(),take_id=take.get("id"))); locate.setEnabled(bool(take.get("id"))); r.addWidget(locate)
        self.setFixedHeight(58)
    def payload(self): return {"id":self.take.get("id"),"nome_arquivo":self.take.get("nome_arquivo"),"caminho_arquivo":self.take.get("caminho_arquivo"),"comentario":self.comment.text().strip(),"tags":self.tags.text().strip(),"importante":self.important.isChecked(),"status_take":self.status.currentText()}
    def open_file(self):
        path=self.take.get("caminho_arquivo") or ""
        if os.path.isfile(path):os.startfile(path)
        else:QMessageBox.warning(self,"Arquivo não encontrado",path)
    def open_folder(self):
        path=self.take.get("caminho_arquivo") or ""
        if os.path.isfile(path):os.startfile(os.path.dirname(path))
        else:QMessageBox.warning(self,"Arquivo não encontrado",path)

class EditorWorkspace(QWidget):
    saved=Signal()
    def __init__(self):
        super().__init__(); self.pauta_id=None; self.folder=""; self.take_rows=[]; root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0); self.save_btn=btn("Salvar pauta   Ctrl S","accent"); self.save_btn.clicked.connect(self.save); self.title_header=header("PAUTA / NOVA","Nova pauta",self.save_btn); root.addWidget(self.title_header); split=QSplitter(Qt.Horizontal); canvas=QWidget(); cl=QVBoxLayout(canvas); cl.setContentsMargins(12,10,12,10); self.name=QLineEdit(); self.name.setPlaceholderText("Nome da pauta"); self.name.setStyleSheet("font-size:18px;font-weight:700"); cl.addWidget(self.name); self.desc=QTextEdit(); self.desc.setPlaceholderText("Descrição inicial"); self.desc.setMaximumHeight(60); cl.addWidget(self.desc); bar=QHBoxLayout(); self.total=txt("Nenhuma mídia selecionada","Micro"); bar.addWidget(self.total); bar.addStretch(); self.folder_btn=btn("Selecionar pasta"); self.folder_btn.clicked.connect(self.select_folder); bar.addWidget(self.folder_btn); cl.addLayout(bar); self.take_holder=QWidget(); self.take_layout=QVBoxLayout(self.take_holder); self.take_layout.setContentsMargins(0,0,0,0); self.take_layout.setSpacing(0); cl.addWidget(scroll(self.take_holder),1); split.addWidget(canvas)
        meta=QWidget(); meta.setObjectName("Master"); ml=QVBoxLayout(meta); ml.setContentsMargins(13,12,13,12); ml.addWidget(txt("PROPRIEDADES OBRIGATÓRIAS","Micro")); ml.addWidget(txt("CLIENTE","Micro")); self.owner=QLineEdit(); self.owner.setPlaceholderText("Digite o nome do cliente"); ml.addWidget(self.owner); ml.addWidget(txt("DATA","Micro")); self.date=QLineEdit(); self.date.setPlaceholderText("DD/MM/AAAA"); ml.addWidget(self.date); ml.addWidget(txt("PASTA DOS BRUTOS","Micro")); self.folder_display=QLineEdit(); self.folder_display.setReadOnly(True); ml.addWidget(self.folder_display); ml.addWidget(txt("STATUS DA PAUTA","Micro")); self.pauta_status=QComboBox(); self.pauta_status.addItems(["TRIAGEM","CORTE","PRONTO"]); ml.addWidget(self.pauta_status); ml.addStretch(); self.cancel=btn("Cancelar alterações","flat"); self.cancel.clicked.connect(self.new); ml.addWidget(self.cancel); split.addWidget(meta); split.setSizes([760,280]); root.addWidget(split,1); self.new()
    def new(self): self.pauta_id=None; self.folder=""; self.name.clear(); self.date.clear(); self.desc.clear(); self.folder_display.clear(); self.owner.clear(); self.pauta_status.setCurrentText("TRIAGEM"); self.set_takes([],True); self.save_btn.setText("Criar pauta   Ctrl S")
    def load(self,pauta_id):
        try:
            data=backend.detail(pauta_id)
            if not data: raise ValueError("Pauta não encontrada")
            p=data["pauta"]; self.pauta_id=pauta_id; self.folder=p.get("caminho_pasta") or ""; self.name.setText(p.get("nome_pauta") or ""); self.date.setText(p.get("data_pauta") or ""); self.desc.setPlainText(p.get("descricao_inicial") or ""); self.folder_display.setText(self.folder); self.owner.setText(p.get("cliente") or ""); self.pauta_status.setCurrentText(p["status"]); self.set_takes(data["takes"],False); self.save_btn.setText("Salvar alterações   Ctrl S")
        except Exception as e: report_error(self,"Erro ao abrir pauta",e)
    def select_folder(self):
        folder=QFileDialog.getExistingDirectory(self,"Selecionar pasta dos arquivos")
        if not folder:return
        try:
            self.folder=folder; self.folder_display.setText(folder); files=backend.scan(folder); self.set_takes(files,True); self.autofill(folder)
        except Exception as e: report_error(self,"Erro ao ler pasta",e)
    def autofill(self,folder):
        match=re.search(r"(\d{4})-(\d{2})-(\d{2})\s*-\s*([^/\\]+)",folder)
        if match:
            y,m,d,n=match.groups()
            if not self.name.text():self.name.setText(n.strip())
            if not self.date.text():self.date.setText(f"{d}/{m}/{y}")
        desc_path=os.path.join(folder,"desc.txt")
        if os.path.isfile(desc_path) and not self.desc.toPlainText():
            for enc in ("utf-8","latin-1"):
                try:
                    with open(desc_path,"r",encoding=enc) as f:self.desc.setPlainText(f.read().strip())
                    break
                except UnicodeDecodeError:continue
    def set_takes(self,takes,new):
        clear(self.take_layout); self.take_rows=[]; self.window().media_generation=self.window().media_loader.nova_geracao() if self.window()!=self else 0
        for t in takes:
            r=TakeEditorRow(t,self.window().media_loader,self.window().media_generation,new); self.take_layout.addWidget(r); self.take_rows.append(r)
        self.take_layout.addStretch(); self.take_holder.setMinimumHeight(max(1,len(takes))*58); self.total.setText(f"{len(takes)} arquivos")
    def save(self):
        name=self.name.text().strip()
        if not self.owner.text().strip(): QMessageBox.warning(self,"Campo obrigatório","Informe o nome do cliente."); return
        if not name: QMessageBox.warning(self,"Campo obrigatório","Informe o nome da pauta."); return
        if not self.pauta_id and not self.folder: QMessageBox.warning(self,"Campo obrigatório","Selecione a pasta dos arquivos."); return
        try:
            takes=[r.payload() for r in self.take_rows]
            if self.pauta_id:
                backend.update(pauta_id=self.pauta_id,nome_pauta=name,data_pauta=self.date.text().strip(),cliente=self.owner.text().strip(),descricao=self.desc.toPlainText().strip(),takes=takes); backend.set_status(self.pauta_id,self.pauta_status.currentText());
                for row in self.take_rows: backend.favorite_take(row.take["id"],row.favorite.isChecked())
                message="Alterações salvas"
            else:
                backend.create(nome_pauta=name,data_pauta=self.date.text().strip(),cliente=self.owner.text().strip(),descricao=self.desc.toPlainText().strip(),caminho_pasta=self.folder,takes=takes); message="Pauta criada com sucesso"; self.new()
            self.saved.emit(); Toast(self.window(),message)
        except Exception as e: report_error(self,"Erro ao salvar",e)

class DesignLab(QWidget):
    def __init__(self):
        super().__init__(); content=QWidget(); content.setObjectName("Stage"); root=QVBoxLayout(content); root.addWidget(header("AMBIENTE DEMONSTRATIVO — SEM DADOS REAIS","Design Lab")); grid=QGridLayout(); a=panel(True); al=QVBoxLayout(a); al.addWidget(txt("AÇÕES E ESTADOS","Micro")); row=QHBoxLayout()
        for n,k in (("Principal","accent"),("Secundária",None),("Discreta","flat"),("Excluir","danger")):row.addWidget(btn(n,k))
        al.addLayout(row); field=QLineEdit(); field.setPlaceholderText("Campo demonstrativo"); al.addWidget(field); grid.addWidget(a,0,0,1,2); b=panel(True); bl=QVBoxLayout(b); bl.addWidget(txt("STATUS","Micro")); r=QHBoxLayout(); [r.addWidget(Status(x)) for x in ("ENTRADA","TRIAGEM","CORTE","PRONTO","USAR","IGNORAR")]; bl.addLayout(r); grid.addWidget(b,1,0); c=panel(True); cl=QVBoxLayout(c); cl.addWidget(txt("ESTADO VAZIO","Micro")); cl.addStretch(); cl.addWidget(txt("Nenhum item selecionado","Section"),alignment=Qt.AlignCenter); cl.addWidget(txt("Conteúdo exclusivamente demonstrativo.","Meta"),alignment=Qt.AlignCenter); cl.addStretch(); grid.addWidget(c,1,1); root.addLayout(grid); host=QVBoxLayout(self); host.setContentsMargins(0,0,0,0); host.addWidget(scroll(content))
