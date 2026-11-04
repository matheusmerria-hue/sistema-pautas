# Localizar arquivos perdidos

Arquivos desta implementação: `smart_locate.py` (serviço e persistência), `ui/ui_locate.py` (janela/worker), `database.py` (inicialização das tabelas), `ui/ui_home.py`, `ui/ui_search.py`, `ui_v3/app.py` e `ui_v3/screens.py` (integrações), `tests/test_smart_locate.py` (21 testes novos) e este documento.

## Uso

Inicie a versão atualizada com `python main.py` ou `python -m ui_v3`. Na interface principal, abra **Localizar arquivos perdidos** pelo menu lateral ou pela busca. Na V3, use o botão na busca. Os itens com caminhos indisponíveis também oferecem **Localizar**: pautas no acervo/resultado/inspector e takes nos detalhes/edição. A busca individual restringe os registros à pauta ou take escolhido.

1. Escolha uma pasta raiz ou unidade, por exemplo `D:\`.
2. Clique em **Iniciar localização**. A ferramenta identifica os vínculos inválidos em segundo plano; arquivos ainda acessíveis ficam fora da operação.
3. Acompanhe os contadores. A navegação permanece disponível; **Cancelar operação** encerra cooperativamente a busca e preserva os resultados já identificados.
4. Revise a tabela paginada. Correspondências únicas de alta confiança são pré-selecionadas apenas ao concluir sem erros de acesso nem cancelamento. Escolha manualmente as opções de confiança média/baixa ou ambíguas. A coluna de confiança indica quando é preciso revisar.
5. Clique em **Atualizar vínculos selecionados** e confirme o lote. Não há alteração do banco durante a pesquisa.
6. Refaça a busca do acervo para recarregar os caminhos. **Desfazer última atualização** restaura o último lote, mesmo depois de reabrir o programa. **Invalidar mapeamentos** desativa regras anteriores. **Salvar relatório** exporta caminhos anteriores, opções, classificações e contadores em JSON.

O modo `LEITURA` permite inspecionar, pesquisar e exportar o relatório, mas desativa atualização, desfazimento e invalidação de regras. Durante uma tarefa, fechar a janela ou pressionar Escape pede cancelamento; feche novamente após a conclusão. Fechar a aplicação durante uma tarefa também pede cancelamento e aguarda uma nova tentativa de fechamento, evitando destruir threads ativas.

## Estratégia e custo

- Consulta apenas IDs, nomes e caminhos; não carrega comentários nem conteúdo de mídia para localizar arquivos.
- Verifica os caminhos cadastrados com cache de existência, eliminando verificações duplicadas.
- Testa primeiro os mapeamentos persistidos e os sufixos da pasta original diretamente sob a raiz escolhida.
- Agrupa os takes pela pauta e reconstrói seus caminhos relativos quando uma pasta correspondente aparece. Prefixos descobertos também são testados nas outras pautas durante a mesma operação.
- Quando necessário, realiza **uma única varredura compartilhada** da raiz, com `os.scandir` e iteradores em profundidade. A mesma passagem resolve pastas e indexa apenas nomes de arquivos procurados, inclusive os casos de estrutura parcialmente reorganizada. Não ocorre uma varredura por take.
- O índice temporário fica em memória e contém somente os alvos, caminhos consultados e opções relevantes; não guarda a árvore inteira da unidade. Descarta coincidências de nome mais fracas quando encontra uma estrutura melhor. Guarda até 32 opções por vínculo/pasta; se exceder o limite, bloqueia a pré-seleção e recomenda uma raiz mais restrita. A tabela mostra até 200 vínculos por página.
- O padrão é uma verificação por vez, indicado para HDD. É possível testar duas verificações de metadados simultâneas em SSD; o limite é dois, a fila é limitada e a varredura de diretórios continua sequencial. Não se presume ganho em SSD sem medição no equipamento de destino.
- Progresso agrupado a cada 250 ms, além de transições de etapa. A execução usa `QThread`, sem polling na interface nem pausas artificiais no algoritmo.

Não há leitura de vídeos, thumbnails, decodificação, hashes ou dependências adicionais. Não se usa o indexador do Windows: a solução funciona também em unidades externas sem indexação.

## Confiança e segurança

Uma correspondência usa a extensão e o nome completos, os maiores sufixos coincidentes e a reconstrução relativa a uma pasta da pauta. Uma pasta com todos os takes pendentes presentes na estrutura relativa pode alcançar alta confiança; sufixos parciais têm confiança média e coincidências apenas de nome têm confiança baixa. Cópias igualmente plausíveis ficam ambíguas e exigem escolha explícita. A existência de um nome isolado nunca o torna uma seleção automática.

O banco atual não armazena tamanho/hash original; portanto não é possível comparar esses atributos com o original perdido. A ferramenta não afirma equivalência de conteúdo: se duas cópias preservam a mesma estrutura, o usuário precisa escolher a correta. Hashing não foi adicionado.

A varredura é somente leitura. Não segue symlinks, junctions/reparse points ou montagens fora do volume escolhido; erros de acesso são contabilizados sem abortar as outras pastas. Os destinos reconstruídos são validados contra a raiz e novamente antes da gravação. A operação não move, copia, renomeia ou modifica arquivos físicos.

As alterações usam uma transação SQLite com `BEGIN IMMEDIATE`. Se um destino desaparecer, o caminho antigo voltar a funcionar, a pauta for excluída, um take mudar de pauta, houver edição concorrente ou cancelamento antes do commit, todo o lote é revertido. IDs, comentários, tags, favoritos, clientes e associações permanecem intactos. O desfazimento também é transacional e não sobrescreve referências editadas posteriormente.

## Persistência

O inicializador cria três tabelas adicionais de maneira idempotente: `locate_batches`, `locate_changes` e `locate_mappings`. Elas guardam o lote, os caminhos anterior/novo e regras confirmadas ativas. Não são removidos registros nem recriadas as tabelas do acervo. Regras só são persistidas após confirmar e aplicar a recuperação; são testadas dentro da raiz selecionada antes de reutilizar. Uma regra única já confirmada e revalidada pode evitar completamente uma nova varredura. A invalidação e o desfazimento desativam as regras correspondentes.

O banco original não foi atualizado durante o desenvolvimento. As tabelas serão criadas ao iniciar o código atualizado. O executável existente em `dist` não foi recompilado; para distribuir, gere uma nova versão no ambiente do projeto com `python -m PyInstaller --noconfirm SistemaPautas.spec`.

## Testes e limites

Execute `python -B -m unittest discover -s tests -v`.

Resultado final: **32 testes aprovados**, incluindo os 11 testes anteriores da migração para clientes. A verificação `git diff --check` também passou.

Os testes incluem uma, duas e várias pastas adicionais, pauta inteira, várias pautas, nomes repetidos, ambiguidades, caminhos válidos, unidade indisponível, permissões simuladas, junctions simuladas, cancelamento, rollback, persistência/reabertura, reutilização/invalidação de prefixos, desfazimento, relacionamentos e interface Qt em modo `offscreen`. O teste de escala cria **2.000 arquivos em quatro pautas**: todos foram encontrados em **uma varredura de 12 diretórios**, sem abrir conteúdo; a última medição ficou em cerca de **0,7 segundo** neste ambiente. Esse tempo é sintético e não é uma promessa de desempenho em HDDs ou unidades externas reais.

O cancelamento aguarda a chamada de sistema em andamento; uma unidade de rede ou USB sem resposta pode demorar a devolver o controle. Quando não existe um prefixo confirmado, a ferramenta pode precisar percorrer toda a raiz selecionada uma vez para descobrir pastas arbitrariamente aninhadas e detectar duplicidades. Recomenda-se selecionar a menor raiz que contenha o material. Os testes automatizados não substituem a conferência visual da janela no monitor de destino nem uma medição em hardware HDD/SSD real.
