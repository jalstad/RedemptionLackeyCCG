@echo off
REM Double-click to launch the Redemption Update Tool.
cd /d "%~dp0\..\.."
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 is not installed. Please install it from https://www.python.org/downloads/
  pause
  exit /b 1
)
python -m tools.updater.server
pause
