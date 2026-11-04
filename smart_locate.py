"""Localização somente por metadados. Uma varredura compartilhada, sem mídia/hashes."""
from collections import defaultdict, deque
from contextlib import closing, nullcontext
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import threading
import time
import uuid
import sqlite3

from database import get_connection


def init_storage():
    with closing(get_connection()) as conn, conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS locate_batches (
                id TEXT PRIMARY KEY, created TEXT NOT NULL, undone INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS locate_changes (
                batch_id TEXT NOT NULL, kind TEXT NOT NULL, record_id INTEGER NOT NULL,
                old_path TEXT NOT NULL, new_path TEXT NOT NULL,
                PRIMARY KEY(batch_id, kind, record_id)
            );
            CREATE TABLE IF NOT EXISTS locate_mappings (
                id INTEGER PRIMARY KEY, old_prefix TEXT NOT NULL, new_prefix TEXT NOT NULL,
                batch_id TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(old_prefix, new_prefix)
            );
        ''')


def pure(path):
    return PureWindowsPath(path) if '\\' in path or (len(path) > 1 and path[1] == ':') else PurePosixPath(path)


def parts(path):
    p = pure(path)
    return p.parts[1:] if p.anchor else p.parts


def suffix_length(old, new):
    count = 0
    for a, b in zip(reversed(parts(old)), reversed(parts(new))):
        if a.casefold() != b.casefold(): break
        count += 1
    return count


def relative(path, parent):
    try:
        return pure(path).relative_to(pure(parent)).parts
    except (ValueError, TypeError):
        return None


def exists(path, kind):
    return bool(path) and (os.path.isdir(path) if kind == 'pauta' else os.path.isfile(path))


def safe_path(path, root):
    """Não segue symlinks/junctions abaixo da raiz escolhida nem sai de seu volume."""
    try:
        path = os.path.abspath(path); root = os.path.abspath(root)
        if os.path.commonpath([path, root]) != root: return False
        root_dev = os.stat(root).st_dev
        current = root
        for component in Path(path).relative_to(root).parts:
            current = os.path.join(current, component)
            info = os.lstat(current)
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                return False
            if info.st_dev != root_dev: return False
        return True
    except (OSError, ValueError):
        return False


@dataclass(frozen=True)
class Target:
    kind: str
    id: int
    pauta_id: int
    old: str
    title: str

    @property
    def key(self): return (self.kind, self.id)


@dataclass
class Candidate:
    path: str
    score: int
    confidence: str
    source: str


@dataclass
class Result:
    root: str
    targets: list = field(default_factory=list)
    candidates: dict = field(default_factory=lambda: defaultdict(dict))
    truncated: set = field(default_factory=set)
    stats: dict = field(default_factory=lambda: dict(analyzed=0, invalid_pautas=0, pending=0,
        found=0, missing=0, ambiguous=0, directories=0, errors=0, elapsed=0., scans=0,
        complete_pautas=0, partial_pautas=0, stage='Identificando caminhos inválidos'))
    cancelled: bool = False
    incomplete: bool = False

    def options(self, target):
        return sorted(self.candidates.get(target.key, {}).values(), key=lambda c: (-c.score, c.path))

    def status(self, target):
        options = self.candidates.get(target.key,{})
        if not options: return 'Não encontrado'
        best_score=max(c.score for c in options.values())
        best=[c for c in options.values() if c.score==best_score]
        if len(best)>1 or target.key in self.truncated: return 'Ambíguo'
        if best[0].confidence=='Alta' and sum(c.confidence=='Alta' for c in options.values())>1:
            return 'Ambíguo'
        return best[0].confidence

    def summarize(self):
        states = [self.status(t) for t in self.targets if t.kind == 'take']
        self.stats.update(found=sum(s not in ('Não encontrado','Ambíguo') for s in states),
                          missing=states.count('Não encontrado'), ambiguous=states.count('Ambíguo'))
        groups = defaultdict(list)
        for target in self.targets: groups[target.pauta_id].append(self.status(target))
        complete = partial = 0
        for states in groups.values():
            n = sum(s not in ('Não encontrado', 'Ambíguo') for s in states)
            complete += n == len(states)
            partial += 0 < n < len(states)
        self.stats.update(complete_pautas=complete, partial_pautas=partial)


def load_records(pauta_id=None, take_id=None):
    with closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        condition = 'AND p.id = ?' if pauta_id is not None else ''
        params = [pauta_id] if pauta_id is not None else []
        if take_id is not None:
            condition += ' AND p.id = (SELECT pauta_id FROM takes WHERE id = ?)'
            params.append(take_id)
        pautas = [dict(r) for r in conn.execute('SELECT p.id,p.nome_pauta,p.caminho_pasta FROM pautas p WHERE IFNULL(p.excluida,0)=0 '+condition, params)]
        query = 'SELECT t.id,t.pauta_id,t.nome_arquivo,t.caminho_arquivo FROM takes t JOIN pautas p ON p.id=t.pauta_id WHERE IFNULL(p.excluida,0)=0 '+condition
        if take_id is not None: query += ' AND t.id = ?'; params = params + [take_id]
        takes = [dict(r) for r in conn.execute(query, params)]
    return pautas, takes


def mappings():
    with closing(get_connection()) as conn:
        return conn.execute('SELECT id,old_prefix,new_prefix FROM locate_mappings WHERE active=1 ORDER BY id DESC').fetchall()


def invalidate_mappings(ids=None):
    with closing(get_connection()) as conn, conn:
        if ids is None: conn.execute('UPDATE locate_mappings SET active=0')
        else: conn.executemany('UPDATE locate_mappings SET active=0 WHERE id=?', [(i,) for i in ids])


class Locator:
    """Um worker sequencial. Índice somente dos alvos e até 32 opções por vínculo."""
    def __init__(self, root, cancel=None, progress=None, pauta_id=None, take_id=None, metadata_workers=1):
        self.root = os.path.realpath(os.path.abspath(root))
        self.cancel = cancel or threading.Event()
        self.progress = progress or (lambda stats: None)
        self.pauta_id = pauta_id; self.take_id = take_id
        self.metadata_workers=max(1,min(2,int(metadata_workers)))
        self._executor=None
        self.result = Result(self.root)
        self._checks = {}; self._last = 0; self._start = time.monotonic()
        self.groups = defaultdict(list); self.folders = {}; self.learned = defaultdict(set)
        self._rules=set(); self._rule_queue=[]; self._processing_rules=False

    def tick(self, force=False):
        now = time.monotonic()
        if force or now - self._last >= .25:
            self.result.stats['elapsed'] = now - self._start
            self.result.summarize()
            self.progress(dict(self.result.stats)); self._last = now

    def check(self, path, kind):
        key = (os.path.normcase(path), kind)
        if key not in self._checks: self._checks[key] = exists(path,kind)
        return self._checks[key]

    def add(self, target, path, confidence, source):
        if self.cancel.is_set(): return
        path = os.path.abspath(path)
        options = self.result.candidates[target.key]
        score=suffix_length(target.old,path)
        if options:
            best=max(c.score for c in options.values())
            if score<best and confidence!='Alta': return
            if score>best:
                if not self.check(path,target.kind) or not safe_path(path,self.root):return
                # Descartar coincidências fracas evita N×M opções para C0001.MP4.
                keep={p:c for p,c in options.items() if c.confidence=='Alta'}
                if not keep:self.result.truncated.discard(target.key)
                options.clear(); options.update(keep)
        if len(options) >= 32 and path not in options:
            self.result.truncated.add(target.key); return
        if not self.check(path,target.kind) or not safe_path(path,self.root): return
        candidate = Candidate(path,score,confidence,source)
        previous = options.get(path)
        rank={'Baixa':0,'Média':1,'Alta':2}
        if previous is None or rank[confidence] > rank[previous.confidence]: options[path] = candidate

    def recover_folder(self, pauta_id, new, source):
        old = self.folders[pauta_id]
        key=os.path.normcase(new)
        if len(self.learned[pauta_id])>=32 and key not in self.learned[pauta_id]:
            for target in self.groups[pauta_id]: self.result.truncated.add(target.key)
            return
        if key in self.learned[pauta_id] or not safe_path(new,self.root) or not self.check(new,'pauta'): return
        self.learned[pauta_id].add(key)
        # Caminho da pauta + estrutura relativa é a evidência principal.
        confidence = 'Alta' if suffix_length(old,new) >= len(parts(old)) else 'Média'
        validated=[]
        paths=((target,os.path.join(new,*rel)) for target in self.groups[pauta_id]
               if (rel:=relative(target.old,old)) is not None)
        if self._executor:
            # Janela limitada; nunca cria milhares de futures de uma vez.
            pending=deque()
            def validate(target,path):
                return exists(path,target.kind) and safe_path(path,self.root)
            for target,path in paths:
                if self.cancel.is_set():break
                pending.append((target,path,self._executor.submit(validate,target,path)))
                if len(pending)>=self.metadata_workers*2:
                    t,p,future=pending.popleft()
                    if future.result():validated.append((t,p))
            for t,p,future in pending:
                if self.cancel.is_set():future.cancel()
                elif future.result():validated.append((t,p))
        else:
            for target,path in paths:
                if self.cancel.is_set(): return
                if self.check(path,target.kind) and safe_path(path,self.root): validated.append((target,path))
        # Pasta de pauta e todos os caminhos relativos preservados, mesmo após reorganização.
        files=[t for t in self.groups[pauta_id] if t.kind=='take']
        if files and sum(t.kind=='take' for t,p in validated)==len(files): confidence='Alta'
        for target,path in validated: self.add(target,path,confidence,source)
        if confidence=='Alta':
            rule=derive_mapping(old,new)
            if rule not in self._rules:
                self._rules.add(rule); self._rule_queue.append(rule)
            if not self._processing_rules:
                self._processing_rules=True
                try:
                    while self._rule_queue and not self.cancel.is_set():
                        before,after=self._rule_queue.pop()
                        for pid,folder in self.folders.items():
                            rel=relative(folder,before)
                            if rel is not None and self.groups[pid]:
                                self.recover_folder(pid,os.path.join(after,*rel),'Prefixo aprendido nesta operação')
                finally:self._processing_rules=False
        self.tick()

    def run(self):
        pool=ThreadPoolExecutor(max_workers=self.metadata_workers) if self.metadata_workers>1 else nullcontext()
        with pool as executor:
            self._executor=executor
            return self._run()

    def _run(self):
        r=self.result
        pautas,takes=load_records(self.pauta_id,self.take_id)
        for p in pautas:
            self.folders[p['id']]=p['caminho_pasta'] or ''
        # Cache só de caminhos cadastrados/consultados, nunca de toda a unidade.
        for kind,records,column in [('pauta',pautas,'caminho_pasta'),('take',takes,'caminho_arquivo')]:
            for record in records:
                if self.cancel.is_set(): break
                r.stats['analyzed'] += kind=='take'
                path=record[column] or ''
                if not self.check(path,kind):
                    pid=record['id'] if kind=='pauta' else record['pauta_id']
                    target=Target(kind,record['id'],pid,path,record.get('nome_pauta') or record.get('nome_arquivo') or '')
                    r.targets.append(target); self.groups[pid].append(target)
                    r.stats['invalid_pautas'] += kind=='pauta'
                    r.stats['pending'] += kind=='take'
                self.tick()
        if self.cancel.is_set(): return self.finish()
        if not r.targets: return self.finish()
        if not os.path.isdir(self.root):
            r.incomplete=True; r.stats['errors']+=1; return self.finish()
        r.stats['stage']='Reutilizando mapeamentos e caminhos relativos'; self.tick(True)
        known=mappings()
        for target in r.targets:
            for _,old,new in known:
                if self.cancel.is_set(): return self.finish()
                rel=relative(target.old,old)
                if rel is not None: self.add(target,os.path.join(new,*rel),'Alta','Mapeamento confirmado')
        # Reutilização resolve sem varrer quando todos os vínculos são conhecidos.
        if r.targets and all(len(r.options(t))==1 for t in r.targets): return self.finish()
        folders_by_name=defaultdict(list); files_by_name=defaultdict(list)
        for pid,old in self.folders.items():
            if not self.groups[pid] or not parts(old): continue
            folders_by_name[parts(old)[-1].casefold()].append(pid)
            # Primeiro testa sufixos diretamente sob a raiz selecionada.
            components=parts(old)
            for n in range(len(components),0,-1):
                if self.cancel.is_set(): return self.finish()
                self.recover_folder(pid,os.path.join(self.root,*components[-n:]),'Estrutura relativa')
        for target in r.targets:
            if target.kind=='take' and parts(target.old): files_by_name[parts(target.old)[-1].casefold()].append(target)
        r.stats['stage']='Varredura compartilhada de diretórios'; r.stats['scans']=1; self.tick(True)
        # DFS com iteradores: memória proporcional à profundidade, sem guardar a árvore.
        stack=[]
        def enter(path):
            if self.cancel.is_set(): return
            try:
                iterator=os.scandir(path)
                stack.append(iterator); r.stats['directories']+=1
                for pid in folders_by_name.get(os.path.basename(path).casefold(),()):
                    self.recover_folder(pid,path,'Pasta da pauta + caminhos relativos')
            except OSError:
                r.stats['errors']+=1; r.incomplete=True
        enter(self.root)
        try: root_dev=os.stat(self.root).st_dev
        except OSError:
            for iterator in stack: iterator.close()
            r.incomplete=True; r.stats['errors']+=1; return self.finish()
        try:
            while stack and not self.cancel.is_set():
                try: entry=next(stack[-1])
                except StopIteration: stack.pop().close(); continue
                except OSError:
                    r.stats['errors']+=1; r.incomplete=True; stack.pop().close(); continue
                try:
                    if entry.is_symlink(): continue
                    if entry.is_dir(follow_symlinks=False):
                        info=entry.stat(follow_symlinks=False)
                        # DirEntry.stat pode omitir st_dev (zero) no Windows.
                        if getattr(info,'st_file_attributes',0)&0x400 or (info.st_dev and info.st_dev!=root_dev): continue
                        enter(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        for target in files_by_name.get(entry.name.casefold(),()):
                            suffix=suffix_length(target.old,entry.path)
                            level='Alta' if suffix>=len(parts(target.old)) and suffix>=2 else ('Média' if suffix>=2 else 'Baixa')
                            self.add(target,entry.path,level,'Sufixo do caminho' if suffix>=2 else 'Somente nome: revisão obrigatória')
                except OSError:
                    r.stats['errors']+=1; r.incomplete=True
                self.tick()
        finally:
            for iterator in stack: iterator.close()
        return self.finish()

    def finish(self):
        r=self.result; r.cancelled=self.cancel.is_set()
        r.stats['stage']='Cancelado; resultados parciais preservados' if r.cancelled else ('Concluído com áreas inacessíveis' if r.incomplete else 'Concluído')
        self.tick(True)
        return r


def table_column(kind):
    if kind=='pauta': return 'pautas','caminho_pasta'
    if kind=='take': return 'takes','caminho_arquivo'
    raise ValueError('Tipo de vínculo inválido')


def derive_mapping(old,new):
    count=suffix_length(old,new)
    if not count: return old,new
    a=pure(old); b=pure(new)
    for _ in range(count-1): a=a.parent; b=b.parent
    return str(a),str(b)


def apply_updates(result, selections, cancel=None):
    """Seleções explícitas key->path. Tudo ou nada, com controle de concorrência."""
    if not selections:raise ValueError('Selecione pelo menos um vínculo para atualizar.')
    batch=uuid.uuid4().hex; targets={t.key:t for t in result.targets}
    folder_selections={targets[key].pauta_id for key in selections if targets[key].kind=='pauta'}
    with closing(get_connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT INTO locate_batches(id,created) VALUES (?,?)',(batch,datetime.now().isoformat()))
        for key,path in selections.items():
            if cancel and cancel.is_set(): raise ValueError('Atualização cancelada; nenhuma alteração aplicada.')
            target=targets[key]; table,column=table_column(target.kind)
            if path not in result.candidates.get(key,{}): raise ValueError('Destino não pertence aos resultados revisados.')
            current=conn.execute(f'SELECT {column} FROM {table} WHERE id=?',(target.id,)).fetchone()
            if not current or current[0]!=target.old: raise ValueError('Um vínculo foi alterado por outra operação. Execute a localização novamente.')
            active=conn.execute('SELECT 1 FROM pautas WHERE id=? AND IFNULL(excluida,0)=0',(target.pauta_id,)).fetchone()
            if not active:raise ValueError('A pauta foi excluída após a busca; nenhuma alteração aplicada.')
            if target.kind=='take':
                parent=conn.execute('SELECT pauta_id FROM takes WHERE id=?',(target.id,)).fetchone()
                if parent[0]!=target.pauta_id:raise ValueError('O vínculo do take mudou; execute a localização novamente.')
            if exists(current[0],target.kind): raise ValueError('O caminho original voltou a funcionar; nenhuma alteração aplicada.')
            if not safe_path(path,result.root) or not exists(path,target.kind): raise ValueError('Destino indisponível ou fora da raiz selecionada.')
            conn.execute(f'UPDATE {table} SET {column}=? WHERE id=?',(path,target.id))
            conn.execute('INSERT INTO locate_changes VALUES (?,?,?,?,?)',(batch,target.kind,target.id,target.old,path))
            candidate=result.candidates[key][path]
            if candidate.confidence=='Alta' and (target.kind=='pauta' or target.pauta_id not in folder_selections):
                before=target.old if target.kind=='pauta' else str(pure(target.old).parent)
                after=path if target.kind=='pauta' else str(pure(path).parent)
                old,new=derive_mapping(before,after)
                conn.execute('''INSERT INTO locate_mappings(old_prefix,new_prefix,batch_id,active) VALUES (?,?,?,1)
                    ON CONFLICT(old_prefix,new_prefix) DO UPDATE SET active=1,batch_id=excluded.batch_id''',(old,new,batch))
        if cancel and cancel.is_set(): raise ValueError('Atualização cancelada; nenhuma alteração aplicada.')
    return batch


def last_batch():
    with closing(get_connection()) as conn:
        row=conn.execute('SELECT id FROM locate_batches WHERE undone=0 ORDER BY created DESC LIMIT 1').fetchone()
        return row[0] if row else None


def undo_batch(batch, cancel=None):
    with closing(get_connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT undone FROM locate_batches WHERE id=?',(batch,)).fetchone()
        if not row or row[0]: raise ValueError('Lote inexistente ou já desfeito.')
        changes=conn.execute('SELECT kind,record_id,old_path,new_path FROM locate_changes WHERE batch_id=?',(batch,)).fetchall()
        for kind,record_id,old,new in changes:
            if cancel and cancel.is_set(): raise ValueError('Cancelado; desfazimento não aplicado.')
            table,column=table_column(kind)
            current=conn.execute(f'SELECT {column} FROM {table} WHERE id=?',(record_id,)).fetchone()
            if not current or current[0]!=new: raise ValueError('Vínculo alterado após a recuperação; lote não desfeito.')
            conn.execute(f'UPDATE {table} SET {column}=? WHERE id=?',(old,record_id))
        conn.execute('UPDATE locate_batches SET undone=1 WHERE id=?',(batch,))
        conn.execute('UPDATE locate_mappings SET active=0 WHERE batch_id=?',(batch,))
    return len(changes)
