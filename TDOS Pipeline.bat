@echo off
rem Opens the TDOS Pipeline desktop app (ui\app.py) with no console window.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo No .venv here. Create it and install the app's dependencies first:
    echo   py -3.11 -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements-ui.txt -r requirements-transcribe.txt
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "ui\app.py"
