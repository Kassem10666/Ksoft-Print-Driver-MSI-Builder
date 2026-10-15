import os
import sys
from pathlib import Path
from waitress import serve
from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print("=" * 65)
    print("   Enterprise Printer MSI Builder - Windows Server Production")
    print(f"   Listening on: http://{host}:{port}")
    print("   Access locally via: http://127.0.0.1:5000")
    print("   Access from LAN/network via: http://<SERVER_IP>:5000")
    print("=" * 65)
    
    serve(app, host=host, port=port, threads=8)
