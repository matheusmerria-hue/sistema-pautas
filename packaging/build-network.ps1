param([string]$Python = 'python', [ValidateSet('All','Client','Server')][string]$Target='All')
$ErrorActionPreference='Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$sharedArgs = @('--noconfirm','--clean','--onedir','--distpath','release-network','--workpath','build-network','--specpath','packaging/generated')
$assetsPath=Join-Path $projectRoot 'assets'
$iconPath=Join-Path $assetsPath 'icons/logo.ico'
if ($Target -in @('All','Client')) {
    & $Python -m PyInstaller @sharedArgs --name PautasCliente --windowed --icon $iconPath --add-data "$assetsPath;assets" --exclude-module fastapi --exclude-module uvicorn --exclude-module httpx --exclude-module pydantic --exclude-module win32service client_main.py
    if ($LASTEXITCODE -ne 0) { throw 'Build do cliente falhou' }
}
if ($Target -in @('All','Server')) {
    & $Python -m PyInstaller @sharedArgs --name PautasServidor --console --exclude-module PySide6 --exclude-module cv2 --collect-all uvicorn --collect-all fastapi --collect-all starlette --collect-all pydantic --hidden-import win32timezone --hidden-import win32serviceutil --hidden-import servicemanager server_service.py
    if ($LASTEXITCODE -ne 0) { throw 'Build do servidor falhou' }
}
Copy-Item -LiteralPath 'packaging/install-client.ps1' -Destination 'release-network/install-client.ps1' -Force
Copy-Item -LiteralPath 'packaging/install-server.ps1' -Destination 'release-network/install-server.ps1' -Force
Copy-Item -LiteralPath 'REDE_LOCAL.md' -Destination 'release-network/REDE_LOCAL.md' -Force
Copy-Item -LiteralPath 'INSTALACAO_REDE.md' -Destination 'release-network/INSTALACAO_REDE.md' -Force
Write-Output 'Build concluído. Distribua a pasta completa de cada aplicativo, incluindo _internal.'
