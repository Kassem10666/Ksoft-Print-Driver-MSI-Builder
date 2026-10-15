import os
import re
import shutil
import tempfile
import uuid
import zipfile
import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from builder import build_msi, find_wix_executable

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def get_bundle_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

def get_template_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "templates"
    return Path(__file__).resolve().parent / "templates"

def get_asset_dir(folder_name):
    """Finds asset folder: first checks alongside EXE, falls back to bundled in _MEIPASS."""
    external = get_base_dir() / folder_name
    if external.exists() and len(os.listdir(external)) > 0:
        return external
    bundle = get_bundle_dir() / folder_name
    if bundle.exists() and len(os.listdir(bundle)) > 0:
        return bundle
    return external

BASE_PROJECT_DIR = get_base_dir()
TEMPLATE_DIR = get_template_dir()
try:
    BUILDS_DIR = BASE_PROJECT_DIR / "builds"
    BUILDS_DIR.mkdir(exist_ok=True)
except Exception:
    BUILDS_DIR = Path(tempfile.gettempdir()) / "KSoft_Printer_Builds"
    BUILDS_DIR.mkdir(exist_ok=True)

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

# Store build metadata in memory
BUILDS = {}

def extract_models_from_inf_text(text):
    """
    Accurately extracts printer driver model names from Windows INF files.
    Follows [Manufacturer] section, resolves [Strings], filters directives,
    and preserves definition order without injecting keywords like CopyFiles.
    """
    lines = text.splitlines()
    current_section = ''
    sections = {}

    for raw_line in lines:
        line = raw_line.strip()
        if ';' in line:
            line = line.split(';')[0].strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            current_section = line[1:-1].strip().lower()
            if current_section not in sections:
                sections[current_section] = []
        else:
            if current_section:
                sections[current_section].append(line)

    # 1. Parse [strings] section for variable replacement (%var%)
    strings_map = {}
    for s_name, s_lines in sections.items():
        if s_name == 'strings' or s_name.startswith('strings.'):
            for l in s_lines:
                if '=' in l:
                    k, v = l.split('=', 1)
                    k = k.strip().lower()
                    v = v.strip().strip('"').strip("'")
                    strings_map[k] = v

    def resolve_string(val):
        val = val.strip().strip('"').strip("'")
        if val.startswith('%') and val.endswith('%') and len(val) > 2:
            key = val[1:-1].strip().lower()
            return strings_map.get(key, val)
        return val

    # 2. Extract model section prefixes from [manufacturer]
    manufacturer_lines = sections.get('manufacturer', [])
    model_section_roots = set()
    for l in manufacturer_lines:
        if '=' in l:
            _, right = l.split('=', 1)
            parts = [p.strip() for p in right.split(',') if p.strip()]
            if parts:
                model_section_roots.add(parts[0].lower())

    # Keywords and directives that must NEVER be treated as driver model names
    ignored_keywords = {
        'copyfiles', 'needs', 'include', 'driverver', 'catalogfile', 'provider',
        'class', 'classguid', 'pnplockdown', 'printprocessor', 'datafile', 'datasection',
        'coredriverdependencies', 'coredriversections', 'addservice', 'defaultdestdir',
        'destinationdirs', 'sourcedisksnames', 'sourcedisksfiles', 'oem urls', 'signature',
        'version', 'driverisolation', 'packageaware', 'layoutfile', 'addreg', 'delreg'
    }

    discovered_models = []
    seen = set()

    def add_model(name):
        clean_name = resolve_string(name)
        if clean_name and clean_name.lower() not in ignored_keywords and clean_name not in seen:
            seen.add(clean_name)
            discovered_models.append(clean_name)

    # 3. Look in model sections identified by Manufacturer roots or containing 'models'
    for s_name, s_lines in sections.items():
        is_model_section = False
        for root in model_section_roots:
            if s_name == root or s_name.startswith(root + '.'):
                is_model_section = True
                break
        if not is_model_section and ('models' in s_name or 'printer' in s_name):
            is_model_section = True

        if is_model_section:
            for l in s_lines:
                if '=' in l:
                    left, right = l.split('=', 1)
                    left = left.strip()
                    if left.lower() not in ignored_keywords:
                        add_model(left)

    # 4. Fallback if no models discovered via Manufacturer sections
    if not discovered_models:
        for s_name, s_lines in sections.items():
            if s_name in ('strings', 'version', 'manufacturer', 'sourcedisksnames', 'sourcedisksfiles', 'destinationdirs'):
                continue
            for l in s_lines:
                if '=' in l:
                    left, right = l.split('=', 1)
                    if any(hw in right.upper() for hw in ['USBPRINT', 'WSDPRINT', 'LPTENUM', '1284_CID', 'DOT4PRT', 'PRINT', 'HWID']):
                        add_model(left.strip())

    return discovered_models

def normalize_extracted_dir(target_dir):
    """If target_dir contains only a single subfolder and no loose files, flatten it."""
    entries = os.listdir(target_dir)
    if len(entries) == 1:
        sub = os.path.join(target_dir, entries[0])
        if os.path.isdir(sub):
            for item in os.listdir(sub):
                shutil.move(os.path.join(sub, item), os.path.join(target_dir, item))
            os.rmdir(sub)

@app.route('/')
def index():
    existing_driver_dir = get_asset_dir("driver")
    existing_settings_dir = get_asset_dir("PrinterSettings")
    
    driver_files_count = len(os.listdir(existing_driver_dir)) if existing_driver_dir.exists() else 0
    settings_files_count = len(os.listdir(existing_settings_dir)) if existing_settings_dir.exists() else 0
    
    default_models = []
    seen = set()
    if existing_driver_dir.exists():
        for inf_path in existing_driver_dir.glob("*.inf"):
            try:
                with open(inf_path, "r", encoding="utf-8", errors="ignore") as f:
                    for m in extract_models_from_inf_text(f.read()):
                        if m not in seen:
                            seen.add(m)
                            default_models.append(m)
            except Exception:
                pass

    return render_template('index.html',
                           driver_files_count=driver_files_count,
                           settings_files_count=settings_files_count,
                           default_models=default_models)

@app.route('/api/check-wix', methods=['GET'])
@app.route('/api/check-engine', methods=['GET'])
def check_engine():
    try:
        find_wix_executable("heat.exe")
        find_wix_executable("candle.exe")
        find_wix_executable("light.exe")
        return jsonify({"ready": True, "message": "Package Engine is online and ready."})
    except Exception as e:
        return jsonify({"ready": False, "message": str(e)}), 500

@app.route('/api/parse-inf', methods=['POST'])
def parse_inf():
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    try:
        filename = (file.filename or '').lower()
        models = []
        if filename.endswith('.zip'):
            with zipfile.ZipFile(file, 'r') as z:
                for name in z.namelist():
                    if name.lower().endswith('.inf') and not name.startswith('__MACOSX'):
                        content = z.read(name).decode('utf-8', errors='ignore')
                        models.extend(extract_models_from_inf_text(content))
        else:
            content = file.read().decode('utf-8', errors='ignore')
            models = extract_models_from_inf_text(content)

        unique_models = []
        seen = set()
        for m in models:
            if m not in seen:
                seen.add(m)
                unique_models.append(m)

        return jsonify({"models": unique_models})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/build', methods=['POST'])
def handle_build():
    build_id = str(uuid.uuid4())[:8]
    work_dir = BUILDS_DIR / f"build_{build_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    logs = []
    def logger(msg):
        logs.append(msg)

    try:
        printer_name = request.form.get('printer_name', '').strip()
        driver_name = request.form.get('driver_name', '').strip()
        printer_ip = request.form.get('printer_ip', '').strip()
        manufacturer = request.form.get('manufacturer', 'Xerox').strip() or "Xerox"
        custom_msi_name = request.form.get('msi_name', '').strip()
        set_default = request.form.get('set_default') in ('true', '1', 'on')
        port_protocol = request.form.get('port_protocol', 'RAW').strip().upper()
        if port_protocol not in ('RAW', 'LPR'):
            port_protocol = 'RAW'
        port_name = request.form.get('port_name', '').strip()
        raw_port_number = request.form.get('raw_port_number', '9100').strip() or '9100'
        lpr_queue_name = request.form.get('lpr_queue_name', '').strip()
        lpr_byte_counting = request.form.get('lpr_byte_counting') in ('true', '1', 'on')

        if not printer_name:
            return jsonify({"success": False, "error": "Printer / Queue Name is required."}), 400
        if not driver_name:
            return jsonify({"success": False, "error": "Driver Model Name is required."}), 400
        if not printer_ip:
            return jsonify({"success": False, "error": "Printer IP address is required."}), 400
        if port_protocol == 'LPR' and not lpr_queue_name:
            return jsonify({"success": False, "error": "Queue Name is required when using LPR protocol."}), 400

        # Output MSI name
        safe_name = "".join(c for c in printer_name if c.isalnum() or c in ("-", "_")).strip() or "Printer"
        if not custom_msi_name:
            msi_filename = f"{safe_name}_Installer.msi"
        else:
            if not custom_msi_name.lower().endswith(".msi"):
                msi_filename = f"{custom_msi_name}.msi"
            else:
                msi_filename = custom_msi_name

        # Prepare driver directory
        target_driver_dir = work_dir / "driver"
        target_driver_dir.mkdir(exist_ok=True)

        driver_source = request.form.get('driver_source', 'upload')
        if driver_source == 'existing':
            existing_driver_dir = get_asset_dir("driver")
            if not existing_driver_dir.exists() or not os.listdir(existing_driver_dir):
                return jsonify({"success": False, "error": "Driver directory is empty or not found."}), 400
            for item in existing_driver_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, target_driver_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(item, target_driver_dir / item.name)
            logger(f"[*] Loaded {len(os.listdir(target_driver_dir))} files from project driver folder.")
        else:
            # Check zip upload or file list
            driver_zip = request.files.get('driver_zip')
            driver_files = request.files.getlist('driver_files')

            if driver_zip and driver_zip.filename:
                zip_path = work_dir / "driver_temp.zip"
                driver_zip.save(zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_driver_dir)
                os.remove(zip_path)
                normalize_extracted_dir(str(target_driver_dir))
                logger(f"[*] Extracted driver files from ZIP package.")
            elif driver_files and len(driver_files) > 0 and driver_files[0].filename:
                for f in driver_files:
                    if f.filename:
                        filename = os.path.basename(f.filename)
                        f.save(target_driver_dir / filename)
                logger(f"[*] Uploaded {len(os.listdir(target_driver_dir))} driver files.")
            else:
                return jsonify({"success": False, "error": "Please upload driver files or select the project driver folder option."}), 400

        # Verify that driver has at least 1 INF file
        inf_files = list(target_driver_dir.glob("*.inf"))
        if not inf_files:
            return jsonify({"success": False, "error": "No .INF file was found in the uploaded driver directory!"}), 400

        # Prepare PrinterSettings directory
        target_settings_dir = work_dir / "PrinterSettings"
        target_settings_dir.mkdir(exist_ok=True)

        settings_source = request.form.get('settings_source', 'none')
        if settings_source == 'existing':
            existing_settings_dir = get_asset_dir("PrinterSettings")
            if existing_settings_dir.exists():
                for item in existing_settings_dir.iterdir():
                    if item.is_file():
                        shutil.copy2(item, target_settings_dir / item.name)
                    elif item.is_dir():
                        shutil.copytree(item, target_settings_dir / item.name)
                logger(f"[*] Loaded configuration files from project settings folder.")
        elif settings_source == 'upload':
            settings_zip = request.files.get('settings_zip')
            settings_files = request.files.getlist('settings_files')

            if settings_zip and settings_zip.filename:
                zip_path = work_dir / "settings_temp.zip"
                settings_zip.save(zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_settings_dir)
                os.remove(zip_path)
                normalize_extracted_dir(str(target_settings_dir))
                logger(f"[*] Extracted configuration files from ZIP package.")
            elif settings_files and len(settings_files) > 0 and settings_files[0].filename:
                for f in settings_files:
                    if f.filename:
                        filename = os.path.basename(f.filename)
                        f.save(target_settings_dir / filename)
                logger(f"[*] Uploaded {len(os.listdir(target_settings_dir))} configuration files.")

        # Build MSI
        msi_path = build_msi(
            work_dir=str(work_dir),
            printer_name=printer_name,
            driver_name=driver_name,
            printer_ip=printer_ip,
            manufacturer=manufacturer,
            msi_filename=msi_filename,
            set_as_default=set_default,
            port_protocol=port_protocol,
            port_name=port_name,
            raw_port_number=raw_port_number,
            lpr_queue_name=lpr_queue_name,
            lpr_byte_counting=lpr_byte_counting,
            log_callback=logger
        )

        size_bytes = os.path.getsize(msi_path)
        size_mb = f"{size_bytes / (1024 * 1024):.2f}"

        BUILDS[build_id] = {
            "msi_path": msi_path,
            "filename": msi_filename,
            "printer_name": printer_name,
            "size_mb": size_mb,
            "logs": logs
        }

        return jsonify({
            "success": True,
            "build_id": build_id,
            "filename": msi_filename,
            "size_mb": size_mb,
            "logs": logs,
            "download_url": f"/download/{build_id}"
        })

    except Exception as e:
        logger(f"[!] Build error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "logs": logs
        }), 500

@app.route('/download/<build_id>')
def download_msi(build_id):
    build_info = BUILDS.get(build_id)
    if not build_info or not os.path.exists(build_info["msi_path"]):
        return "File not found or expired.", 404
    return send_file(
        build_info["msi_path"],
        as_attachment=True,
        download_name=build_info["filename"]
    )

if __name__ == '__main__':
    print("="*60)
    print("  Printer MSI Package Generator")
    print("  Server running at: http://127.0.0.1:5000")
    print("="*60)
    app.run(host='127.0.0.1', port=5000, debug=False)
