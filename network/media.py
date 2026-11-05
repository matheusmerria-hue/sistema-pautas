"""Tradução por componentes: caminhos do servidor ↔ compartilhamentos UNC."""
import os
import re
from pathlib import Path, PureWindowsPath, PurePosixPath


def path_object(value):
    return PureWindowsPath(value) if '\\' in value or (len(value)>1 and value[1]==':') else PurePosixPath(value)


def under(value, prefix):
    try:
        rel=path_object(value).relative_to(path_object(prefix))
        if '..' in rel.parts:raise ValueError('Caminho contém navegação para pasta superior.')
        return rel.parts
    except ValueError:
        return None


class MediaRoots:
    def __init__(self, roots):
        self.roots=[{**root,'id':root.get('id') or f'media_{index+1}'} for index,root in enumerate(roots)]
        if not roots:raise ValueError('Configure pelo menos uma raiz de mídia.')
        ids=set()
        for root in self.roots:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',root['id']) or root['id'] in ids:raise ValueError('Identificadores das raízes devem ser únicos, usando letras, números, hífen ou sublinhado.')
            ids.add(root['id'])
            if not Path(root['local']).is_absolute():raise ValueError('Raiz local precisa ser absoluta.')
            if root['local'].startswith('\\\\'):raise ValueError('Use os HDs locais do servidor como raízes de varredura.')
            share=PureWindowsPath(root['share'])
            if not str(share).startswith('\\\\') or not share.anchor:raise ValueError('Configure um compartilhamento UNC para cada HD.')

    def reference(self,value):
        for root in sorted(self.roots,key=lambda r:len(r['local']),reverse=True):
            for prefix in [root['local'],root['share'],*root.get('legacy',[])]:
                rel=under(value,prefix)
                if rel is not None:return dict(root_id=root['id'],relative_path=str(PureWindowsPath(*rel)) if rel else '')
        raise ValueError('Caminho sem raiz de mídia configurada.')

    def resolve(self,root_id,relative_path,client=False):
        rel=path_object(relative_path)
        if rel.anchor or '..' in rel.parts or '\x00' in relative_path:raise ValueError('Informe somente um caminho relativo seguro.')
        root=next((r for r in self.roots if r['id']==root_id),None)
        if root is None:raise ValueError('Raiz de mídia desconhecida.')
        local=self.to_local(str(Path(root['local']).joinpath(*rel.parts)))
        return str(PureWindowsPath(root['share']).joinpath(*rel.parts)) if client else local

    def to_local(self,value):
        if not isinstance(value,str) or not value or '\x00' in value:raise ValueError('Caminho inválido.')
        if '..' in path_object(value).parts:raise ValueError('Caminho contém navegação para pasta superior.')
        for root in sorted(self.roots,key=lambda r:len(r['local']),reverse=True):
            for base in [root['share'],root['local']]:
                rel=under(value,base)
                if rel is None:continue
                candidate=Path(root['local']).joinpath(*rel)
                # Também impede saída por symlinks/junctions em componentes existentes.
                base_real=Path(root['local']).resolve()
                try:candidate.resolve().relative_to(base_real)
                except ValueError:raise ValueError('Caminho fora da raiz autorizada.')
                return str(candidate)
        raise ValueError('Caminho fora dos HDs/compartilhamentos configurados.')

    def to_share(self,value):
        if not value:return ''
        for root in sorted(self.roots,key=lambda r:len(r['local']),reverse=True):
            for prefix in [root['local'],root['share'],*root.get('legacy',[])]:
                rel=under(value,prefix)
                if rel is not None:return str(PureWindowsPath(root['share']).joinpath(*rel))
        # Nunca entregar D:\... para o cliente abrir um disco local por engano.
        return ''

    def outbound(self,value):
        if isinstance(value,list):return [self.outbound(v) for v in value]
        if not isinstance(value,dict):return value
        out={k:self.outbound(v) for k,v in value.items()}
        for key in ['caminho_pasta','caminho_arquivo']:
            if key in out:
                out[key]=self.to_share(value[key])
                if value[key] and not out[key]:out['_unmapped_'+key]=True
        return out

    def inbound(self,value):
        if isinstance(value,list):return [self.inbound(v) for v in value]
        if not isinstance(value,dict):return value
        return {k:self.to_local(v) if k in ('caminho_pasta','caminho_arquivo') else self.inbound(v)
                for k,v in value.items() if not k.startswith('_')}
