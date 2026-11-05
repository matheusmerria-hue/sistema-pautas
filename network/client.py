"""HTTP sem SQLite local e sem envio de mídia. Credenciais só na memória."""
import hashlib
import ipaddress
import json
import socket
import ssl
import threading
import time
from urllib import request, error, parse
import uuid
from . import runtime


class NetworkError(RuntimeError):pass
class EditConflict(NetworkError):pass


class Page(list):
    def __init__(self,items,has_more=False):super().__init__(items); self.has_more=has_more


class ApiSession:
    def __init__(self,url,ca_file=None,transport=None):
        parsed=parse.urlsplit(url.strip())
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            raise NetworkError('Informe http://servidor:porta ou https://servidor:porta, sem usuário ou caminho.')
        addresses=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM) if transport is None else []
        if any(not ipaddress.ip_address(a[4][0]).is_private for a in addresses):raise NetworkError('Use um servidor da rede local.')
        self.url=url.rstrip('/'); self.token=None; self.role='reader'; self.username=None; self.transport=transport
        self.context=ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self,req,fp,code,msg,headers,newurl):return None
        self.opener=request.build_opener(request.ProxyHandler({}),request.HTTPSHandler(context=self.context),NoRedirect())
        self.pending={}; self.pending_lock=threading.Lock(); self.online=True
        self.names_cache=None
        self.last_revisions={}

    def http(self,method,path,payload=None):
        headers={'Accept':'application/json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8') if payload is not None else None
        if data is not None:headers['Content-Type']='application/json'
        try:
            if self.transport:
                response=self.transport.request(method,path,json=payload,headers=headers)
                status=response.status_code; body=response.json()
            else:
                req=request.Request(self.url+path,data=data,headers=headers,method=method)
                with self.opener.open(req,timeout=12) as response:
                    status=response.status; body=json.load(response)
            self.online=True
        except error.HTTPError as exc:
            status=exc.code
            try:body=json.load(exc)
            except Exception:body={'detail':'Resposta inválida do servidor.'}
        except (error.URLError,OSError,TimeoutError) as exc:
            self.online=False
            raise NetworkError('Conexão com o servidor perdida. O conteúdo não salvo foi mantido. Verifique a rede e tente novamente; não será criado um banco local.') from exc
        except (ValueError,UnicodeError) as exc:
            raise NetworkError('O endereço não respondeu como servidor de pautas. Confira o hostname/IP, a porta e a versão.') from exc
        if status>=300:
            message=body.get('detail','Não foi possível concluir a operação.')
            if not isinstance(message,str):message='O servidor rejeitou os dados enviados.'
            if status==409:raise EditConflict(message)
            raise NetworkError(message)
        return body

    def login(self,username,password):
        data=self.http('POST','/login',dict(username=username,password=password))
        self.token=data['token']; self.role=data['role']
        health=self.http('GET','/health')
        if health.get('api_version')!=1 or self.role not in ('reader','editor','admin'):
            self.token=None;raise NetworkError('Versão ou perfil incompatível com este cliente. Atualize os dois componentes.')
        self.username=username
        return health

    def rpc(self,operation,values,expected=None):
        if operation=='listar_clientes' and self.names_cache and time.monotonic()-self.names_cache[0]<15:
            return list(self.names_cache[1])
        payload=dict(operation=operation,kwargs=values,expected=dict(expected or {}))
        fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        write=operation in ('salvar_pauta','atualizar_pauta','excluir_pauta','atualizar_status_pauta',
                            'alternar_favorito_pauta','alternar_favorito_take','salvar_busca')
        with self.pending_lock:
            if write and len(self.pending)>=1024 and fingerprint not in self.pending:
                raise NetworkError('Há muitas gravações sem confirmação. Confira a conexão e os resultados antes de enviar novos dados.')
            payload['request_id']=self.pending.setdefault(fingerprint,uuid.uuid4().hex) if write else uuid.uuid4().hex
        try:data=responsive(lambda:self.http('POST','/rpc',payload))
        except EditConflict:
            with self.pending_lock:self.pending.pop(fingerprint,None)
            raise
        with self.pending_lock:self.pending.pop(fingerprint,None)
        runtime.LAST_REVISIONS.update(data.get('revisions',{}))
        self.last_revisions=data.get('revisions',{})
        value=data['value']
        if operation=='listar_clientes':self.names_cache=(time.monotonic(),value)
        elif operation in ('salvar_pauta','atualizar_pauta'):self.names_cache=None
        return Page(value,data.get('has_more',False)) if operation in ('buscar_pautas','listar_pautas_acervo') else value

    def all_results(self):
        offset=0
        while True:
            page=self.rpc('buscar_pautas',dict(limite=200,offset=offset))
            yield from page
            if not page.has_more:break
            offset+=len(page)


def responsive(operation):
    """Compatibilidade com os slots existentes; I/O em worker, event loop Qt ativo."""
    try:
        from PySide6.QtCore import QCoreApplication,QThread,QObject,Signal,QEventLoop
        app=QCoreApplication.instance()
        if not app or QThread.currentThread()!=app.thread():return operation()
    except ImportError:return operation()
    class Completed(QObject):done=Signal()
    signal=Completed(); loop=QEventLoop(); signal.done.connect(loop.quit)
    result=[]
    def run():
        try:result.append((True,operation()))
        except BaseException as exc:result.append((False,exc))
        signal.done.emit()
    worker=threading.Thread(target=run,daemon=True)
    runtime.ACTIVE_CALLS+=1
    try:
        worker.start(); loop.exec(); worker.join()
    finally:runtime.ACTIVE_CALLS-=1
    if not result[0][0]:raise result[0][1]
    return result[0][1]


def locate(root,cancel,progress,pauta_id,take_id,workers):
    from smart_locate import Result,Target,Candidate
    session=runtime.SESSION
    job_id=session.http('POST','/locate/start',dict(root=root,pauta_id=pauta_id,take_id=take_id,workers=workers))['job_id']
    sent_cancel=False
    while True:
        if cancel.is_set() and not sent_cancel:
            session.http('POST','/locate/'+job_id+'/cancel',{}); sent_cancel=True
        data=session.http('GET','/locate/'+job_id)
        metadata={k:data.get(k) for k in ('status','started_at','finished_at')}
        if data['stats']:progress({**data['stats'],'job_id':job_id,'job_status':metadata['status'],
                                   'started_at':metadata['started_at'],'finished_at':metadata['finished_at']})
        if data['finished']:break
        # Espera cancelável entre consultas, no worker; nenhum polling na thread da UI.
        if sent_cancel:threading.Event().wait(.5)
        else:cancel.wait(.5)
    if data['error']:raise NetworkError(data['error'])
    result=Result(data['root']); result.stats={**data['stats'],'job_id':job_id,'job_status':data.get('status'),
        'started_at':data.get('started_at'),'finished_at':data.get('finished_at')}; result.cancelled=data['cancelled']; result.incomplete=data['incomplete']
    offset=0
    while True:
        if offset:data=session.http('GET',f'/locate/{job_id}?offset={offset}')
        for item in data['items']:
            t=Target(**item['target']); result.targets.append(t)
            result.candidates[t.key]={c['path']:Candidate(**c) for c in item['options']}
            if item['truncated']:result.truncated.add(t.key)
        offset+=len(data['items'])
        if offset>=data['total']:break
    result.job_id=job_id
    return result
