param location string = resourceGroup().location
param appName string
param registryName string
param imageTag string
param sqlServer string
param sqlUser string = 'aw_demo_reader'
@secure()
param sqlPassword string
@secure()
@minLength(32)
param mcpToken string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${appName}-pull'
  location: location
}

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'AcrPull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-logs'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${appName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8000, transport: 'http', allowInsecure: false }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
      secrets: [{ name: 'sql-password', value: sqlPassword }, { name: 'mcp-token', value: mcpToken }]
    }
    template: {
      containers: [{
        name: 'mcp'
        image: '${registry.properties.loginServer}/adventureworks-mcp:${imageTag}'
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'AW_SQL_SERVER', value: sqlServer }
          { name: 'AW_SQL_DATABASE', value: 'AdventureWorksLT_MCPDemo' }
          { name: 'AW_SQL_USER', value: sqlUser }
          { name: 'AW_SQL_PASSWORD', secretRef: 'sql-password' }
          { name: 'AW_MCP_TOKEN', secretRef: 'mcp-token' }
        ]
        probes: [
          { type: 'Liveness', httpGet: { path: '/health', port: 8000 }, initialDelaySeconds: 10, periodSeconds: 15 }
          { type: 'Readiness', httpGet: { path: '/health', port: 8000 }, initialDelaySeconds: 5, periodSeconds: 10 }
        ]
      }]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
  dependsOn: [pull]
}

output mcpUrl string = 'https://${app.properties.configuration.ingress.fqdn}/mcp'
