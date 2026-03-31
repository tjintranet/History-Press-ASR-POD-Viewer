@echo off
:: ============================================================
:: stop.bat — Stop the ASR Folder Watcher
:: ============================================================
:: Finds and terminates any python.exe process running
:: watch_asr_folder.py and closes its console window.
:: ============================================================

echo Stopping ASR Folder Watcher...

:: Find the PID of python.exe running watch_asr_folder.py using WMIC
set FOUND=0
for /f "tokens=1" %%P in ('wmic process where "name='python.exe' and commandline like '%%watch_asr_folder%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    echo   Terminating process PID %%P
    taskkill /PID %%P /F >nul 2>&1
    set FOUND=1
)

:: Also close the titled console window if it is still open
taskkill /FI "WINDOWTITLE eq ASR Folder Watcher" /F >nul 2>&1

if "%FOUND%"=="1" (
    echo Watcher stopped successfully.
) else (
    echo No running ASR Folder Watcher process found.
)

timeout /t 2 >nul
