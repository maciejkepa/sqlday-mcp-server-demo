[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][string]$SqlResourceGroup,
    [Parameter(Mandatory)][string]$SqlServer,
    [Parameter(Mandatory)][ValidatePattern('^[a-z][a-z0-9-]{1,30}[a-z0-9]$')][string]$AppName,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9]{5,50}$')][string]$RegistryName,
    [Parameter(Mandatory)][string]$PresenterIPv4,
    [ValidatePattern('^[a-zA-Z0-9_.-]+$')][string]$ImageTag = (Get-Date -Format 'yyyyMMddHHmmss')
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = Split-Path $PSScriptRoot -Parent
$azCli = & (Join-Path $PSScriptRoot 'Use-AzureCli.ps1') -PassThru
if (-not $env:AW_SQL_PASSWORD -or -not $env:AW_MCP_TOKEN -or $env:AW_MCP_TOKEN.Length -lt 32) {
    throw 'Set AW_SQL_PASSWORD and AW_MCP_TOKEN (at least 32 random characters) in this process.'
}
function Invoke-AzJson([string[]]$Arguments) {
    $raw = & $azCli @Arguments --only-show-errors --output json
    if ($LASTEXITCODE -ne 0) { throw 'Azure CLI command failed.' }
    if ($raw) { return ($raw | ConvertFrom-Json) }
}
$server = Invoke-AzJson -Arguments @('sql', 'server', 'show', '-g', $SqlResourceGroup, '-n', $SqlServer)
$location = $server.location
Invoke-AzJson -Arguments @('group', 'create', '-n', $ResourceGroup, '-l', $location) | Out-Null
Invoke-AzJson -Arguments @('deployment', 'group', 'create', '-g', $ResourceGroup,
    '--template-file', (Join-Path $repoRoot 'infra/registry.bicep'),
    '--parameters', "registryName=$RegistryName", "location=$location") | Out-Null

# ACR builds the image remotely: Docker Desktop is not required on the presenter laptop.
# Azure CLI traverses even ignored directories. Give it a fresh, minimal context instead.
$buildContext = & (Join-Path $PSScriptRoot 'New-BuildContext.ps1')
try {
    & $azCli acr build -r $RegistryName -g $ResourceGroup --image "adventureworks-mcp:$ImageTag" `
        --file (Join-Path $buildContext 'Dockerfile') $buildContext --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw 'Container build failed.' }
} finally {
    # Delete only the temporary directory created above, after checking its absolute path.
    $resolvedContext = (Resolve-Path -LiteralPath $buildContext).Path
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/')
    if ((Split-Path $resolvedContext -Parent) -ne $tempRoot -or
        (Split-Path $resolvedContext -Leaf) -notmatch '^sqlday-acr-[a-f0-9]{32}$' -or
        ((Get-Item -LiteralPath $resolvedContext).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Unexpected build-context path; refusing cleanup.'
    }
    Remove-Item -LiteralPath $resolvedContext -Recurse -Force
}

$parameters = @{
    location = @{ value = $location }; appName = @{ value = $AppName }
    registryName = @{ value = $RegistryName }; imageTag = @{ value = $ImageTag }
    sqlServer = @{ value = $server.fullyQualifiedDomainName }
    sqlUser = @{ value = 'aw_demo_reader' }; sqlPassword = @{ value = $env:AW_SQL_PASSWORD }
    mcpToken = @{ value = $env:AW_MCP_TOKEN }
}
$document = @{ '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    contentVersion = '1.0.0.0'; parameters = $parameters }
$secretFile = Join-Path ([IO.Path]::GetTempPath()) ('aw-' + [guid]::NewGuid().ToString('N') + '.json')
try {
    [IO.File]::WriteAllText($secretFile, ($document | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    $deployment = Invoke-AzJson -Arguments @('deployment', 'group', 'create', '-g', $ResourceGroup,
        '--template-file', (Join-Path $repoRoot 'infra/main.bicep'), '--parameters', "@$secretFile")
} finally {
    if (Test-Path -LiteralPath $secretFile) { Remove-Item -LiteralPath $secretFile -Force }
}
& (Join-Path $PSScriptRoot 'Update-SqlFirewall.ps1') -ResourceGroup $ResourceGroup `
    -SqlResourceGroup $SqlResourceGroup -SqlServer $SqlServer -AppName $AppName -PresenterIPv4 $PresenterIPv4
Write-Host ('MCP endpoint: ' + $deployment.properties.outputs.mcpUrl.value)
Write-Host 'Next: run scripts.smoke with this URL, then presenter.verify with reader credentials.'
