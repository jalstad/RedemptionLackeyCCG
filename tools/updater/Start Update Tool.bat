@echo off
REM Double-click to launch the Redemption Update Tool.
cd /d "%~dp0\..\.."

REM Locate Python. Prefer the "py" launcher (bundled with python.org installs),
REM then a real "python" on PATH. The Microsoft Store stub is skipped: it lives
REM under WindowsApps, reports success to "where", but only opens the Store.
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
  for /f "delims=" %%I in ('where python 2^>nul ^| find /i /v "WindowsApps"') do (
    if not defined PY set "PY=%%I"
  )
)

if not defined PY (
  echo.
  echo Python 3 was not found.
  echo Install it from https://www.python.org/downloads/ and tick
  echo "Add Python to PATH" during setup, then run this again.
  echo.
  pause
  exit /b 1
)

REM Make sure it's actually Python 3 (an old "python" alias could be Python 2).
"%PY%" -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" 2>nul
if errorlevel 1 (
  echo.
  echo The Python that was found is not version 3.
  echo Install Python 3 from https://www.python.org/downloads/ and run this again.
  echo.
  pause
  exit /b 1
)

"%PY%" -m tools.updater.server
pause
