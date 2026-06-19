@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10+ is required but was not found on PATH.
  echo Install from https://www.python.org/downloads/ and enable "Add to PATH".
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv venv
  if errorlevel 1 exit /b 1
)

call venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

echo Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Dashboard: http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
echo.

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
