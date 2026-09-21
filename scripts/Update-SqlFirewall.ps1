[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][string]$SqlResourceGroup,
    [Parameter(Mandatory)][string]$SqlServer,
    [Parameter(Mandatory)][string]$AppName,
    [Parameter(Mandatory)][string]$PresenterIPv4
)
$ErrorActionPreference = 'Stop'
$azCli = & (Join-Path $PSScriptRoot 'Use-AzureCli.ps1') -PassThru
function Assert-IPv4([string]$Address) {
    $ip = $null
    if (-not [Net.IPAddress]::TryParse($Address, [ref]$ip) -or
        $ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or $Address -eq '0.0.0.0') {
        throw "Expected one IPv4 address, got: $Address"
    }
}
Assert-IPv4 $PresenterIPv4
$app = & $azCli containerapp show -g $ResourceGroup -n $AppName --only-show-errors -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Container App.' }
$outbound = @($app.properties.outboundIpAddresses)
if (-not $outbound.Count -or -not $outbound[0]) { throw 'No outbound IPs returned. Inspect the Container Apps network before opening SQL access.' }
$addresses = @($outbound + @($PresenterIPv4) | Sort-Object -Unique)
$prefix = "mcp-$AppName-"
$wantedNames = @()
foreach ($address in $addresses) {
    Assert-IPv4 $address
    $ruleName = $prefix + $address.Replace('.', '-')
    $wantedNames += $ruleName
    & $azCli sql server firewall-rule create -g $SqlResourceGroup -s $SqlServer -n $ruleName `
        --start-ip-address $address --end-ip-address $address --only-show-errors -o none
    if ($LASTEXITCODE -ne 0) { throw 'Firewall rule update failed.' }
}
$rules = & $azCli sql server firewall-rule list -g $SqlResourceGroup -s $SqlServer --only-show-errors -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect firewall rules.' }
foreach ($rule in $rules) {
    if ($rule.name.StartsWith($prefix) -and $wantedNames -notcontains $rule.name) {
        & $azCli sql server firewall-rule delete -g $SqlResourceGroup -s $SqlServer -n $rule.name --only-show-errors -o none
        if ($LASTEXITCODE -ne 0) { throw 'Removing an obsolete demo firewall rule failed.' }
    }
}
Write-Host 'Demo firewall rules synchronized. Run the authenticated smoke test to verify SQL connectivity.'
