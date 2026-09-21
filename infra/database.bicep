param location string = resourceGroup().location
param sqlServerName string = 'sqlday-sql-${uniqueString(subscription().id, resourceGroup().id)}'
param administratorLogin string = 'sqldayadmin'
@secure()
@minLength(16)
param administratorPassword string
param presenterIPv4 string

resource sqlServer 'Microsoft.Sql/servers@2023-08-01' = {
  name: sqlServerName
  location: location
  properties: {
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

resource database 'Microsoft.Sql/servers/databases@2023-08-01' = {
  parent: sqlServer
  name: 'AdventureWorksLT_MCPDemo'
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
    capacity: 5
  }
  properties: {
    sampleName: 'AdventureWorksLT'
    maxSizeBytes: 2147483648
    requestedBackupStorageRedundancy: 'Local'
  }
}

resource presenterFirewall 'Microsoft.Sql/servers/firewallRules@2023-08-01' = {
  parent: sqlServer
  name: 'sqlday-presenter'
  properties: {
    startIpAddress: presenterIPv4
    endIpAddress: presenterIPv4
  }
}

output sqlServerName string = sqlServer.name
output sqlFqdn string = sqlServer.properties.fullyQualifiedDomainName
output databaseName string = database.name
