# Activate venv dan run server
$venvPath = ".\venv\Scripts\Activate.ps1"

# Check venv exists
if (-not (Test-Path $venvPath)) {
    Write-Host "[!] venv not found! Run: python -m venv venv" -ForegroundColor Red
    exit 1
}

# Activate venv
Write-Host "[*] Activating venv..." -ForegroundColor Green
& $venvPath

# Run server
Write-Host "[*] Starting server..." -ForegroundColor Green
python main_server.py
