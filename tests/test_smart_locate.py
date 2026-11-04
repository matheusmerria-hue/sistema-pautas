import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from unittest.mock import patch

import database as db
from smart_locate import (Locator, apply_updates, undo_batch, mappings, invalidate_mappings,
                          last_batch, suffix_length, relative, safe_path)


class SmartLocateTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=Path(self.temp.name).resolve()
        self.root=self.base/'disco'; self.root.mkdir()
        self.old=self.base/'antigo'/'Gravacoes'
        self.patcher=patch.object(db,'DB_PATH',self.base/'db.sqlite'); self.patcher.start()
        db.init_database()

    def tearDown(self):
        self.patcher.stop(); self.temp.cleanup()

    def create(self,name='Pauta 001',count=3,prefix=None):
        folder=(prefix or self.old)/name
        takes=[dict(nome_arquivo=f'C{i:04}.MP4',caminho_arquivo=str(folder/'Camera 01'/f'C{i:04}.MP4'),
                    comentario=f'Comentário {i}',tags='evento',importante=True) for i in range(count)]
        db.salvar_pauta(name,'04/11/2026','Núcleo D3','Descrição',str(folder),takes)
        with closing(db.get_connection()) as conn:pid=conn.execute('SELECT MAX(id) FROM pautas').fetchone()[0]
        return pid,folder,takes

    def material(self,pid,new):
        detail=db.obter_pauta_com_takes(pid)
        folder=detail['pauta']['caminho_pasta']
        for take in detail['takes']:
            rel=relative(take['caminho_arquivo'],folder)
            dest=new.joinpath(*rel); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(b'midia simulada')
        new.mkdir(parents=True,exist_ok=True)
        return new

    def selections(self,result):
        return {t.key:result.options(t)[0].path for t in result.targets if result.status(t)=='Alta'}

    def test_uma_duas_tres_e_mais_pastas_adicionais(self):
        for depth in [1,2,3,5]:
            with self.subTest(depth=depth):
                pid,old,_=self.create(f'Pauta {depth}')
                new=self.root.joinpath(*[f'Nivel{i}' for i in range(depth)],'Gravacoes',old.name)
                self.material(pid,new)
                result=Locator(self.root,pauta_id=pid).run()
                self.assertEqual(len(self.selections(result)),4)
                self.assertEqual(result.stats['scans'],1)
                self.assertEqual(result.stats['complete_pautas'],1)

    def test_pauta_inteira_preserva_takes_comentarios_favoritos_e_undo(self):
        pid,old,_=self.create(count=20)
        data=db.obter_pauta_com_takes(pid)
        db.alternar_favorito_pauta(pid,True); db.alternar_favorito_take(data['takes'][0]['id'],True)
        before=db.obter_pauta_com_takes(pid)
        new=self.material(pid,self.root/'Backup'/'Gravacoes'/old.name)
        result=Locator(self.root).run(); batch=apply_updates(result,self.selections(result))
        after=db.obter_pauta_com_takes(pid)
        self.assertEqual(after['pauta']['caminho_pasta'],str(new))
        for left,right in zip(before['takes'],after['takes']):
            self.assertEqual({k:v for k,v in left.items() if k!='caminho_arquivo'}, {k:v for k,v in right.items() if k!='caminho_arquivo'})
            self.assertTrue(Path(right['caminho_arquivo']).is_file())
        self.assertEqual(after['pauta']['favorita'],1)
        self.assertEqual(last_batch(),batch)
        self.assertEqual(undo_batch(batch),21)
        self.assertEqual(db.obter_pauta_com_takes(pid),before)
        self.assertEqual(mappings(),[])

    def test_varias_pautas_e_nomes_repetidos(self):
        for name in ['Pauta A','Pauta B','Pauta C']:
            pid,old,_=self.create(name)
            self.material(pid,self.root/'Arquivo'/'Gravacoes'/old.name)
        result=Locator(self.root).run()
        self.assertEqual(len(self.selections(result)),12)
        self.assertEqual(result.stats['complete_pautas'],3)
        self.assertEqual(result.stats['scans'],1)
        self.assertTrue(any(c.source=='Prefixo aprendido nesta operação' for cs in result.candidates.values() for c in cs.values()))

    def test_copias_ambiguas_nao_preselecionadas(self):
        pid,old,_=self.create()
        for dest in ['Backup A','Backup B']:self.material(pid,self.root/dest/'Gravacoes'/old.name)
        result=Locator(self.root).run()
        self.assertTrue(all(result.status(t)=='Ambíguo' for t in result.targets))
        self.assertEqual(self.selections(result),{})
        target=next(t for t in result.targets if t.kind=='take')
        chosen=result.options(target)[1].path
        apply_updates(result,{target.key:chosen})
        self.assertEqual(db.obter_pauta_com_takes(pid)['takes'][0]['caminho_arquivo'],chosen)

    def test_apenas_nome_e_estrutura_parcial_exigem_revisao(self):
        pid,old,takes=self.create(count=1)
        low=self.root/'Outros'/'C0000.MP4'; low.parent.mkdir(); low.write_bytes(b'x')
        result=Locator(self.root).run()
        take=next(t for t in result.targets if t.kind=='take')
        self.assertEqual(result.status(take),'Baixa')
        partial=self.root/'Renomeada'/'Camera 01'/'C0000.MP4'; partial.parent.mkdir(parents=True); partial.write_bytes(b'x')
        result=Locator(self.root).run()
        take=next(t for t in result.targets if t.kind=='take')
        self.assertEqual(result.status(take),'Média')

    def test_nao_encontrados_e_disco_desconectado(self):
        self.create()
        result=Locator(self.root).run()
        self.assertEqual(result.stats['missing'],3)
        disconnected=Locator(self.root/'Disco inexistente').run()
        self.assertTrue(disconnected.incomplete)
        self.assertEqual(disconnected.stats['directories'],0)

    def test_diretorios_sem_permissao(self):
        pid,old,_=self.create()
        self.material(pid,self.root/'Gravacoes'/old.name)
        blocked=self.root/'Bloqueada'; blocked.mkdir()
        original=os.scandir
        def scandir(path):
            if Path(path)==blocked:raise PermissionError('acesso negado')
            return original(path)
        with patch('smart_locate.os.scandir',side_effect=scandir):result=Locator(self.root).run()
        self.assertTrue(result.incomplete); self.assertEqual(result.stats['errors'],1)
        self.assertEqual(result.stats['found'],3)

    def test_cancelamento_preserva_resultados_sem_gravar(self):
        pid,old,_=self.create(); new=self.material(pid,self.root/'Gravacoes'/old.name)
        cancel=threading.Event()
        def progress(stats):
            if stats['stage']=='Varredura compartilhada de diretórios':cancel.set()
        result=Locator(self.root,cancel,progress).run()
        self.assertTrue(result.cancelled); self.assertEqual(result.stats['found'],3)
        self.assertEqual(db.obter_pauta_com_takes(pid)['pauta']['caminho_pasta'],str(old))
        cancel.clear(); apply_updates(result,self.selections(result))
        self.assertEqual(db.obter_pauta_com_takes(pid)['pauta']['caminho_pasta'],str(new))

    def test_reutilizacao_persistente_reabertura_e_invalidacao(self):
        pid,old,_=self.create()
        self.material(pid,self.root/'Arquivo'/'Gravacoes'/old.name)
        first=Locator(self.root).run(); apply_updates(first,self.selections(first))
        self.assertEqual(len(mappings()),1)
        second,old2,_=self.create('Pauta 002')
        new2=self.material(second,self.root/'Arquivo'/'Gravacoes'/old2.name)
        db.init_database()
        result=Locator(self.root,pauta_id=second).run()
        self.assertEqual(result.stats['scans'],0)
        self.assertEqual(len(self.selections(result)),4)
        apply_updates(result,self.selections(result))
        self.assertEqual(db.obter_pauta_com_takes(second)['pauta']['caminho_pasta'],str(new2))
        invalidate_mappings(); self.assertEqual(mappings(),[])

    def test_caminhos_validos_nao_alterados(self):
        pid,old,_=self.create(prefix=self.root/'Existentes')
        self.material(pid,old)
        before=db.obter_pauta_com_takes(pid)
        result=Locator(self.root).run()
        self.assertEqual(result.targets,[]); self.assertEqual(result.stats['scans'],0)
        self.assertEqual(db.obter_pauta_com_takes(pid),before)

    def test_destino_desaparece_e_transacao_reverte_tudo(self):
        pid,old,_=self.create()
        new=self.material(pid,self.root/'Gravacoes'/old.name)
        result=Locator(self.root).run(); selections=self.selections(result)
        (new/'Camera 01'/'C0001.MP4').unlink()
        before=db.obter_pauta_com_takes(pid)
        with self.assertRaises(ValueError):apply_updates(result,selections)
        self.assertEqual(db.obter_pauta_com_takes(pid),before)
        self.assertIsNone(last_batch())

    def test_caminho_original_reaparece_ou_edicao_concorrente(self):
        pid,old,_=self.create()
        self.material(pid,self.root/'Gravacoes'/old.name)
        result=Locator(self.root).run()
        old.mkdir(parents=True)
        with self.assertRaises(ValueError):apply_updates(result,self.selections(result))
        old.rmdir()
        with closing(db.get_connection()) as conn,conn:
            conn.execute('UPDATE pautas SET caminho_pasta=? WHERE id=?',('outro',pid))
        with self.assertRaises(ValueError):apply_updates(result,self.selections(result))
        self.assertIsNone(last_batch())

    def test_cancelamento_de_atualizacao_atomicamente(self):
        pid,old,_=self.create()
        self.material(pid,self.root/'Gravacoes'/old.name)
        result=Locator(self.root).run(); before=db.obter_pauta_com_takes(pid)
        cancelled=threading.Event(); cancelled.set()
        with self.assertRaises(ValueError):apply_updates(result,self.selections(result),cancelled)
        self.assertEqual(db.obter_pauta_com_takes(pid),before)

    def test_undo_nao_sobrescreve_edicao_posterior(self):
        pid,old,_=self.create()
        self.material(pid,self.root/'Gravacoes'/old.name)
        result=Locator(self.root).run(); batch=apply_updates(result,self.selections(result))
        with closing(db.get_connection()) as conn,conn:
            conn.execute('UPDATE takes SET caminho_arquivo=? WHERE pauta_id=?',('edicao posterior',pid))
        before=db.obter_pauta_com_takes(pid)
        with self.assertRaises(ValueError):undo_batch(batch)
        self.assertEqual(db.obter_pauta_com_takes(pid),before)
        self.assertEqual(last_batch(),batch)

    def test_atualizacao_de_take_individual_aprende_prefixo(self):
        pid,old,_=self.create()
        self.material(pid,self.root/'Gravacoes'/old.name)
        take=db.obter_pauta_com_takes(pid)['takes'][0]
        result=Locator(self.root,take_id=take['id']).run()
        target=next(t for t in result.targets if t.kind=='take')
        apply_updates(result,{target.key:result.options(target)[0].path})
        self.assertEqual(len(mappings()),1)
        followup=Locator(self.root,pauta_id=pid).run()
        self.assertEqual(followup.stats['found'],2)

    def test_nao_segue_junctions_e_nao_sai_da_raiz(self):
        pid,old,_=self.create()
        outside=self.material(pid,self.base/'Fora'/'Gravacoes'/old.name)
        self.assertFalse(safe_path(outside,self.root))
        with patch('smart_locate.os.scandir', wraps=os.scandir) as scan:
            result=Locator(self.root).run()
        self.assertEqual(result.stats['found'],0)
        self.assertEqual(scan.call_count,1)
        # Sem privilégio de symlink no Windows: reparse é exercitado por entrada simulada.
        fake=unittest.mock.Mock()
        fake.is_symlink.return_value=False; fake.is_dir.return_value=True
        fake.stat.return_value=type('Stat',(),dict(st_file_attributes=0x400,st_dev=os.stat(self.root).st_dev))()
        class Entries:
            def __init__(self):self.it=iter([fake])
            def __next__(self):return next(self.it)
            def close(self):pass
        with patch('smart_locate.os.scandir',return_value=Entries()) as scan:
            Locator(self.root).run()
            self.assertEqual(scan.call_count,1)

    def test_comparacao_de_caminhos_windows(self):
        self.assertEqual(suffix_length(r'D:\Gravacoes\Pauta\Camera\C0001.MP4',r'E:\Backup\Gravacoes\Pauta\Camera\C0001.mp4'),4)
        self.assertEqual(relative(r'D:\MaterialX\take.mp4',r'D:\Material'),None)
        self.assertEqual(relative(r'D:\Material\Camera\take.mp4',r'D:\Material'),('Camera','take.mp4'))

    def test_concorrencia_opcional_limitada_a_duas_verificacoes(self):
        pid,old,_=self.create(count=40)
        self.material(pid,self.root/'Gravacoes'/old.name)
        sequential=Locator(self.root).run()
        locator=Locator(self.root,metadata_workers=20)
        parallel=locator.run()
        self.assertEqual(locator.metadata_workers,2)
        self.assertEqual(self.selections(sequential),self.selections(parallel))

    def test_interface_worker_revisao_e_paginacao(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtTest import QTest
        from ui.ui_locate import LocateDialog
        app=QApplication.instance() or QApplication([])
        pid,old,_=self.create(count=205)
        self.material(pid,self.root/'Gravacoes'/old.name)
        dialog=LocateDialog(pauta_id=pid)
        errors=[]
        with patch.object(QMessageBox,'warning',side_effect=lambda *args:errors.append(args)):
            try:
                dialog.root.setText(str(self.root)); dialog.scan()
                limit=time.monotonic()+10
                while dialog.worker.isRunning() and time.monotonic()<limit:
                    app.processEvents()
                    threading.Event().wait(.005)
                self.assertFalse(dialog.worker.isRunning())
                app.processEvents()
                self.assertEqual(errors,[])
                self.assertIsNotNone(dialog.result)
                self.assertEqual(len(dialog.selections),206)
                self.assertEqual(dialog.table.rowCount(),200)
                self.assertEqual(dialog.page.maximum(),2)
                dialog.page.setValue(2); self.assertEqual(dialog.table.rowCount(),6)
                dialog.table.item(0,0).setCheckState(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.Unchecked)
                self.assertEqual(len(dialog.selections),205)
                self.assertTrue(dialog.apply.isEnabled())
            finally:
                dialog.worker.cancel.set(); dialog.worker.wait(10000); dialog.close(); app.processEvents()

    def test_interface_leitura_nao_atualiza_e_cancelado_nao_preseleciona(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from ui.ui_locate import LocateDialog
        app=QApplication.instance() or QApplication([])
        pid,old,_=self.create(); self.material(pid,self.root/'Gravacoes'/old.name)
        result=Locator(self.root).run(); result.cancelled=True
        with patch('ui.ui_locate.MODO','LEITURA'):
            dialog=LocateDialog()
            try:
                dialog.scan_complete(result); dialog.set_busy(False)
                self.assertFalse(dialog.apply.isEnabled())
                self.assertFalse(dialog.undo.isEnabled())
                self.assertFalse(dialog.forget.isEnabled())
                self.assertEqual(dialog.selections,{})
            finally:dialog.close(); app.processEvents()

    def test_milhares_de_arquivos_uma_varredura_sem_leitura_de_conteudo(self):
        for name in ['Pauta 1','Pauta 2','Pauta 3','Pauta 4']:
            pid,old,_=self.create(name,count=500)
            self.material(pid,self.root/'Arquivo'/'2026'/'Gravacoes'/old.name)
        visited=[]; original=os.scandir; events=[]
        def scandir(path):visited.append(os.path.normcase(str(path))); return original(path)
        start=time.monotonic()
        with patch('smart_locate.os.scandir',side_effect=scandir),patch('builtins.open',side_effect=AssertionError('Não abrir mídia')):
            result=Locator(self.root,progress=events.append).run()
        elapsed=time.monotonic()-start
        self.assertEqual(result.stats['found'],2000)
        self.assertEqual(result.stats['scans'],1)
        self.assertEqual(len(visited),len(set(visited)))
        self.assertLess(len(visited),20)
        self.assertLess(len(events),elapsed*4+8)
        print(f'\nSMART_LOCATE: 2000 arquivos; {len(visited)} diretórios; 1 varredura; {elapsed:.3f}s')


if __name__=='__main__':unittest.main()
