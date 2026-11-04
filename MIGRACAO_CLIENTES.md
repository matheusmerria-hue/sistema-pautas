# Migração para clientes

Nos campos de busca de cliente (busca original, filtro do acervo e busca V3), a seta à direita mostra os clientes existentes. Ao digitar, aparecem sugestões de nomes correspondentes, ignorando caixa e acentos. A lista é consultada novamente a cada uso, não repete nomes equivalentes e inclui somente clientes com pautas não excluídas. A digitação permanece livre; limpar o campo pesquisa todos os clientes.

O campo Cliente é texto livre no cadastro, edição, busca, acervo e interface V3. O protótipo V2 também apresenta texto livre. A pesquisa vazia inclui todos os clientes; nomes parciais ignoram caixa, acentos e diferenças de espaços. Os demais filtros e o histórico podem ser usados em conjunto. CSV e JSON passam a usar `cliente`.

## Banco e implantação

O caminho continua definido em `config.py`: `C:\PAUTAS_DB\pautas.db`. Não foi alterado o banco original durante o desenvolvimento; os testes usam bancos temporários e uma cópia consistente do banco real.

Feche versões antigas do programa antes de iniciar a versão atualizada. Execute `python main.py` (interface original) ou `python -m ui_v3` (V3). Na primeira inicialização:

1. É criado, na mesma pasta do banco, um backup SQLite consistente chamado `pautas.db.antes-clientes-<data-hora>.bak`. Se o backup falhar, a renomeação não acontece.
2. A coluna `pautas.candidato` é renomeada para `cliente`, preservando todos os valores, IDs, índices e relacionamentos. Não há recriação de tabelas ou remoção de registros.
3. O histórico recebe a coluna `filtros`, em JSON, com padrão `{}` para entradas antigas. Colunas opcionais de versões mais antigas são adicionadas pelo inicializador existente.

A migração pode ser repetida. Os nomes Vander e Soraya permanecem nos registros correspondentes. Não há cadastro central: cada pauta guarda seu próprio cliente; nomes equivalentes por caixa, espaços e acentos reutilizam a primeira grafia existente, sem alterar outras pautas.

O executável já existente em `dist` não foi recompilado. Para distribuir a atualização empacotada, gere uma nova versão com `python -m PyInstaller --noconfirm SistemaPautas.spec`, no ambiente com as dependências instaladas. Não execute o binário antigo contra o banco já migrado, pois ele espera a coluna antiga. Para rollback, feche o aplicativo e restaure o backup, guardando separadamente o banco atualizado (o backup não contém registros criados depois da migração).

## Contratos

As funções públicas do banco usam `cliente`. O argumento nomeado legado `candidato` ainda é aceito durante a transição; em filtros legados, `candidato="Todos"` representa ausência de filtro. Na API nova, `cliente="Todos"` procura literalmente esse nome. Os retornos de pautas e exportações usam `cliente`; estatísticas usam `pautas_por_cliente`. Consumidores externos que leiam diretamente o SQLite ou o JSON/CSV precisam adotar esses nomes. Não foram identificadas integrações externas no código do projeto.

## Verificação

Execute `python -B -m unittest discover -s tests -v`.

Os 11 testes cobrem criação de Núcleo D3 e Governo MS, busca parcial/vazia, normalização, edição isolada, favoritos, takes, comentários, caminhos de arquivos, datas ISO e brasileiras, exportações CSV/JSON (incluindo pautas sem takes), histórico antigo e novo, compatibilidade de argumentos e campos de texto das interfaces conectadas ao banco. Os testes de interface usam Qt sem janela (`offscreen`); não substituem uma conferência visual no monitor de destino.

A migração também foi executada duas vezes sobre uma cópia do banco configurado (61 pautas e 3.400 takes). Todos os valores das pautas e takes foram comparados antes/depois; o histórico foi preservado, `integrity_check` retornou `ok` e `foreign_key_check` não encontrou violações. O banco original permaneceu intacto.
