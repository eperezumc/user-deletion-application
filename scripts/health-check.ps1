# Quick health check for IT monitoring (Task Scheduler / manual).
# Exit 0 = Stratus OK; exit 1 = problem or app not running.

param(
    [string]$Environment = "prod"
)

$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:5000"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path (Join-Path $ProjectRoot ".env")) {
    Get-Content (Join-Path $ProjectRoot ".env") | ForEach-Object {
        if ($_ -match '^\s*APP_PORT=(.+)$') { $port = [int]$Matches[1].Trim() }
    }
    if ($port) { $BaseUrl = "http://127.0.0.1:$port" }
}

$url = "$BaseUrl/api/stratus/health?environment=$Environment"
try {
    $r = Invoke-RestMethod -Uri $url -TimeoutSec 15
    if ($r.ok) {
        Write-Host "OK: Stratus ($Environment)"
        exit 0
    }
    Write-Host "FAIL: Stratus ($Environment) - $($r | ConvertTo-Json -Compress)"
    exit 1
} catch {
    Write-Host "FAIL: $($_.Exception.Message)"
    exit 1
}
