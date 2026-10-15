@echo off
setlocal
title Printer MSI Builder - Windows Server 2025

cd /d "%~dp0"
set "PACKAGE_DIR=%~dp0"
if "%PACKAGE_DIR:~-1%"=="\" set "PACKAGE_DIR=%PACKAGE_DIR:~0,-1%"

echo ================================================================
echo    Starting Printer MSI Builder Production Server
echo ================================================================
echo Working Directory: %PACKAGE_DIR%
echo.

:: Terminate any stale process on port 5000 if any
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

if not exist "%PACKAGE_DIR%\PrinterMSIBuilder.exe" (
    echo [ERROR] PrinterMSIBuilder.exe was not found in %PACKAGE_DIR%.
    pause
    exit /b 1
)

"%PACKAGE_DIR%\PrinterMSIBuilder.exe"

pause
