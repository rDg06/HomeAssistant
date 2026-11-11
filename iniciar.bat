@echo off
rem Arranca a app. Com "sem-browser" (usado no arranque com o Windows) nao abre o browser.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo A preparar o ambiente pela primeira vez...
    python -m venv .venv || (echo Nao encontrei o Python. Instala-o em python.org. & pause & exit /b 1)
)
rem Instala o que faltar (e o que for novo depois de uma atualizacao). E rapido quando ja esta tudo.
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt || (pause & exit /b 1)
if /i not "%~1"=="sem-browser" (
    rem Abre o browser passados 3 segundos, quando o servidor ja esta pronto.
    start "" /min cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:5000"
)
echo Fecha esta janela para desligar a app.
.venv\Scripts\python run.py
if errorlevel 1 pause
