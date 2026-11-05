"""Teste real de TCP dos pacotes gerados, usando apenas dados temporários."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import sys

project=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(project))
from network.client import ApiSession


def main():
    server=project/'release-network'/'PautasServidor'/'PautasServidor.exe'
    client=project/'release-network'/'PautasCliente'/'PautasCliente.exe'
    workspace=project/'network.local'; workspace.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=workspace,prefix='smoke-') as directory:
        root=Path(directory); media=root/'media'; media.mkdir()
        config=root/'server.json'; database=root/'database.sqlite'; backup=root/'backups'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        def run_admin(*args,input=None):
            response=subprocess.run([str(server),'admin',*args],input=input,capture_output=True,creationflags=creationflags)
            if response.returncode:raise RuntimeError(response.stderr.decode(errors='replace'))
        run_admin('init','--config',str(config),'--database',str(database),'--backup-directory',str(backup),
                  '--host','127.0.0.1','--port',str(port),'--media',str(media)+r'=\\SERVIDOR\PRODUCOES')
        password='teste-temporario-pacote-2026'
        for name in ['pc01','pc02']:
            run_admin('user','--config',str(config),'--username',name,'--role','editor','--password-stdin',input=(password+'\n').encode('utf-8'))
        run_admin('check','--config',str(config),'--strict')
        assert not database.exists(), 'Diagnóstico de instalação criou banco indevidamente'
        log=open(root/'process.log','wb')
        process=None
        try:
            def start():
                nonlocal process
                process=subprocess.Popen([str(server),'console',str(config)],stdout=log,stderr=log,creationflags=creationflags)
                limit=time.monotonic()+20
                while time.monotonic()<limit:
                    if process.poll() is not None:raise RuntimeError('Pacote servidor encerrou; consulte '+str(root/'process.log'))
                    try:
                        session=ApiSession(f'http://127.0.0.1:{port}'); session.login('pc01',password); return session
                    except Exception:threading.Event().wait(.1)
                raise RuntimeError('Servidor não respondeu no prazo do teste.')
            pc1=start(); pc2=ApiSession(f'http://127.0.0.1:{port}'); pc2.login('pc02',password)
            assert pc1.http('GET','/status')['database']=='available'
            pc1.rpc('salvar_pauta',dict(nome_pauta='Teste TCP',data_pauta='2026-11-04',cliente='Cliente LAN',descricao='Teste',
                    caminho_pasta=r'\\SERVIDOR\PRODUCOES\Teste',takes=[]))
            rows=pc2.rpc('buscar_pautas',{})
            assert len(rows)==1 and rows[0]['pauta']['cliente']=='Cliente LAN'
            process.terminate(); process.wait(15)
            pc1=start()
            assert len(pc1.rpc('buscar_pautas',{}))==1
            run_admin('backup','--config',str(config))
            assert list(backup.glob('pautas-*.sqlite'))
            print('PACOTE_SERVIDOR_TCP_OK: dois clientes, criação/leitura, reinício e backup.')
        finally:
            if process and process.poll() is None:process.terminate(); process.wait(15)
            log.close()
        environment=dict(os.environ,QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=str(root/'perfil-cliente'))
        for ui in ('main','v3'):
            desktop=subprocess.Popen([str(client),'--ui',ui],env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=creationflags)
            try:
                threading.Event().wait(3)
                if desktop.poll() is not None:raise RuntimeError('Pacote cliente '+ui+' encerrou antes do diálogo de conexão.')
                assert not list((root/'perfil-cliente').rglob('*.db'))
                print('PACOTE_CLIENTE_BOOT_OK: '+ui+' ativo em offscreen; nenhum SQLite local criado.')
            finally:
                if desktop.poll() is None:desktop.terminate(); desktop.wait(15)


if __name__=='__main__':main()
