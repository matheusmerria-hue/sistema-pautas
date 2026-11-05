"""Exportar todas as páginas da consulta sem ler SQLite no cliente."""
import database


def filtered_results(filters,commented=False,favorite=False,skip_empty=False):
    results=[]; offset=0
    while True:
        page=database.buscar_pautas(**filters,limite=200,offset=offset)
        for item in page:
            takes=item['takes']
            if commented:takes=[t for t in takes if (t.get('comentario') or '').strip()]
            if favorite:takes=[t for t in takes if t.get('favorito')]
            term=(filters.get('palavra_chave') or '').lower()
            if term:
                matching=[t for t in takes if any(term in (t.get(k) or '').lower() for k in ['nome_arquivo','comentario','tags'])]
                if matching:takes=matching
            if not takes and (commented or favorite or skip_empty):continue
            results.append({'pauta':item['pauta'],'takes':takes})
        if not getattr(page,'has_more',False):return results
        offset+=len(page)
