@echo off
setlocal

cd /d "%~dp0"
title Sistema Web - Checklist de Contratacao

if "%PORT%"=="" set "PORT=5010"
set "APP_URL=http://127.0.0.1:%PORT%"

echo ===============================================
echo  Sistema Web - Checklist de Contratacao
echo ===============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python nao foi encontrado no PATH.
    echo Instale o Python ou adicione-o ao PATH e tente novamente.
    echo.
    pause
    exit /b 1
)

python -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo Flask nao encontrado. Instalando dependencias...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Nao foi possivel instalar as dependencias.
        pause
        exit /b 1
    )
)

echo Iniciando servidor em %APP_URL%
echo.
echo Acesso inicial:
echo   Email: admin@example.com
echo   Senha: admin123
echo.
echo Para encerrar, pressione CTRL+C nesta janela.
echo.

start "" "%APP_URL%"
python -B app.py

echo.
echo Servidor encerrado.
pause
