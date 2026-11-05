from contextlib import contextmanager
from pathlib import Path
import os


@contextmanager
def exclusive_instance(database):
    path=Path(str(database)+'.server.lock'); path.parent.mkdir(parents=True,exist_ok=True)
    handle=open(path,'a+b'); handle.seek(0); handle.write(b'1'); handle.flush(); handle.seek(0)
    locked=False
    try:
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            locked=True
        except OSError as error:raise ValueError('O servidor já está em execução. Pare o serviço antes de restaurar ou iniciar outra instância.') from error
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_UN)
        handle.close()
