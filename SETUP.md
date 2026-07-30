# Setup

## 1. Azure prerequisites

- An active Azure subscription.
- A Microsoft Foundry resource, project, and model deployment (e.g., `gpt-5-mini`).
  The workshop can provision all of this for you via `infra/main.bicep` — see the
  [00 Prerequisites](https://beyondelastic.github.io/foundry-advanced-workshop/00-prereqs/) lesson.
- **Foundry Project Manager** role at project scope (or Owner / User Access Administrator on the resource group for RBAC auto-assignment by `azd`).

> **Important — Region support:** Hosted agents are only available in specific Azure regions during preview.
> If your Foundry resource is in an unsupported region, you must create a new one.
> Recommended region: **Sweden Central** (or East US 2; note East US 2 can be short on Azure AI Search capacity).
> See the [00 Prerequisites](https://beyondelastic.github.io/foundry-advanced-workshop/00-prereqs/) lesson for the full list.

## 2. Local prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Python | 3.12+ (hosted agent runtime uses 3.13) | [python.org](https://www.python.org/downloads/) |
| Azure CLI | 2.67+ | [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| Azure Developer CLI (`azd`) | 1.28.0+ | [Install azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) |
| `azd` agent extension | 1.0.0-beta.7+ | `azd ext install azure.ai.agents` |

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
- `AZURE_AI_MODEL_DEPLOYMENT_NAME` — your deployed model name (e.g., `gpt-5-mini`).

Lessons 05–07 use additional variables (Search/Storage endpoints for Foundry IQ, and a
`WEBIQ_API_KEY` for Web IQ). See `.env.example` and each lesson's prerequisites.

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
5. `examples/05-guardrails/` — Guardrails & Content Safety
6. `examples/06-foundry-iq/` — Foundry IQ Knowledge Base
7. `examples/07-web-iq/` — Microsoft Web IQ (private preview)

> Lessons 01–04 are **hosted agents** deployed with `azd`; lessons 05–07 are **SDK scripts**
> you run with `python main.py` from the root virtual environment.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `DefaultAzureCredential` errors | Run `az login` and `azd auth login` to refresh credentials. |
| `azd ext install` fails | Update azd: `winget upgrade Microsoft.Azd` (Windows) or `brew upgrade azd` (macOS/Linux). |
| Wrong subscription | Run `az account set --subscription <id>`. |
| Region not supported | Create a new Foundry resource in **Sweden Central** or another supported region. |
