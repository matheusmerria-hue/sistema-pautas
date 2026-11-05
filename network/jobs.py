"""Um localizador compartilhado, até oito resultados temporários e cancelamento remoto."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import uuid
from dataclasses import asdict
from datetime import datetime,timezone
import logging
from smart_locate import Locator, apply_updates, undo_batch, last_batch, invalidate_mappings
from .runtime import server_context
from .storage import WRITE_LOCK


class LocateJobs:
    def __init__(self,media):
        self.media=media; self.jobs={}; self.lock=threading.RLock()
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='locate-server')

    def start(self,root,pauta_id=None,take_id=None,workers=1):
        root=self.media.to_local(root); key=(root,pauta_id,take_id)
        with self.lock:
            for job_id,job in list(self.jobs.items()):
                if job['finished'] and time.monotonic()-job['created']>1800:del self.jobs[job_id]
                elif job['key']==key and (not job['finished'] or (job['result'] and not job.get('applied') and
                     not job['result'].cancelled and not job['result'].incomplete and time.monotonic()-job['created']<30)):return job_id
            if any(not j['finished'] for j in self.jobs.values()):raise ValueError('Há uma localização em andamento. Aguarde a conclusão para iniciar outra raiz.')
            if len(self.jobs)>=8:
                oldest=min(self.jobs,key=lambda k:self.jobs[k]['created']); del self.jobs[oldest]
            job_id=uuid.uuid4().hex
            job=dict(key=key,cancel=threading.Event(),stats={},result=None,error=None,finished=False,created=time.monotonic(),
                     status='queued',started_at=None,finished_at=None)
            self.jobs[job_id]=job
        def scan():
            with self.lock:
                job['status']='running';job['started_at']=datetime.now(timezone.utc).isoformat()
            logging.info('Smart Locate iniciado job=%s',job_id)
            try:
                with server_context():
                    locator=Locator(root,job['cancel'],lambda s:self.progress(job_id,s),pauta_id,take_id,workers)
                    result=locator.run()
                with self.lock:job['result']=result
            except Exception as error:
                with self.lock:job['error']=str(error) or type(error).__name__
            finally:
                with self.lock:
                    job['finished']=True;job['finished_at']=datetime.now(timezone.utc).isoformat()
                    job['status']='failed' if job['error'] is not None else ('cancelled' if job['result'].cancelled else 'completed')
                logging.info('Smart Locate concluído job=%s status=%s',job_id,job['status'])
        self.pool.submit(scan)
        return job_id

    def progress(self,job_id,stats):
        with self.lock:self.jobs[job_id]['stats']=dict(stats)

    def status(self,job_id,offset=0,limit=200):
        with self.lock:
            job=self.jobs[job_id]; result=job['result']
            out=dict(id=job_id,status=job['status'],finished=job['finished'],stats=dict(job['stats']),error=job['error'],
                     cancel_requested=job['cancel'].is_set(),started_at=job['started_at'],finished_at=job['finished_at'])
            if result:
                targets=result.targets[offset:offset+limit]
                out.update(root=self.media.to_share(result.root),cancelled=result.cancelled,incomplete=result.incomplete,
                           total=len(result.targets),items=[dict(target=asdict(t),options=[asdict(c) for c in result.options(t)],
                                truncated=t.key in result.truncated) for t in targets])
                for item in out['items']:
                    item['target']['old']=self.media.to_share(item['target']['old']) or '(caminho antigo no servidor)'
                    for c in item['options']:c['path']=self.media.to_share(c['path'])
            return out

    def cancel(self,job_id):
        with self.lock:
            job=self.jobs[job_id]
            if not job['finished']:
                job['cancel'].set();job['status']='cancelling'
        logging.info('Cancelamento de Smart Locate solicitado job=%s',job_id)

    def apply(self,job_id,selections):
        with self.lock:
            job=self.jobs[job_id]
            if not job['finished'] or not job['result']:raise ValueError('Aguarde o resultado da localização.')
            result=job['result']
        choices={(item['kind'],item['id']):self.media.to_local(item['path']) for item in selections}
        with WRITE_LOCK,server_context():batch=apply_updates(result,choices)
        with self.lock:job['applied']=True
        logging.info('Vínculos de Smart Locate atualizados job=%s batch=%s count=%s',job_id,batch,len(choices))
        return batch

    def stop(self):
        with self.lock:
            for job in self.jobs.values():job['cancel'].set()
        self.pool.shutdown(wait=True,cancel_futures=True)
