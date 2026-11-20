@echo off
title Cafe Arara AI - Dashboard TCC
color 0A

echo ========================================================================
echo    CAFE ARARA AI - VISAO COMPUTACIONAL E APRENDIZADO CONTINUO (TCC)
echo    Classificacao da Maturacao com Deep Learning YOLOv8 + Dashboard
echo ========================================================================
echo.

cd /d "%~dp0"

set "VENV_DIR=%~dp0venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PYTHONPATH=%~dp0"

if not exist "%PYTHON_EXE%" (
    echo [ERRO] Ambiente virtual venv nao encontrado!
    pause
    exit /b 1
)

echo [1/2] Verificando integridade das bibliotecas de IA...
"%PYTHON_EXE%" "%~dp0verify_environment.py"
if errorlevel 1 (
    echo.
    echo [AVISO] Nao foi possivel iniciar os modulos de visao computacional.
    pause
    exit /b 1
)

echo.
echo [2/2] Iniciando Servidor Web do Dashboard...
echo Acesse no navegador: http://localhost:8501
echo Para fechar a aplicacao: feche esta janela ou aperte Ctrl+C.
echo.

"%PYTHON_EXE%" "%~dp0web\server.py"

echo.
pause
