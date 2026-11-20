@echo off
chcp 65001 > nul
title Cafe Arara AI — Dashboard Profissional TCC
color 0A

echo ========================================================================
echo    CAFE ARARA AI — VISAO COMPUTACIONAL E APRENDIZADO CONTINUO (TCC)
echo    Classificacao da Maturacao com Deep Learning YOLOv8 + React Dashboard
echo ========================================================================
echo.

cd /d "%~dp0"

set "VENV_DIR=%~dp0venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

:: 1. Verificar ambiente
if not exist "%PYTHON_EXE%" (
    echo [1/3] Localizando Python no sistema...
    where python >nul 2>nul
    if errorlevel 1 (
        color 0C
        echo [ERRO] Python nao foi encontrado no sistema!
        echo Instale o Python em https://www.python.org/downloads/
        echo e marque a opcao "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )
    echo [1/3] Criando ambiente virtual venv...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        color 0C
        echo [ERRO] Falha ao criar o ambiente virtual venv.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado com sucesso!
) else (
    echo [1/3] Ambiente virtual venv pronto.
)

:: 2. Testar e validar bibliotecas
echo [2/3] Verificando integridade das bibliotecas de IA...
"%PYTHON_EXE%" "%~dp0verify_environment.py"
if errorlevel 1 (
    echo.
    echo [AVISO] Nao foi possivel iniciar os modulos de visao computacional.
    echo Siga as instrucoes exibidas acima e tente novamente.
    echo.
    pause
    exit /b 1
)

:: 3. Iniciar Servidor Web React e abrir navegador
echo.
echo ========================================================================
echo    SERVIDOR WEB DO DASHBOARD INICIADO COM SUCESSO!
echo    Acesse no navegador: http://localhost:8501
echo ========================================================================
echo    * Interface React 18 + Deep Learning YOLOv8 ativa.
echo    * Para fechar a aplicacao: feche esta janela ou aperte Ctrl+C.
echo ========================================================================
echo.

start "" "http://localhost:8501"
"%PYTHON_EXE%" "%~dp0web\server.py"

echo.
echo Aplicacao finalizada.
pause
