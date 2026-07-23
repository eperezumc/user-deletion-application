# One-time setup for a local copy of User Disabling Platform.
# Usage: right-click → Run with PowerShell, or:  .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "=== User Disabling Platform — local setup ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host ""

# --- Python ---
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python not found on PATH. Install Python 3.11+ and re-run."
}

Write-Host "[1/4] Creating virtualenv (.venv)..."
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
} else {
    Write-Host "      .venv already exists — skipping"
}

Write-Host "[2/4] Installing Python packages..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\.venv\Scripts\pip.exe install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed." }

Write-Host "[3/4] Installing Playwright browser support (for connect scripts)..."
& .\.venv\Scripts\playwright.exe install chromium
# Edge/Chrome can also be used by connect_sessions.py if installed on the machine.

# --- .env ---
Write-Host "[4/4] Checking .env..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Created .env from .env.example." -ForegroundColor Yellow
    Write-Host "Do NOT fill this from scratch if you can avoid it." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Easiest path:"
    Write-Host "  1. Get the shared team .env from your password manager / IT vault"
    Write-Host "  2. Replace this .env with that file (same folder as app.py)"
    Write-Host "  3. Or paste the missing secret values into the empty fields"
    Write-Host ""
    Write-Host "Opening .env in Notepad..."
    Start-Process notepad ".env"
} else {
    Write-Host "      .env already exists — leaving it alone"
}

Write-Host ""
Write-Host "=== Setup done ===" -ForegroundColor Green
Write-Host "Start the app:  double-click scripts\run-app.bat"
Write-Host "Or:            .\.venv\Scripts\python app.py"
Write-Host "Then open:     http://127.0.0.1:5000"
Write-Host ""
Write-Host "When Stratus / Revizto / Symetri sessions expire, use scripts\connect-*.bat"
Write-Host "(those push cookies into YOUR local .env — no need to paste by hand)."
Write-Host ""
