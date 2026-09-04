@echo off
setlocal

cd /d "%~dp0"

set "CLIENT_DIR=%~dp0"
set "BUILD_ROOT=%CLIENT_DIR%build\windows"
set "BUILD_VENV=%BUILD_ROOT%\.venv"
set "BUILD_PYTHON=%BUILD_VENV%\Scripts\python.exe"
set "DIST_DIR=%CLIENT_DIR%dist\windows"

if not exist "%CLIENT_DIR%\client.py" (
    echo [ERROR] Client entry point was not found: "%CLIENT_DIR%\client.py"
    exit /b 1
)

if not exist "%BUILD_PYTHON%" (
    echo [INFO] Creating the client build environment...
    py -3.13 -m venv "%BUILD_VENV%" 2>nul
    if errorlevel 1 py -3.11 -m venv "%BUILD_VENV%" 2>nul
    if errorlevel 1 python -m venv "%BUILD_VENV%"
    if errorlevel 1 (
        echo [ERROR] Python 3.11 or newer is required.
        exit /b 1
    )
)

echo [INFO] Installing client and build dependencies...
"%BUILD_PYTHON%" -m pip install -r "%CLIENT_DIR%\requirements.txt" pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    exit /b 1
)

echo [INFO] Building OmokClient.exe...
"%BUILD_PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name OmokClient ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_ROOT%\work" ^
    --specpath "%BUILD_ROOT%" ^
    "%CLIENT_DIR%\client.py"

if errorlevel 1 (
    echo [ERROR] Client build failed.
    exit /b 1
)

echo.
echo [SUCCESS] Executable created:
echo "%DIST_DIR%\OmokClient.exe"

exit /b 0
