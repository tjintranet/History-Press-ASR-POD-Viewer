@echo off
:: ============================================================
:: install_task.bat - Register ASR Watcher with Task Scheduler
:: ============================================================
:: Creates a scheduled task that starts the watcher automatically
:: when the server boots, running under a specified user account.
::
:: MUST be run as Administrator.
::
:: Edit the CONFIGURATION section below before running.
:: ============================================================

:: ---- CONFIGURATION ----------------------------------------
set TASK_NAME=ASR Folder Watcher
set SCRIPT_DIR=C:\ASR
set INPUT_DIR=C:\ASR\input
set OUTPUT_DIR=C:\ASR\output
set LOG_FILE=C:\ASR\logs\asr_watcher.log

:: Account the task runs under.
:: Use a dedicated service account if available; otherwise use
:: SYSTEM for a fully automated no-login startup.
:: Example service account: DOMAIN\svc_asr  or  .\svc_asr
set RUN_AS_USER=SYSTEM

:: Only required if RUN_AS_USER is NOT SYSTEM.
:: Leave blank if using SYSTEM.
set RUN_AS_PASS=
:: -----------------------------------------------------------

:: Must be run as Administrator
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click install_task.bat and choose "Run as administrator".
    pause
    exit /b 1
)

set PYTHON=python
set SCRIPT=%SCRIPT_DIR%\watch_asr_folder.py

:: Verify the script exists before registering
if not exist "%SCRIPT%" (
    echo ERROR: Script not found at %SCRIPT%
    pause
    exit /b 1
)

:: Remove any existing task with the same name
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo Removing existing task "%TASK_NAME%"...
    schtasks /delete /tn "%TASK_NAME%" /f >nul
)

echo Registering scheduled task "%TASK_NAME%"...

:: Build the command the task will run
set CMD="%PYTHON%" "%SCRIPT%" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --log "%LOG_FILE%" --no-console

if /i "%RUN_AS_USER%"=="SYSTEM" (
    :: SYSTEM account - no password needed, task runs in background
    schtasks /create ^
        /tn "%TASK_NAME%" ^
        /tr %CMD% ^
        /sc ONSTART ^
        /delay 0001:00 ^
        /ru SYSTEM ^
        /rl HIGHEST ^
        /f
) else (
    :: Named user account
    if "%RUN_AS_PASS%"=="" (
        echo ERROR: RUN_AS_PASS must be set when using a named user account.
        pause
        exit /b 1
    )
    schtasks /create ^
        /tn "%TASK_NAME%" ^
        /tr %CMD% ^
        /sc ONSTART ^
        /delay 0001:00 ^
        /ru "%RUN_AS_USER%" ^
        /rp "%RUN_AS_PASS%" ^
        /rl HIGHEST ^
        /f
)

if errorlevel 1 (
    echo ERROR: Failed to create scheduled task.
    echo Check the account name and password, and that you are running as Administrator.
    pause
    exit /b 1
)

echo.
echo Task "%TASK_NAME%" registered successfully.
echo.
echo Settings:
echo   Trigger  : At system startup (with 1-minute delay)
echo   Run as   : %RUN_AS_USER%
echo   Command  : %CMD%
echo.
echo The watcher will start automatically on next reboot.
echo To start it now without rebooting, run start.bat or:
echo   schtasks /run /tn "%TASK_NAME%"
echo.
echo To remove the task later, run uninstall_task.bat
pause
