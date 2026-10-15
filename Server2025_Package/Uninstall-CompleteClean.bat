@echo off
setlocal
title Complete Setup Uninstaller - Printer MSI Builder

cd /d "%~dp0"
set "PACKAGE_DIR=%~dp0"
if "%PACKAGE_DIR:~-1%"=="\" set "PACKAGE_DIR=%PACKAGE_DIR:~0,-1%"

:: Check for Administrative Privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Administrator privileges required. Relaunching as Administrator...
    powershell -Command "Start-Process cmd -ArgumentList '/k cd /d \"\"%PACKAGE_DIR%\"\" && \"\"%~nx0\"\"' -Verb RunAs"
    exit /b
)

echo ================================================================
echo    Complete Cleanup & Uninstallation - Printer MSI Builder
echo ================================================================
echo.
echo Target Directory: %PACKAGE_DIR%
echo.

:: 1. Terminate any running web server processes
echo [*] Step 1/4: Stopping running server processes...
taskkill /f /im "PrinterMSIBuilder.exe" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo [OK] Server processes stopped.
echo.

:: 2. Remove Windows Scheduled Task
echo [*] Step 2/4: Removing background startup service...
schtasks /delete /tn "PrinterMSIBuilder_AutoStart" /f >nul 2>&1
echo [OK] Background service removed.
echo.

:: 3. Remove Windows Firewall Rule
echo [*] Step 3/4: Removing firewall rule (Port 5000)...
netsh advfirewall firewall delete rule name="Printer MSI Web Builder" >nul 2>&1
echo [OK] Firewall rule removed.
echo.

:: 4. Clean temporary builds
echo [*] Step 4/4: Cleaning temporary build files...
if exist "%PACKAGE_DIR%\builds" (
    rmdir /s /q "%PACKAGE_DIR%\builds" >nul 2>&1
)
echo [OK] Temporary build files cleaned.
echo.

echo ================================================================
echo   [✓] UNINSTALLATION & CLEANUP COMPLETED!
echo ================================================================
echo.
echo The background service, firewall rules, and server processes
echo have been completely removed from this Windows Server.
echo.
set /p DELETE_FOLDER="Do you also want to DELETE this entire folder (%PACKAGE_DIR%)? [y/N]: "
if /i "%DELETE_FOLDER%"=="y" (
    echo.
    echo Deleting folder in 3 seconds...
    start "" cmd /c "timeout /t 3 >nul & rmdir /s /q \"%PACKAGE_DIR%\""
    exit
)

pause
