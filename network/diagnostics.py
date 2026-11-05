"""Sondagens pontuais: banco somente leitura e uma entrada por raiz de mídia."""
from contextlib import closing
from datetime import datetime,timezone
import os
from pathlib import Path
import sqlite3
import threading
import time


def probe_directory(path):
    try:
        with os.scandir(path) as entries:next(entries,None)
        return 'available'
    except PermissionError:return 'permission_denied'
    except (FileNotFoundError,NotADirectoryError):return 'missing'
    except OSError:return 'unavailable'


def inspect_environment(settings,integrity=False):
    database=Path(settings['database'])
    state='new' if not database.exists() else 'unavailable'
    if database.exists():
        try:
            with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as conn:
                conn.execute('SELECT id FROM pautas LIMIT 1').fetchone()
                state='available'
                if integrity and (conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or conn.execute('PRAGMA foreign_key_check').fetchall()):state='integrity_error'
        except sqlite3.Error:state='unavailable'
    media=[dict(name=r.get('name',r['share']),share=r['share'],state=probe_directory(r['local'])) for r in settings['media_roots']]
    return dict(checked_at=datetime.now(timezone.utc).isoformat(),database=state,media=media)


class Diagnostics:
    def __init__(self,settings):self.settings=settings; self.lock=threading.Lock(); self.cached=None; self.checked=0
    def status(self):
        with self.lock:
            if self.cached is None or time.monotonic()-self.checked>=30:
                self.cached=inspect_environment(self.settings); self.checked=time.monotonic()
            return self.cached
