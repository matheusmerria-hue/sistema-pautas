param([string]$Destination = "$env:LOCALAPPDATA\Programs\PautasCliente")
$ErrorActionPreference='Stop'
$source = Join-Path $PSScriptRoot 'PautasCliente'
if (-not (Test-Path -LiteralPath (Join-Path $source 'PautasCliente.exe'))) { throw 'Pacote PautasCliente não encontrado ao lado deste script.' }
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $Destination -Recurse -Force
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Sistema de Pautas.lnk'))
$shortcut.TargetPath = Join-Path $Destination 'PautasCliente.exe'
$shortcut.WorkingDirectory = $Destination
$shortcut.Save()
$v3Shortcut=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Sistema de Pautas V3.lnk'))
$v3Shortcut.TargetPath=Join-Path $Destination 'PautasCliente.exe'
$v3Shortcut.Arguments='--ui v3'
$v3Shortcut.WorkingDirectory=$Destination
$v3Shortcut.Save()
Write-Output 'Cliente instalado. Abra o atalho, informe o servidor e entre com seu usuário. Configurações existentes foram preservadas.'
