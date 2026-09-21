[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SqlResourceGroup,
    [Parameter(Mandatory)][string]$SqlServer,
    [Parameter(Mandatory)][string]$SourceDatabase
)
$ErrorActionPreference = 'Stop'
$azCli = & (Join-Path $PSScriptRoot 'Use-AzureCli.ps1') -PassThru
$targetDatabase = 'AdventureWorksLT_MCPDemo'
if ($SourceDatabase -eq $targetDatabase) { throw 'Source and target must differ.' }
$databases = & $azCli sql db list -g $SqlResourceGroup -s $SqlServer --only-show-errors -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cannot list SQL databases.' }
if ($databases.name -contains $targetDatabase) {
    throw 'Demo copy already exists. This script never overwrites an existing database. Use presenter.prepare to reset its data.'
}
& $azCli sql db copy -g $SqlResourceGroup -s $SqlServer -n $SourceDatabase `
    --dest-name $targetDatabase --only-show-errors -o none
if ($LASTEXITCODE -ne 0) { throw 'Database copy failed.' }
$database = & $azCli sql db show -g $SqlResourceGroup -s $SqlServer -n $targetDatabase --only-show-errors -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect demo database.' }
if ($null -ne $database.autoPauseDelay -and $database.autoPauseDelay -ne -1) {
    & $azCli sql db update -g $SqlResourceGroup -s $SqlServer -n $targetDatabase --auto-pause-delay -1 --only-show-errors -o none
    if ($LASTEXITCODE -ne 0) { throw 'Could not disable serverless auto-pause.' }
}
Write-Host 'Copy created. Next: configure admin variables and run presenter.prepare --reset-demo.'
