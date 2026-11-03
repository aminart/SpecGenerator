@echo off
setlocal

if not exist .venv\Scripts\python.exe (
    echo L'environnement virtuel est absent.
    echo Lancez d'abord install_windows.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if not exist frontend\dist\index.html (
    echo Le frontend n'est pas compile.
    echo Relancez install_windows.bat
    pause
    exit /b 1
)

echo SpecGen demarre sur http://127.0.0.1:8000
start "" http://127.0.0.1:8000
uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
pause
