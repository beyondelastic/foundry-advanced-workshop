# Setup

## 1. Azure prerequisites

- An active Azure subscription.
- A Microsoft Foundry resource, project, and model deployment (e.g., `gpt-4.1-mini`).
  If you don't have these yet, complete the [beginner Foundry workshop](https://beyondelastic.github.io/foundry-workshop/) first.
- **Azure AI Project Manager** role at project scope (or Owner / User Access Administrator on the resource group for RBAC auto-assignment by `azd`).

> **Important — Region support:** Hosted agents are only available in specific Azure regions during preview.
> If your Foundry resource is in an unsupported region, you must create a new one.
> Recommended region: **East US 2**.
> See the [00 Prerequisites](https://beyondelastic.github.io/foundry-advanced-workshop/00-prereqs/) lesson for the full list.

## 2. Local prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Azure CLI | 2.67+ | [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| Azure Developer CLI (`azd`) | 1.24.0+ | [Install azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) |
| `azd` agent extension | 0.1.27-preview+ | `azd ext install azure.ai.agents` |

Docker Desktop is **not** required — `azd deploy` builds containers remotely.

## 3. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
pip install -r requirements.txt
```

## 4. Authenticate

```bash
az login
azd auth login
az account show   # verify correct subscription
```

## 5. Install the azd agent extension

```bash
azd ext install azure.ai.agents
azd ext list   # verify it appears
```

## 6. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

- `AZURE_AI_PROJECT_ENDPOINT` — your Foundry project endpoint (find it in the Foundry portal under project settings).
- `AZURE_AI_MODEL_DEPLOYMENT_NAME` — your deployed model name (e.g., `gpt-4.1-mini`).

## 7. Start the workshop UI

```bash
mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## 8. Suggested workshop order

1. `examples/01-first-hosted-agent/` — Your First Hosted Agent
2. `examples/02-tools-and-files/` — Tools & File Persistence
3. `examples/03-langgraph/` — LangGraph Hosted Agent
4. `examples/04-toolbox/` — Foundry Toolbox

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `DefaultAzureCredential` errors | Run `az login` and `azd auth login` to refresh credentials. |
| `azd ext install` fails | Update azd: `winget upgrade Microsoft.Azd` (Windows) or `brew upgrade azd` (macOS/Linux). |
| Wrong subscription | Run `az account set --subscription <id>`. |
| Region not supported | Create a new Foundry resource in **East US 2** or another supported region. |
