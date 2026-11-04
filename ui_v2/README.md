# UI V2

Protótipo visual independente do Sistema de Pautas. Todos os conteúdos exibidos vêm de
`mock_data.py`; este pacote não importa banco de dados, repositórios, serviços nem a UI original.

## Executar

Na raiz do projeto:

```powershell
python -m ui_v2
```

Resolução-base: 1366×768. A janela é redimensionável e foi validada também em 1920×1080.

## Estrutura

- `app.py`: entrypoint e AppShell.
- `theme.py`: tokens de cor e QSS global.
- `components.py`: componentes, estados, modal, toast, toggle e empty/loading states.
- `screens.py`: Home, Pesquisa, Nova pauta/Editor e UI Showcase.
- `mock_data.py`: pautas e takes fictícios.
