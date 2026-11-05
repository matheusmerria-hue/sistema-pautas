import copy
from contextlib import closing
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from network.server import create_app
except ImportError as exc:
    raise unittest.SkipTest('Instale requirements-test-network.txt para testar a API LAN') from exc
import database as db
from network.client import ApiSession,NetworkError,EditConflict
from network import runtime
from network.media import MediaRoots
from network.security import add_user
from network.backup import backup_database,restore_database,verify
from network.instance import exclusive_instance


class NetworkTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.base=Path(self.temp.name).resolve()
        self.media=self.base/'media'; self.media.mkdir()
        self.database=self.base/'pautas.sqlite'; self.users=self.base/'users.json'
        self.dbpatch=patch.object(db,'DB_PATH',self.database); self.dbpatch.start()
        self.sessionpatch=patch.object(runtime,'SESSION',None); self.sessionpatch.start()
        self.password='senha-de-teste-2026'
        for username,role in [('pc01','editor'),('pc02','editor'),('consulta','reader')]:add_user(self.users,username,self.password,role)
        self.settings=dict(database=str(self.database),users_file=str(self.users),backup_directory=str(self.base/'outro-disco'),
                           media_roots=[dict(name='Produções',local=str(self.media),share=r'\\SERVIDOR\PRODUCOES')],
                           allowed_clients=['127.0.0.1/32'],backup_interval_seconds=3600,_testing=True)
        self.http=TestClient(create_app(self.settings)); self.http.__enter__()
        self.pc1=self.client('pc01'); self.pc2=self.client('pc02'); self.reader=self.client('consulta')

    def tearDown(self):
        runtime.SESSION=None
        self.http.__exit__(None,None,None); self.sessionpatch.stop(); self.dbpatch.stop(); self.temp.cleanup()

    def client(self,username):
        client=ApiSession('http://localhost:8000',transport=self.http)
        client.login(username,self.password); return client

    def create(self,client=None,name='Pauta',count=2):
        client=client or self.pc1
        folder=r'\\SERVIDOR\PRODUCOES'+'\\'+name
        client.rpc('salvar_pauta',dict(nome_pauta=name,data_pauta='04/11/2026',cliente='Núcleo D3',descricao='Original',caminho_pasta=folder,
                   takes=[dict(nome_arquivo=f'C{i:04}.MP4',caminho_arquivo=folder+f'\\Camera\\C{i:04}.MP4',comentario='Comentário',importante=False) for i in range(count)]))
        return client.rpc('buscar_pautas',dict(palavra_chave=name))[0]

    def test_dois_clientes_criacao_leitura_comentarios_favoritos_e_conflito(self):
        first=self.create()
        snapshot=self.pc2.rpc('obter_pauta_com_takes',dict(pauta_id=first['pauta']['id']))
        p=first['pauta']; t=first['takes'][0]
        values=dict(pauta_id=p['id'],nome_pauta=p['nome_pauta'],data_pauta=p['data_pauta'],cliente=p['cliente'],descricao='PC01',
                    takes=[dict(id=t['id'],comentario='Comentário PC01',importante=True,favorito=True)])
        expected={f'pautas:{p["id"]}':p['revision'],f'takes:{t["id"]}':t['revision']}
        self.pc1.rpc('atualizar_pauta',values,expected)
        with self.assertRaises(EditConflict):self.pc2.rpc('atualizar_pauta',{**values,'descricao':'PC02'},expected)
        latest=self.pc2.rpc('obter_pauta_com_takes',dict(pauta_id=p['id']))
        self.assertEqual(latest['pauta']['descricao_inicial'],'PC01')
        self.assertEqual(latest['takes'][0]['comentario'],'Comentário PC01')
        self.assertEqual(latest['takes'][0]['favorito'],1)
        other=snapshot['takes'][1]
        self.pc2.rpc('alternar_favorito_take',dict(take_id=other['id'],favorito=True),{f'takes:{other["id"]}':other['revision']})
        self.assertTrue(self.pc1.rpc('obter_pauta_com_takes',dict(pauta_id=p['id']))['takes'][1]['favorito'])

    def test_sem_autenticacao_e_perfil_leitura(self):
        response=self.http.post('/rpc',json=dict(operation='salvar_pauta',kwargs={}))
        self.assertEqual(response.status_code,401)
        self.assertEqual(self.http.get('/health').status_code,401)
        self.assertEqual(self.reader.rpc('buscar_pautas',{}),[])
        with self.assertRaises(NetworkError):self.create(self.reader)
        with self.assertRaises(NetworkError):self.reader.http('POST','/locate/start',dict(root=r'\\SERVIDOR\PRODUCOES'))

    def test_nao_aceita_sql_ou_caminhos_fora_da_raiz(self):
        with self.assertRaises(NetworkError):self.pc1.rpc('get_connection',{})
        with self.assertRaises(NetworkError):self.pc1.rpc('salvar_pauta',dict(nome_pauta='x',data_pauta='',cliente='x',descricao='',caminho_pasta=r'C:\Windows',takes=[]))
        with self.assertRaises(NetworkError):self.pc1.rpc('scan_media',dict(caminho_pasta=r'\\SERVIDOR\PRODUCOES\..\Windows'))
        with self.assertRaises(ValueError):create_app({**self.settings,'allowed_clients':['0.0.0.0/0']})
        blocked=TestClient(create_app({**self.settings,'_testing':False}))
        self.assertEqual(blocked.get('/health',headers={'X-Forwarded-For':'127.0.0.1'}).status_code,403)

    def test_fachada_cliente_nunca_abre_sqlite_e_preserva_revisoes(self):
        initial=self.create(); runtime.SESSION=self.pc1
        with patch('sqlite3.connect',side_effect=AssertionError('Cliente tentou abrir SQLite')):
            # Transporte simulado usa o servidor no mesmo processo: desfaça o mock apenas no backend.
            with self.assertRaises(RuntimeError):db.get_connection()
        detail=db.obter_pauta_com_takes(initial['pauta']['id'])
        p=detail['pauta']; old=p['revision']
        db.alternar_favorito_pauta(p['id'],True,_expected=runtime.expected(pauta=p))
        self.assertGreater(p['revision'],old)
        self.assertEqual(db.buscar_pautas()[0]['pauta']['favorita'],1)
        with self.assertRaises(EditConflict):db.excluir_pauta(p['id'])

    def test_idempotencia_apos_resposta_perdida(self):
        folder=r'\\SERVIDOR\PRODUCOES\Pauta'
        body=dict(operation='salvar_pauta',kwargs=dict(nome_pauta='Idempotente',data_pauta='',cliente='FIEMS',descricao='',caminho_pasta=folder,takes=[]),request_id=uuid.uuid4().hex)
        headers={'Authorization':'Bearer '+self.pc1.token}
        one=self.http.post('/rpc',json=body,headers=headers); two=self.http.post('/rpc',json=body,headers=headers)
        self.assertEqual(one.status_code,200); self.assertEqual(two.status_code,200)
        self.assertEqual(len(self.pc2.rpc('buscar_pautas',{})),1)

    def test_feed_incremental_paginacao_e_exportacao(self):
        with runtime.server_context(),closing(db.get_connection()) as conn,conn:
            conn.executemany('''INSERT INTO pautas(nome_pauta,data_pauta,cliente,caminho_pasta,data_criacao,data_atualizacao)
                                VALUES(?,?,?,?,?,?)''',[(f'Pauta {i}','2026-11-04','FIEMS',str(self.media/f'Pauta {i}'),'2026','2026') for i in range(230)])
        first=self.pc1.rpc('buscar_pautas',{})
        self.assertEqual(len(first),100); self.assertTrue(first.has_more)
        page=self.pc2.rpc('buscar_pautas',dict(offset=200,limite=100))
        self.assertEqual(len(page),30); self.assertFalse(page.has_more)
        changes=self.pc2.http('GET','/changes?after=0'); self.assertTrue(changes['reset'])
        self.assertFalse(self.pc2.http('GET','/changes?after='+str(changes['cursor']))['changes'])
        runtime.SESSION=self.pc1
        from exporter import exportar_json
        target=self.base/'export.json'; exportar_json(target)
        self.assertEqual(len(json.loads(target.read_text(encoding='utf-8'))),230)

    def test_smart_locate_executa_no_servidor_e_reutiliza_trabalho(self):
        record=self.create(name='Pauta Movida',count=3); old=self.media/'Pauta Movida'; new=self.media/'Backup'/'Pauta Movida'/'Camera'; new.mkdir(parents=True)
        for i in range(3):(new/f'C{i:04}.MP4').write_bytes(b'test')
        request=dict(root=r'\\SERVIDOR\PRODUCOES',pauta_id=record['pauta']['id'])
        job=self.pc1.http('POST','/locate/start',request)['job_id']
        self.assertEqual(job,self.pc2.http('POST','/locate/start',request)['job_id'])
        limit=time.monotonic()+10
        while time.monotonic()<limit:
            result=self.pc2.http('GET','/locate/'+job)
            if result['finished']:break
            threading.Event().wait(.01)
        self.assertTrue(result['finished']); self.assertIsNone(result['error'])
        selections=[dict(kind=item['target']['kind'],id=item['target']['id'],path=item['options'][0]['path']) for item in result['items'] if item['options']]
        self.assertEqual(len(selections),4)
        self.pc1.http('POST','/locate/'+job+'/apply',dict(selections=selections))
        latest=self.pc2.rpc('obter_pauta_com_takes',dict(pauta_id=record['pauta']['id']))
        self.assertIn('Backup',latest['pauta']['caminho_pasta'])
        self.assertEqual(latest['takes'][0]['comentario'],'Comentário')

    def test_perda_retorno_rede_sem_fallback_local(self):
        runtime.SESSION=self.pc1; self.pc1.online=False
        with self.assertRaises(NetworkError):db.salvar_pauta('Não salvar','','FIEMS','',r'\\SERVIDOR\PRODUCOES',[])
        with self.assertRaises(RuntimeError):db.get_connection()
        self.pc1.http('GET','/changes')
        self.assertTrue(self.pc1.online)
        self.assertEqual(db.buscar_pautas(),[])

    def test_backup_consistente_restauracao_e_lock_de_servico(self):
        self.create()
        backup=backup_database(self.database,self.base/'outro-disco',3); verify(backup)
        with self.assertRaises(ValueError):
            with exclusive_instance(self.database):pass
        self.http.__exit__(None,None,None)
        restore_database(backup,self.database)
        self.http=TestClient(create_app(self.settings)); self.http.__enter__()
        self.pc1=self.client('pc01')
        self.assertEqual(len(self.pc1.rpc('buscar_pautas',{})),1)
        self.assertTrue(list((self.base/'antes-restauracao').glob('*.sqlite')))

    def test_reinicio_preserva_ids_e_invalida_sessoes(self):
        record=self.create(); pid=record['pauta']['id']; token=self.pc2.token
        self.http.__exit__(None,None,None)
        self.http=TestClient(create_app(self.settings)); self.http.__enter__()
        self.assertEqual(self.http.get('/health',headers={'Authorization':'Bearer '+token}).status_code,401)
        self.pc2=self.client('pc02')
        self.assertEqual(self.pc2.rpc('obter_pauta_com_takes',dict(pauta_id=pid))['takes'][0]['id'],record['takes'][0]['id'])

    def test_gravacoes_concorrentes_tem_um_vencedor_sem_perda_silenciosa(self):
        from concurrent.futures import ThreadPoolExecutor
        record=self.create(); p=record['pauta']; barrier=threading.Barrier(2)
        def edit(client,name):
            barrier.wait()
            try:
                client.rpc('atualizar_pauta',dict(pauta_id=p['id'],nome_pauta=p['nome_pauta'],data_pauta=p['data_pauta'],
                    cliente=p['cliente'],descricao=name,takes=[]),{f'pautas:{p["id"]}':p['revision']})
                return name
            except EditConflict:return 'conflito'
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(edit,self.pc1,'PC01'); second=pool.submit(edit,self.pc2,'PC02')
            results=[first.result(),second.result()]
        self.assertEqual(results.count('conflito'),1)
        latest=self.pc1.rpc('obter_pauta_com_takes',dict(pauta_id=p['id']))
        self.assertIn(latest['pauta']['descricao_inicial'],results)

    def test_interface_preserva_rascunho_em_conflito_e_offline(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication,QMessageBox
        from ui.ui_search import EditPautaPopup
        app=QApplication.instance() or QApplication([])
        record=self.create(); p=record['pauta']
        runtime.SESSION=self.pc2
        popup=EditPautaPopup(copy.deepcopy(p),copy.deepcopy(record['takes']))
        try:
            popup.input_descricao.setPlainText('Rascunho PC02 preservado')
            self.pc1.rpc('atualizar_pauta',dict(pauta_id=p['id'],nome_pauta=p['nome_pauta'],data_pauta=p['data_pauta'],cliente=p['cliente'],descricao='PC01',takes=[]),{f'pautas:{p["id"]}':p['revision']})
            with patch.object(QMessageBox,'warning') as warning:popup.salvar_alteracoes()
            self.assertTrue(warning.called)
            self.assertEqual(popup.input_descricao.toPlainText(),'Rascunho PC02 preservado')
            self.pc2.online=False
            with patch.object(QMessageBox,'warning') as warning:popup.salvar_alteracoes()
            self.assertTrue(warning.called)
            self.assertEqual(popup.input_descricao.toPlainText(),'Rascunho PC02 preservado')
        finally:popup.close(); app.processEvents()

    def test_monitor_descarta_workers_e_interface_continua_responsiva(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer,QCoreApplication,QEvent
        from ui.ui_search import SearchPautaWindow
        from network.desktop import ConnectionMonitor,ChangeWorker
        from network.client import responsive
        app=QApplication.instance() or QApplication([])
        runtime.SESSION=self.pc1
        window=SearchPautaWindow(); monitor=ConnectionMonitor(window); monitor.timer.stop()
        smb_patch=patch.object(monitor.share_probe,'start');smb_patch.start()
        try:
            ticks=[]; timer=QTimer(); timer.setInterval(10); timer.timeout.connect(lambda:ticks.append(1)); timer.start()
            responsive(lambda:threading.Event().wait(.15))
            timer.stop(); self.assertGreater(len(ticks),2)
            for i in range(5):
                monitor.poll()
                limit=time.monotonic()+3
                while monitor.worker and time.monotonic()<limit:
                    app.processEvents(); threading.Event().wait(.005)
                self.assertIsNone(monitor.worker)
                QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
            self.assertEqual(monitor.findChildren(ChangeWorker),[])
        finally:
            monitor.stop();smb_patch.stop(); window.search_timer.stop(); window.close(); app.processEvents()

    def wait_job(self,job_id):
        limit=time.monotonic()+5
        while time.monotonic()<limit:
            result=self.pc2.http('GET','/locate/'+job_id)
            if result['finished']:return result
            threading.Event().wait(.01)
        self.fail('Tarefa não concluiu no prazo do teste')

    def test_cancelamento_remoto_com_estados_e_horarios(self):
        from smart_locate import Locator
        folder=r'\\SERVIDOR\PRODUCOES\Antigo\Pauta Cancelar'
        self.pc1.rpc('salvar_pauta',dict(nome_pauta='Pauta Cancelar',data_pauta='',cliente='FIEMS',descricao='',caminho_pasta=folder,
            takes=[dict(nome_arquivo='C0001.MP4',caminho_arquivo=folder+r'\Camera\C0001.MP4',comentario='Preservar')]))
        new=self.media/'Pauta Cancelar'/'Camera';new.mkdir(parents=True);(new/'C0001.MP4').write_bytes(b'video')
        ready=threading.Event()
        class ControlledLocator(Locator):
            def tick(self,force=False):
                if self.result.stats['stage']=='Varredura compartilhada de diretórios' and not ready.is_set():
                    ready.set();self.cancel.wait(5)
                super().tick(force)
        with patch('network.jobs.Locator',ControlledLocator):
            job=self.pc1.http('POST','/locate/start',dict(root=r'\\SERVIDOR\PRODUCOES'))['job_id']
            self.assertTrue(ready.wait(3))
            running=self.pc2.http('GET','/locate/'+job)
            self.assertEqual(running['status'],'running');self.assertIsNotNone(running['started_at'])
            self.pc2.http('POST','/locate/'+job+'/cancel',{})
            result=self.wait_job(job)
        self.assertEqual(result['status'],'cancelled');self.assertTrue(result['cancel_requested'])
        self.assertIsNotNone(result['finished_at']);self.assertTrue(result['cancelled'])
        self.assertGreater(result['stats']['found'],0)
        old=self.pc1.rpc('buscar_pautas',{})[0]['pauta']['caminho_pasta']
        self.assertIn('Antigo',old)

    def test_tarefa_com_falha_publica_erro_e_conclusao(self):
        with patch('network.jobs.Locator') as locator:
            locator.return_value.run.side_effect=PermissionError()
            job=self.pc1.http('POST','/locate/start',dict(root=r'\\SERVIDOR\PRODUCOES'))['job_id']
            result=self.wait_job(job)
        self.assertEqual(result['status'],'failed');self.assertEqual(result['error'],'PermissionError')
        self.assertIsNotNone(result['started_at']);self.assertIsNotNone(result['finished_at'])

    def test_desfazimento_remoto_observado_por_dois_clientes(self):
        record=self.create(name='Pauta Undo',count=1)
        new=self.media/'Backup'/'Pauta Undo'/'Camera';new.mkdir(parents=True);(new/'C0000.MP4').write_bytes(b'video')
        job=self.pc1.http('POST','/locate/start',dict(root=r'\\SERVIDOR\PRODUCOES'))['job_id']
        result=self.wait_job(job)
        choices=[dict(kind=i['target']['kind'],id=i['target']['id'],path=i['options'][0]['path']) for i in result['items'] if i['options']]
        self.pc1.http('POST','/locate/'+job+'/apply',dict(selections=choices))
        updated=self.pc2.rpc('obter_pauta_com_takes',dict(pauta_id=record['pauta']['id']))
        self.assertIn('Backup',updated['pauta']['caminho_pasta'])
        self.assertEqual(self.pc2.http('POST','/locate-undo',{})['count'],2)
        restored=self.pc1.rpc('obter_pauta_com_takes',dict(pauta_id=record['pauta']['id']))
        self.assertEqual(restored['pauta']['caminho_pasta'],record['pauta']['caminho_pasta'])
        self.assertEqual(restored['takes'][0]['comentario'],record['takes'][0]['comentario'])

    def test_multiplos_hds_referencias_relativas_e_status_autenticado(self):
        self.http.__exit__(None,None,None)
        second=self.base/'hd2';second.mkdir()
        self.settings['media_roots']=[dict(id='PRODUCOES',local=str(self.media),share=r'\\SERVIDOR\PRODUCOES'),
                                      dict(id='ARQUIVO',local=str(second),share=r'\\SERVIDOR\ARQUIVO')]
        self.http=TestClient(create_app(self.settings));self.http.__enter__();self.pc1=self.client('pc01')
        media=self.http.app.state.media
        ref=media.reference(str(second/'Cliente'/'Camera'/'Take01.mp4'))
        self.assertEqual(ref,dict(root_id='ARQUIVO',relative_path=r'Cliente\Camera\Take01.mp4'))
        self.assertEqual(media.resolve(**ref),str(second/'Cliente'/'Camera'/'Take01.mp4'))
        self.assertEqual(self.pc1.http('POST','/media/resolve',ref)['path'],r'\\SERVIDOR\ARQUIVO\Cliente\Camera\Take01.mp4')
        with self.assertRaises(NetworkError):self.pc1.http('POST','/media/resolve',dict(root_id='ARQUIVO',relative_path=r'..\users.json'))
        status=self.pc1.http('GET','/status')
        self.assertEqual(status['database'],'available');self.assertEqual(len(status['media']),2)
        self.assertTrue(all(r['state']=='available' for r in status['media']))
        self.assertEqual(self.http.get('/status').status_code,401)
        self.assertEqual(self.http.post('/media/resolve',json=ref).status_code,401)

    def test_cliente_main_e_v3_usam_login_de_rede(self):
        import client_main
        with patch('main.main',return_value=0) as start:client_main.main([])
        start.assert_called_once_with(network=True)
        with patch('ui_v3.app.main',return_value=0) as start:client_main.main(['--ui','v3'])
        start.assert_called_once_with(network=True)

    def test_configuracao_e_diagnostico_sem_modificar_banco(self):
        from network.configuration import validate_settings
        from network.diagnostics import inspect_environment
        before=self.database.read_bytes()
        report=inspect_environment(self.settings,integrity=True)
        self.assertEqual(report['database'],'available');self.assertEqual(self.database.read_bytes(),before)
        with self.assertRaises(ValueError):validate_settings({**self.settings,'port':70000})
        with self.assertRaises(ValueError):validate_settings({**self.settings,'backup_interval_seconds':1})

    def test_teste_de_instalacao_aceita_proprio_servidor_sem_liberar_outros_pcs(self):
        settings={**self.settings,'host':'192.168.1.10','_testing':False}
        app=create_app(settings)
        own=TestClient(app,client=('192.168.1.10',40000))
        self.assertEqual(own.get('/health').status_code,401)
        other=TestClient(app,client=('192.168.1.99',40000))
        self.assertEqual(other.get('/health',headers={'X-Forwarded-For':'192.168.1.10'}).status_code,403)

    def test_sondagem_smb_em_worker_sem_ler_conteudo(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from network.desktop import ShareProbe
        app=QApplication.instance() or QApplication([]);probe=ShareProbe(None);received=[];probe.done.connect(received.append)
        with patch('network.diagnostics.probe_directory',side_effect=['available','permission_denied']) as check:
            probe.start([r'\\SERVIDOR\PRODUCOES',r'\\SERVIDOR\ARQUIVO'])
            limit=time.monotonic()+2
            while not received and time.monotonic()<limit:app.processEvents();threading.Event().wait(.005)
            self.assertEqual([s['state'] for s in received[0]],['available','permission_denied'])
            probe.start([r'\\SERVIDOR\PRODUCOES',r'\\SERVIDOR\ARQUIVO']);self.assertEqual(check.call_count,2)
        probe.stop()

    def test_smart_locate_fachada_remota_nao_varre_o_cliente(self):
        record=self.create(name='Pauta remota',count=1)
        new=self.media/'Movidos'/'Pauta remota'/'Camera'; new.mkdir(parents=True); (new/'C0000.MP4').write_bytes(b'test')
        from smart_locate import Locator,apply_updates
        runtime.SESSION=self.pc1
        events=[]
        result=Locator(r'\\SERVIDOR\PRODUCOES',progress=events.append).run()
        self.assertTrue(result.job_id)
        selected={t.key:result.options(t)[0].path for t in result.targets if result.status(t)=='Alta'}
        self.assertEqual(len(selected),2)
        apply_updates(result,selected)
        self.assertTrue(self.pc2.http('GET','/changes')['changes'])

    def test_restauracao_reseta_cursor_e_troca_senha_revoga_sessao(self):
        feed=self.pc1.http('GET','/changes?after=99999')
        self.assertTrue(feed['reset']); self.assertEqual(feed['cursor'],0)
        add_user(self.users,'pc01','outra-senha-de-teste','editor')
        with self.assertRaises(NetworkError):self.pc1.http('GET','/health')

    def test_backup_retencao_nao_remove_arquivo_manual(self):
        self.create(); directory=self.base/'outro-disco'; directory.mkdir(exist_ok=True)
        manual=directory/'pautas-manual.sqlite'; manual.write_bytes(b'nao remover')
        for i in range(3):backup_database(self.database,directory,1)
        self.assertEqual(manual.read_bytes(),b'nao remover')
        self.assertEqual(len(list(directory.glob('pautas-2*.sqlite'))),1)

    def test_migracao_copia_real_preserva_dados_e_backup_original(self):
        from config import DB_PATH
        if not DB_PATH.exists():self.skipTest('Banco real indisponível')
        import sqlite3
        self.http.__exit__(None,None,None)
        with closing(sqlite3.connect(DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as source:
            source.row_factory=sqlite3.Row
            old={table:[dict(r) for r in source.execute('SELECT * FROM '+table+' ORDER BY id')] for table in ['pautas','takes']}
            with closing(sqlite3.connect(self.database)) as target:source.backup(target)
        self.http=TestClient(create_app(self.settings)); self.http.__enter__()
        with runtime.server_context(),closing(db.get_connection()) as conn:
            conn.row_factory=sqlite3.Row
            for table,rows in old.items():
                after=[dict(r) for r in conn.execute('SELECT * FROM '+table+' ORDER BY id')]
                self.assertEqual(len(rows),len(after))
                for before,now in zip(rows,after):
                    for key,value in before.items():self.assertEqual(now['cliente' if key=='candidato' else key],value)
        self.assertTrue(list((self.base/'outro-disco').glob('antes-rede-*.sqlite')))
        self.pc1=self.client('pc01')
        results=self.pc1.rpc('buscar_pautas',dict(limite=100))
        with runtime.server_context(),closing(db.get_connection()) as conn:
            active=conn.execute('SELECT COUNT(*) FROM takes t JOIN pautas p ON p.id=t.pauta_id WHERE IFNULL(p.excluida,0)=0').fetchone()[0]
        self.assertEqual(sum(len(r['takes']) for r in results),active)


if __name__=='__main__':unittest.main()
