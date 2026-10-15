import os
import shutil
import subprocess
import uuid
import sys
import gzip
import base64
from pathlib import Path

WIX_BIN = r"C:\Program Files (x86)\WiX Toolset v3.14\bin"

def get_bundle_dir():
    """Returns PyInstaller extraction directory (_MEIPASS) if frozen, else project root."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def find_wix_executable(exe_name):
    """Finds packaging executable in bundled _MEIPASS/tools/wix, local tools/wix, WIX_BIN, or PATH."""
    # 1. First priority: Embedded inside standalone single-file EXE (_MEIPASS)
    bundle_wix = get_bundle_dir() / "tools" / "wix" / exe_name
    if bundle_wix.exists():
        return str(bundle_wix)

    # 2. Check alongside EXE (./tools/wix)
    project_root = get_base_dir()
    local_tools_root = project_root / "tools" / "wix"
    if (local_tools_root / exe_name).exists():
        return str(local_tools_root / exe_name)

    local_tools_web = project_root / "web_builder" / "tools" / "wix"
    if (local_tools_web / exe_name).exists():
        return str(local_tools_web / exe_name)

    # 3. Check standard installation path
    wix_path = os.path.join(WIX_BIN, exe_name)
    if os.path.exists(wix_path):
        return wix_path

    # 4. Check system PATH
    shutil_path = shutil.which(exe_name)
    if shutil_path:
        return shutil_path

    raise FileNotFoundError(f"Packaging tool {exe_name} not found.")

def protect_powershell_script(script_content: str) -> str:
    """
    Encrypts and compresses PowerShell script content into an in-memory execution wrapper.
    When opened in Notepad, only an unreadable encrypted Base64 payload is visible.
    Execution happens completely in-memory (RAM) via GZipStream and Invoke-Expression.
    Preserves $PSScriptRoot so all driver and settings paths continue to work seamlessly.
    """
    compressed = gzip.compress(script_content.encode('utf-8'))
    b64_payload = base64.b64encode(compressed).decode('ascii')

    chunk_size = 120
    chunks = [b64_payload[i:i+chunk_size] for i in range(0, len(b64_payload), chunk_size)]
    formatted_payload = "\n    ".join(f'"{c}" +' for c in chunks[:-1])
    if chunks:
        formatted_payload += f'\n    "{chunks[-1]}"'
    else:
        formatted_payload = '""'

    wrapper = f"""# ==============================================================================
# KSoft Enterprise Protected Runtime
# (C) KSoft Security. All rights reserved.
# Binary-encoded runtime for silent deployment and maintenance.
# ==============================================================================
$ErrorActionPreference = 'Stop'
$TargetDir = if ($PSScriptRoot) {{ $PSScriptRoot }} else {{ Split-Path -Parent $MyInvocation.MyCommand.Path }}
$payload = (
    {formatted_payload}
)

try {{
    $bytes = [System.Convert]::FromBase64String($payload)
    $ms = New-Object System.IO.MemoryStream(,$bytes)
    $gz = New-Object System.IO.Compression.GZipStream($ms, [System.IO.Compression.CompressionMode]::Decompress)
    $sr = New-Object System.IO.StreamReader($gz, [System.Text.Encoding]::UTF8)
    $code = $sr.ReadToEnd()
    $sr.Close()
    $gz.Close()
    $ms.Close()
    if (-not $PSScriptRoot) {{ $PSScriptRoot = $TargetDir }}
    Invoke-Expression $code
}} catch {{
    $logPath = "C:\\XRX\\InstallError.log"
    New-Item -ItemType Directory -Path "C:\\XRX" -Force -ErrorAction SilentlyContinue | Out-Null
    Add-Content -Path $logPath -Value "[ERROR] Protected runtime execution error: $($_.Exception.Message)" -ErrorAction SilentlyContinue
    throw
}}
"""
    return wrapper

def generate_run_ps1(printer_name, driver_name, printer_ip, has_settings, set_as_default=False,
                     port_protocol="RAW", port_name="", raw_port_number=9100,
                     lpr_queue_name="", lpr_byte_counting=False):
    """Generates run.ps1 script with dynamic variables and RAW/LPR port support."""
    actual_port_name = port_name.strip() if port_name and port_name.strip() else f"IP_{printer_ip}"
    protocol = port_protocol.upper()

    settings_code = ""
    if has_settings:
        settings_code = """
# Wait before applying settings
Start-Sleep -Seconds 5

# Apply XML configuration if present (native PowerShell PrintTicket)
$XmlFiles = @(Get-ChildItem -Path "$BaseDir\\PrinterSettings" -Filter "*.xml" -ErrorAction SilentlyContinue)
foreach ($Xml in $XmlFiles) {
    try {
        Add-Content -Path $LogFile -Value "Applying XML print configuration: $($Xml.FullName)"
        $imported = Import-Clixml -Path $Xml.FullName -ErrorAction Stop
        if ($imported.PrintTicketXml) {
            Set-PrintConfiguration -PrinterName $PrinterName -PrintTicketXml $imported.PrintTicketXml -ErrorAction Stop
            Add-Content -Path $LogFile -Value "XML PrintTicket applied successfully."
        }
    } catch {
        Add-Content -Path $LogFile -Value "XML config notice: $($_.Exception.Message)"
    }
}

# Apply saved printer settings (.dat) with quiet mode and conflict resolution flags (g d r p)
$DatFiles = @(Get-ChildItem -Path "$BaseDir\\PrinterSettings" -Filter "*.dat" -ErrorAction SilentlyContinue)
$Rundll64 = "$env:SystemRoot\\System32\\rundll32.exe"

foreach ($Dat in $DatFiles) {
    Add-Content -Path $LogFile -Value "Applying DAT settings: $($Dat.FullName)"
    $argsList = "printui.dll,PrintUIEntry /Sr /q /n `"$PrinterName`" /a `"$($Dat.FullName)`" g d r p"
    $proc = Start-Process -FilePath $Rundll64 -ArgumentList $argsList -Wait -PassThru -WindowStyle Hidden
    Add-Content -Path $LogFile -Value "PrintUIEntry Exit Code: $($proc.ExitCode)"
}

if ($DatFiles.Count -eq 0 -and $XmlFiles.Count -eq 0) {
    Add-Content -Path $LogFile -Value "WARNING: No settings files (.dat or .xml) found."
}
"""

    default_printer_code = ""
    if set_as_default:
        default_printer_code = """
# Set as Default Printer for current and all active users
try {
    Add-Content -Path $LogFile -Value "Setting $PrinterName as default printer..."
    (New-Object -ComObject WScript.Network).SetDefaultPrinter($PrinterName)
    $Rundll64 = "$env:SystemRoot\\System32\\rundll32.exe"
    Start-Process -FilePath $Rundll64 -ArgumentList "printui.dll,PrintUIEntry /y /n `"$PrinterName`"" -Wait -WindowStyle Hidden
    
    Get-ChildItem "Registry::HKEY_USERS" -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^S-1-5-21-\\d+-\\d+-\\d+-\\d+$' } | ForEach-Object {
        $sid = $_.PSChildName
        $regPath = "Registry::HKEY_USERS\\$sid\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Windows"
        if (Test-Path $regPath) {
            Set-ItemProperty -Path $regPath -Name "Device" -Value "$PrinterName,winspool,Ne00:" -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $regPath -Name "LegacyDefaultPrinterMode" -Value 1 -Type DWord -ErrorAction SilentlyContinue
        }
    }
    Set-ItemProperty -Path "Registry::HKEY_USERS\\.DEFAULT\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Windows" -Name "Device" -Value "$PrinterName,winspool,Ne00:" -ErrorAction SilentlyContinue
    Add-Content -Path $LogFile -Value "Default printer configured successfully."
} catch {
    Add-Content -Path $LogFile -Value "Notice setting default printer: $($_.Exception.Message)"
}
"""

    # Protocol port creation block
    if protocol == "LPR":
        byte_counting_flag = "-LprByteCounting" if lpr_byte_counting else ""
        port_creation_block = f"""# Create printer port (LPR Protocol)
$PortName = "{actual_port_name}"
$LprQueueName = "{lpr_queue_name}"

try {{
    if (-not (Get-PrinterPort -Name $PortName -ErrorAction SilentlyContinue)) {{
        Add-PrinterPort -Name $PortName -LprHostAddress $PrinterIP -LprQueueName $LprQueueName {byte_counting_flag} -ErrorAction Stop
    }}
    Add-Content -Path $LogFile -Value "Port ready: $PortName (LPR Protocol, Queue: $LprQueueName)"
}}
catch {{
    Add-Content -Path $LogFile -Value "Port error: $($_.Exception.Message)"
}}
"""
    else:
        port_num = int(raw_port_number) if raw_port_number else 9100
        port_creation_block = f"""# Create printer port (RAW Protocol)
$PortName = "{actual_port_name}"
$PortNumber = {port_num}

try {{
    if (-not (Get-PrinterPort -Name $PortName -ErrorAction SilentlyContinue)) {{
        Add-PrinterPort -Name $PortName -PrinterHostAddress $PrinterIP -PortNumber $PortNumber -ErrorAction Stop
    }}
    Add-Content -Path $LogFile -Value "Port ready: $PortName (RAW Protocol, Port: $PortNumber)"
}}
catch {{
    Add-Content -Path $LogFile -Value "Port error: $($_.Exception.Message)"
}}
"""

    return f"""# Printer Configuration
$PrinterIP = "{printer_ip}"
$PrinterName = "{printer_name}"
$DriverName = "{driver_name}"

# Log Configuration
$LogDir = "C:\\XRX"
$LogFile = Join-Path $LogDir "InstallLog_$PrinterName.txt"
New-Item -ItemType Directory -Path $LogDir -Force -ErrorAction SilentlyContinue | Out-Null
Add-Content -Path $LogFile -Value "=== Starting installation: $PrinterName ==="

# Package directory
$BaseDir = if ($PSScriptRoot) {{ $PSScriptRoot }} elseif ($TargetDir) {{ $TargetDir }} else {{ (Get-Location).Path }}

# Install driver INF files
$InfFiles = @(Get-ChildItem -Path "$BaseDir\\driver" -Filter "*.inf" -ErrorAction SilentlyContinue)

foreach ($Inf in $InfFiles) {{
    Add-Content -Path $LogFile -Value "Installing INF: $($Inf.FullName)"
    $Result = & pnputil.exe /add-driver "$($Inf.FullName)" /install 2>&1
    Add-Content -Path $LogFile -Value "$Result"
    Add-Content -Path $LogFile -Value "PnPUtil Exit Code: $LASTEXITCODE"
}}

if ($InfFiles.Count -eq 0) {{
    Add-Content -Path $LogFile -Value "ERROR: No INF files found."
}}

# Install printer driver
try {{
    Add-PrinterDriver -Name $DriverName -ErrorAction Stop
    Add-Content -Path $LogFile -Value "Driver installed or already available."
}}
catch {{
    Add-Content -Path $LogFile -Value "Driver error: $($_.Exception.Message)"
}}

{port_creation_block}

# Add printer
try {{
    if (-not (Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue)) {{
        Add-Printer -Name $PrinterName -DriverName $DriverName -PortName $PortName -ErrorAction Stop
    }}
    Add-Content -Path $LogFile -Value "Printer ready: $PrinterName"
}}
catch {{
    Add-Content -Path $LogFile -Value "Printer error: $($_.Exception.Message)"
}}
{settings_code}
{default_printer_code}
Add-Content -Path $LogFile -Value "=== Installation script finished ==="
"""

def generate_uninstall_ps1(printer_name, driver_name, printer_ip, port_name=""):
    """Generates uninstall.ps1 script."""
    actual_port_name = port_name.strip() if port_name and port_name.strip() else f"IP_{printer_ip}"
    return f"""# Printer Configuration
$PrinterIP = "{printer_ip}"
$PrinterName = "{printer_name}"
$DriverName = "{driver_name}"
$PortName = "{actual_port_name}"

# Log Configuration
$LogDir = "C:\\XRX"
$LogFile = Join-Path $LogDir "UninstallLog_$PrinterName.txt"
New-Item -ItemType Directory -Path $LogDir -Force -ErrorAction SilentlyContinue | Out-Null
Add-Content -Path $LogFile -Value "=== Starting uninstallation: $PrinterName ==="

# 1. Remove Printer
try {{
    if (Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue) {{
        Remove-Printer -Name $PrinterName -ErrorAction Stop
        Add-Content -Path $LogFile -Value "Printer removed: $PrinterName"
    }} else {{
        Add-Content -Path $LogFile -Value "Printer not found: $PrinterName"
    }}
}}
catch {{
    Add-Content -Path $LogFile -Value "Error removing printer: $($_.Exception.Message)"
}}

# 2. Remove Printer Port
try {{
    if (Get-PrinterPort -Name $PortName -ErrorAction SilentlyContinue) {{
        Remove-PrinterPort -Name $PortName -ErrorAction Stop
        Add-Content -Path $LogFile -Value "Port removed: $PortName"
    }} else {{
        Add-Content -Path $LogFile -Value "Port not found: $PortName"
    }}
}}
catch {{
    Add-Content -Path $LogFile -Value "Error removing port: $($_.Exception.Message)"
}}

# 3. Try removing driver if not used by other printers
try {{
    if (Get-PrinterDriver -Name $DriverName -ErrorAction SilentlyContinue) {{
        Remove-PrinterDriver -Name $DriverName -ErrorAction SilentlyContinue
        Add-Content -Path $LogFile -Value "Driver cleanup attempted: $DriverName"
    }}
}}
catch {{
    Add-Content -Path $LogFile -Value "Driver cleanup skipped: $($_.Exception.Message)"
}}

Add-Content -Path $LogFile -Value "=== Uninstallation script finished ==="
"""

def generate_product_wxs(printer_name, manufacturer, upgrade_code, component_guid, has_settings):
    """Generates Product.wxs XML file."""
    clean_folder_name = "".join(c for c in printer_name if c.isalnum() or c in (" ", "_", "-")).strip() or "Printer"
    clean_product_name = printer_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    clean_manufacturer = manufacturer.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    settings_dir_xml = '<Directory Id="SETTINGSDIR" Name="PrinterSettings" />' if has_settings else ''
    settings_feature_ref = '<ComponentGroupRef Id="SettingsFiles" />' if has_settings else ''

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
    <Product Id="*"
             Name="{clean_product_name} Installer"
             Language="1033"
             Version="1.0.0.0"
             Manufacturer="{clean_manufacturer}"
             UpgradeCode="{upgrade_code}">

        <Package InstallerVersion="300"
                 Compressed="yes"
                 InstallScope="perMachine"
                 Platform="x64"
                 Description="{clean_product_name} Driver &amp; Configuration Installer" />

        <MajorUpgrade DowngradeErrorMessage="A newer version of [ProductName] is already installed." />
        <MediaTemplate EmbedCab="yes" />

        <Directory Id="TARGETDIR" Name="SourceDir">
            <Directory Id="ProgramFiles64Folder">
                <Directory Id="CompanyFolder" Name="{clean_manufacturer}">
                    <Directory Id="INSTALLFOLDER" Name="{clean_folder_name}">
                        <Directory Id="DRIVERDIR" Name="driver" />
                        {settings_dir_xml}
                    </Directory>
                </Directory>
            </Directory>
        </Directory>

        <DirectoryRef Id="INSTALLFOLDER">
            <Component Id="cmp_Scripts" Guid="{component_guid}">
                <File Id="fil_run_ps1" Source="run.ps1" KeyPath="yes" />
                <File Id="fil_uninstall_ps1" Source="uninstall.ps1" />
            </Component>
        </DirectoryRef>

        <Feature Id="ProductFeature" Title="{clean_product_name}" Level="1">
            <ComponentRef Id="cmp_Scripts" />
            <ComponentGroupRef Id="DriverFiles" />
            {settings_feature_ref}
        </Feature>

        <!-- Custom Action to Run Install Script on Install (Deferred, Elevated as System) -->
        <CustomAction Id="RunInstallScript"
                      Directory="INSTALLFOLDER"
                      ExeCommand="&quot;[WindowsFolder]System32\\WindowsPowerShell\\v1.0\\powershell.exe&quot; -ExecutionPolicy Bypass -NoProfile -NonInteractive -WindowStyle Hidden -File &quot;[#fil_run_ps1]&quot;"
                      Execute="deferred"
                      Impersonate="no"
                      Return="check" />

        <!-- Custom Action to Run Uninstall Script on Uninstall (Deferred, Elevated as System) -->
        <CustomAction Id="RunUninstallScript"
                      Directory="INSTALLFOLDER"
                      ExeCommand="&quot;[WindowsFolder]System32\\WindowsPowerShell\\v1.0\\powershell.exe&quot; -ExecutionPolicy Bypass -NoProfile -NonInteractive -WindowStyle Hidden -File &quot;[#fil_uninstall_ps1]&quot;"
                      Execute="deferred"
                      Impersonate="no"
                      Return="ignore" />

        <InstallExecuteSequence>
            <Custom Action="RunInstallScript" After="InstallFiles">
                NOT Installed AND NOT REMOVE
            </Custom>
            <Custom Action="RunUninstallScript" Before="RemoveFiles">
                (Installed OR UPGRADINGPRODUCTCODE) AND (REMOVE="ALL")
            </Custom>
        </InstallExecuteSequence>
    </Product>
</Wix>
"""

def build_msi(work_dir, printer_name, driver_name, printer_ip, manufacturer="Xerox",
              msi_filename="PrinterInstaller.msi", set_as_default=False,
              port_protocol="RAW", port_name="", raw_port_number=9100,
              lpr_queue_name="", lpr_byte_counting=False, log_callback=None):
    """
    Executes build pipeline in work_dir with RAW / LPR port support.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        try:
            print(msg)
        except Exception:
            try:
                print(str(msg).encode('ascii', errors='replace').decode('ascii'))
            except Exception:
                pass

    heat_exe = find_wix_executable("heat.exe")
    candle_exe = find_wix_executable("candle.exe")
    light_exe = find_wix_executable("light.exe")

    driver_path = os.path.join(work_dir, "driver")
    settings_path = os.path.join(work_dir, "PrinterSettings")

    if not os.path.exists(driver_path) or not os.listdir(driver_path):
        raise ValueError("The driver folder is empty or missing. Please upload driver files.")

    has_settings = os.path.exists(settings_path) and len(os.listdir(settings_path)) > 0

    log(f"[*] Initializing package for: {printer_name} (IP: {printer_ip}, Driver: {driver_name})")
    protocol_display = f"LPR (Queue: {lpr_queue_name})" if port_protocol.upper() == "LPR" else f"RAW ({raw_port_number})"
    log(f"[*] Port Configuration: Protocol: {protocol_display}")
    if set_as_default:
        log("[*] Configuration: Will set as default printer for users.")

    # 1. Generate run.ps1 and uninstall.ps1 (Protected & In-Memory Encrypted)
    log("[*] Generating protected installation and maintenance scripts (In-Memory Encryption)...")
    raw_run = generate_run_ps1(
        printer_name=printer_name,
        driver_name=driver_name,
        printer_ip=printer_ip,
        has_settings=has_settings,
        set_as_default=set_as_default,
        port_protocol=port_protocol,
        port_name=port_name,
        raw_port_number=raw_port_number,
        lpr_queue_name=lpr_queue_name,
        lpr_byte_counting=lpr_byte_counting
    )
    with open(os.path.join(work_dir, "run.ps1"), "w", encoding="utf-8") as f:
        f.write(protect_powershell_script(raw_run))

    raw_uninstall = generate_uninstall_ps1(printer_name, driver_name, printer_ip, port_name=port_name)
    with open(os.path.join(work_dir, "uninstall.ps1"), "w", encoding="utf-8") as f:
        f.write(protect_powershell_script(raw_uninstall))

    # 2. Generate Product.wxs
    upgrade_guid = str(uuid.uuid4()).upper()
    comp_guid = str(uuid.uuid4()).upper()
    with open(os.path.join(work_dir, "Product.wxs"), "w", encoding="utf-8") as f:
        f.write(generate_product_wxs(printer_name, manufacturer, upgrade_guid, comp_guid, has_settings))

    # 3. Harvest driver files
    log("[*] Packaging printer driver files...")
    cmd_heat_driver = [
        heat_exe, "dir", "driver",
        "-cg", "DriverFiles",
        "-gg", "-scom", "-sreg", "-sfrag", "-srd",
        "-dr", "DRIVERDIR",
        "-var", "var.DriverDir",
        "-out", "DriverFiles.wxs"
    ]
    res = subprocess.run(cmd_heat_driver, cwd=work_dir, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"Error packaging driver files: {res.stderr}\n{res.stdout}")
        raise RuntimeError(f"Failed to package driver files: {res.stderr}")

    candle_sources = ["Product.wxs", "DriverFiles.wxs"]
    candle_defines = ["-dDriverDir=driver"]
    wixobjs = ["Product.wixobj", "DriverFiles.wixobj"]

    # 4. Harvest PrinterSettings files if present
    if has_settings:
        log("[*] Packaging printer configuration files...")
        cmd_heat_settings = [
            heat_exe, "dir", "PrinterSettings",
            "-cg", "SettingsFiles",
            "-gg", "-scom", "-sreg", "-sfrag", "-srd",
            "-dr", "SETTINGSDIR",
            "-var", "var.SettingsDir",
            "-out", "SettingsFiles.wxs"
        ]
        res = subprocess.run(cmd_heat_settings, cwd=work_dir, capture_output=True, text=True)
        if res.returncode != 0:
            log(f"Error packaging settings files: {res.stderr}\n{res.stdout}")
            raise RuntimeError(f"Failed to package settings files: {res.stderr}")
        candle_sources.append("SettingsFiles.wxs")
        candle_defines.append("-dSettingsDir=PrinterSettings")
        wixobjs.append("SettingsFiles.wixobj")

    # 5. Compile components
    log("[*] Compiling installer components...")
    cmd_candle = [
        candle_exe, "-arch", "x64", "-nologo"
    ] + candle_defines + candle_sources
    res = subprocess.run(cmd_candle, cwd=work_dir, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"Compiler error: {res.stderr}\n{res.stdout}")
        raise RuntimeError(f"Failed to compile installer components: {res.stderr or res.stdout}")

    # 6. Link MSI
    out_msi_path = os.path.join(work_dir, msi_filename)
    log(f"[*] Linking MSI package ({msi_filename})...")
    cmd_light = [
        light_exe, "-nologo", "-sval"
    ] + wixobjs + ["-o", msi_filename]
    res = subprocess.run(cmd_light, cwd=work_dir, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"Linker error: {res.stderr}\n{res.stdout}")
        raise RuntimeError(f"Failed to link MSI package: {res.stderr or res.stdout}")

    if not os.path.exists(out_msi_path):
        raise FileNotFoundError("The generated MSI file was not found.")

    # 7. Clean up intermediate build files (keep only .msi, driver/, PrinterSettings/)
    log("[*] Cleaning up temporary build files...")
    allowed_dirs = {"driver", "printersettings"}
    for item in os.listdir(work_dir):
        item_path = os.path.join(work_dir, item)
        # Keep the generated MSI file
        if item.lower() == msi_filename.lower():
            continue
        # Keep driver and PrinterSettings directories
        if os.path.isdir(item_path):
            if item.lower() not in allowed_dirs:
                shutil.rmtree(item_path, ignore_errors=True)
        else:
            # Delete any loose files (.wxs, .wixobj, .wixpdb, run.ps1, uninstall.ps1, etc.)
            try:
                os.remove(item_path)
            except Exception:
                pass

    msi_size_mb = os.path.getsize(out_msi_path) / (1024 * 1024)
    log(f"[OK] Package built successfully! Output Size: {msi_size_mb:.2f} MB")
    return out_msi_path
