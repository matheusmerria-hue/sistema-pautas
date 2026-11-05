"""Conexão por operação, CAS por revisão e feed incremental no próprio SQLite."""
from contextlib import closing
import logging
import sqlite3
import threading
import database as db
from .runtime import CONNECTION

WRITE_LOCK=threading.RLock()


class TransactionConnection:
    def __init__(self,connection):object.__setattr__(self,'connection',connection)
    def __getattr__(self,name):return getattr(self.connection,name)
    def __setattr__(self,name,value):setattr(self.connection,name,value)
    def commit(self):pass
    def close(self):pass


def wal_supported():
    v=sqlite3.sqlite_version_info
    return v>=(3,51,3) or (v[:2]==(3,50) and v>=(3,50,7)) or (v[:2]==(3,44) and v>=(3,44,6))


def init_network_storage(wal=True):
    with closing(db.get_connection()) as conn,conn:
        mode='WAL' if wal and wal_supported() else 'DELETE'
        conn.execute('PRAGMA journal_mode='+mode)
        if wal and mode!='WAL':logging.warning('SQLite %s: usando DELETE; atualize SQLite para habilitar WAL corrigido.',sqlite3.sqlite_version)
        conn.execute('PRAGMA wal_autocheckpoint=1000')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS network_changes (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT NOT NULL,
                record_id INTEGER NOT NULL, pauta_id INTEGER, revision INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS network_requests (
                request_id TEXT PRIMARY KEY, username TEXT NOT NULL, fingerprint TEXT NOT NULL,
                response TEXT NOT NULL, created REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS takes_pauta_index ON takes(pauta_id);
            CREATE INDEX IF NOT EXISTS pautas_acervo_index ON pautas(excluida,data_pauta,id);
            CREATE INDEX IF NOT EXISTS network_requests_created_index ON network_requests(created);
        ''')
        for table in ['pautas','takes']:
            if 'revision' not in {r[1] for r in conn.execute('PRAGMA table_info('+table+')')}:
                conn.execute('ALTER TABLE '+table+' ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
            parent='NEW.id' if table=='pautas' else 'NEW.pauta_id'
            conn.executescript(f'''
                CREATE TRIGGER IF NOT EXISTS {table}_network_insert AFTER INSERT ON {table}
                BEGIN INSERT INTO network_changes(entity,record_id,pauta_id,revision)
                    VALUES('{table}',NEW.id,{parent},NEW.revision); END;
                CREATE TRIGGER IF NOT EXISTS {table}_network_update AFTER UPDATE ON {table}
                WHEN NEW.revision=OLD.revision
                BEGIN UPDATE {table} SET revision=OLD.revision+1 WHERE id=NEW.id;
                    INSERT INTO network_changes(entity,record_id,pauta_id,revision)
                    VALUES('{table}',NEW.id,{parent},OLD.revision+1); END;
            ''')


def check_expected(conn,required,revisions):
    for table,record_id in required:
        key=f'{table}:{record_id}'
        value=revisions.get(key)
        if not isinstance(value,int):raise Conflict('Recarregue o registro antes de editar. Revisão original ausente.')
        row=conn.execute(f'SELECT revision FROM {table} WHERE id=?',(record_id,)).fetchone()
        if not row or row[0]!=value:raise Conflict('Outro usuário alterou este registro. Seu texto foi preservado; recarregue e compare antes de salvar.')


class Conflict(ValueError):pass
