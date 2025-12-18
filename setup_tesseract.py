#!/usr/bin/env python3
"""
Setup script for Tesseract OCR on Windows
Downloads and installs Tesseract if not already present
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_tesseract_installed():
    """Check if Tesseract is already installed"""
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Tesseract is already installed")
            print(f"  Version: {result.stdout.split(chr(10))[0]}")
            return True
    except FileNotFoundError:
        pass
    
    # Check common installation paths on Windows
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\ProgramData\chocolatey\lib\tesseract\tools\tesseract.exe",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            print(f"✓ Found Tesseract at: {path}")
            return True
    
    return False

def setup_pytesseract_config():
    """Configure pytesseract with Tesseract path"""
    import pytesseract
    
    # Try to find Tesseract installation
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
        r"C:\ProgramData\chocolatey\lib\tesseract\tools",
    ]
    
    tesseract_path = None
    for path in possible_paths:
        exe_path = os.path.join(path, "tesseract.exe")
        if os.path.exists(exe_path):
            tesseract_path = exe_path
            break
    
    if tesseract_path:
        pytesseract.pytesseract.pytesseract_path = tesseract_path
        print(f"✓ Configured pytesseract path: {tesseract_path}")
        return True
    else:
        print("⚠ Warning: Could not find Tesseract installation")
        return False

def install_tesseract_windows():
    """Install Tesseract on Windows using pre-built binary"""
    print("\n[*] Installing Tesseract OCR...")
    print("    Tesseract requires manual installation on Windows.")
    print("    Please download from: https://github.com/UB-Mannheim/tesseract/wiki")
    print("    Select the latest release: tesseract-ocr-w64-setup-v5.x.x.exe")
    print("\n    Installation steps:")
    print("    1. Download the installer")
    print("    2. Run the installer (accepts default paths)")
    print("    3. Select 'Indonesian' + 'English' language packs during install")
    print("    4. Install location: C:\\Program Files\\Tesseract-OCR")
    print("\n    After installation, run this script again to verify.")
    
    # Try to open download page
    try:
        import webbrowser
        webbrowser.open("https://github.com/UB-Mannheim/tesseract/wiki")
        print("\n[✓] Opening download page in browser...")
    except:
        pass

def main():
    print("=" * 60)
    print("Tesseract OCR Setup for Windows")
    print("=" * 60)
    
    # Check if already installed
    if check_tesseract_installed():
        print("\n[✓] Tesseract setup complete!")
        setup_pytesseract_config()
        return 0
    
    # Try to install
    print("\n[!] Tesseract not found on system")
    install_tesseract_windows()
    
    return 1

if __name__ == "__main__":
    sys.exit(main())
