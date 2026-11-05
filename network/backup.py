from contextlib import closing
from datetime import datetime
import logging
from pathlib import Path
import sqlite3
import threading
import re


def verify(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup não passou no teste de integridade.')
        if conn.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Backup tem vínculos inválidos.')


def backup_database(source,directory,retention=30,prefix='pautas'):
    source=Path(source); directory=Path(directory)
    if not source.exists():raise ValueError('Banco de origem não existe.')
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/(prefix+'-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite')
    temporary=target.with_suffix('.partial')
    try:
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(temporary)) as dst:
            src.backup(dst,pages=256,sleep=.05)
        verify(temporary); temporary.replace(target)
        owned=[p for p in directory.glob(prefix+'-*.sqlite')
               if re.fullmatch(re.escape(prefix)+r'-\d{8}-\d{6}-\d{6}\.sqlite',p.name) and p.resolve()!=source.resolve()]
        for old in sorted(owned,reverse=True)[max(1,retention):]:old.unlink()
        logging.info('Backup consistente concluído: %s',target.name)
        return target
    finally:
        if temporary.exists():temporary.unlink()


def restore_database(backup,target):
    """Somente com o serviço parado; o CLI exige confirmação explícita."""
    target=Path(target); verify(backup)
    if Path(backup).resolve()==target.resolve():raise ValueError('Origem e destino devem ser diferentes.')
    if target.exists():backup_database(target,target.parent/'antes-restauracao',100,'resgate')
    temporary=target.with_suffix('.restoring')
    with closing(sqlite3.connect(Path(backup).resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(temporary)) as dst:
        src.backup(dst)
    verify(temporary)
    # Não restaurar sobre um WAL ainda presente: o serviço pode estar em uso.
    if Path(str(target)+'-wal').exists() or Path(str(target)+'-shm').exists():
        temporary.unlink(); raise ValueError('Pare o serviço e feche todas as conexões antes de restaurar.')
    temporary.replace(target)


class BackupScheduler:
    def __init__(self,source,directory,interval,retention):
        self.stop_event=threading.Event()
        def loop():
            while not self.stop_event.wait(max(60,interval)):
                try:backup_database(source,directory,retention)
                except Exception:logging.exception('Falha no backup automático')
        self.thread=threading.Thread(target=loop,name='pautas-backup',daemon=True)
    def start(self):self.thread.start()
    def stop(self):self.stop_event.set(); self.thread.join(30)
