# Start the app in production mode (Waitress). Logs to logs\app.log
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "app.log"

if (-not (Test-Path $Python)) {
    Write-Error "Virtual env not found. Run: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Set-Location $ProjectRoot
Write-Host "Starting User Disabling Platform (production)..."
Write-Host "Log file: $LogFile"

& $Python run_production.py 2>&1 | Tee-Object -FilePath $LogFile -Append
