"""Fachada compartilhada: clientes nunca abrem SQLite, nem em falha de conexão."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import inspect

SESSION=None
SERVER_CONTEXT=ContextVar('pautas_server_context',default=False)
CONNECTION=ContextVar('pautas_request_connection',default=None)
LAST_REVISIONS={}
ACTIVE_CALLS=0


def remote():return SESSION is not None and not SERVER_CONTEXT.get()


@contextmanager
def server_context(connection=None):
    local=SERVER_CONTEXT.set(True); token=CONNECTION.set(connection)
    try:yield
    finally:CONNECTION.reset(token); SERVER_CONTEXT.reset(local)


class Expected(dict):
    def __init__(self,refs):
        self.refs=refs
        super().__init__((key,record.get('revision')) for key,record in refs.items())


def expected(pauta=None,takes=()):
    refs={}
    if pauta:refs['pautas:'+str(pauta['id'])]=pauta
    for take in takes:refs['takes:'+str(take['id'])]=take
    return Expected(refs)


def route(func):
    signature=inspect.signature(func)
    @wraps(func)
    def call(*args,**kwargs):
        revisions=kwargs.pop('_expected',None)
        if not remote():return func(*args,**kwargs)
        if func.__name__ in ('salvar_pauta','atualizar_pauta','excluir_pauta','atualizar_status_pauta',
                             'alternar_favorito_pauta','alternar_favorito_take'):
            from .client import NetworkError
            if SESSION.role=='reader':raise NetworkError('Usuário somente de leitura.')
            if not SESSION.online:raise NetworkError('Servidor indisponível. Aguarde a reconexão; seu texto foi mantido.')
        if 'candidato' in kwargs and 'cliente' in signature.parameters:
            legacy=kwargs.pop('candidato')
            kwargs['cliente']='' if legacy=='Todos' else legacy
        bound=signature.bind(*args,**kwargs); bound.apply_defaults()
        values=dict(bound.arguments)
        for name,param in signature.parameters.items():
            if param.kind==inspect.Parameter.VAR_KEYWORD:values.update(values.pop(name,{}))
        session=SESSION
        result=session.rpc(func.__name__,values,revisions)
        if isinstance(revisions,Expected):
            for key,record in revisions.refs.items():
                if key in session.last_revisions:record['revision']=session.last_revisions[key]
        return result
    return call
