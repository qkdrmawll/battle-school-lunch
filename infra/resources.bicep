@description('The location used for all deployed resources')
param location string = resourceGroup().location

@description('Tags that will be applied to all resources')
param tags object = {}

@secure()
@description('NEIS API key used by the backend')
param neisApiKey string


param backendExists bool
param frontendExists bool

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)
var containerRegistryName = '${abbrs.containerRegistryRegistries}${resourceToken}'

// Monitor application with Azure Monitor
module monitoring 'br/public:avm/ptn/azd/monitoring:0.1.0' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    applicationInsightsDashboardName: '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
  }
}
// Container registry
module containerRegistry 'br/public:avm/res/container-registry/registry:0.1.1' = {
  name: 'registry'
  params: {
    name: containerRegistryName
    location: location
    tags: tags
    acrAdminUserEnabled: true
    publicNetworkAccess: 'Enabled'
  }
}

resource containerRegistryResource 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
  dependsOn: [
    containerRegistry
  ]
}
var containerRegistryCredentials = containerRegistryResource.listCredentials()

// Container apps environment
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.4.5' = {
  name: 'container-apps-environment'
  params: {
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
  }
}

module backendFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'backend-fetch-image'
  params: {
    exists: backendExists
    name: 'backend'
  }
}

module backend 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'backend'
  params: {
    name: 'backend'
    ingressExternal: false
    ingressTargetPort: 8000
    corsPolicy: {
      allowedOrigins: [
        'https://frontend.${containerAppsEnvironment.outputs.defaultDomain}'
      ]
      allowedMethods: [
        '*'
      ]
    }
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  [
        {
          name: 'neis-api-key'
          value: neisApiKey
        }
        {
          name: 'acr-password'
          value: containerRegistryCredentials.passwords[0].value
        }
      ]
    }
    containers: [
      {
        image: backendFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: [
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'FRONTEND_ORIGIN'
            value: 'https://frontend.${containerAppsEnvironment.outputs.defaultDomain}'
          }
          {
            name: 'NEIS_API_KEY'
            secretRef: 'neis-api-key'
          }
          {
            name: 'PORT'
            value: '8000'
          }
        ]
      }
    ]
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        username: containerRegistryCredentials.username
        passwordSecretRef: 'acr-password'
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'backend' })
  }
}

module frontendFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'frontend-fetch-image'
  params: {
    exists: frontendExists
    name: 'frontend'
  }
}

module frontend 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'frontend'
  params: {
    name: 'frontend'
    ingressExternal: true
    ingressTargetPort: 8080
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  [
        {
          name: 'acr-password'
          value: containerRegistryCredentials.passwords[0].value
        }
      ]
    }
    containers: [
      {
        image: frontendFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: [
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'BACKEND_BASE_URL'
            value: 'https://${backend.outputs.fqdn}'
          }
          {
            name: 'BACKEND_HOST'
            value: backend.outputs.fqdn
          }
          {
            name: 'PORT'
            value: '8080'
          }
        ]
      }
    ]
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        username: containerRegistryCredentials.username
        passwordSecretRef: 'acr-password'
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'frontend' })
  }
}
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_RESOURCE_BACKEND_ID string = backend.outputs.resourceId
output AZURE_RESOURCE_FRONTEND_ID string = frontend.outputs.resourceId
