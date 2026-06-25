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
// Azure AI Search (required for FoundryIQ / Knowledge Bases)
// ──────────────────────────────────────────────
resource searchService 'Microsoft.Search/searchServices@2025-02-01-preview' = {
  name: '${baseName}-search'
  location: location
  sku: {
    name: 'basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

// ──────────────────────────────────────────────
// Storage Account (for Knowledge Base blob sources)
// ──────────────────────────────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: replace(baseName, '-', '')
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource knowledgeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'knowledge-docs'
}

// ──────────────────────────────────────────────
// Embedding Model Deployment (for Knowledge Source vectorization)
// ──────────────────────────────────────────────
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: foundryAccount
  name: 'text-embedding-3-large'
  sku: {
    name: 'Standard'
    capacity: 50
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
  }
  dependsOn: [modelDeployment]
}

// Connection: Foundry Account → AI Search
resource searchConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  name: '${baseName}-aisearch'
  parent: foundryAccount
  properties: {
    category: 'CognitiveSearch'
    target: searchService.properties.endpoint
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: searchService.listAdminKeys().primaryKey
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchService.id
      location: searchService.location
    }
  }
}

// ──────────────────────────────────────────────
// RBAC: Cognitive Services User for AI Search identity → Foundry Account
// Required so AI Search can use models (embedding, chat completion) during ingestion.
// ──────────────────────────────────────────────
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource searchCogServicesUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, searchService.id, cognitiveServicesUserRoleId)
  scope: foundryAccount
  properties: {
    principalId: searchService.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ──────────────────────────────────────────────
// RBAC: Storage Blob Data Reader for AI Search identity → Storage Account
// Required so AI Search can read blobs during knowledge source ingestion.
// ──────────────────────────────────────────────
var storageBlobDataReaderRoleId = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

resource searchStorageBlobReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, searchService.id, storageBlobDataReaderRoleId)
  scope: storageAccount
  properties: {
    principalId: searchService.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataReaderRoleId)
    principalType: 'ServicePrincipal'
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
// RBAC: Search Index Data Contributor for project identity on AI Search
// Required so FoundryIQ can create/manage vector store indexes.
// ──────────────────────────────────────────────
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

resource searchDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, foundryProject.id, searchIndexDataContributorRoleId)
  scope: searchService
  properties: {
    principalId: foundryProject.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ──────────────────────────────────────────────
// RBAC: Search Service Contributor for project identity on AI Search
// Required so FoundryIQ can manage search service indexes.
// ──────────────────────────────────────────────
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'

resource searchServiceContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, foundryProject.id, searchServiceContributorRoleId)
  scope: searchService
  properties: {
    principalId: foundryProject.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
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
output foundryEndpoint string = 'https://${baseName}.services.ai.azure.com/'
output searchServiceName string = searchService.name
output searchEndpoint string = 'https://${baseName}-search.search.windows.net'
output searchConnectionName string = searchConnection.name
output storageAccountName string = storageAccount.name
output acrLoginServer string = acr.properties.loginServer
output projectPrincipalId string = foundryProject.identity.principalId
