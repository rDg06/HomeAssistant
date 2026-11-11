@echo off
rem Faz a app arrancar sozinha (minimizada) sempre que entras no Windows.
rem Para desfazer, corre este ficheiro com "remover": arrancar-com-o-windows.bat remover
set "ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Casa.cmd"
if /i "%~1"=="remover" (
    del "%ATALHO%" 2>nul
    echo A app ja nao arranca com o Windows.
    pause
    exit /b
)
> "%ATALHO%" echo @start "Casa" /min "%~dp0iniciar.bat" sem-browser
echo Feito. A app vai arrancar sozinha da proxima vez que entrares no Windows.
echo (Para desfazer: arrancar-com-o-windows.bat remover)
pause
