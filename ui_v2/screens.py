from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,
 QScrollArea,QLineEdit,QTextEdit,QComboBox,QCheckBox,QTabWidget,QMenu,QTableWidget,QTableWidgetItem,QHeaderView)
from .components import label,button,surface,divider,StatusBadge,Toggle,SearchInput,Modal,Toast,Skeleton,EmptyState
from .mock_data import PAUTAS, TAKES


def scroll_page(content):
    area=QScrollArea(); area.setWidgetResizable(True); area.setWidget(content); return area

def page_header(title,subtitle,actions=()):
    box=QWidget(); row=QHBoxLayout(box); row.setContentsMargins(0,0,0,0)
    txt=QVBoxLayout(); txt.setSpacing(3); txt.addWidget(label(title,"PageTitle")); txt.addWidget(label(subtitle,"Muted")); row.addLayout(txt); row.addStretch()
    for a in actions: row.addWidget(a)
    return box

def status_dot(color):
    d=QLabel("●"); d.setStyleSheet(f"color:{color};font-size:10px"); return d


class HomePage(QWidget):
    def __init__(self, navigate):
        super().__init__(); root=QVBoxLayout(self); root.setContentsMargins(24,20,24,20); root.setSpacing(16)
        new=button("+  Nova pauta","primary"); new.clicked.connect(lambda:navigate(2)); root.addWidget(page_header("Visão geral","Sexta-feira, 14 de agosto",[button("Exportar","ghost"),new]))
        body=QHBoxLayout(); body.setSpacing(14); root.addLayout(body,1)
        left=QVBoxLayout(); left.setSpacing(14); body.addLayout(left,3)
        right=QVBoxLayout(); right.setSpacing(14); body.addLayout(right,1)
        summary=surface(); sr=QHBoxLayout(summary); sr.setContentsMargins(18,15,18,15)
        for i,(n,t,c) in enumerate((("8","A editar","#E7B75F"),("6","Em produção","#62A8F7"),("24","Finalizadas","#48C78E"))):
            cell=QVBoxLayout(); top=QHBoxLayout(); top.addWidget(status_dot(c)); top.addWidget(label(t,"Muted")); top.addStretch(); cell.addLayout(top); cell.addWidget(label(n,"Metric")); sr.addLayout(cell,1)
            if i<2: sep=QFrame(); sep.setFixedWidth(1); sep.setStyleSheet("background:#293240"); sr.addWidget(sep)
        left.addWidget(summary)
        recent=surface(); rl=QVBoxLayout(recent); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)
        rh=QHBoxLayout(); rh.setContentsMargins(16,13,12,10); rh.addWidget(label("Continuar trabalhando","SectionTitle")); rh.addStretch(); see=button("Ver acervo  →","ghost"); see.clicked.connect(lambda:navigate(1)); rh.addWidget(see); rl.addLayout(rh)
        for p in PAUTAS[:5]: rl.addWidget(PautaRow(p))
        left.addWidget(recent,1)
        quick=surface(); ql=QVBoxLayout(quick); ql.setContentsMargins(15,14,15,14); ql.addWidget(label("Ações rápidas","SectionTitle"));
        for txt,sub,idx in (("Criar pauta","Registrar pasta e takes",2),("Pesquisar acervo","Encontrar pautas e arquivos",1),("Revisar pendências","8 pautas aguardando edição",1)):
            b=button(txt+"\n"+sub,"ghost"); b.setMinimumHeight(48); b.clicked.connect(lambda _,x=idx:navigate(x)); ql.addWidget(b)
        right.addWidget(quick)
        activity=surface(); al=QVBoxLayout(activity); al.setContentsMargins(15,14,15,14); al.addWidget(label("Atividade recente","SectionTitle"))
        for t,s in (("Pauta finalizada","Feira de agricultura · 12:41"),("Take favoritado","CAM_B_0041 · 11:08"),("Pauta atualizada","Plano de segurança · ontem")):
            al.addWidget(label(t,"ItemTitle")); al.addWidget(label(s,"Caption")); al.addWidget(divider())
        al.addStretch(); right.addWidget(activity,1)


class PautaRow(QFrame):
    def __init__(self,p):
        super().__init__(); self.setObjectName("ListRow"); row=QHBoxLayout(self); row.setContentsMargins(16,10,12,10); row.setSpacing(12)
        thumb=QLabel(p["title"][:1]); thumb.setAlignment(Qt.AlignCenter); thumb.setFixedSize(48,34); thumb.setStyleSheet("background:#222B37;color:#7C6EF6;border-radius:5px;font-weight:700;"); row.addWidget(thumb)
        info=QVBoxLayout(); info.setSpacing(2); info.addWidget(label(p["title"],"ItemTitle")); info.addWidget(label(f'{p["owner"]}  ·  {p["date"]}  ·  {p["takes"]} takes',"Caption")); row.addLayout(info,1); row.addWidget(StatusBadge(p["status"])); more=button("•••","ghost","Mais ações"); more.setFixedWidth(38)
        menu=QMenu(more); menu.addAction("Abrir detalhes"); menu.addAction("Editar pauta"); menu.addSeparator(); menu.addAction("Excluir…"); more.clicked.connect(lambda:menu.exec(more.mapToGlobal(more.rect().bottomLeft()))); row.addWidget(more)


class SearchPage(QWidget):
    def __init__(self,navigate):
        super().__init__(); root=QVBoxLayout(self); root.setContentsMargins(24,20,24,20); root.setSpacing(13)
        root.addWidget(page_header("Pesquisar acervo","Encontre pautas, falas, tags e arquivos",[button("Exportar resultado","ghost")]))
        bar=QHBoxLayout(); self.query=SearchInput("Busque por pauta, comentário, arquivo ou tag…"); self.query.textChanged.connect(self.filter_rows); bar.addWidget(self.query,1); owner=QLineEdit(); owner.setPlaceholderText("Digite o nome do cliente"); owner.setAccessibleName("Cliente"); bar.addWidget(owner); bar.addWidget(button("Filtros  3","secondary")); root.addLayout(bar)
        chips=QHBoxLayout(); chips.setSpacing(7)
        for i,t in enumerate(("Todos","Comentados","Favoritos","Últimos 30 dias")):
            b=button(t,"primary" if i==0 else "ghost"); b.setCheckable(True); b.setChecked(i==0); chips.addWidget(b)
        chips.addStretch(); chips.addWidget(label("Ordenar por","Caption")); sort=QComboBox(); sort.addItems(["Mais recentes","Mais antigos","Título"]); chips.addWidget(sort); root.addLayout(chips)
        info=QHBoxLayout(); self.count=label("10 pautas encontradas","Muted"); info.addWidget(self.count); info.addStretch(); info.addWidget(label("LISTA","Eyebrow")); root.addLayout(info)
        self.list=QVBoxLayout(); self.list.setSpacing(0); holder=surface(); holder.setLayout(self.list); self.rows=[]
        for p in PAUTAS:
            r=PautaRow(p); self.rows.append((r,p)); self.list.addWidget(r)
        self.empty=EmptyState("Limpar filtros"); self.empty.hide(); self.list.addWidget(self.empty); self.list.addStretch(); root.addWidget(scroll_page(holder),1)
    def filter_rows(self,text):
        text=text.lower().strip(); shown=0
        for row,p in self.rows:
            ok=not text or text in (p["title"]+p["desc"]+" ".join(p["tags"])).lower(); row.setVisible(ok); shown+=ok
        self.count.setText(f"{shown} pauta{'s' if shown!=1 else ''} encontrada{'s' if shown!=1 else ''}"); self.empty.setVisible(shown==0)


class EditorPage(QWidget):
    def __init__(self,navigate):
        super().__init__(); root=QVBoxLayout(self); root.setContentsMargins(24,16,24,16); root.setSpacing(12)
        save=button("Salvar pauta","primary"); save.clicked.connect(lambda:Toast(self.window(),"Pauta salva no protótipo (MOCK)")); root.addWidget(page_header("Nova pauta","Rascunho · alterações locais do protótipo",[button("Descartar","ghost"),save]))
        body=QHBoxLayout(); body.setSpacing(14); root.addLayout(body,1)
        main=QVBoxLayout(); main.setSpacing(12); body.addLayout(main,3)
        details=surface(); grid=QGridLayout(details); grid.setContentsMargins(17,15,17,16); grid.setSpacing(9); grid.addWidget(label("Informações principais","SectionTitle"),0,0,1,4)
        grid.addWidget(label("Título da pauta  *","Muted"),1,0,1,4); title=QLineEdit(); title.setPlaceholderText("Ex.: Entrevista sobre transporte público"); grid.addWidget(title,2,0,1,4)
        grid.addWidget(label("Data  *","Muted"),3,0); grid.addWidget(label("Cliente  *","Muted"),3,2); date=QLineEdit("14/08/2026"); owner=QLineEdit(); owner.setPlaceholderText("Digite o nome do cliente"); grid.addWidget(date,4,0,1,2); grid.addWidget(owner,4,2,1,2)
        grid.addWidget(label("Descrição","Muted"),5,0,1,4); desc=QTextEdit(); desc.setPlaceholderText("Contexto breve para orientar a edição…"); desc.setMaximumHeight(64); grid.addWidget(desc,6,0,1,4); main.addWidget(details)
        media=surface(); ml=QVBoxLayout(media); ml.setContentsMargins(0,0,0,0); mh=QHBoxLayout(); mh.setContentsMargins(16,12,12,9); mh.addWidget(label("Takes da pasta","SectionTitle")); mh.addWidget(StatusBadge("6 arquivos")); mh.addStretch(); mh.addWidget(button("Selecionar pasta","secondary")); ml.addLayout(mh)
        for take in TAKES: ml.addWidget(TakeEditorRow(take))
        main.addWidget(scroll_page(media),1)
        side=QVBoxLayout(); side.setSpacing(12); body.addLayout(side,1)
        folder=surface(); fl=QVBoxLayout(folder); fl.setContentsMargins(15,14,15,14); fl.addWidget(label("Origem da mídia","SectionTitle")); fl.addWidget(label("C:\\Midia\\Campanha\\14-08-Saude","Caption",True)); fl.addWidget(divider()); fl.addWidget(label("6 arquivos  ·  4,8 GB","Muted")); side.addWidget(folder)
        progress=surface(); pl=QVBoxLayout(progress); pl.setContentsMargins(15,14,15,14); pl.addWidget(label("Progresso","SectionTitle")); pl.addWidget(label("4 de 6 takes revisados","Muted"));
        for t,c in (("Usar",3),("Talvez",2),("Ignorar",1)): r=QHBoxLayout(); r.addWidget(StatusBadge(t)); r.addStretch(); r.addWidget(label(str(c),"ItemTitle")); pl.addLayout(r)
        side.addWidget(progress); side.addStretch()


class TakeEditorRow(QFrame):
    def __init__(self,t):
        super().__init__(); self.setObjectName("ListRow"); row=QHBoxLayout(self); row.setContentsMargins(14,8,12,8); thumb=QLabel("VIDEO"); thumb.setAlignment(Qt.AlignCenter); thumb.setFixedSize(58,34); thumb.setStyleSheet("background:#222B37;color:#667181;border-radius:4px;font-size:9px"); row.addWidget(thumb)
        n=QVBoxLayout(); n.setSpacing(2); n.addWidget(label(t["file"],"ItemTitle")); n.addWidget(label(t["time"]+"  ·  1080p  ·  29,97 fps","Caption")); row.addLayout(n); note=QLineEdit(t["note"]); note.setPlaceholderText("Comentário do take"); row.addWidget(note,1); typ=QComboBox(); typ.addItems(["Usar","Talvez","Ignorar"]); typ.setCurrentText(t["type"]); row.addWidget(typ)


class ShowcasePage(QWidget):
    def __init__(self,navigate):
        super().__init__(); content=QWidget(); content.setObjectName("Canvas"); root=QVBoxLayout(content); root.setContentsMargins(24,20,24,24); root.setSpacing(14)
        root.addWidget(page_header("UI Showcase","Design system · estados e componentes da interface V2",[button("v0.1 · MOCK","ghost")]))
        tabs=QTabWidget(); tabs.addTab(self.controls(),"Componentes"); tabs.addTab(self.states(),"Estados"); tabs.addTab(self.palette(),"Fundamentos"); root.addWidget(tabs); host=QVBoxLayout(self); host.setContentsMargins(0,0,0,0); host.addWidget(scroll_page(content))
    def section(self,title):
        s=surface(); l=QVBoxLayout(s); l.setContentsMargins(16,14,16,16); l.setSpacing(10); l.addWidget(label(title,"SectionTitle")); return s,l
    def controls(self):
        w=QWidget(); g=QGridLayout(w); g.setContentsMargins(0,12,0,0); g.setSpacing(12)
        s,l=self.section("Botões"); r=QHBoxLayout()
        for txt,v in (("Primário","primary"),("Secundário","secondary"),("Sutil","ghost"),("Destrutivo","danger")): r.addWidget(button(txt,v))
        d=button("Desabilitado"); d.setDisabled(True); r.addWidget(d); r.addStretch(); l.addLayout(r); g.addWidget(s,0,0,1,2)
        s,l=self.section("Campos e seleção"); inp=QLineEdit(); inp.setPlaceholderText("Estado padrão"); err=QLineEdit("Valor inválido"); err.setProperty("error","true"); combo=QComboBox(); combo.addItems(["Opção selecionada","Outra opção"]); r=QHBoxLayout(); r.addWidget(inp); r.addWidget(err); r.addWidget(combo); l.addLayout(r); l.addWidget(QCheckBox("Checkbox selecionável")); g.addWidget(s,1,0)
        s,l=self.section("Badges e status"); r=QHBoxLayout(); [r.addWidget(StatusBadge(x)) for x in ("A editar","Em produção","Finalizada","Usar","Ignorar")]; r.addStretch(); l.addLayout(r); g.addWidget(s,1,1)
        s,l=self.section("Toggles e chips"); r=QHBoxLayout(); r.addWidget(Toggle(True)); r.addWidget(Toggle(False)); [r.addWidget(button(x,"primary" if i==0 else "ghost")) for i,x in enumerate(("Todos","Favoritos","Comentados"))]; r.addStretch(); l.addLayout(r); g.addWidget(s,2,0)
        s,l=self.section("Feedback e overlays"); r=QHBoxLayout(); toast=button("Mostrar toast"); toast.clicked.connect(lambda:Toast(self.window(),"Ação concluída com sucesso")); modal=button("Abrir modal"); modal.clicked.connect(lambda:Modal(self,"Confirmar alteração","Esta é uma confirmação demonstrativa da UI V2.").exec()); delete=button("Excluir…","danger"); delete.clicked.connect(lambda:Modal(self,"Excluir pauta?","Esta ação não pode ser desfeita no produto integrado.",True).exec()); [r.addWidget(x) for x in (toast,modal,delete)]; r.addStretch(); l.addLayout(r); g.addWidget(s,2,1); return w
    def states(self):
        w=QWidget(); g=QGridLayout(w); s,l=self.section("Loading / skeleton"); [l.addWidget(Skeleton(x)) for x in (260,190,230)]; g.addWidget(s,0,0); s,l=self.section("Empty state"); l.addWidget(EmptyState("Criar pauta")); g.addWidget(s,0,1); s,l=self.section("Estados de formulário"); l.addWidget(label("Campo com erro","Muted")); e=QLineEdit("Data inválida"); e.setProperty("error","true"); l.addWidget(e); l.addWidget(label("Use o formato DD/MM/AAAA","Required")); g.addWidget(s,1,0); s,l=self.section("Tooltip e foco"); b=button("Passe o mouse","secondary","Uma orientação curta e objetiva"); l.addWidget(b); f=QLineEdit("Pressione Tab para testar o foco"); l.addWidget(f); g.addWidget(s,1,1); return w
    def palette(self):
        from .theme import COLORS
        w=QWidget(); g=QGridLayout(w); s,l=self.section("Paleta de superfícies e semântica");
        for name,color in COLORS.items(): r=QHBoxLayout(); sw=QFrame(); sw.setFixedSize(28,28); sw.setStyleSheet(f"background:{color};border:1px solid #3A4350;border-radius:5px"); r.addWidget(sw); r.addWidget(label(name,"ItemTitle")); r.addStretch(); r.addWidget(label(color,"Caption")); l.addLayout(r)
        g.addWidget(s,0,0); s,l=self.section("Tipografia"); l.addWidget(label("Título de página","PageTitle")); l.addWidget(label("Título de seção","SectionTitle")); l.addWidget(label("Título de item","ItemTitle")); l.addWidget(label("Texto de corpo para conteúdo corrente.")); l.addWidget(label("Metadados e informações secundárias","Muted")); l.addWidget(label("CAPTION · 11 PX","Caption")); l.addStretch(); g.addWidget(s,0,1); return w
