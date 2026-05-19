# 00 — Prerequisites

Before starting this workshop, make sure you have the tools, access, and Azure resources listed below.

---

## Region support for hosted agents

!!! danger "Hosted agents are only available in specific Azure regions"
    Choose a supported region when provisioning your resources.

    **Recommended region: East US 2 or Sweden Central**

Hosted agents are currently in **public preview** and available in these regions:

| Americas | Europe | Asia-Pacific | Other |
|----------|--------|-------------|-------|
| East US 2 | Sweden Central | Southeast Asia | South Africa North |
| North Central US | Norway East | Japan East | |
| West US | France Central | Korea Central | |
| West US 3 | Switzerland North | South India | |
| Canada Central | Poland Central | Australia East | |
| Brazil South | Spain Central | | |

Source: [Hosted agents — Region availability](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents#region-availability) (updated April 2026).

---

## Azure prerequisites

| Requirement | Details |
|-------------|---------|
| Azure subscription | [Create one for free](https://azure.microsoft.com/pricing/purchase-options/azure-account) |
| Role | **Owner** on the subscription (or Contributor + User Access Administrator) — needed to create resources and assign roles |

All other Azure resources (Foundry account, project, model deployment, ACR) are provisioned by the workshop's Bicep template.

---

## Local prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Azure CLI | 2.67+ | [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| Azure Developer CLI (`azd`) | 1.24.0+ | [Install azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) |

Docker Desktop is **not** required — `azd deploy` builds containers remotely.

---

## Step-by-step setup

### 1. Authenticate

```bash
az login
azd auth login
```

Verify:

```bash
az account show --query "{subscription: name, id: id}" -o table
```

### 2. Install the azd agent extension

```bash
azd ext install azure.ai.agents
```

Verify the extension is installed (version 0.1.27-preview or later):

```bash
azd ext list
```

### 3. Clone the repository

```bash
git clone https://github.com/beyondelastic/foundry-advanced-workshop.git
cd foundry-advanced-workshop
```

### 4. Provision Azure resources

This workshop provisions its own Foundry account, project, model deployment, and container registry using Bicep.

!!! warning "Resource name = subdomain (critical)"
    The Bicep template uses `baseName` as both the ARM resource name **and** the custom subdomain for the Foundry account. This ensures the hosted agent platform can correctly resolve the project endpoint. **Do not** reuse an existing Foundry account where the resource name differs from the subdomain.

```bash
# Create a resource group in a supported region
az group create \
  --name rg-foundry-advanced-workshop \
  --location eastus2

# Deploy all infrastructure
az deployment group create \
  --resource-group rg-foundry-advanced-workshop \
  --template-file infra/main.bicep \
  --parameters baseName=<your-unique-name>
```

Replace `<your-unique-name>` with a globally unique string (lowercase, no spaces, e.g. `foundryws-janedoe`). This becomes both the resource name and the endpoint subdomain.

??? example "Example output"
    ```json
    {
      "foundryAccountName": "foundryws-janedoe",
      "foundryProjectName": "foundryws-janedoe-project",
      "projectEndpoint": "https://foundryws-janedoe.services.ai.azure.com/api/projects/foundryws-janedoe-project",
      "acrLoginServer": "foundrywsjanedoe.azurecr.io",
      "projectPrincipalId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
    ```

Save the outputs — you'll need them in the next step.

### 5. Assign yourself the Foundry Project Manager role

Export variables from your deployment output so you can reuse them throughout the workshop:

```bash
# Set these once — used in all subsequent commands
export BASE_NAME=<your-unique-name>
export RESOURCE_GROUP=rg-foundry-advanced-workshop
export ACCOUNT_ID=$(az cognitiveservices account show \
  --name $BASE_NAME --resource-group $RESOURCE_GROUP --query id -o tsv)
```

```bash
az role assignment create \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --role "Foundry Project Manager" \
  --scope "$ACCOUNT_ID"
```

!!! tip "Why Foundry Project Manager?"
    This role includes both data-plane permissions to create agents **and** the ability to assign the `Foundry User` role to the agent identity that the platform creates at deploy time.

### 6. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 7. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in from your deployment outputs:

| Variable | Value from Bicep output |
|----------|------------------------|
| `AZURE_AI_PROJECT_ENDPOINT` | `projectEndpoint` output |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | The model name (e.g. `gpt-4.1-mini`) |

### 8. Start the workshop UI

```bash
mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## Verification checklist

- [ ] `az account show` displays the correct subscription
- [ ] `azd ext list` shows `azure.ai.agents` at version 0.1.27-preview or later
- [ ] Python 3.12+ is active in your virtual environment (`python --version`)
- [ ] `az deployment group show` confirms your infra deployed successfully
- [ ] `.env` file contains your `AZURE_AI_PROJECT_ENDPOINT` and `AZURE_AI_MODEL_DEPLOYMENT_NAME`
- [ ] Your Foundry resource is in a [supported region](#region-support-for-hosted-agents)
- [ ] `mkdocs serve` runs and the workshop site loads at localhost:8000

---

## Official references

- [Hosted agents concept & region list](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent?pivots=azd)
- [Install Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
