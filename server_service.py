"""Entrada do servidor Windows: administração, console ou serviço SCM."""
import json
import os
from pathlib import Path
import sys
import threading


def config_path():
    return Path(os.getenv('PAUTAS_SERVER_CONFIG',str(Path(os.getenv('PROGRAMDATA',r'C:\ProgramData'))/'PautasServer'/'server.json')))


def main():
    if len(sys.argv)>1 and sys.argv[1]=='admin':
        from network.admin import main as admin_main
        return admin_main(sys.argv[2:])
    if len(sys.argv)>1 and sys.argv[1]=='console':
        from network.server import run
        return run(sys.argv[2] if len(sys.argv)>2 else config_path())
    import win32serviceutil
    import win32service
    import servicemanager
    class PautasService(win32serviceutil.ServiceFramework):
        _svc_name_='PautasServer'
        _svc_display_name_='Sistema de Pautas - Servidor LAN'
        _svc_description_='API autenticada do acervo de pautas na rede local.'
        def __init__(self,args):
            super().__init__(args); self.http_server=None; self.stopping=threading.Event()
        def SvcStop(self):
            self.stopping.set()
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING,waitHint=30000)
            if self.http_server:self.http_server.should_exit=True
        def SvcDoRun(self):
            import uvicorn
            from network.server import create_app
            from logging.handlers import RotatingFileHandler
            import logging
            from network.configuration import load_settings
            path=config_path(); settings=load_settings(path)
            log=path.parent/'logs'; log.mkdir(parents=True,exist_ok=True)
            logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(log/'server.log',maxBytes=5_000_000,backupCount=5,encoding='utf-8')])
            config=uvicorn.Config(create_app(settings),host=settings.get('host','127.0.0.1'),port=int(settings.get('port',8000)),
                http='h11',ws='none',loop='asyncio',proxy_headers=False,access_log=False,
                ssl_certfile=settings.get('tls_cert'),ssl_keyfile=settings.get('tls_key'))
            self.http_server=uvicorn.Server(config)
            if self.stopping.is_set():return
            try:self.http_server.run()
            except Exception:
                logging.exception('Servidor encerrado por falha'); raise
            if not self.stopping.is_set():raise RuntimeError('API encerrada sem solicitação de parada; serviço sinalizará falha ao Windows.')
    # Necessário para pywin32 registrar a classe em execução por Python/frozen.
    globals()['PautasService']=PautasService
    if len(sys.argv)==1:
        servicemanager.Initialize(); servicemanager.PrepareToHostSingle(PautasService); servicemanager.StartServiceCtrlDispatcher()
    else:win32serviceutil.HandleCommandLine(PautasService)


if __name__=='__main__':main()
