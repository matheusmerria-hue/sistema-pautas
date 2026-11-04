"""Regressão da migração: python -B -m unittest discover -s tests -v."""
import csv
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

import database as db
import exporter


class ClientesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path_patch = patch.object(db, 'DB_PATH', self.root / 'pautas.db')
        self.path_patch.start()
        db.init_database()

    def tearDown(self):
        self.path_patch.stop()
        self.temp.cleanup()

    def create(self, cliente, date='04/11/2026', takes=True):
        db.salvar_pauta('Cobertura', date, cliente, 'Descrição', '/midia',
                       [{'nome_arquivo': 'take.mp4', 'caminho_arquivo': '/midia/take.mp4',
                         'comentario': 'Entrevista', 'tags': 'evento', 'importante': True}] if takes else [])
        with closing(db.get_connection()) as conn:
            return conn.execute('SELECT MAX(id) FROM pautas').fetchone()[0]

    def test_criacao_busca_parcial_e_todos(self):
        self.create('Núcleo D3'); self.create('Governo MS')
        for term in ['Núcleo', 'NUCLEO', '  núcleo  ', 'd3']:
            self.assertEqual(len(db.buscar_pautas(cliente=term)), 1)
        self.assertEqual(len(db.buscar_pautas(cliente='')), 2)
        self.assertEqual(len(db.listar_pautas_acervo(cliente='NUCLEO')), 1)
        self.assertEqual(len(db.buscar_pautas(palavra_chave='nucleo')), 1)

    def test_normalizacao_sem_duplicar_nomes(self):
        self.create('Núcleo D3'); self.create('  NUCLEO   d3 ')
        self.assertEqual({r['pauta']['cliente'] for r in db.buscar_pautas()}, {'Núcleo D3'})
        self.create('Câmara Municipal / D3 & Cia. 2026')
        self.assertEqual(len(db.buscar_pautas(cliente='câmara municipal /')), 1)

    def test_edicao_isolada_e_vinculos(self):
        first=self.create('Núcleo D3'); other=self.create('Núcleo D3')
        before=db.obter_pauta_com_takes(first)
        db.alternar_favorito_take(before['takes'][0]['id'], True)
        db.alternar_favorito_pauta(first, True)
        db.atualizar_pauta(first, 'Cobertura', '04/11/2026', 'FIEMS', 'Descrição', [])
        after=db.obter_pauta_com_takes(first)
        self.assertEqual(after['pauta']['cliente'], 'FIEMS')
        self.assertEqual(after['pauta']['favorita'], 1)
        self.assertEqual(after['takes'][0]['favorito'], 1)
        for key in ['id','pauta_id','comentario','caminho_arquivo','tags','marcado_como_importante']:
            self.assertEqual(before['takes'][0][key], after['takes'][0][key])
        self.assertEqual(db.obter_pauta_com_takes(other)['pauta']['cliente'], 'Núcleo D3')

    def test_clientes_disponiveis_no_acervo(self):
        self.create('Núcleo D3'); self.create('Governo MS')
        self.create('  NUCLEO   d3 ')
        removed = self.create('Cliente removido')
        db.excluir_pauta(removed)
        self.assertEqual(db.listar_clientes(), ['Governo MS', 'Núcleo D3'])
        self.create('FIEMS')
        self.assertEqual(db.listar_clientes(), ['FIEMS', 'Governo MS', 'Núcleo D3'])

    def test_filtros_combinados(self):
        wanted=self.create('Núcleo D3'); self.create('Núcleo D3','01/10/2026'); self.create('Governo MS')
        db.alternar_favorito_pauta(wanted, True)
        take=db.obter_pauta_com_takes(wanted)['takes'][0]
        db.alternar_favorito_take(take['id'], True)
        result=db.buscar_pautas(cliente='NUCLEO', palavra_chave='Entrevista', data_inicial='2026-11-01', data_final='2026-11-30', somente_pautas_favoritas=True)
        self.assertEqual([r['pauta']['id'] for r in result], [wanted])
        self.assertTrue(result[0]['takes'][0]['comentario'])
        self.assertEqual(result[0]['takes'][0]['favorito'], 1)
        self.assertEqual(len(db.buscar_pautas(data_inicial='01/11/2026',data_final='30/11/2026')),2)

    def test_historico_com_filtros_e_legado(self):
        db.salvar_busca('antiga')
        filters=dict(cliente='Núcleo', data_inicial='2026-11-01', somente_favoritos=True)
        db.salvar_busca('', **filters)
        db.salvar_busca('antiga', cliente='Governo MS')
        entries=db.obter_historico_buscas(detalhado=True)
        self.assertEqual(entries[1],dict(termo='', **filters))
        self.assertIn({'termo':'antiga'},entries)
        self.assertIn('antiga',db.obter_historico_buscas())

    def test_exportacoes(self):
        self.create('Núcleo D3'); self.create('Governo MS'); self.create('Núcleo D3',takes=False)
        results=db.buscar_pautas(cliente='nucleo')
        for func,name in [(exporter.exportar_resultados_json,'results.json'), (exporter.exportar_resultados_csv,'results.csv')]:
            func(self.root/name, results)
        content=json.loads((self.root/'results.json').read_text(encoding='utf-8'))
        self.assertEqual(len(content),2)
        self.assertEqual({r['pauta']['cliente'] for r in content},{'Núcleo D3'})
        with (self.root/'results.csv').open(encoding='utf-8-sig',newline='') as file:
            rows=list(csv.DictReader(file,delimiter=';'))
        self.assertEqual(len(rows),2); self.assertEqual({r['cliente'] for r in rows},{'Núcleo D3'})
        exporter.exportar_json(self.root/'all.json'); exporter.exportar_csv(self.root/'all.csv')
        self.assertEqual(len(json.loads((self.root/'all.json').read_text(encoding='utf-8'))),3)
        self.assertIn('cliente',(self.root/'all.csv').read_text(encoding='utf-8-sig').splitlines()[0])

    def test_validacao_e_compatibilidade(self):
        with self.assertRaises(ValueError): self.create('   ')
        db.salvar_pauta(nome_pauta='Legado',data_pauta='',candidato='Soraya',descricao='',caminho_pasta='',takes=[])
        self.assertEqual(len(db.buscar_pautas(candidato='Soraya')),1)
        self.assertEqual(db.obter_estatisticas(cliente='soraya')['total_pautas'],1)
        self.assertIn('pautas_por_cliente',db.obter_estatisticas())

    def test_migracao_idempotente_com_backup(self):
        self.create('Vander'); self.create('Soraya')
        db.salvar_busca('antiga')
        with closing(db.get_connection()) as conn:
            conn.execute('ALTER TABLE pautas RENAME COLUMN cliente TO candidato')
            conn.execute('ALTER TABLE historico_buscas DROP COLUMN filtros')
            before=conn.execute('SELECT * FROM pautas ORDER BY id').fetchall()
            takes=conn.execute('SELECT * FROM takes ORDER BY id').fetchall()
        db.init_database(); db.init_database()
        with closing(db.get_connection()) as conn:
            self.assertEqual(conn.execute('SELECT * FROM pautas ORDER BY id').fetchall(),before)
            self.assertEqual(conn.execute('SELECT * FROM takes ORDER BY id').fetchall(),takes)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(len(list(self.root.glob('*.bak'))),1)
        self.assertEqual(len(db.buscar_pautas(cliente='Vander')),1)
        self.assertEqual(len(db.buscar_pautas(cliente='Soraya')),1)
        self.assertEqual(db.obter_historico_buscas(detalhado=True),[{'termo':'antiga'}])

    def test_migracao_copia_do_banco_real(self):
        from config import DB_PATH
        if not DB_PATH.exists(): self.skipTest('Banco real indisponível')
        with closing(sqlite3.connect(DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as source:
            before={table:source.execute(f'SELECT * FROM {table} ORDER BY id').fetchall() for table in ['pautas','takes','historico_buscas']}
            with closing(sqlite3.connect(db.DB_PATH)) as target: source.backup(target)
        db.init_database(); db.init_database()
        with closing(db.get_connection()) as conn:
            for table in ['pautas','takes']:
                self.assertEqual(conn.execute(f'SELECT * FROM {table} ORDER BY id').fetchall(),before[table])
            rows=conn.execute('SELECT id,termo,data_busca FROM historico_buscas ORDER BY id').fetchall()
            self.assertEqual(rows,[r[:3] for r in before['historico_buscas']])
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_interfaces_texto_historico_e_filtros(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        with patch.dict(os.environ, {'LOCALAPPDATA':str(self.root)}):
            from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox
            from ui.ui_create import CreatePautaWindow
            from ui.ui_search import SearchPautaWindow, EditPautaPopup
            from ui.ui_home import HomeWindow
            from ui_v3.app import Workstation
        app=QApplication.instance() or QApplication([])
        first=self.create('Núcleo D3'); self.create('Governo MS')
        detail=db.obter_pauta_com_takes(first)
        windows=[]
        with patch.object(QMessageBox,'critical',side_effect=AssertionError('Erro inesperado na interface')):
            try:
                create=CreatePautaWindow(); windows.append(create)
                self.assertIsInstance(create.input_cliente,QLineEdit)
                edit=EditPautaPopup(detail['pauta'],detail['takes']); windows.append(edit)
                self.assertEqual(edit.input_cliente.text(),'Núcleo D3')
                search=SearchPautaWindow(); windows.append(search)
                self.assertEqual(search.input_cliente.refresh_clients(), ['Governo MS','Núcleo D3'])
                self.assertEqual(search.input_cliente.refresh_clients('NUCLEO'), ['Núcleo D3'])
                self.assertEqual(search.input_cliente.refresh_clients('inexistente'), [])
                search.input_cliente.setText('Governo MS')
                search.input_cliente.completer().activated[str].emit('Núcleo D3')
                self.assertEqual(search.input_cliente.text(), 'Núcleo D3')
                filters=dict(termo='',cliente='nucleo',data_inicial='2026-11-01',data_final='2026-11-30',somente_comentados=True,somente_favoritos=True,somente_pautas_favoritas=True)
                db.alternar_favorito_pauta(first,True); db.alternar_favorito_take(detail['takes'][0]['id'],True)
                search.reutilizar_busca(filters)
                self.assertEqual(len(search.resultados_exportaveis),1)
                search.executar_busca(); self.assertEqual(db.obter_historico_buscas(detalhado=True)[0],filters)
                home=HomeWindow(); windows.append(home)
                self.assertIsInstance(home.input_cliente_acervo,QLineEdit)
                self.assertEqual(home.input_cliente_acervo.refresh_clients(), ['Governo MS','Núcleo D3'])
                v3=Workstation(); windows.append(v3)
                self.assertIsInstance(v3.editor.owner,QLineEdit)
                self.assertEqual(v3.search.owner.refresh_clients('nucleo'), ['Núcleo D3'])
                v3.editor.load(first); self.assertEqual(v3.editor.owner.text(),'Núcleo D3')
                v3.editor.new(); self.assertEqual(v3.editor.owner.text(),'')
                v3.search.load_history(); v3.search.restore_history(1)
                self.assertEqual(len(v3.search.results_export),1)
            finally:
                for window in windows:
                    if hasattr(window,'search_timer'):window.search_timer.stop()
                    window.close()
                    if hasattr(window,'media_loader'):window.media_loader.pool.waitForDone(6500)
                app.processEvents()


if __name__=='__main__': unittest.main()
