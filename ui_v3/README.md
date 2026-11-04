# UI V3 — Mesa de Corte

Interface funcional alternativa em formato de workstation editorial, executada com
`python -m ui_v3`. As telas operacionais usam o banco e as funções de domínio reais.
Somente o Design Lab contém conteúdo demonstrativo.

- `app.py`: shell, rail, workspaces, inspector e atalhos.
- `screens.py`: Central, Acervo, Edição e Design Lab.
- `components.py`: componentes contextuais, palette, overlays e mídia assíncrona.
- `backend.py`: adaptador fino para as funções existentes em `database.py`.
- `screens.py`: telas reais e Design Lab demonstrativo claramente isolado.
- `theme.py`: linguagem visual petróleo/ciano.
