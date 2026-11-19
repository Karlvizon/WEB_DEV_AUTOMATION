@echo off
rem Web Dev Tracker: starts the local tracker (hidden) if it is not running yet, then opens it in your browser.
cd /d "%~dp0"
powershell -NoProfile -Command "try { Invoke-WebRequest http://127.0.0.1:8765/api/version -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  where pythonw >nul 2>nul && (start "" pythonw -I "%~dp0webapp\server.py") || (start "" /min python -I "%~dp0webapp\server.py")
  timeout /t 3 /nobreak >nul
)
start "" http://127.0.0.1:8765
