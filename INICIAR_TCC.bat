@echo off
chcp 65001 > nul
title Sistema de Maturação Café Arara - TCC
color 0A

echo ========================================================================
echo    COFFEE ARARA - IDENTIFICACAO E MATURACAO AUTOMATICA (TCC)
echo    Visao Computacional com Deep Learning (YOLOv8 + Streamlit)
echo ========================================================================
echo.

cd /d "%~dp0"

:: 1. Verificar se Python esta instalado
set PYTHON_EXE=
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
        if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        if exist "C:\Python312\python.exe" set "PYTHON_EXE=C:\Python312\python.exe"
        if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"
        if exist "C:\Python310\python.exe" set "PYTHON_EXE=C:\Python310\python.exe"
    )
)

if "%PYTHON_EXE%"=="" (
    color 0C
    echo [ERRO CRITICO] O Python nao foi encontrado no seu computador!
    echo Por favor, instale o Python 3.10+ em: https://www.python.org/downloads/
    echo Certifique-se de marcar "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

:: 2. Criar venv se nao existir
if not exist "venv\Scripts\python.exe" (
    echo [1/3] Criando ambiente virtual isolado (venv)... Aguarde...
    "%PYTHON_EXE%" -m venv venv
    if %ERRORLEVEL% neq 0 (
        color 0C
        echo [ERRO] Falha ao criar o ambiente virtual venv.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado com sucesso!
) else (
    echo [1/3] Ambiente virtual (venv) verificado e pronto.
)

:: 3. Verificar e instalar requisitos
if not exist "venv\Scripts\streamlit.exe" (
    echo.
    echo [2/3] Baixando e instalando todos os requisitos (requirements.txt)...
    echo       (YOLOv8, Streamlit, OpenCV, Torch, etc. Isso pode levar alguns minutos)...
    echo.
    "venv\Scripts\python.exe" -m pip install --upgrade pip
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [AVISO] Ocorreram avisos durante a instalacao dos requisitos.
    ) else (
        echo [OK] Todos os requisitos foram instalados com sucesso!
    )
) else (
    echo [2/3] Requisitos e dependencias ja estao instalados!
)

:: 4. Iniciar Streamlit e abrir navegador
echo.
echo ========================================================================
echo    >> SERVIDOR LOCAL INICIADO COM SUCESSO! <<
echo    Acesse no navegador: http://localhost:8501
echo    (Uma aba do navegador sera aberta automaticamente em instantes)
echo ========================================================================
echo    * Para encerrar a aplicacao: feche esta janela ou aperte Ctrl+C.
echo ========================================================================
echo.

start "" http://localhost:8501
"venv\Scripts\streamlit.exe" run app/app.py --server.port 8501

pause
