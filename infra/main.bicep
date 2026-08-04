// Deliberately light: this project consumes the shared Foundry resource and
// only owns its observability plumbing — a Log Analytics workspace and a
// workspace-based Application Insights, so the platform's own behavior is
// auditable inside the subscription (the same pattern the Azure SRE Agent
// uses). Deleting rg-aep-dev-eus2 deletes this project entirely.
targetScope = 'resourceGroup'

@description('Environment name; this portfolio only has dev')
param environment string = 'dev'

@description('Project prefix used in resource names')
param projectPrefix string = 'aep'

@description('Region short code used in resource names')
param regionShort string = 'eus2'

param location string = resourceGroup().location

@description('Planned teardown date, required by the portfolio tagging policy')
param expiresOn string = '2026-12-31'

var tags = {
  project: projectPrefix
  environment: environment
  owner: 'marvicqui'
  costCenter: 'portfolio'
  createdBy: 'bicep'
  expiresOn: expiresOn
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'law-${projectPrefix}-${environment}-${regionShort}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    workspaceCapping: {
      // Hard cap: this is a portfolio project with a $30/month budget.
      dailyQuotaGb: 1
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${projectPrefix}-${environment}-${regionShort}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

output appInsightsConnectionString string = appInsights.properties.ConnectionString
output logAnalyticsWorkspaceId string = logAnalytics.id
