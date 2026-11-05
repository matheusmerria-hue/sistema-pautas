"""Configuração/login e notificações leves, mantendo os formulários existentes."""
import json
import os
import threading
import time
from functools import wraps
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QThread,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLineEdit,QPushButton,
    QMessageBox,QLabel,QHBoxLayout,QApplication)
from .client import ApiSession,responsive,NetworkError
from . import runtime


def settings_path():return Path(os.getenv('LOCALAPPDATA',str(Path.home())))/'SistemaPautas'/'connection.json'


def load_settings():
    path=settings_path()
    if not path.exists():return {}
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


class ConnectionDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle('Conectar ao servidor de pautas'); self.resize(480,260)
        self.session=None; form=QFormLayout(); root=QVBoxLayout(self); root.addLayout(form)
        settings=load_settings()
        self.url=QLineEdit(settings.get('url','')); self.url.setPlaceholderText('http://hostname:porta')
        self.username=QLineEdit(settings.get('username','')); self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        self.ca=QLineEdit(settings.get('ca_file','')); self.ca.setPlaceholderText('Opcional: certificado CA confiável (.pem)')
        for label,field in [('Servidor',self.url),('Usuário',self.username),('Senha',self.password),('Certificado CA',self.ca)]:form.addRow(label,field)
        self.message=QLabel('As senhas não são salvas neste computador.'); self.message.setWordWrap(True); root.addWidget(self.message)
        self.connect_button=QPushButton('Testar conexão e entrar'); self.connect_button.clicked.connect(self.connect_server); root.addWidget(self.connect_button)
    def connect_server(self):
        self.connect_button.setEnabled(False); self.message.setText('Conectando…')
        url=self.url.text().strip(); username=self.username.text().strip(); password=self.password.text(); ca=self.ca.text().strip()
        try:
            def login():
                session=ApiSession(url,ca or None); session.login(username,password); return session
            session=responsive(login)
            path=settings_path(); path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(dict(url=url,username=username,ca_file=ca,network=True),indent=2),encoding='utf-8')
            self.password.clear(); self.session=session; self.accept()
        except Exception as error:self.message.setText(str(error))
        finally:self.connect_button.setEnabled(True)
    def reject(self):
        if not self.connect_button.isEnabled():return
        super().reject()


def connect(parent=None):
    dialog=ConnectionDialog(parent)
    if dialog.exec()!=QDialog.Accepted:return False
    runtime.SESSION=dialog.session
    import user_config
    user_config.MODO='LEITURA' if dialog.session.role=='reader' else 'ADMIN'
    return True


class ChangeWorker(QThread):
    result=Signal(object)
    def __init__(self,session,cursor,parent):super().__init__(parent); self.session=session; self.cursor=cursor
    def run(self):
        try:
            status=self.session.http('GET','/status')
            if status['database']!='available':
                self.result.emit((True,dict(server_status=status,sync_error='Banco central indisponível.')));return
            data=self.session.http('GET','/changes?after='+str(self.cursor));data['server_status']=status
            self.result.emit((True,data))
        except Exception as error:self.result.emit((False,str(error)))


class ShareProbe(QObject):
    done=Signal(object)
    def __init__(self,parent):
        super().__init__(parent);self.worker=None;self.checked=0;self.signature=None;self.closed=False
    def start(self,shares):
        signature=tuple(shares)
        if self.closed or (self.worker and self.worker.is_alive()):return
        if signature==self.signature and time.monotonic()-self.checked<30:return
        self.signature=signature;self.checked=time.monotonic()
        def probe():
            from .diagnostics import probe_directory
            states=[dict(share=share,state=probe_directory(share)) for share in shares]
            if not self.closed:
                try:self.done.emit(states)
                except RuntimeError:pass  # A janela já foi destruída durante I/O nativo.
        self.worker=threading.Thread(target=probe,name='pautas-smb-probe',daemon=True);self.worker.start()
    def stop(self):self.closed=True


class ConnectionMonitor(QObject):
    changed=Signal(object)
    def __init__(self,window):
        super().__init__(window); self.window=window; self.cursor=0; self.worker=None; self.was_online=True; self.deferred=False
        self.database_state='verificando';self.share_state='verificando';self.sync_state='verificando'
        self.share_probe=ShareProbe(self);self.share_probe.done.connect(self.receive_shares)
        self.banner=QLabel('Conectado ao servidor'); self.banner.setWordWrap(True)
        self.relogin=QPushButton('Conexão…'); self.relogin.clicked.connect(self.login_again)
        row=QHBoxLayout(); row.addWidget(self.banner,1); row.addWidget(self.relogin)
        if hasattr(window,'main_layout'):window.main_layout.insertLayout(0,row)
        elif hasattr(window,'statusBar'):
            window.statusBar().addWidget(self.banner,1); window.statusBar().addPermanentWidget(self.relogin)
        self.timer=QTimer(self); self.timer.setInterval(5000); self.timer.timeout.connect(self.poll); self.timer.start()
        self.changed.connect(self.refresh_visible)
        self.protect_buttons(True)
    def login_again(self):
        previous=runtime.SESSION
        dialog=ConnectionDialog(self.window)
        if dialog.exec()==QDialog.Accepted:
            if dialog.session.url!=previous.url:
                QMessageBox.information(self.window,'Conexão','Novo endereço salvo. Reinicie o aplicativo para trocar de servidor; seus formulários atuais permanecem abertos.')
            else:
                if previous.username==dialog.session.username:
                    with previous.pending_lock:dialog.session.pending=dict(previous.pending)
                runtime.SESSION=dialog.session; self.poll()
    def poll(self):
        if self.worker and self.worker.isRunning():return
        self.worker=ChangeWorker(runtime.SESSION,self.cursor,self)
        self.worker.result.connect(self.receive); self.worker.finished.connect(self.worker_finished); self.worker.start()
    def worker_finished(self):
        worker=self.sender()
        if self.worker is worker:self.worker=None
        worker.deleteLater()
    def receive(self,result):
        online,data=result
        status=data.get('server_status') if online else None
        self.protect_buttons(online and not data.get('sync_error') if online else False)
        if not online:
            self.banner.setText('Servidor desconectado • Banco: sem confirmação • Compartilhamentos: '+self.share_state+' • Sincronização: aguardando reconexão. Texto não salvo mantido.')
            self.was_online=False; return
        reconnect=not self.was_online; self.was_online=True
        if status:
            self.database_state='disponível' if status['database']=='available' else 'indisponível'
            self.share_probe.start([r['share'] for r in status['media']])
        if data.get('sync_error'):
            self.sync_state='aguardando banco central';self.render_status();return
        self.sync_state='atualizando' if data.get('changes') or data.get('reset') or self.deferred else 'em dia'
        self.render_status()
        if data.get('changes') or data.get('reset') or reconnect or self.deferred:
            if runtime.ACTIVE_CALLS:return
            runtime.SESSION.names_cache=None
            self.cursor=data['cursor']; self.changed.emit(data)
            self.sync_state='atualização adiada durante digitação' if self.deferred else 'em dia';self.render_status()
    def receive_shares(self,states):
        unavailable=[s['share'] for s in states if s['state']!='available']
        self.share_state='disponíveis' if states and not unavailable else ('indisponíveis: '+', '.join(unavailable) if unavailable else 'nenhum configurado')
        if self.was_online:self.render_status()
    def render_status(self):
        self.banner.setText('Servidor conectado • Banco: '+self.database_state+' • Compartilhamentos: '+self.share_state+' • Sincronização: '+self.sync_state)
    def protect_buttons(self,online):
        allowed=online and runtime.SESSION.role!='reader'
        for button in self.window.findChildren(QPushButton):
            name=button.text().strip().lower()
            write=name.startswith(('salvar','criar pauta','excluir','☆','★','⭐','atualizar vínculos','desfazer','invalidar')) or button.objectName().startswith('StatusDot_')
            if not write:continue
            if not allowed:
                if button.property('network_previous_enabled') is None:button.setProperty('network_previous_enabled',button.isEnabled())
                button.setEnabled(False)
            elif button.property('network_previous_enabled') is not None:
                button.setEnabled(bool(button.property('network_previous_enabled'))); button.setProperty('network_previous_enabled',None)
    def refresh_visible(self,data):
        self.deferred=False
        # Nunca recarregar o editor: rascunhos mantêm a revisão original para CAS.
        from PySide6.QtWidgets import QApplication
        for window in QApplication.topLevelWidgets():
            if not window.isVisible():continue
            if hasattr(window,'executar_busca'):window.executar_busca(salvar_no_historico=False)
            elif hasattr(window,'pages') and hasattr(window,'search_page'):
                if window.pages.currentWidget()==window.search_page:window.search_page.executar_busca(False)
                elif window.pages.currentWidget()==window.dashboard_page:
                    field=getattr(window,'input_cliente_acervo',None)
                    if field and field.hasFocus():self.deferred=True;continue
                    window.mostrar_dashboard()
            elif hasattr(window,'pages') and hasattr(window,'home'):
                if window.pages.currentIndex()==0:window.home.refresh()
                elif window.pages.currentIndex()==1:window.search.refresh(False)
    def stop(self):
        self.timer.stop()
        if self.worker and self.worker.isRunning():return False
        self.share_probe.stop()
        return True


def install_monitor(window):
    if runtime.remote():window.connection_monitor=ConnectionMonitor(window)


def allow_network_close(window,event):
    if runtime.ACTIVE_CALLS:
        event.ignore();return False
    monitor=getattr(window,'connection_monitor',None)
    if monitor and not monitor.stop():event.ignore(); return False
    return True


def operation_errors(function):
    @wraps(function)
    def call(self,*args,**kwargs):
        try:return function(self,*args,**kwargs)
        except NetworkError as error:
            QMessageBox.warning(self,'Operação não concluída',str(error))
    return call


def saving_form(function):
    @wraps(function)
    def call(self,*args,**kwargs):
        if getattr(self,'_saving_network_form',False):return
        self._saving_network_form=True; enabled=self.isEnabled(); self.setEnabled(False)
        try:return function(self,*args,**kwargs)
        finally:self.setEnabled(enabled); self._saving_network_form=False
    return call


def serial_refresh(timer_name):
    def decorate(function):
        @wraps(function)
        def call(self,*args,**kwargs):
            if getattr(self,'_refresh_running',False):
                getattr(self,timer_name).start();return
            self._refresh_running=True
            try:return function(self,*args,**kwargs)
            finally:self._refresh_running=False
        return call
    return decorate
