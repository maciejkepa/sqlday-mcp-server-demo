[CmdletBinding()]
param(
    [string]$SubscriptionId = 'f2515b68-6632-4afd-b4cc-7f7808fca36d',
    [string]$ResourceGroup = 'sqldaylite-demo-rg',
    [Parameter(Mandatory)][string]$PresenterIPv4
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = Split-Path $PSScriptRoot -Parent
$azCli = & (Join-Path $PSScriptRoot 'Use-AzureCli.ps1') -PassThru
if (-not $env:AW_ADMIN_PASSWORD -or $env:AW_ADMIN_PASSWORD.Length -lt 16) {
    throw 'Set AW_ADMIN_PASSWORD to a strong password of at least 16 characters.'
}
if (-not $env:AW_ADMIN_USER) { $env:AW_ADMIN_USER = 'sqldayadmin' }
$ip = $null
if (-not [Net.IPAddress]::TryParse($PresenterIPv4, [ref]$ip) -or
    $ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or $PresenterIPv4 -eq '0.0.0.0') {
    throw 'PresenterIPv4 must be a single public IPv4 address.'
}
& $azCli account set --subscription $SubscriptionId
if ($LASTEXITCODE -ne 0) { throw 'Sign in with az login first.' }
$group = & $azCli group show -n $ResourceGroup --only-show-errors -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cannot read the target resource group.' }
$parameters = @{
    location = @{ value = $group.location }; administratorLogin = @{ value = $env:AW_ADMIN_USER }
    administratorPassword = @{ value = $env:AW_ADMIN_PASSWORD }; presenterIPv4 = @{ value = $PresenterIPv4 }
}
$document = @{ '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    contentVersion = '1.0.0.0'; parameters = $parameters }
$secretFile = Join-Path ([IO.Path]::GetTempPath()) ('aw-db-' + [guid]::NewGuid().ToString('N') + '.json')
try {
    [IO.File]::WriteAllText($secretFile, ($document | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    $raw = & $azCli deployment group create -g $ResourceGroup --template-file (Join-Path $repoRoot 'infra/database.bicep') `
        --parameters "@$secretFile" --only-show-errors -o json
    if ($LASTEXITCODE -ne 0) { throw 'SQL provisioning failed.' }
    $deployment = $raw | ConvertFrom-Json
} finally {
    if (Test-Path -LiteralPath $secretFile) { Remove-Item -LiteralPath $secretFile -Force }
}
$env:AW_SQL_SERVER = $deployment.properties.outputs.sqlFqdn.value
$env:AW_SQL_DATABASE = 'AdventureWorksLT_MCPDemo'
$artifactRoot = Join-Path $repoRoot 'artifacts'
New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null
[IO.File]::WriteAllText((Join-Path $artifactRoot 'demo-settings.json'),
    (@{ SqlServer = $env:AW_SQL_SERVER } | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
Write-Host ('SQL server: ' + $deployment.properties.outputs.sqlServerName.value)
Write-Host 'SQL sample ready. Next: set reader credentials and run presenter.prepare --reset-demo.'
