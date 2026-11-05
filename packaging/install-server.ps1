# Execute como administrador no servidor. Não cria compartilhamentos amplos de disco.
param([string]$Destination = "$env:ProgramFiles\PautasServidor",
      [string]$ConfigDirectory = "$env:ProgramData\PautasServer")
$ErrorActionPreference='Stop'
$OutputEncoding=New-Object System.Text.UTF8Encoding($false)
foreach ($targetDirectory in @($Destination,$ConfigDirectory)) {
    $absoluteTarget=[IO.Path]::GetFullPath($targetDirectory).TrimEnd('\')
    if ($absoluteTarget -eq [IO.Path]::GetPathRoot($absoluteTarget).TrimEnd('\')) { throw 'Escolha uma subpasta dedicada para instalar o servidor.' }
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Execute o PowerShell como administrador.' }
$source=Join-Path $PSScriptRoot 'PautasServidor'
if (-not (Test-Path -LiteralPath (Join-Path $source 'PautasServidor.exe'))) { throw 'Pacote PautasServidor não encontrado ao lado deste script.' }
$service=Get-Service -Name PautasServer -ErrorAction SilentlyContinue
if ($service -and $service.Status -ne 'Stopped') { throw 'Pare o serviço PautasServer antes de atualizar os binários.' }
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
New-Item -ItemType Directory -Path $ConfigDirectory -Force | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $Destination -Recurse -Force
$exe=Join-Path $Destination 'PautasServidor.exe'
$configPath=Join-Path $ConfigDirectory 'server.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    $db=Read-Host 'Caminho local do banco existente (ou novo banco), fora das pastas compartilhadas'
    $backups=Read-Host 'Diretório de backup em outro disco'
    $bindAddress=Read-Host 'IP LAN fixo do servidor'
    $portText=Read-Host 'Porta da API (exemplo: 8000)'
    $clientAddresses=(Read-Host 'IPs autorizados dos dois clientes, separados por vírgula').Split(',') | ForEach-Object { $_.Trim() }
    $arguments=@('admin','init','--config',$configPath,'--database',$db,'--backup-directory',$backups,'--host',$bindAddress,'--port',$portText)
    do {
        $localRoot=Read-Host 'Pasta/HD local dos materiais'
        $uncRoot=Read-Host 'Compartilhamento UNC correspondente (exemplo: \\SERVIDOR\PRODUCOES)'
        $arguments+=@('--media',"$localRoot=$uncRoot")
        $more=Read-Host 'Adicionar outro HD? (s/N)'
    } while ($more -eq 's')
    foreach ($address in $clientAddresses) { $arguments+=@('--allow',$address) }
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Configuração não concluída' }
}
$settings=Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $settings.users_file)) {
    foreach ($number in @(1,2)) {
        $username=Read-Host "Usuário do PC $number"
        $securePassword=Read-Host 'Senha do aplicativo (mínimo 12 caracteres)' -AsSecureString
        $passwordHandle=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        try {
            $plainPassword=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordHandle)
            $plainPassword | & $exe admin user --config $configPath --username $username --role editor --password-stdin
            if ($LASTEXITCODE -ne 0) { throw 'Cadastro de usuário falhou' }
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordHandle)
            $plainPassword=$null
        }
    }
}
# Verificação somente leitura antes de registrar/iniciar o serviço.
& $exe admin check --config $configPath --strict
if ($LASTEXITCODE -ne 0) { throw 'Banco/mídias não passaram na verificação. Configuração preservada; corrija o acesso e execute novamente.' }
# Arquivos privados acessíveis apenas a Administradores e SYSTEM. SIDs independem do idioma.
& icacls.exe $ConfigDirectory /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F'
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível proteger a configuração' }
if (-not $service) {
    & $exe --startup auto install
    if ($LASTEXITCODE -ne 0) { throw 'Instalação do serviço falhou' }
}
$registryPath='HKLM:\SYSTEM\CurrentControlSet\Services\PautasServer'
New-ItemProperty -LiteralPath $registryPath -Name Environment -PropertyType MultiString -Value @("PAUTAS_SERVER_CONFIG=$configPath") -Force | Out-Null
& sc.exe failure PautasServer reset= 86400 actions= restart/10000/restart/30000/restart/60000
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível configurar reinício automático' }
& sc.exe failureflag PautasServer 1
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível ativar recuperação de falhas do serviço' }
$existingRule=Get-NetFirewallRule -DisplayName 'Pautas API LAN' -ErrorAction SilentlyContinue
if ($existingRule) { throw 'Regra de firewall já existente: confira os IPs e a porta antes de iniciar o serviço manualmente.' }
$remoteAddresses=@($settings.allowed_clients | Where-Object { $_ -notin @('127.0.0.1/32','::1/128') })
if (-not $remoteAddresses) { throw 'Nenhum computador cliente autorizado na configuração.' }
$selfAddress=$null
if ([Net.IPAddress]::TryParse([string]$settings.host,[ref]$selfAddress) -and
    $selfAddress.ToString() -notin @('0.0.0.0','::')) {
    $remoteAddresses=@($remoteAddresses + $selfAddress.ToString() | Select-Object -Unique)
}
New-NetFirewallRule -DisplayName 'Pautas API LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $settings.port -RemoteAddress $remoteAddresses -Program $exe -Profile Private | Out-Null
Start-Service PautasServer
$bindHost=[string]$settings.host
if ($bindHost -eq '0.0.0.0') { $bindHost='127.0.0.1' }
elseif ($bindHost -eq '::') { $bindHost='::1' }
if ($bindHost.Contains(':')) { $bindHost="[$bindHost]" }
$scheme=if ($settings.tls_cert) { 'https' } else { 'http' }
$apiUrl="${scheme}://${bindHost}:$($settings.port)"
$apiReady=$false
for ($attempt=0; $attempt -lt 20; $attempt++) {
    try { Invoke-WebRequest -UseBasicParsing -Uri "$apiUrl/health" -TimeoutSec 2 | Out-Null }
    catch {
        # /health exige autenticação: 401 confirma que o servidor respondeu e protege o endpoint.
        if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { $apiReady=$true;break }
    }
    Start-Sleep -Seconds 1
}
if (-not $apiReady) { throw 'Serviço iniciado, mas a API não respondeu ao teste. Confira logs, certificado TLS e endereço configurado.' }
Write-Output 'Serviço e API verificados. Teste SMB nos dois PCs e siga INSTALACAO_REDE.md.'
