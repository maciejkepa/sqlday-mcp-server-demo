# Copy only named runtime files. Never enumerate the repository or its cache directories.
[CmdletBinding()]
param([string]$SourceRoot = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = 'Stop'
$files = @(
    'Dockerfile', '.dockerignore', 'pyproject.toml', 'uv.lock',
    'MCP instrukcje.md', 'app/__init__.py', 'app/server.py',
    'app/database.py', 'app/sql_policy.py', 'app/logging.json'
)
# Check inputs before allocating the temporary directory.
foreach ($relativePath in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot $relativePath) -PathType Leaf)) {
        throw "Missing container input: $relativePath"
    }
}
$context = Join-Path ([IO.Path]::GetTempPath()) ('sqlday-acr-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $context 'app') -Force | Out-Null
foreach ($relativePath in $files) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot $relativePath) -Destination (Join-Path $context $relativePath)
}
Write-Output $context
