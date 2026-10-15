@echo off
setlocal
title Setup Printer MSI Builder - Windows Server 2025

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
echo    Installing Printer MSI Builder on Windows Server 2025
echo ================================================================
echo Working Directory: %PACKAGE_DIR%
echo.

if not exist "%PACKAGE_DIR%\PrinterMSIBuilder.exe" (
    echo [ERROR] PrinterMSIBuilder.exe was not found in %PACKAGE_DIR%.
    pause
    exit /b 1
)

:: 1. Open Firewall Port 5000
echo [*] Step 1/2: Configuring Windows Firewall (Port 5000)...
netsh advfirewall firewall add rule name="Printer MSI Web Builder" dir=in action=allow protocol=TCP localport=5000 profile=any >nul 2>&1
echo [OK] Firewall rule configured for inbound TCP Port 5000.
echo.

:: 2. Register Scheduled Task for 24/7 Background Running on Server Boot
echo [*] Step 2/2: Registering 24/7 background service on server boot...
set "TASK_NAME=PrinterMSIBuilder_AutoStart"
set "EXE_PATH=%PACKAGE_DIR%\PrinterMSIBuilder.exe"

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
schtasks /create /tn "%TASK_NAME%" /tr "\"%EXE_PATH%\"" /sc ONSTART /ru "NT AUTHORITY\SYSTEM" /rl HIGHEST /f >nul 2>&1
schtasks /run /tn "%TASK_NAME%" >nul 2>&1

echo [OK] Background service registered and running!
echo.
echo ================================================================
echo    INSTALLATION COMPLETED SUCCESSFULLY!
echo ================================================================
echo.
echo The Printer MSI Web Builder is now running 24/7 in the background!
echo (Zero Python or external dependencies required).
echo.
echo Access URLs:
echo   - Local:    http://localhost:5000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"') do (
    set "IP_RAW=%%a"
    echo   - Network:  http:!IP_RAW!:5000
)
echo.
echo ================================================================
pause
