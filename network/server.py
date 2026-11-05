"""API LAN autenticada. Execute um único processo; SQLite permanece local."""
from contextlib import asynccontextmanager, closing
import hashlib
import inspect
import ipaddress
import json
import logging
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

import database as db
from .backup import backup_database, BackupScheduler
from .media import MediaRoots
from .security import Auth
from .storage import TransactionConnection, WRITE_LOCK, init_network_storage, check_expected, Conflict
from .runtime import server_context
from .jobs import LocateJobs
from .configuration import load_settings,validate_settings
from .diagnostics import Diagnostics

READS={'listar_clientes','listar_pautas_acervo','buscar_pautas','obter_pauta_com_takes',
       'obter_estatisticas','obter_historico_buscas','obter_top_palavras'}
WRITES={'salvar_pauta','atualizar_pauta','excluir_pauta','atualizar_status_pauta',
        'alternar_favorito_pauta','alternar_favorito_take','salvar_busca'}


class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username:str=Field(min_length=1,max_length=80)
    password:str=Field(min_length=1,max_length=1024)


class RPC(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operation:str=Field(max_length=80)
    kwargs:dict=Field(default_factory=dict)
    expected:dict=Field(default_factory=dict)
    request_id:str=Field(default_factory=lambda:uuid.uuid4().hex,max_length=80)


class MediaReference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    root_id:str=Field(min_length=1,max_length=80)
    relative_path:str=Field(max_length=32000)


def required_revisions(operation,values):
    required=[]
    if operation in {'atualizar_pauta','excluir_pauta','atualizar_status_pauta','alternar_favorito_pauta'}:
        required.append(('pautas',int(values['pauta_id'])))
    if operation=='alternar_favorito_take':required.append(('takes',int(values['take_id'])))
    if operation=='atualizar_pauta':required.extend(('takes',int(t['id'])) for t in values.get('takes',[]))
    return required


def validate_values(operation,values,media,conn):
    values=media.inbound(values)
    for field in ['nome_pauta','cliente']:
        if operation in ('salvar_pauta','atualizar_pauta') and field in values and (not isinstance(values[field],str) or not values[field].strip() or len(values[field])>500):
            raise ValueError('Preencha '+field+' com até 500 caracteres.')
    if values.get('status_pauta') is not None and values['status_pauta'] not in ('a_editar','em_producao','finalizada'):
        raise ValueError('Status da pauta inválido.')
    if 'takes' in values:
        if not isinstance(values['takes'],(list,tuple)) or len(values['takes'])>20000:raise ValueError('Quantidade de takes inválida.')
        ids=[]
        for take in values['takes']:
            if take.get('status_take','talvez') not in ('usar','talvez','ignorar'):raise ValueError('Status de take inválido.')
            if operation=='atualizar_pauta':
                tid=int(take['id']); ids.append(tid)
                row=conn.execute('SELECT pauta_id FROM takes WHERE id=?',(tid,)).fetchone()
                if not row or row[0]!=values['pauta_id']:raise ValueError('Take não pertence à pauta editada.')
            else:
                from config import EXTENSOES_VALIDAS
                if not take.get('nome_arquivo') or not take.get('caminho_arquivo'):raise ValueError('Take sem nome ou caminho.')
                if Path(take['caminho_arquivo']).suffix.lower() not in EXTENSOES_VALIDAS:raise ValueError('Extensão de mídia não permitida.')
        if len(ids)!=len(set(ids)):raise ValueError('Takes duplicados no lote.')
    return values


def create_app(settings):
    settings=validate_settings(settings)
    database_path=Path(settings['database']).resolve()
    if str(settings['database']).startswith('\\\\'):raise ValueError('SQLite deve permanecer em disco local do servidor.')
    media=MediaRoots(settings['media_roots']); auth=Auth(settings['users_file'])
    if not Path(settings['users_file']).is_file():raise ValueError('Cadastre os usuários antes de iniciar o servidor.')
    if media.to_share(str(database_path)) or media.to_share(str(Path(settings['users_file']).resolve())):
        raise ValueError('Banco e credenciais devem ficar fora das raízes de mídia compartilhadas.')
    allowed=[ipaddress.ip_network(value,strict=False) for value in settings.get('allowed_clients',['127.0.0.1/32','::1/128'])]
    # Não aceitar uma configuração que exponha a API a toda a internet.
    if any(net.prefixlen==0 or not net.is_private for net in allowed):raise ValueError('Autorize apenas IPs/sub-redes privadas da rede local.')
    jobs=LocateJobs(media)
    diagnostics=Diagnostics(settings)
    @asynccontextmanager
    async def lifespan(app):
        from .instance import exclusive_instance
        with exclusive_instance(database_path):
            scheduler=None
            try:
                db.DB_PATH=database_path
                with server_context():
                    if database_path.exists():backup_database(database_path,settings['backup_directory'],settings.get('backup_retention',30),'antes-rede')
                    db.init_database(); init_network_storage(settings.get('wal',True))
                scheduler=BackupScheduler(database_path,settings['backup_directory'],settings.get('backup_interval_seconds',3600),settings.get('backup_retention',30))
                scheduler.start(); app.state.ready=True
                yield
            finally:
                app.state.ready=False; jobs.stop()
                if scheduler:
                    scheduler.stop()
                    with server_context(),closing(db.get_connection()) as conn:conn.execute('PRAGMA wal_checkpoint(PASSIVE)')
    app=FastAPI(title='Sistema de Pautas LAN',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.jobs=jobs; app.state.media=media
    @app.middleware('http')
    async def network_boundary(request,call_next):
        peer=request.client.host if request.client else ''
        try:
            address=ipaddress.ip_address(peer);address=getattr(address,'ipv4_mapped',None) or address
            permitted=any(address in net for net in allowed)
        except ValueError:permitted=peer=='testclient' and settings.get('_testing',False)
        if not permitted:return JSONResponse({'detail':'Computador não autorizado na configuração de rede.'},status_code=403)
        if request.method=='POST':
            # Limite real também para pedidos chunked, sem confiar só no cabeçalho.
            size=0; chunks=[]
            async for chunk in request.stream():
                size+=len(chunk)
                if size>32*1024*1024:return JSONResponse({'detail':'Solicitação excede 32 MB.'},status_code=413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
        return await call_next(request)
    def user(request:Request):
        header=request.headers.get('authorization','')
        session=auth.verify(header[7:]) if header.startswith('Bearer ') else None
        if not session:raise HTTPException(401,'Sessão expirada ou não autenticada. Entre novamente.')
        return session
    def editor(session=Depends(user)):
        if session['role'] not in ('editor','admin'):raise HTTPException(403,'Seu usuário tem permissão somente de leitura.')
        return session
    @app.exception_handler(Conflict)
    async def conflict_handler(request,error):return JSONResponse({'detail':str(error)},status_code=409)
    @app.exception_handler(ValueError)
    async def value_handler(request,error):return JSONResponse({'detail':str(error)},status_code=400)
    @app.post('/login')
    def login(body:Login,request:Request):
        try:token,role=auth.login(body.username,body.password,request.client.host)
        except ValueError as error:raise HTTPException(401,str(error))
        return dict(token=token,role=role)
    @app.get('/health')
    def health(session=Depends(user)):
        return dict(ok=True,role=session['role'],api_version=1)
    @app.get('/media-roots')
    def roots(session=Depends(user)):
        return [dict(id=r['id'],name=r.get('name',r['share']),share=r['share']) for r in media.roots]
    @app.post('/media/resolve')
    def resolve_media(body:MediaReference,session=Depends(user)):
        return dict(path=media.resolve(body.root_id,body.relative_path,client=True))
    @app.get('/status')
    def status(session=Depends(user)):
        return dict(api='connected',**diagnostics.status())
    @app.get('/changes')
    def changes(after:int=0,session=Depends(user)):
        with server_context(),closing(db.get_connection()) as conn:
            rows=conn.execute('SELECT seq,entity,record_id,pauta_id,revision FROM network_changes WHERE seq>? ORDER BY seq LIMIT 201',(max(0,after),)).fetchall()
            latest=conn.execute('SELECT IFNULL(MAX(seq),0) FROM network_changes').fetchone()[0]
        return dict(cursor=latest if len(rows)>200 or after>latest else (rows[-1][0] if rows else max(0,after)),reset=len(rows)>200 or after>latest,
                    changes=[dict(zip(['seq','entity','id','pauta_id','revision'],r)) for r in rows[:200]])
    @app.post('/rpc')
    def rpc(body:RPC,session=Depends(user)):
        operation=body.operation
        if operation not in READS|WRITES|{'scan_media','init_database'}:raise HTTPException(404,'Operação não disponível.')
        write=operation in WRITES
        if write and operation!='salvar_busca' and session['role'] not in ('editor','admin'):raise HTTPException(403,'Usuário somente de leitura.')
        if operation=='init_database':return dict(value=None,revisions={})
        lock=WRITE_LOCK if write else __import__('contextlib').nullcontext()
        with lock,server_context(),closing(db.get_connection()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
                fingerprint=hashlib.sha256(json.dumps([operation,body.kwargs,body.expected],sort_keys=True).encode()).hexdigest()
                if write:
                    prior=conn.execute('SELECT username,fingerprint,response FROM network_requests WHERE request_id=?',(body.request_id,)).fetchone()
                    if prior:
                        if prior[:2]!=(session['username'],fingerprint):raise ValueError('Identificador de operação já utilizado.')
                        return json.loads(prior[2])
                values=dict(body.kwargs)
                has_more=False
                if operation=='scan_media':
                    from file_scanner import listar_arquivos_midia
                    with server_context(TransactionConnection(conn)):value=listar_arquivos_midia(media.to_local(values['caminho_pasta']))
                else:
                    func=getattr(db,operation)
                    try:inspect.signature(func).bind(**values)
                    except TypeError as error:raise ValueError('Parâmetros inválidos para esta operação.') from error
                    if write:
                        check_expected(conn,required_revisions(operation,values),body.expected)
                        values=validate_values(operation,values,media,conn)
                    if operation in ('buscar_pautas','listar_pautas_acervo'):
                        limit=min(200,max(1,int(values.get('limite') or 100)))
                        values.update(limite=limit+1,offset=max(0,int(values.get('offset') or 0)))
                    with server_context(TransactionConnection(conn)):value=func(**values)
                    if operation in ('buscar_pautas','listar_pautas_acervo'):
                        has_more=len(value)>limit; value=value[:limit]
                revisions={}
                for table,rid in required_revisions(operation,values) if write else []:
                    row=conn.execute(f'SELECT revision FROM {table} WHERE id=?',(rid,)).fetchone()
                    if row:revisions[f'{table}:{rid}']=row[0]
                response=dict(value=media.outbound(value),revisions=revisions,has_more=has_more)
                if write:
                    conn.execute('INSERT INTO network_requests VALUES (?,?,?,?,?)',(body.request_id,session['username'],fingerprint,json.dumps(response),time.time()))
                    conn.execute('DELETE FROM network_requests WHERE created<?',(time.time()-86400,))
                    conn.execute('DELETE FROM network_changes WHERE seq < (SELECT IFNULL(MAX(seq),0)-50000 FROM network_changes)')
                conn.commit()
                if write:logging.info('Operação persistida user=%s operation=%s request=%s',session['username'],operation,body.request_id)
                return response
            except Exception:
                conn.rollback();raise
    @app.post('/locate/start')
    def locate_start(body:dict,session=Depends(editor)):
        job_id=jobs.start(body['root'],body.get('pauta_id'),body.get('take_id'),min(2,max(1,int(body.get('workers',1)))))
        logging.info('Smart Locate solicitado user=%s job=%s',session['username'],job_id)
        return dict(job_id=job_id)
    @app.get('/locate/{job_id}')
    def locate_status(job_id:str,offset:int=0,session=Depends(user)):
        try:return jobs.status(job_id,max(0,offset))
        except KeyError:raise HTTPException(404,'Resultado expirou. Execute a busca novamente.')
    @app.post('/locate/{job_id}/cancel')
    def locate_cancel(job_id:str,session=Depends(editor)):
        try:jobs.cancel(job_id)
        except KeyError:raise HTTPException(404,'Busca não encontrada.')
        return dict(ok=True)
    @app.post('/locate/{job_id}/apply')
    def locate_apply(job_id:str,body:dict,session=Depends(editor)):
        try:batch=jobs.apply(job_id,body.get('selections',[]))
        except KeyError:raise HTTPException(404,'Resultado expirou. Execute a busca novamente.')
        return dict(batch=batch)
    @app.post('/locate-undo')
    def locate_undo(session=Depends(editor)):
        from smart_locate import last_batch, undo_batch
        with WRITE_LOCK,server_context():
            batch=last_batch()
            if not batch:raise ValueError('Não há atualizações para desfazer.')
            count=undo_batch(batch)
            logging.info('Smart Locate desfeito user=%s batch=%s count=%s',session['username'],batch,count)
            return dict(count=count)
    @app.post('/locate-forget')
    def locate_forget(session=Depends(editor)):
        from smart_locate import invalidate_mappings
        with WRITE_LOCK,server_context():invalidate_mappings()
        logging.info('Mapeamentos invalidados user=%s',session['username'])
        return dict(ok=True)
    return app


def run(config_path):
    import uvicorn
    settings=load_settings(config_path)
    log=Path(settings.get('log_directory',str(Path(config_path).parent/'logs'))); log.mkdir(parents=True,exist_ok=True)
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(log/'server.log',maxBytes=5_000_000,backupCount=5,encoding='utf-8')])
    uvicorn.run(create_app(settings),host=settings.get('host','127.0.0.1'),port=int(settings.get('port',8000)),
                proxy_headers=False,workers=1,http='h11',ws='none',loop='asyncio',
                ssl_certfile=settings.get('tls_cert'),ssl_keyfile=settings.get('tls_key'),access_log=False)
