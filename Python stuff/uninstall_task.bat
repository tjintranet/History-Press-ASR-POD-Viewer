@echo off
:: ============================================================
:: uninstall_task.bat - Remove ASR Watcher from Task Scheduler
:: ============================================================
:: Stops the running watcher (if any) and removes the scheduled
:: task so it no longer starts at boot.
::
:: MUST be run as Administrator.
:: ============================================================

set TASK_NAME=ASR Folder Watcher

:: Must be run as Administrator
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click uninstall_task.bat and choose "Run as administrator".
    pause
    exit /b 1
)

:: Stop the running process first
echo Stopping any running watcher process...
for /f "tokens=1" %%P in ('wmic process where "name='python.exe' and commandline like '%%watch_asr_folder%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    echo   Terminating PID %%P
    taskkill /PID %%P /F >nul 2>&1
)
taskkill /FI "WINDOWTITLE eq ASR Folder Watcher" /F >nul 2>&1

:: Check the task exists
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if errorlevel 1 (
    echo No scheduled task named "%TASK_NAME%" was found.
    pause
    exit /b 0
)

:: Remove the task
echo Removing scheduled task "%TASK_NAME%"...
schtasks /delete /tn "%TASK_NAME%" /f

if errorlevel 1 (
    echo ERROR: Failed to remove the scheduled task.
    pause
    exit /b 1
)

echo.
echo Task "%TASK_NAME%" removed successfully.
echo The watcher will no longer start automatically at boot.
pause
