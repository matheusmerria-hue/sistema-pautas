"""Janela não modal; identificação, varredura e transações fora da thread da UI."""
import json
import threading
from dataclasses import asdict
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QHeaderView)
from smart_locate import Locator, apply_updates, undo_batch, last_batch, invalidate_mappings
from user_config import MODO


class LocateWorker(QThread):
    progress = Signal(dict)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation
        self.cancel = threading.Event()

    def run(self):
        try: self.done.emit(self.operation(self.cancel, self.progress.emit))
        except Exception as error: self.failed.emit(str(error))


class LocateDialog(QDialog):
    updated = Signal()
    PAGE_SIZE = 200

    def __init__(self, parent=None, pauta_id=None, take_id=None):
        super().__init__(parent)
        self.setWindowTitle('Localizar arquivos perdidos')
        self.resize(1100,700)
        self.pauta_id=pauta_id; self.take_id=take_id
        self.worker=None; self.result=None; self.selections={}; self._rendering=False
        layout=QVBoxLayout(self)
        scope='um arquivo' if take_id is not None else ('uma pauta' if pauta_id is not None else 'todo o acervo')
        description=QLabel(f'Localizar em {scope}. Escolha uma pasta ou unidade. Os arquivos físicos não serão modificados.')
        description.setWordWrap(True); layout.addWidget(description)
        row=QHBoxLayout(); self.root=QLineEdit(); self.root.setPlaceholderText('Unidade ou pasta raiz para pesquisa')
        self.browse=QPushButton('Escolher pasta…'); self.browse.clicked.connect(self.choose_root)
        self.start=QPushButton('Iniciar localização'); self.start.clicked.connect(self.scan)
        row.addWidget(self.root,1); row.addWidget(self.browse); row.addWidget(self.start); layout.addLayout(row)
        concurrency=QHBoxLayout(); concurrency.addWidget(QLabel('Verificações simultâneas:'))
        self.workers=QSpinBox(); self.workers.setRange(1,2); self.workers.setValue(1)
        self.workers.setToolTip('1 recomendado para HDD. 2 opcional para testar em SSD; a varredura de diretórios permanece sequencial.')
        concurrency.addWidget(self.workers); concurrency.addWidget(QLabel('1 recomendado para HDD; 2 opcional para SSD.')); concurrency.addStretch(); layout.addLayout(concurrency)
        self.summary=QLabel('Nenhuma busca iniciada.'); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.progress=QProgressBar(); self.progress.setRange(0,1); layout.addWidget(self.progress)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['Atualizar','Pauta / arquivo','Caminho anterior','Novo caminho / opções','Confiança'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True); self.table.setColumnWidth(0,70); self.table.setColumnWidth(1,160); self.table.setColumnWidth(2,240); self.table.setColumnWidth(3,350)
        self.table.itemChanged.connect(self.check_selection); layout.addWidget(self.table,1)
        paging=QHBoxLayout(); paging.addWidget(QLabel('Página:')); self.page=QSpinBox(); self.page.setMinimum(1); self.page.valueChanged.connect(self.render_page); paging.addWidget(self.page); self.page_info=QLabel(); paging.addWidget(self.page_info); paging.addStretch(); layout.addLayout(paging)
        note=QLabel('Alta confiança única é pré-selecionada ao concluir a busca. Revise as demais opções manualmente. Buscas canceladas ou incompletas exigem seleção manual. Até 32 opções por vínculo; restrinja a raiz se houver mais.')
        note.setWordWrap(True); layout.addWidget(note)
        actions=QHBoxLayout(); self.apply=QPushButton('Atualizar vínculos selecionados'); self.apply.setEnabled(False); self.apply.clicked.connect(self.confirm_apply)
        self.undo=QPushButton('Desfazer última atualização'); self.undo.clicked.connect(self.confirm_undo)
        self.forget=QPushButton('Invalidar mapeamentos'); self.forget.clicked.connect(self.forget_maps)
        self.report=QPushButton('Salvar relatório'); self.report.setEnabled(False); self.report.clicked.connect(self.save_report)
        self.cancel=QPushButton('Cancelar operação'); self.cancel.setEnabled(False); self.cancel.clicked.connect(self.cancel_operation)
        for b in [self.apply,self.undo,self.forget,self.report,self.cancel]: actions.addWidget(b)
        layout.addLayout(actions)
        self.set_busy(False)

    def choose_root(self):
        path=QFileDialog.getExistingDirectory(self,'Escolher unidade ou pasta raiz',self.root.text())
        if path:self.root.setText(path)

    def run_operation(self, operation, complete):
        self.set_busy(True)
        self.worker=LocateWorker(operation,self)
        self.worker.progress.connect(self.show_progress)
        self.worker.done.connect(complete)
        self.worker.failed.connect(lambda error:QMessageBox.warning(self,'Localização',error))
        self.worker.finished.connect(lambda:self.set_busy(False))
        self.worker.start()

    def set_busy(self,busy):
        for w in [self.start,self.root,self.browse,self.undo,self.forget,self.table,self.page,self.workers]:w.setEnabled(not busy)
        self.apply.setEnabled(not busy and bool(self.selections)); self.report.setEnabled(not busy and self.result is not None)
        self.cancel.setEnabled(busy); self.progress.setRange(0,0 if busy else 1)
        if not busy:self.progress.setValue(1)
        self.cancel.setText('Cancelar operação')
        if MODO!='ADMIN':
            for w in [self.apply,self.undo,self.forget]:w.setEnabled(False)

    def scan(self):
        if not self.root.text().strip():self.choose_root()
        if not self.root.text().strip():return
        self.result=None; self.selections={}; self.table.setRowCount(0)
        root=self.root.text().strip()
        workers=self.workers.value()
        self.run_operation(lambda cancel,progress:Locator(root,cancel,progress,self.pauta_id,self.take_id,workers).run(),self.scan_complete)

    def show_progress(self,s):
        self.summary.setText(
            f"{s['stage']}\nArquivos analisados: {s['analyzed']} • Pautas inválidas: {s['invalid_pautas']} • "
            f"Arquivos pendentes: {s['pending']} • Encontrados: {s['found']} • Não encontrados: {s['missing']} • Ambíguos: {s['ambiguous']}\n"
            f"Diretórios examinados: {s['directories']} • Erros de acesso: {s['errors']} • Tempo: {s['elapsed']:.1f}s • "
            f"Pautas localizadas integralmente: {s['complete_pautas']} • Parcialmente: {s['partial_pautas']}")

    def scan_complete(self,result):
        self.result=result
        self.selections={t.key:result.options(t)[0].path for t in result.targets
                         if result.status(t)=='Alta' and not result.cancelled and not result.incomplete}
        self.page.setMaximum(max(1,(len(result.targets)+self.PAGE_SIZE-1)//self.PAGE_SIZE))
        self.page.setValue(1); self.render_page()

    def render_page(self):
        if not self.result:return
        self._rendering=True
        start=(self.page.value()-1)*self.PAGE_SIZE
        targets=self.result.targets[start:start+self.PAGE_SIZE]
        self.table.setRowCount(len(targets))
        for row,target in enumerate(targets):
            check=QTableWidgetItem(); check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            check.setData(Qt.UserRole,target.key); check.setCheckState(Qt.Checked if target.key in self.selections else Qt.Unchecked)
            self.table.setItem(row,0,check)
            for column,text in [(1,('Pauta: ' if target.kind=='pauta' else 'Arquivo: ')+target.title),(2,target.old),(4,self.result.status(target))]:
                item=QTableWidgetItem(text); item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable); item.setToolTip(text); self.table.setItem(row,column,item)
            options=QComboBox(); options.addItem('Selecione um destino…',None)
            for candidate in self.result.options(target):
                options.addItem(candidate.path,candidate.path); options.setItemData(options.count()-1,f'{candidate.confidence} • {candidate.source}',Qt.ToolTipRole)
            selected=self.selections.get(target.key)
            if selected:options.setCurrentIndex(options.findData(selected))
            options.activated.connect(lambda index,r=row,t=target,c=options:self.choose_candidate(r,t,c))
            self.table.setCellWidget(row,3,options)
        self.page_info.setText(f'de {self.page.maximum()} • {len(self.selections)} vínculos selecionados')
        self._rendering=False

    def choose_candidate(self,row,target,combo):
        path=combo.currentData()
        if path:self.selections[target.key]=path
        else:self.selections.pop(target.key,None)
        self.table.item(row,0).setCheckState(Qt.Checked if path else Qt.Unchecked)
        self.update_selection_count()

    def check_selection(self,item):
        if self._rendering or item.column()!=0:return
        path=self.table.cellWidget(item.row(),3).currentData()
        key=tuple(item.data(Qt.UserRole))
        if item.checkState()==Qt.Checked and path:self.selections[key]=path
        else:
            self.selections.pop(key,None)
            if not path and item.checkState()==Qt.Checked:
                item.setCheckState(Qt.Unchecked)
        self.update_selection_count()

    def update_selection_count(self):
        self.page_info.setText(f'de {self.page.maximum()} • {len(self.selections)} vínculos selecionados')
        self.apply.setEnabled(bool(self.selections) and MODO=='ADMIN')

    def confirm_apply(self):
        if MODO!='ADMIN':return
        if not self.result or not self.selections:return
        if QMessageBox.question(self,'Atualizar referências?',f'Atualizar {len(self.selections)} vínculos selecionados? Os caminhos anteriores serão guardados para desfazer.')!=QMessageBox.Yes:return
        result=self.result; selections=dict(self.selections)
        self.run_operation(lambda cancel,progress:apply_updates(result,selections,cancel),self.applied)

    def applied(self,batch):
        self.selections={}; self.render_page(); self.updated.emit()
        QMessageBox.information(self,'Localização','Referências atualizadas. Você pode desfazer pela mesma janela. Faça a busca novamente para recarregar os resultados do acervo.')

    def confirm_undo(self):
        if MODO!='ADMIN':return
        if QMessageBox.question(self,'Desfazer localização?','Restaurar os caminhos anteriores do último lote? Os arquivos físicos não serão modificados.')!=QMessageBox.Yes:return
        def operation(cancel,progress):
            batch=last_batch()
            if not batch:raise ValueError('Não há atualizações para desfazer.')
            return undo_batch(batch,cancel)
        self.run_operation(operation,self.undone)

    def undone(self,count):
        self.updated.emit(); QMessageBox.information(self,'Localização',f'{count} vínculos restaurados.')

    def forget_maps(self):
        if MODO!='ADMIN':return
        if QMessageBox.question(self,'Invalidar mapeamentos?','Deixar de reutilizar todos os prefixos conhecidos nas próximas buscas?')==QMessageBox.Yes:
            self.run_operation(lambda cancel,progress:invalidate_mappings(),lambda _:QMessageBox.information(self,'Localização','Mapeamentos invalidados.'))

    def save_report(self):
        if not self.result:return
        path,_=QFileDialog.getSaveFileName(self,'Salvar relatório','localizacao.json','JSON (*.json)')
        if not path:return
        payload=dict(stats=self.result.stats,root=self.result.root,cancelled=self.result.cancelled,incomplete=self.result.incomplete,
            results=[dict(target=asdict(t),status=self.result.status(t),options=[asdict(c) for c in self.result.options(t)],
                          truncated=t.key in self.result.truncated) for t in self.result.targets])
        try:
            with open(path,'w',encoding='utf-8') as file:json.dump(payload,file,ensure_ascii=False,indent=2)
        except OSError as error:QMessageBox.warning(self,'Relatório',str(error))

    def cancel_operation(self):
        if self.worker and self.worker.isRunning():self.worker.cancel.set(); self.cancel.setText('Cancelando…')

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.cancel_operation(); event.ignore(); return
        super().closeEvent(event)

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.cancel_operation()
            return
        super().reject()


def open_locator(parent,pauta_id=None,take_id=None):
    dialog=LocateDialog(parent,pauta_id,take_id)
    dialog.setAttribute(Qt.WA_DeleteOnClose)
    if not hasattr(parent,'_locate_dialogs'):parent._locate_dialogs=[]
    parent._locate_dialogs.append(dialog)
    dialog.destroyed.connect(lambda:parent._locate_dialogs.remove(dialog) if dialog in parent._locate_dialogs else None)
    dialog.show()
    dialog.set_busy(False)
    return dialog


def allow_close(parent,event):
    running=[d for d in parent.findChildren(LocateDialog) if d.worker and d.worker.isRunning()]
    if running:
        for dialog in running:dialog.cancel_operation()
        event.ignore()
        return False
    return True
