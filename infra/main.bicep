@description('Azure region — must support hosted agents (e.g. swedencentral, eastus2, westus3)')
param location string = resourceGroup().location

@description('Base name used to derive all resource names')
param baseName string

@description('Model to deploy (e.g. gpt-4.1-mini)')
param modelName string = 'gpt-4.1-mini'

@description('Model version')
param modelVersion string = '2025-04-14'

@description('Model deployment SKU capacity (tokens-per-minute in thousands)')
param modelCapacity int = 50

// ──────────────────────────────────────────────
// Foundry Account (Cognitive Services)
// ──────────────────────────────────────────────
resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: baseName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: baseName
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
  }
}

// ──────────────────────────────────────────────
// Foundry Project
// ──────────────────────────────────────────────
resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: foundryAccount
  name: '${baseName}-project'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// ──────────────────────────────────────────────
// Model Deployment
// ──────────────────────────────────────────────
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: foundryAccount
  name: modelName
  sku: {
    name: 'Standard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

// ──────────────────────────────────────────────
// Azure Container Registry
// ──────────────────────────────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: replace(baseName, '-', '')
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

// ──────────────────────────────────────────────
// RBAC: AcrPull for the project identity
// ──────────────────────────────────────────────
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, foundryProject.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: foundryProject.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ──────────────────────────────────────────────
// RBAC: Foundry User for the project identity on the account
// Required so the hosted agent runtime can access project storage and invoke models.
// ──────────────────────────────────────────────
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource foundryUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, foundryProject.id, foundryUserRoleId)
  scope: foundryAccount
  properties: {
    principalId: foundryProject.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ──────────────────────────────────────────────
// Outputs
// ──────────────────────────────────────────────
output foundryAccountName string = foundryAccount.name
output foundryProjectName string = foundryProject.name
output projectEndpoint string = 'https://${baseName}.services.ai.azure.com/api/projects/${foundryProject.name}'
output acrLoginServer string = acr.properties.loginServer
output projectPrincipalId string = foundryProject.identity.principalId
