# Instalação cliente-servidor do Sistema de Pautas — Windows

Este é o manual principal da versão de rede. O motor documentado em `SMART_LOCATE.md` foi preservado, com execução local no servidor e controle remoto pelas duas estações. O roteiro abaixo deve ser realizado no Windows 10 de destino; os testes automatizados e o teste TCP em uma única máquina não substituem essa validação física.

## Arquitetura entregue

Os PCs 01/02 executam o cliente PySide6 localmente. Só o processo do servidor abre o SQLite, que deve ficar em disco local e fora dos compartilhamentos de mídia. Os vídeos são abertos diretamente pelo SMB/UNC com a autorização do Windows; a API não transmite vídeos. Não há banco secundário nem fila offline no cliente.

Componentes novos: `network/server.py` (FastAPI), `network/runtime.py` e `network/client.py` (fachada das APIs Python existentes), `network/media.py` (raízes/UNC), `network/storage.py` (revisões e eventos), `network/security.py` (usuários/sessões), `network/jobs.py` (Smart Locate centralizado), `network/desktop.py` (login e atualização), `network/backup.py`, `network/instance.py`, `network/admin.py`, `client_main.py`, `server_service.py` e `packaging/*.ps1`. Integrações nos módulos de banco, exportação, scanner, Smart Locate e interfaces original/V3 preservam clientes, comentários, favoritos e o desenho existente.

## 1. Preparar os três computadores

1. Use uma rede privada confiável. Reserve o IP do servidor e dos dois clientes no roteador/DHCP, ou use IPs fixos administrados pela equipe. Registre o hostname do servidor.
2. Escolha um SSD local para o banco, por exemplo `C:\ProgramData\PautasServer\data\pautas.db`. Não compartilhe essa pasta nem coloque o SQLite em UNC/unidade de rede mapeada.
3. Escolha outro disco/destino autorizado para backups, por exemplo `E:\BackupsPautas`. Garanta espaço livre e acesso da conta do serviço. O diretório de backup não deve ficar dentro de uma pasta de mídia compartilhada com usuários comuns.
4. Pare a versão antiga do aplicativo no servidor antes de migrar o banco. Preserve também o executável antigo e sua configuração para recuperação. Não abra o banco de produção simultaneamente pela versão local antiga e pelo novo servidor.

## 2. Compartilhar os materiais por SMB

No servidor, escolha pastas de materiais como `D:\Producoes` e `F:\Arquivo`, em vez de compartilhar o disco do banco. Crie grupos/contas Windows autorizados e configure **Compartilhamento avançado → Permissões** e **Segurança/NTFS**. Conceda leitura para reprodução e somente as permissões de escrita necessárias a quem organiza os arquivos. Não conceda acesso a `Todos`/`Everyone`.

Exemplo administrativo, após criar o grupo Windows `EditoresPautas` e incluir as contas corretas:

```powershell
New-SmbShare -Name PRODUCOES -Path 'D:\Producoes' -ReadAccess "$env:COMPUTERNAME\EditoresPautas"
New-SmbShare -Name ARQUIVO -Path 'F:\Arquivo' -ReadAccess "$env:COMPUTERNAME\EditoresPautas"
```

O administrador deve conceder também o acesso NTFS correspondente. O instalador não muda automaticamente as permissões dos seus HDs. Restrinja a entrada SMB/TCP 445 no firewall ao perfil Privado e aos IPs dos dois clientes; confira regras preexistentes de compartilhamento para evitar permissões mais amplas.

Nos dois clientes, abra `\\SERVIDOR\PRODUCOES` e `\\SERVIDOR\ARQUIVO` no Explorer. Autentique com uma conta Windows autorizada; se necessário, use o **Gerenciador de Credenciais do Windows**. Abra um vídeo real em ambos os PCs antes de configurar o aplicativo. Não dependa de `Z:` ou de outra letra de unidade mapeada. As permissões SMB/NTFS são independentes do login da API e continuam obrigatórias.

## 3. Gerar os pacotes Windows

Na máquina de build com Python Windows, crie um ambiente virtual e instale:

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-client.txt -r requirements-test-network.txt
& .\packaging\build-network.ps1 -Python .\.venv-build\Scripts\python.exe
```

O script cria `release-network/PautasCliente/` e `release-network/PautasServidor/`, os instaladores PowerShell e uma cópia deste guia. Distribua a pasta inteira de cada pacote, incluindo `_internal`; não apenas o `.exe`. Os computadores de destino não precisam de Python. Não copie bancos, configurações com credenciais ou vídeos junto com esses pacotes. Binários gerados são ignorados pelo Git.

Se a política local impedir scripts, peça ao administrador para autorizar os scripts revisados conforme a política da equipe. Para scripts locais autorizados, uma execução com `powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File caminho-do-script.ps1` limita essa escolha ao processo; políticas corporativas superiores continuam valendo. Nenhuma política permanente do Windows é alterada pelos instaladores.

## 4. Instalar e configurar o servidor

Copie a distribuição para o servidor. No PowerShell elevado, execute:

```powershell
& .\install-server.ps1
```

O instalador solicita banco local, destino de backup, IP de escuta, porta, IPs autorizados e uma ou mais correspondências **pasta local = compartilhamento UNC**. Exemplos:

- `D:\Producoes` → `\\SERVIDOR\PRODUCOES`
- `F:\Arquivo` → `\\SERVIDOR\ARQUIVO`

Depois solicita os dois usuários do aplicativo e senhas de pelo menos 12 caracteres. As senhas são lidas de forma oculta, não aparecem na linha de comando e são armazenadas somente como PBKDF2 com salt individual. O arquivo `users.json` fica fora do código e das raízes compartilhadas. O cliente salva endereço/usuário/certificado CA em `%LOCALAPPDATA%\SistemaPautas\connection.json`, sem salvar senha nem token.

O serviço `PautasServer` inicia automaticamente com o Windows e é configurado para reiniciar após falha. A regra de firewall criada permite apenas a porta escolhida, o programa servidor, o perfil Privado e os IPs autorizados. **Não encaminhe essa porta no roteador e não exponha a API à internet.** Também há uma lista de IPs/sub-redes privadas na própria API; cabeçalhos de proxy não substituem o IP real.

Configuração: `%PROGRAMDATA%\PautasServer\server.json`. Logs rotativos: subpasta `logs` desse diretório. Por padrão, o serviço usa SYSTEM, que precisa de acesso aos HDs locais. Se sua política exigir uma conta dedicada, configure a conta na guia **Logon** do serviço e conceda acesso NTFS apenas ao banco, configuração, logs, backups e raízes necessárias.

O instalador preserva banco e configuração existentes. Para uma atualização, pare o serviço antes de copiar novos binários; se a regra de firewall já existir, o instalador pede conferência manual em vez de substituir suas permissões. Inicie novamente após verificar o endereço/porta/IPs.

Para administração local do pacote:

```powershell
.\PautasServidor.exe admin user --config 'C:\ProgramData\PautasServer\server.json' --username consulta --role reader
.\PautasServidor.exe admin backup --config 'C:\ProgramData\PautasServer\server.json'
.\PautasServidor.exe console 'C:\ProgramData\PautasServer\server.json'
```

Perfis: `reader` consulta/exporta; `editor` também edita e executa/aplica Smart Locate; `admin` tem as mesmas operações de acervo que editor e pode ser usado como identificação administrativa. Criação/troca de usuários e restauração são comandos locais do servidor, não endpoints remotos. Reiniciar o servidor invalida as sessões; alterar uma senha também invalida sessões daquela credencial. As sessões expiram em oito horas.

### Transporte HTTPS

HTTP é aceito para a rede privada isolada do exemplo, mas não cifra senhas/dados em trânsito. Para confidencialidade na LAN, provisione um certificado TLS para o hostname do servidor, com chave privada PEM protegida, e configure `tls_cert` e `tls_key` no `server.json`. Use `https://hostname:porta` nos clientes e uma CA confiável pelo Windows/Python ou o caminho do certificado CA no diálogo de conexão. Não há opção de desativar a validação TLS. A emissão do certificado depende da infraestrutura da equipe; o instalador não gera nem publica chaves.

## 5. Migrar o banco e os caminhos

Na primeira inicialização com um banco existente, o servidor faz backup consistente **antes** da migração. A migração anterior `candidato → cliente` continua funcionando; IDs e conteúdo são preservados. O servidor acrescenta `revision` em pautas/takes e tabelas de eventos/requisições, além das tabelas existentes do Smart Locate. As leituras e gravações do cliente passam pela API; não abra o `.db` por SMB.

Os caminhos existentes permanecem no banco em sua representação do servidor; o limite API traduz os prefixos configurados para UNC. Não é necessário regravar todos os caminhos da coleção. Se uma instalação anterior usava outro prefixo que corresponde ao mesmo material, um administrador pode adicionar `legacy` à raiz relevante, por exemplo `"legacy": ["E:\\Producoes"]`. Isso só traduz exibição; caminhos realmente movidos devem ser corrigidos com Smart Locate. Caminhos não mapeados não são enviados como letras de disco para o cliente abrir por engano.

SQLite atende ao acesso serializado de escrita dos dois clientes. Há timeout de dez segundos, transações por operação e índices de pauta/takes. WAL só é habilitado quando a biblioteca SQLite contém a correção do WAL-reset; com a biblioteca 3.50.4 deste ambiente o servidor escolhe `DELETE` e registra o motivo. Isso foi implementado conforme a [documentação oficial do SQLite](https://www.sqlite.org/wal.html). Há checkpoints automáticos/na parada quando WAL está disponível. Não se deve usar múltiplos workers/processos Uvicorn; um bloqueio de instância impede dois servidores sobre o mesmo banco.

## 6. Instalar os clientes e testar

Em cada PC, copie a distribuição e execute `install-client.ps1` no PowerShell do usuário. O script instala em `%LOCALAPPDATA%\Programs\PautasCliente` e cria um atalho no Desktop, preservando as preferências. Abra o atalho e informe o hostname/IP/porta reais do servidor, usuário e senha. O botão **Testar conexão e entrar** autentica e verifica a API antes de abrir o acervo.

O instalador também cria **Sistema de Pautas V3**, que usa o mesmo cliente e servidor com o argumento `--ui v3`. Pela linha de comando, execute `PautasCliente.exe --ui main` ou `PautasCliente.exe --ui v3`. Ambos exigem login de rede; nenhum deles inicializa um SQLite local.

A pequena área de status informa conexão com o servidor, banco central, compartilhamentos e sincronização. O servidor verifica banco e raízes físicas; cada cliente verifica por conta própria se consegue listar as raízes UNC usando suas credenciais Windows. As sondagens são leves e limitadas a uma entrada por diretório, em segundo plano e com intervalo mínimo de trinta segundos. Acesso à raiz não prova permissão para todos os vídeos: teste também a reprodução dos arquivos reais nos dois PCs.

Teste de aceitação nos dois computadores:

1. PC01 cria uma pauta com cliente novo e takes em UNC. PC02 deve enxergá-la após a notificação/atualização (consulta leve de eventos a cada cinco segundos, além das buscas manuais).
2. PC01/PC02 abrem a mesma pauta. PC01 salva; PC02 tenta salvar seu formulário antigo. Deve receber conflito, mantendo seu texto para comparação. Recarregue o registro em uma nova edição antes de reaplicar suas mudanças.
3. Edite comentários, tags, status e favoritos; confira pelo outro PC. As alterações de formulário V3 são enviadas em um único lote transacional.
4. Abra mídia/Explorer e confira thumbnails locais em ambos. A API não envia o conteúdo dos vídeos nem os copia para os clientes.
5. Em Smart Locate, escolha uma raiz autorizada do servidor. Dois usuários que pedirem a mesma busca compartilham o trabalho em andamento; só há uma varredura pesada por vez. Revise/aplique as opções; os outros clientes recebem os eventos dos vínculos atualizados.
6. Desconecte temporariamente a rede do cliente. O aplicativo deve informar falha, manter o editor e recusar gravações. Após a reconexão, as listas visíveis são atualizadas, sem recarregar editores abertos. Em caso de sessão expirada, use **Conexão…** para entrar novamente.
7. Navegue pelas páginas de cem pautas; o servidor limita cada resposta a no máximo duzentas pautas. A exportação do acervo percorre páginas por API.

O I/O HTTP dos slots legados é executado em worker com um event loop Qt ativo, preservando a responsividade sem reescrever as telas. Os eventos não baixam o banco inteiro; só geram recarga da consulta/lista visível quando há mudanças. Os editores preservam a revisão capturada ao abrir. Sem rede não há gravação local nem criação de outro banco. Se a resposta de uma gravação se perder, repetir o mesmo envio reutiliza o identificador da operação, evitando duplicação de pautas; não altere os campos antes de conferir o resultado.

## 7. Backup e recuperação

`backup_interval_seconds` (padrão 3600, mínimo 60) e `backup_retention` (padrão 30 arquivos) são configuráveis. O agendador usa a API de backup do SQLite, grava primeiro um arquivo parcial, testa integridade/vínculos e somente então publica o `.sqlite` datado. Não copia simplesmente o arquivo ativo. Erros ficam no log. A retenção nunca remove o banco principal; mantenha também cópias externas conforme a política da equipe.

Para restaurar, pare o serviço, feche versões locais antigas e execute no servidor:

```powershell
Stop-Service PautasServer
.\PautasServidor.exe admin restore --config 'C:\ProgramData\PautasServer\server.json' --source 'E:\BackupsPautas\pautas-AAAAmmdd-HHMMSS.sqlite' --confirm-service-stopped
Start-Service PautasServer
```

A restauração valida o backup e salva uma cópia recuperável do banco atual antes de substituí-lo. O bloqueio de instância e a verificação de WAL impedem restauração sobre um serviço ativo. Teste periodicamente a restauração em ambiente separado.

## Validação e pendências de implantação

Execute a suíte no ambiente com `requirements-test-network.txt` instalado:

```powershell
.\.venv-build\Scripts\python.exe -B -m unittest discover -s tests -v
```

Os testes usam bancos temporários, dois clientes HTTP, revisões concorrentes, autenticação/permissões, idempotência, UNC, paginação, eventos, Smart Locate no servidor, reinício, perda/reconexão lógica, backup/restauração e preservação dos dados. Os testes anteriores de clientes e Smart Locate permanecem na suíte. Testes de API em processo não provam conectividade entre três PCs físicos: a montagem dos HDs/SMB, reprodução de vídeos reais, credenciais Windows, firewall, TLS e início automático após reiniciar o Windows devem ser conferidos no local com as etapas acima.

### Resultado desta entrega

- A suíte anterior tinha **49 testes aprovados**, incluindo os 32 testes originais. A validação desta revisão está registrada na seção final deste manual.
- Pacotes Windows x64 gerados com PyInstaller 6.21.0 e Python 3.13.14 no Windows 11. Ainda é necessária a conferência de instalação/serviço no Windows 10 de destino.
- Teste dos executáveis com TCP real em `127.0.0.1`: dois clientes autenticados, criação pelo PC01/leitura pelo PC02, reinício do processo servidor com dados preservados e backup consistente. Usou apenas diretórios/banco/usuários temporários.
- Pacote cliente iniciou em modo Qt `offscreen`, permaneceu ativo no diálogo de conexão e não criou SQLite local. Esse teste não substitui a reprodução real por SMB.
- Scripts PowerShell passaram na análise sintática; `git diff --check` passou. Os instaladores não foram executados contra o Windows de produção: serviço, firewall e compartilhamentos reais permanecem como implantação local.
- Migração exercitada em uma cópia consistente do banco real; o banco original não foi alterado.

Arquivos existentes alterados nesta etapa: `.gitignore`, `database.py`, `exporter.py`, `file_scanner.py`, `main.py`, `smart_locate.py`, `ui/ui_create.py`, `ui/ui_home.py`, `ui/ui_search.py`, `ui/ui_locate.py`, `ui_v3/app.py`, `ui_v3/backend.py` e `ui_v3/screens.py`.

Arquivos novos: os módulos em `network/`, `client_main.py`, `server_service.py`, `requirements-client.txt`, `requirements-server.txt`, `requirements-test-network.txt`, `tests/test_network.py`, `packaging/build-network.ps1`, `packaging/install-client.ps1`, `packaging/install-server.ps1`, `packaging/smoke-network.py` e este guia.

## Verificações adicionais e referências de mídia

Antes de registrar o serviço, o instalador executa `PautasServidor.exe admin check --config caminho-do-server.json --strict`. Esse diagnóstico não cria nem migra o banco: verifica integridade do banco existente (ou identifica que será um banco novo) e acesso às raízes locais. Em caso de falha, interrompe a instalação e preserva a configuração para correção. Depois de iniciar o serviço, confere se `/health` responde com 401, como esperado para uma rota protegida. O login nos clientes valida também uma resposta autenticada e as operações reais devem ser testadas com o procedimento acima.

O módulo `network/configuration.py` valida a configuração tanto no administrador local quanto na API e no serviço. Banco e raízes físicas em unidades de rede mapeadas são rejeitados antes da inicialização. `network/diagnostics.py` implementa os diagnósticos. Logs importantes incluem identificador da requisição/operação, usuário autenticado, tarefa de localização e lote aplicado/desfeito, sem registrar senhas, tokens ou conteúdo dos comentários.

O próprio IP privado configurado como endereço de escuta também é autorizado para o autoteste do servidor, além do loopback e dos clientes definidos. Isso não autoriza outros computadores da mesma sub-rede. Se configurar um hostname no campo de escuta, inclua seus IPs locais explicitamente em `allowed_clients`; para a instalação assistida, use o IP LAN fixo solicitado pelo roteiro.

Cada raiz pode ter um identificador estável, por exemplo:

```json
{
  "id": "PRODUCOES",
  "name": "Produções",
  "local": "D:\\Producoes",
  "share": "\\\\SERVIDOR\\Producoes"
}
```

Novas configurações recebem IDs persistidos (`media_1`, `media_2`, ...); configurações antigas sem ID continuam aceitas. Para estabilidade ao reordenar configurações antigas, atribua IDs explícitos e únicos. A camada de mídia resolve referências como `{"root_id":"PRODUCOES","relative_path":"Cliente\\Pauta001\\Camera01\\Video001.mp4"}` para disco local ou UNC. A rota autenticada `/media/resolve` devolve somente o UNC autorizado. Caminhos absolutos ou com `..` são recusados.

Os registros existentes conservam seus caminhos e IDs. Essa representação lógica é suportada sem recriar tabelas ou regravar toda a coleção; o Smart Locate continua sendo o responsável por confirmar e persistir os novos caminhos físicos quando os materiais foram movidos.

## Tarefas remotas e cancelamento

As tarefas têm ID, estado (`queued`, `running`, `cancelling`, `cancelled`, `completed` ou `failed`), contadores, erro e horários de início/fim em ISO 8601/UTC. O cliente exibe o ID e o estado em português, e inclui esses metadados no relatório de localização. Tarefas/resultados de pesquisa são temporários (até oito resultados e trinta minutos de retenção); após reiniciar o serviço, uma pesquisa interrompida deve ser iniciada novamente. O histórico dos lotes já aplicados e seu desfazimento permanecem no SQLite.

O cancelamento remoto é cooperativo durante a busca e mantém os resultados já identificados. Uma confirmação de atualização iniciada no servidor permanece transacional: o botão de cancelamento da pesquisa não interrompe um commit em andamento nem deixa um lote pela metade. Depois de aplicar, ambos os clientes observam os eventos de alteração; um editor com revisão antiga recebe conflito em vez de sobrescrever os vínculos recuperados.

## Conferência física obrigatória no Windows 10

- Reiniciar o Windows 10 e confirmar em **Serviços** que `PautasServer` iniciou automaticamente, sem terminal nem aplicativo desktop abertos.
- Testar a recuperação automática do serviço após falha, observando os logs e o estado do serviço.
- Entrar pelo PC01 e PC02, criar/editar/consultar registros e provocar um conflito de edição controlado.
- Conferir os quatro indicadores em cada estação e testar leitura/reprodução real por cada compartilhamento e HD.
- Executar localização, cancelamento e desfazimento de um lote de teste, verificando os resultados nas duas estações.
- Desconectar/reconectar uma estação e confirmar preservação dos rascunhos, atualização das listas e necessidade de novo login após reiniciar o servidor.
- Restaurar um backup em ambiente de teste antes de depender do procedimento em produção.

Estas etapas dependem das máquinas, dos HDs e das credenciais locais. Não foram executadas nos três computadores físicos durante o desenvolvimento e não são substituídas pelos testes locais.

## Resultado da revisão cliente-servidor

**57 testes automatizados aprovados**, mantendo os 32 testes originais e passando por 25 testes de rede. As verificações novas cobrem cancelamento remoto com resultados preservados, estados/horários e falhas de tarefa, desfazimento observado pelo outro cliente, duas raízes de mídia, resolução local/UNC por ID e caminho relativo, proteção contra navegação fora das raízes, diagnóstico sem alterar o banco, sondagem SMB isolada e seleção das interfaces principal/V3 com login obrigatório. A autorização do próprio servidor no autoteste é exercitada sem liberar um terceiro PC não autorizado.

Os executáveis Windows foram recompilados. O teste dos pacotes usa TCP real em `127.0.0.1` para dois clientes autenticados, gravação/leitura, reinício do processo servidor e backup. Também verifica o diagnóstico de instalação sem criação indevida do banco e a inicialização de ambas as interfaces em `offscreen`, sem SQLite local. Isso valida os pacotes nesta máquina, sem substituir o teste de serviço/SMB nos equipamentos de destino.

Nesta revisão, foram adicionados `network/configuration.py`, `network/diagnostics.py` e este manual. Foram ajustados o gerenciador de tarefas, a API, resolução de mídias, cliente de rede, indicadores da interface, lançador do cliente, serviço, administrador local, instaladores/build e testes. O motor `smart_locate.py` e as operações existentes de `database.py` foram preservados nesta etapa; a janela `ui/ui_locate.py` recebeu somente a apresentação da identificação e do estado da tarefa remota.
