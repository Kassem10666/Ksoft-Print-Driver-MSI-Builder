@echo off
setlocal

echo ===================================================
echo   Building Xerox Flow Printer MSI Package with WiX
echo ===================================================

set WIX_BIN=C:\Program Files (x86)\WiX Toolset v3.14\bin
if exist "%WIX_BIN%\candle.exe" (
    set "PATH=%WIX_BIN%;%PATH%"
)

echo [1/4] Harvesting driver files...
heat dir "driver" -cg DriverFiles -gg -scom -sreg -sfrag -srd -dr DRIVERDIR -var var.DriverDir -out DriverFiles.wxs
if %ERRORLEVEL% neq 0 (
    echo Error during heat for driver folder.
    goto :error
)

echo [2/4] Harvesting PrinterSettings files...
heat dir "PrinterSettings" -cg SettingsFiles -gg -scom -sreg -sfrag -srd -dr SETTINGSDIR -var var.SettingsDir -out SettingsFiles.wxs
if %ERRORLEVEL% neq 0 (
    echo Error during heat for PrinterSettings folder.
    goto :error
)

echo [3/4] Compiling WiX source files (candle)...
candle -arch x64 -nologo -dDriverDir="driver" -dSettingsDir="PrinterSettings" Product.wxs DriverFiles.wxs SettingsFiles.wxs
if %ERRORLEVEL% neq 0 (
    echo Error during candle compilation.
    goto :error
)

echo [4/4] Linking MSI package (light)...
light -nologo -sval Product.wixobj DriverFiles.wixobj SettingsFiles.wixobj -o XeroxFlowPrinterInstaller.msi
if %ERRORLEVEL% neq 0 (
    echo Error during light linking.
    goto :error
)

echo Cleaning intermediate files...
del /q *.wixobj *.wixpdb 2>nul

echo ===================================================
echo   Build Successful! Output: XeroxFlowPrinterInstaller.msi
echo ===================================================
goto :end

:error
echo ===================================================
echo   Build Failed! Check the error messages above.
echo ===================================================
exit /b 1

:end
endlocal
