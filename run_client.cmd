@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "CLIENT_PYTHON=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "CLIENT_PYTHON=..\.venv\Scripts\python.exe"
) else (
    echo [ERROR] Python virtual environment was not found.
    echo Create one with: py -3.13 -m venv .venv
    echo Then install dependencies with: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

"%CLIENT_PYTHON%" client.py
set "CLIENT_EXIT_CODE=%ERRORLEVEL%"

if not "%CLIENT_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Gomoku client exited with code %CLIENT_EXIT_CODE%.
    pause
)

exit /b %CLIENT_EXIT_CODE%
