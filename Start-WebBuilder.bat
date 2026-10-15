@echo off
setlocal
title Printer MSI Package Generator

set PYTHONIOENCODING=utf-8
cd /d "%~dp0web_builder"

:: Terminate any stale process currently occupying port 5000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo ==========================================================
echo        Printer MSI Package Generator Web Service
echo ==========================================================
echo.
echo Starting web server at http://127.0.0.1:5000 ...
echo.

:: Launch the browser after 2 seconds
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:5000"

:: Start Flask app
python app.py

pause
