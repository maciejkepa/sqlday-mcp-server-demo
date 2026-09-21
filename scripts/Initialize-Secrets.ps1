# Windows-only convenience: encrypted with the current user's Windows DPAPI key.
[CmdletBinding()]
param(
    [switch]$IncludeAdmin,
    [ValidatePattern('^[a-zA-Z0-9.-]+\.database\.windows\.net$')][string]$SqlServer
)
$ErrorActionPreference = 'Stop'
$artifactRoot = Join-Path (Split-Path $PSScriptRoot -Parent) 'artifacts'
New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null
$secretPath = Join-Path $artifactRoot 'demo-secrets.clixml'
$settingsPath = Join-Path $artifactRoot 'demo-settings.json'
if ($SqlServer) {
    $env:AW_SQL_SERVER = $SqlServer
    [IO.File]::WriteAllText($settingsPath, (@{ SqlServer = $SqlServer } | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
} elseif (-not $env:AW_SQL_SERVER -and (Test-Path -LiteralPath $settingsPath)) {
    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
    $env:AW_SQL_SERVER = $settings.SqlServer
}
function New-Secret {
    $bytes = New-Object byte[] 36
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    # Prefix guarantees SQL password complexity; remaining entropy is random.
    return ConvertTo-SecureString ('Aw9!' + [Convert]::ToBase64String($bytes)) -AsPlainText -Force
}
if (-not (Test-Path -LiteralPath $secretPath)) {
    @{ Reader = (New-Secret); Admin = (New-Secret); Token = (New-Secret) } | Export-Clixml -LiteralPath $secretPath
}
$secrets = Import-Clixml -LiteralPath $secretPath
function Read-Secret([Security.SecureString]$Value) {
    return [Net.NetworkCredential]::new('', $Value).Password
}
$env:AW_SQL_USER = 'aw_demo_reader'
$env:AW_SQL_DATABASE = 'AdventureWorksLT_MCPDemo'
$env:AW_SQL_PASSWORD = Read-Secret $secrets.Reader
$env:AW_MCP_TOKEN = Read-Secret $secrets.Token
if ($IncludeAdmin) {
    $env:AW_ADMIN_USER = 'sqldayadmin'
    $env:AW_ADMIN_PASSWORD = Read-Secret $secrets.Admin
} else {
    Remove-Item Env:AW_ADMIN_USER, Env:AW_ADMIN_PASSWORD -ErrorAction SilentlyContinue
}
Write-Host 'Secrets loaded into this process; values were not printed. Encrypted backup: artifacts/demo-secrets.clixml'
if (-not $env:AW_SQL_SERVER) {
    Write-Warning 'SQL server is not set. Run this script with -SqlServer <server>.database.windows.net once to save it.'
}
