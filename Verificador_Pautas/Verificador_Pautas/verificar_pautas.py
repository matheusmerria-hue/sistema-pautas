"""Verificador local de pautas. Python 3.10+; somente biblioteca padrão."""
import datetime as dt
import json
import os
from pathlib import Path
import queue
import re
import threading
import unicodedata
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText


def normalizar(s):
    s = unicodedata.normalize('NFKD', str(s)).casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in s if not unicodedata.combining(c))).split())


def separar_data(nome):
    for patron, ordem in [(r'^(\d{4})[-_. ](\d{2})[-_. ](\d{2})(?!\d)', 'ymd'),
                           (r'^(\d{2})[-_. ](\d{2})[-_. ](\d{4})(?!\d)', 'dmy'),
                           (r'^(\d{4})(\d{2})(\d{2})(?!\d)', 'ymd')]:
        m = re.match(patron, nome.strip())
        if m:
            a,b,c = map(int,m.groups())
            try:
                data = dt.date(a,b,c) if ordem == 'ymd' else dt.date(c,b,a)
                return data, normalizar(nome.strip()[m.end():])
            except ValueError:
                pass
    return None, normalizar(nome)


def tecnica(nome):
    n = normalizar(nome)
    return n in {'bruto','brutos','private','m4root','clip','dcim','avchd','bdmv','stream'} or bool(re.fullmatch(r'(card|cartao|camera|drone|dji|crad|cad)\s*\d*',n))


class Registro:
    def __init__(self, arquivo):
        with open(arquivo, encoding='utf-8-sig') as f:
            rows = json.load(f)
        if not isinstance(rows,list) or not rows:
            raise ValueError('O JSON deve conter uma lista não vazia de registros com o campo pauta.')
        self.chaves = set()
        self.quantidade = len(rows)
        for item in rows:
            p = item.get('pauta') if isinstance(item,dict) else None
            if not isinstance(p,dict):
                raise ValueError('Registro sem objeto pauta. Selecione a exportação resultado_busca.json.')
            partes = [s for s in re.split(r'[\\/]+',str(p.get('caminho_pasta') or '')) if s and not re.fullmatch('[A-Za-z]:',s)]
            datadas = [s for s in partes if separar_data(s)[0]]
            if datadas:
                # A primeira pasta datada identifica a pauta, acima das pastas de câmera.
                self.chaves.add(separar_data(datadas[0]))
            else:
                while partes and tecnica(partes[-1]):
                    partes.pop()
                if partes:
                    self.chaves.add(separar_data(partes[-1]))
                else:
                    raise ValueError('Há uma pauta sem caminho de pasta utilizável no JSON.')


def varrer(raiz, registro, cancelar, progresso):
    pendentes, cadastradas, avisos = [], [], []
    pilha = [(os.path.abspath(raiz), False, True)]
    total = 0
    while pilha:
        if cancelar.is_set():
            return pendentes, cadastradas, avisos, True
        caminho, dentro_pauta, selecionada = pilha.pop()
        nome = os.path.basename(caminho.rstrip(os.sep)) or caminho
        chave = separar_data(nome)
        # A raiz selecionada só entra como pauta se tiver data ou registro exato.
        candidata = bool(chave[0]) or (not dentro_pauta and (not selecionada or chave in registro.chaves))
        if candidata:
            linha = (chave[0], nome, caminho)
            (cadastradas if chave in registro.chaves else pendentes).append(linha)
        total += 1
        if total % 100 == 0:
            progresso(f'{total} pastas percorridas em {raiz}')
        try:
            with os.scandir(caminho) as entradas:
                for entrada in entradas:
                    if cancelar.is_set():
                        break
                    if entrada.name.casefold() in {'$recycle.bin','system volume information'}:
                        continue
                    try:
                        if entrada.is_symlink() or (hasattr(os.path,'isjunction') and os.path.isjunction(entrada.path)):
                            avisos.append('Atalho/junção não percorrido: '+entrada.path)
                            continue
                        # Inclui junctions no Windows com Python anterior ao 3.12.
                        if os.name == 'nt' and getattr(entrada.stat(follow_symlinks=False),'st_file_attributes',0) & 0x400:
                            avisos.append('Ponto de redirecionamento não percorrido: '+entrada.path)
                            continue
                        if entrada.is_dir(follow_symlinks=False):
                            pilha.append((entrada.path, dentro_pauta or bool(chave[0]),False))
                    except OSError as e:
                        avisos.append(f'{entrada.path}: {e}')
        except OSError as e:
            avisos.append(f'{caminho}: {e}')
    ordenar = lambda r: (r[0] is not None, r[0] or dt.date.min, normalizar(r[1]),r[2])
    return sorted(pendentes,key=ordenar), sorted(cadastradas,key=ordenar), avisos, cancelar.is_set()


def relatorio(resultados, arquivo, quantidade, cancelado):
    partes = ['PASTAS PARA VERIFICAR', 'Gerado em: '+dt.datetime.now().strftime('%d/%m/%Y %H:%M'),
              f'Base: {arquivo} ({quantidade} registros)',
              'Comparação por data + nome da pasta, independentemente do caminho/HD.',
              'Correspondência indica presença no registro; não comprova revisão de todo o conteúdo.',
              'Sem data primeiro; depois datas da mais antiga para a mais recente.',
              'Pastas sem data podem incluir pastas de organização. Veja LEIA-ME.txt.',
              'RESULTADO PARCIAL — verificação cancelada.' if cancelado else 'Verificação finalizada.']
    for i,(raiz,pendentes,cadastradas,avisos) in enumerate(resultados,1):
        partes += ['', '='*65, f'HD {i}: {raiz}', f'{len(pendentes)} para verificar | {len(cadastradas)} com correspondência no registro','']
        for data,nome,caminho in pendentes:
            partes += [('[SEM DATA] ' if data is None else '')+nome, '    '+caminho]
        if not pendentes:
            partes.append('Nenhuma pendência encontrada nas pastas acessíveis.')
        if avisos:
            partes += ['', 'ATENÇÃO: áreas não verificadas / avisos:']+avisos
    partes += ['', '='*65, 'PASTAS COM CORRESPONDÊNCIA NO REGISTRO (auditoria)']
    for i,(_,_,cadastradas,_) in enumerate(resultados,1):
        partes += ['',f'HD {i}:']+[p for _,_,p in cadastradas]
    return '\n'.join(partes)+'\n'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Verificador de pautas — 2 HDs')
        self.geometry('1050x730')
        self.minsize(750,520)
        self.fila = queue.Queue()
        self.cancelar = threading.Event()
        self.texto = ''
        area = ttk.Frame(self,padding=16)
        area.pack(fill='both',expand=True)
        ttk.Label(area,text='Quais pastas ainda preciso verificar?',font=('Segoe UI',18,'bold')).pack(anchor='w')
        ttk.Label(area,text='Selecione o registro e os dois HDs ou pastas principais das pautas.').pack(anchor='w',pady=(4,12))
        self.campos=[]
        for titulo,padrao in [('Registro JSON',str(Path(__file__).with_name('resultado_busca.json'))),('HD 1',''),('HD 2','')]:
            linha=ttk.Frame(area);linha.pack(fill='x',pady=4)
            ttk.Label(linha,text=titulo,width=15).pack(side='left')
            valor=tk.StringVar(value=padrao);self.campos.append(valor)
            ttk.Entry(linha,textvariable=valor).pack(side='left',fill='x',expand=True)
            ttk.Button(linha,text='Selecionar',command=lambda v=valor,t=titulo:self.escolher(v,t)).pack(side='left',padx=(8,0))
        ttk.Label(area,text='Sem data no topo • Ordem cronológica crescente • Não move nem altera as pastas').pack(anchor='w',pady=10)
        controles=ttk.Frame(area);controles.pack(fill='x')
        self.iniciar=ttk.Button(controles,text='VERIFICAR OS DOIS HDs',command=self.executar);self.iniciar.pack(side='left')
        self.parar=ttk.Button(controles,text='Cancelar',command=self.cancelar.set,state='disabled');self.parar.pack(side='left',padx=8)
        self.salvar=ttk.Button(controles,text='Salvar lista TXT',command=self.exportar,state='disabled');self.salvar.pack(side='left')
        self.status=tk.StringVar(value='Pronto para verificar.')
        ttk.Label(area,textvariable=self.status).pack(anchor='w',pady=10)
        self.saida=ScrolledText(area,wrap='none',font=('Consolas',10))
        self.saida.pack(fill='both',expand=True)
        self.after(120,self.eventos)

    def escolher(self,valor,titulo):
        p=filedialog.askopenfilename(filetypes=[('Registro JSON','*.json')]) if titulo=='Registro JSON' else filedialog.askdirectory(title='Selecione '+titulo)
        if p: valor.set(p)

    def executar(self):
        arquivo,h1,h2=[v.get().strip() for v in self.campos]
        if not os.path.isfile(arquivo) or not all(os.path.isdir(p) for p in (h1,h2)):
            messagebox.showerror('Seleção incompleta','Selecione um JSON existente e duas pastas/HDs acessíveis.');return
        a,b=map(lambda p:os.path.normcase(os.path.realpath(p)),(h1,h2))
        try: sobrepostos=os.path.commonpath([a,b]) in (a,b)
        except ValueError: sobrepostos=False
        if sobrepostos:
            messagebox.showerror('Seleção repetida','Selecione locais diferentes que não estejam um dentro do outro.');return
        self.iniciar.config(state='disabled');self.parar.config(state='normal');self.salvar.config(state='disabled')
        self.cancelar.clear();self.texto='';self.saida.delete('1.0','end');self.status.set('Lendo o registro e percorrendo as pastas…')
        def trabalho():
            try:
                reg=Registro(arquivo);resultados=[];cancelado=False
                for raiz in (h1,h2):
                    p,c,e,cancelado=varrer(raiz,reg,self.cancelar,lambda s:self.fila.put(('status',s)))
                    resultados.append((raiz,p,c,e))
                    if cancelado: break
                self.fila.put(('fim',relatorio(resultados,arquivo,reg.quantidade,cancelado)))
            except Exception as e:
                self.fila.put(('erro',str(e)))
        threading.Thread(target=trabalho,daemon=True).start()

    def eventos(self):
        try:
            while True:
                tipo,valor=self.fila.get_nowait()
                if tipo=='status': self.status.set(valor)
                else:
                    self.iniciar.config(state='normal');self.parar.config(state='disabled')
                    if tipo=='erro':
                        self.status.set('Não foi possível concluir.');messagebox.showerror('Erro',valor)
                    else:
                        self.texto=valor;self.saida.insert('1.0',valor);self.salvar.config(state='normal')
                        self.status.set('Resultado disponível. Clique em Salvar lista TXT. Confira os avisos no relatório.')
        except queue.Empty: pass
        self.after(120,self.eventos)

    def exportar(self):
        p=filedialog.asksaveasfilename(defaultextension='.txt',initialfile='pastas_para_verificar.txt',filetypes=[('Texto','*.txt')])
        if p:
            try:
                Path(p).write_text(self.texto,encoding='utf-8-sig');messagebox.showinfo('Salvo','Lista salva em:\n'+p)
            except OSError as e: messagebox.showerror('Erro ao salvar',str(e))


if __name__=='__main__':
    App().mainloop()
