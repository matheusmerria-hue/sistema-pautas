@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 verificar_pautas.py
    if errorlevel 1 pause
    exit /b
)
where python >nul 2>nul
if not errorlevel 1 (
    python verificar_pautas.py
    if errorlevel 1 pause
    exit /b
)
echo Instale Python 3.10 ou superior com Tcl/Tk e execute novamente.
pause
