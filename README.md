# KSoft Print Driver MSI Package Generator 🖨️📦

An enterprise-grade desktop tool and automated build engine designed to convert Xerox (and other vendor) printer drivers, network ports, and saved print configurations into fully silent, standalone **MSI installation packages**


<img width="617" height="626" alt="image" src="https://github.com/user-attachments/assets/dd208163-4eb3-4a1d-89f6-dd447e60d373" />

<img width="647" height="447" alt="image" src="https://github.com/user-attachments/assets/73d3d5f4-b89c-4697-b4a2-e1bc3b1d4e8a" />

<img width="641" height="442" alt="image" src="https://github.com/user-attachments/assets/4b990161-8617-4de5-b3d8-84d3745ed897" />




---

## 🌟 Key Features

* **🎨 Sleek IT Admin Wizard UI:**
  * Dark Mode theme (`#151515` background) with  Red (`#D92231`) accents.
  * 4-step wizard: `1. Config`, `2. Drivers`, `3. Settings`, `4. Build`.
  * Real-time package review summary and live build console.

* **⚙️ Network Port Monitoring:**
  * **RAW Protocol:** Standard direct printing on port 9100.
  * **LPR Protocol:** LPR queue naming with optional byte-counting mode.

* **📂 Smart Driver & Model Extraction:**
  * Auto-detects models from uploaded INF files (or ZIP archives) directly into a selectable dropdown.
  * Filters out internal INF directives like `CopyFiles` to show only valid printer models.

* **🛡️ Protected PowerShell Runtime:**
  * Both installation (`run.ps1`) and uninstallation (`uninstall.ps1`) scripts are cryptographically packed and decompressed in RAM (In-Memory Execution).
  * No plaintext IPs, ports, or registry commands are exposed when opened in text editors.
  * Clean uninstallation via Windows Programs & Features is 100% preserved.

* **🧹 Automated Post-Build Cleanup:**
  * After building the MSI, all intermediate compilation files (`.wxs`, `.wixobj`, `.wixpdb`) are automatically purged, leaving only:
    * 📦 Final `.msi` package
    * 📁 `driver/` folder
    * 📁 `PrinterSettings/` folder

* **🚀 Standalone All-In-One Executable:**
  * Packaged into a single zero-dependency executable (`PrinterMSIBuilder.exe`).
  * Embedded WiX binaries and server engine — runs without requiring Python or external tool installations.

---

## 🛠️ Project Structure

```text
├── driver/                 # Default driver files (.inf, .cat, .dll, etc.)
├── PrinterSettings/        # Saved printer profiles (.dat, .xml)
├── Server2025_Package/     # Automated deployment bundle for Windows Server 2025
│   ├── Install-Server2025.bat
│   ├── Start-Server-Manual.bat
│   ├── Uninstall-CompleteClean.bat
│   └── PrinterMSIBuilder.exe
├── tools/                  # Embedded WiX Toolset binaries
│   └── wix/
├── web_builder/            # Generator engine & Web UI
│   ├── app.py              # Flask REST API and file handling
│   ├── builder.py          # WiX build pipeline and script generator
│   ├── server.py           # Waitress production WSGI server
│   └── templates/
│       └── index.html      # Dark mode wizard interface
├── build.bat               # WiX build batch script
├── Product.wxs             # Base WiX product definition
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start

### Option A: Standalone Executable (Recommended)
1. Double-click `PrinterMSIBuilder.exe`.
2. Open your browser and navigate to:
   ```text
   http://127.0.0.1:5000
   ```
3. Follow the 4-step wizard to configure your printer and click **Build MSI Package Now**.

### Option B: Running from Source
```powershell
# 1. Clone repository
git clone https://github.com/Kassem10666/Printer-Tools-.git
cd "KSoft Print Driver MSI Package Generator"

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start the server
python web_builder/server.py
```

---

## 💻 Silent Deployment (SCCM / Intune / GPO)

To silently install a generated MSI package across your network:

```cmd
msiexec.exe /i "Xerox_MFP_Installer.msi" /qn /norestart
```

To silently uninstall and remove the printer, driver, and port:

```cmd
msiexec.exe /x "Xerox_MFP_Installer.msi" /qn /norestart
```

---

## 📄 License
Internal Enterprise Tool - (C) KSoft . All rights reserved.
