@echo off
:: ============================================================
:: start.bat - Start the ASR Folder Watcher
:: ============================================================
:: Edit the paths in the CONFIGURATION section below to match
:: your installation before first use.
:: ============================================================

:: ---- CONFIGURATION ----------------------------------------
set SCRIPT_DIR=C:\ASR
set INPUT_DIR=C:\ASR\input
set OUTPUT_DIR=C:\ASR\output
set LOG_FILE=C:\ASR\logs\asr_watcher.log
:: -----------------------------------------------------------

set PYTHON=python
set SCRIPT=%SCRIPT_DIR%\watch_asr_folder.py

:: Check the script exists
if not exist "%SCRIPT%" (
    echo ERROR: watch_asr_folder.py not found at %SCRIPT%
    pause
    exit /b 1
)

:: Check if already running
for /f "tokens=1" %%P in ('wmic process where "name='python.exe' and commandline like '%%watch_asr_folder%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    echo WARNING: Watcher is already running as PID %%P
    echo Run stop.bat first if you need to restart it.
    pause
    exit /b 1
)

echo Starting ASR Folder Watcher...
echo   Input  : %INPUT_DIR%
echo   Output : %OUTPUT_DIR%
echo   Log    : %LOG_FILE%
echo.

:: /MIN         - start minimised (appropriate for server use)
:: --no-console - log to file only; no console output needed
start "ASR Folder Watcher" /MIN "%PYTHON%" "%SCRIPT%" ^
    --input      "%INPUT_DIR%"  ^
    --output     "%OUTPUT_DIR%" ^
    --log        "%LOG_FILE%"   ^
    --no-console

echo Watcher started in minimised window.
echo Run stop.bat to stop it.
timeout /t 3 >nul
