@echo off
setlocal EnableExtensions EnableDelayedExpansion
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

set "REQ_STAMP=venv\.requirements.stamp"
set "NEED_INSTALL="
if not exist "%REQ_STAMP%" (
  set "NEED_INSTALL=1"
) else (
  for /f %%i in ('powershell -NoProfile -Command "if ((Get-Item requirements.txt).LastWriteTimeUtc -gt (Get-Item '%REQ_STAMP%').LastWriteTimeUtc) { 1 } else { 0 }"') do set "NEED_INSTALL=%%i"
  if "!NEED_INSTALL!"=="0" set "NEED_INSTALL="
)

if defined NEED_INSTALL (
  echo Installing dependencies...
  python -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
  copy /y nul "%REQ_STAMP%" >nul
) else (
  echo Dependencies up to date, skipping install.
)

echo.
echo Dashboard: http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
echo.

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
