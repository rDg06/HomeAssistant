@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo A preparar o ambiente pela primeira vez...
    python -m venv .venv || (echo Nao encontrei o Python. Instala-o em python.org. & pause & exit /b 1)
    .venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
)
rem Abre o browser passados 2 segundos, quando o servidor ja esta pronto.
start "" /min cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"
echo A app esta a correr. Fecha esta janela para a desligar.
.venv\Scripts\python run.py
