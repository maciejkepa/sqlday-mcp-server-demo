# Resolve a working launcher, including uv installs whose copied az.bat cannot find Python.
[CmdletBinding()]
param([switch]$PassThru)
$ErrorActionPreference = 'Stop'
$launcher = $null
$uvCommand = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($uvCommand) {
    $toolRoot = & $uvCommand.Source tool dir
    if ($LASTEXITCODE -eq 0 -and $toolRoot) {
        $cliScripts = Join-Path ($toolRoot.Trim()) 'azure-cli/Scripts'
        $candidate = Join-Path $cliScripts 'az.bat'
        if ((Test-Path -LiteralPath $candidate) -and
            (Test-Path -LiteralPath (Join-Path $cliScripts 'python.exe'))) {
            $launcher = $candidate
        }
    }
}
if (-not $launcher) {
    $command = Get-Command az -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $command) { throw 'Azure CLI is not installed. Install it or run uv tool install azure-cli.' }
    $launcher = $command.Source
}
$version = & $launcher version --output json
if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed to start using: $launcher" }
# Also make plain `az` work in this terminal. Deployment scripts use the absolute path.
$cliDirectory = Split-Path $launcher -Parent
$otherDirectories = @($env:PATH -split [regex]::Escape([IO.Path]::PathSeparator) |
    Where-Object { $_ -ne $cliDirectory })
$env:PATH = (@($cliDirectory) + $otherDirectories) -join [IO.Path]::PathSeparator
if ($PassThru) { $launcher } else { $version }
