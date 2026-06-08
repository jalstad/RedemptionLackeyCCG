@echo off
REM Double-click this ONCE to enable the image-cropping step (Step 0).
REM It installs the free "Pillow" library. Everything else works without it.
cd /d "%~dp0\..\.."

REM Locate Python. Prefer the "py" launcher; skip the Microsoft Store stub.
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

echo Installing the image-cropping library (Pillow)...
echo.
"%PY%" -m pip install -r tools\updater\requirements.txt
if errorlevel 1 (
  echo.
  echo Install failed. Check your internet connection and try again.
  echo.
  pause
  exit /b 1
)
echo.
echo Done. If the update tool is already open, close its window and start it
echo again before using the Crop step -- it only sees Pillow after a restart.
pause
