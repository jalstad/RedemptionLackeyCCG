@echo off
REM Windows shim so `make run`, `make setup`, `make test`, `make clean` work
REM WITHOUT installing GNU make. (cmd runs this make.bat from the current folder.)
REM Non-technical maintainers don't need this at all — just double-click
REM tools\updater\Start Update Tool.bat to launch the tool.
setlocal
cd /d "%~dp0"

REM Locate Python. Prefer the "py" launcher; skip the Microsoft Store stub.
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
  for /f "delims=" %%I in ('where python 2^>nul ^| find /i /v "WindowsApps"') do (
    if not defined PY set "PY=%%I"
  )
)
if not defined PY (
  echo Python 3 was not found. Install it from https://www.python.org/downloads/
  echo and tick "Add Python to PATH" during setup, then try again.
  exit /b 1
)

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=help"

if /i "%TARGET%"=="run"   goto run
if /i "%TARGET%"=="setup" goto setup
if /i "%TARGET%"=="test"  goto test
if /i "%TARGET%"=="clean" goto clean
goto help

:run
"%PY%" -m tools.updater.server
goto end

:setup
"%PY%" -m pip install -r tools\updater\requirements.txt
goto end

:test
"%PY%" -m unittest discover -s tools/updater/tests -v
goto end

:clean
for /d /r tools\updater %%D in (__pycache__) do if exist "%%D" rd /s /q "%%D"
goto end

:help
echo Redemption plugin update tool - available commands:
echo.
echo   make.bat run      Start the tool (opens http://127.0.0.1:8765 in your browser)
echo   make.bat setup    One-time: install Pillow (only needed for image cropping)
echo   make.bat test     Run the automated test suite
echo   make.bat clean    Remove Python cache files
echo.
echo Not comfortable with the terminal? Double-click
echo   tools\updater\Start Update Tool.bat            (to run the tool)
echo   tools\updater\Install image cropping.bat       (one-time, for cropping)

:end
