"""Adaptador fino: a UI V3 usa exclusivamente as APIs existentes do sistema."""
from database import (init_database, listar_pautas_acervo, buscar_pautas,
    salvar_pauta, obter_pauta_com_takes, atualizar_pauta, excluir_pauta,
    atualizar_status_pauta, alternar_favorito_take, alternar_favorito_pauta,
    salvar_busca, obter_historico_buscas, obter_estatisticas)
from file_scanner import listar_arquivos_midia
from config import DB_PATH

STATUS_LABEL={"a_editar":"TRIAGEM","em_producao":"CORTE","finalizada":"PRONTO"}
STATUS_VALUE={v:k for k,v in STATUS_LABEL.items()}
TAKE_LABEL={"usar":"USAR","talvez":"TALVEZ","ignorar":"IGNORAR"}

def initialize(): init_database()
def display_pauta(p):
    p=dict(p); p.update({"title":p.get("nome_pauta") or "Sem título","owner":p.get("cliente") or "—",
        "date":p.get("data_pauta") or "—","status":STATUS_LABEL.get(p.get("status_pauta") or "a_editar","TRIAGEM"),
        "category":p.get("cliente") or "—","desc":p.get("descricao_inicial") or "Sem descrição"})
    return p
def home(cliente="",periodo="Todos",status="Todos"):
    return [display_pauta(p) for p in listar_pautas_acervo(cliente,periodo,status)]
def search(term="",date_from="",date_to="",owner="",favorite_pautas=False,offset=0,limite=None):
    result=buscar_pautas(term,date_from,date_to,owner,favorite_pautas,limite=limite,offset=offset)
    from network.client import Page
    return Page([{"pauta":display_pauta(x["pauta"]),"takes":x["takes"]} for x in result],getattr(result,'has_more',False))
def detail(pauta_id):
    data=obter_pauta_com_takes(pauta_id)
    if data: data["pauta"]=display_pauta(data["pauta"])
    return data
def create(**values): return salvar_pauta(**values)
def update(**values): return atualizar_pauta(**values)
def delete(pauta_id,**kw): return excluir_pauta(pauta_id,**kw)
def set_status(pauta_id,label,**kw): return atualizar_status_pauta(pauta_id,STATUS_VALUE[label],**kw)
def favorite_take(take_id,on,**kw): return alternar_favorito_take(take_id,on,**kw)
def favorite_pauta(pauta_id,on,**kw): return alternar_favorito_pauta(pauta_id,on,**kw)
def scan(folder): return listar_arquivos_midia(folder)
def history(limit=8): return obter_historico_buscas(limit, detalhado=True)
def save_search(term, **filters): return salvar_busca(term, **filters)
def stats(): return obter_estatisticas()
