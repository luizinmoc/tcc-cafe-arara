@echo off
chcp 65001 > nul
echo =======================================================
echo    ☕ ENVIAR PROJETO TCC CAFÉ ARARA PARA O GITHUB
echo =======================================================
echo.

set PATH=%LOCALAPPDATA%\Programs\Git\cmd;%PATH%

set /p REPO_URL="Cole aqui a URL do seu repositorio no GitHub: "

if "%REPO_URL%"=="" (
    echo [ERRO] Nenhuma URL informada. Operacao cancelada.
    pause
    exit /b 1
)

echo.
echo [1/3] Conectando ao repositorio remoto...
git remote remove origin 2>nul
git remote add origin %REPO_URL%

echo [2/3] Verificando branch...
git branch -M main

echo [3/3] Enviando arquivos para o GitHub...
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo =======================================================
    echo   [SUCESSO] Projeto enviado para o GitHub com sucesso!
    echo =======================================================
) else (
    echo.
    echo [AVISO] Se solicitou login, faca a confirmacao na janela do navegador.
)

echo.
pause
