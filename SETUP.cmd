@echo off
rem MLP Automation setup - one click. New PC: installs what is missing and sets up the Web Dev Tracker.
rem Older version on this PC: updates it and keeps your settings, pages, notes and QA lessons. Safe to run again.
cd /d "%~dp0"
set "PY="
for /f "delims=" %%i in ('python -c "import sys;print(sys.executable) if sys.version_info>=(3,10) else None" 2^>nul') do set "PY=%%i"
if not defined PY for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable) if sys.version_info>=(3,10) else None" 2^>nul') do set "PY=%%i"
if not defined PY (
  echo Python is not installed - installing it now, this takes a few minutes...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
  echo.
  echo Could not install Python by itself. Install Python 3.12 from python.org - tick "Add to PATH" - then run SETUP.cmd again.
  pause
  exit /b 1
)
"%PY%" "%~dp0tracker\setup_tracker.py"
echo.
pause
