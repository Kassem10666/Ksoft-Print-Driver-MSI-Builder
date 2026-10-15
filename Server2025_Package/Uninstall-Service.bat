@echo off
setlocal
title Uninstall Printer MSI Builder Service

echo ================================================================
echo    Removing Printer MSI Builder Service
echo ================================================================
echo.

:: Check Admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Requesting Administrator Privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~dpnx0\"\"' -Verb RunAs"
    exit /b
)

:: Terminate running server process
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: Remove scheduled task
schtasks /delete /tn "PrinterMSIBuilder_AutoStart" /f >nul 2>&1
echo [✓] Scheduled background task removed.

:: Remove firewall rule
netsh advfirewall firewall delete rule name="Printer MSI Web Builder" >nul 2>&1
echo [✓] Firewall rule removed.

echo.
echo ================================================================
echo   Service successfully removed.
echo ================================================================
pause
