@echo off
setlocal
cd /d "%~dp0"

title GameSite Server

echo ========================================
echo            GameSite Server
echo ========================================
echo.

REM Find Python without relying on the PATH if possible.
set "PYTHON="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON=py"
if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON=python"
)

if not defined PYTHON (
    echo Python was not found.
    echo Please install Python 3.10 or newer and enable Add Python to PATH.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Installing/checking dependencies...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Starting GameSite...
echo Website: http://127.0.0.1:8000/
echo Close this window to stop the server.
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:8000/"

"venv\Scripts\python.exe" main.py

pause
