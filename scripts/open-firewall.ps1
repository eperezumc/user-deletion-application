# Open inbound TCP port for the app (run PowerShell as Administrator).
param(
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"

$ruleName = "User Disabling Platform (TCP $Port)"

$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Firewall rule already exists: $ruleName"
    exit 0
}

New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort $Port `
    -Action Allow `
    -Profile Domain, Private

Write-Host "Created firewall rule: $ruleName (TCP $Port, Domain + Private profiles)"
