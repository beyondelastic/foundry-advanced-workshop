# 04 — Foundry Toolbox

Connect your hosted agent to a **Foundry Toolbox** — a managed collection of tools (Code Interpreter, File Search, and more) exposed via an MCP (Model Context Protocol) endpoint. Your agent gains powerful capabilities without you having to build or host them.

---

## What you'll learn

- What a Foundry Toolbox is and how it works.
- Create a Toolbox with Code Interpreter and File Search in the Foundry portal.
- Connect to the Toolbox MCP endpoint using `MCPStreamableHTTPTool`.
- Authenticate with `get_bearer_token_provider` and a custom `httpx.Auth` class.
- Mix local tools and Toolbox tools in the same agent.

---

## What is a Foundry Toolbox?

A **Toolbox** is a managed resource in your Foundry project that bundles one or more server-side tools behind an MCP-compliant endpoint. You create a Toolbox in the portal, add tools (like Code Interpreter or Web Search), and your agent connects to it over HTTP.

```mermaid
flowchart LR
    Agent["Hosted Agent"] -->|MCP / Streamable HTTP| Toolbox["Foundry Toolbox"]
    Toolbox --> CI["Code Interpreter"]
    Toolbox --> FS["File Search (RAG)"]
    Toolbox --> Custom["Custom tools (future)"]
```

Key properties:

| Feature | Detail |
|---------|--------|
| Protocol | MCP (Streamable HTTP transport) |
| Authentication | Azure AD bearer token (`https://ai.azure.com/.default`) |
| Required header | `Foundry-Features: Toolboxes=V1Preview` |
| Built-in tools | Code Interpreter, Web Search (Bing), File Search |
| Scope | Per Foundry project |
| Endpoint format | `{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1` |

---

## Set up the vector store

File Search requires a vector store with at least one uploaded document. This lesson includes a sample clinical guidelines document in `data/clinical-guidelines.md`.

### Upload via the Foundry portal

1. Open your Foundry project → **Data + indexes** → **Vector stores**.
2. Click **+ Create vector store** → name it (e.g., `workshop-guidelines`).
3. Upload `data/clinical-guidelines.md`.
4. Wait for processing to complete (a few seconds for this small file).
5. Copy the vector store ID (starts with `vs_...`) — you'll need it when adding File Search to your Toolbox.

### Or use the REST API

```bash
# Create vector store
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "$PROJECT_ENDPOINT/vector_stores?api-version=2025-11-15-preview" \
  -d '{"name":"workshop-guidelines"}'

# Upload file
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/clinical-guidelines.md" \
  -F "purpose=assistants" \
  "$PROJECT_ENDPOINT/files?api-version=2025-11-15-preview"

# Attach file to vector store
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "$PROJECT_ENDPOINT/vector_stores/<VS_ID>/files?api-version=2025-11-15-preview" \
  -d '{"file_id":"<FILE_ID>"}'
```

---

## Create a Toolbox

Before deploying this lesson's agent, create a Toolbox in the Foundry portal:

1. Open your Foundry project in the [Foundry portal](https://ai.azure.com).
2. Navigate to **Build** → **Toolboxes**.
3. Click **+ Create toolbox**.
4. Give it a name (e.g., `workshop-toolbox`).
5. Add tools:
   - **Code Interpreter** — executes Python code in a sandboxed environment.
   - **File Search** — searches through uploaded documents using vector embeddings (requires a vector store with at least one uploaded file).
6. Click **Publish**.

!!! tip "File Search requires a vector store"
    Before adding File Search to your Toolbox, create a vector store in your
    Foundry project and upload at least one document. The Toolbox will use this
    vector store for semantic search over your documents.

!!! tip "Toolbox name"
    Note the toolbox name — you'll need it for the `TOOLBOX_NAME` environment variable.

### Update your `.env`

Add the toolbox name to your `.env` file:

```
TOOLBOX_NAME=workshop-toolbox
```

---

## Project structure

```
examples/04-toolbox/
├── main.py            ← agent with Toolbox MCP integration
├── agent.yaml         ← includes TOOLBOX_NAME env var
├── azure.yaml         ← azd project manifest
├── Dockerfile
├── requirements.txt
└── data/
    └── clinical-guidelines.md  ← sample doc for File Search
```

---

## The code

[`examples/04-toolbox/main.py`](https://github.com/beyondelastic/foundry-advanced-workshop/blob/main/examples/04-toolbox/main.py)

```python
"""Lesson 04 — Foundry Toolbox."""

import os
from typing import Annotated

import httpx
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from pydantic import Field

from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

load_dotenv()

credential = DefaultAzureCredential()

client = FoundryChatClient(
    project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=credential,
)


_TOOLBOX_FEATURES = "Toolboxes=V1Preview"


class _ToolboxAuth(httpx.Auth):
    """httpx Auth that injects a fresh bearer token on every request."""

    def __init__(self, token_provider) -> None:
        self._get_token = token_provider

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._get_token()}"
        yield request


def resolve_toolbox_endpoint() -> str:
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"].rstrip("/")
    toolbox_name = os.environ["TOOLBOX_NAME"]
    return f"{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1"


token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
http_client = httpx.AsyncClient(
    auth=_ToolboxAuth(token_provider),
    headers={"Foundry-Features": _TOOLBOX_FEATURES},
    timeout=120.0,
)

toolbox = MCPStreamableHTTPTool(
    name="toolbox",
    url=resolve_toolbox_endpoint(),
    http_client=http_client,
    load_prompts=False,
)


@tool(approval_mode="never_require")
def summarize_findings(
    findings: Annotated[str, Field(description="The findings text to summarize")],
) -> str:
    """Summarize a set of findings into a concise bullet list."""
    return f"Summary of findings:\n{findings}"


async def main() -> None:
    agent = Agent(
        client=client,
        instructions=(
            "You are a healthcare research assistant with access to a Foundry Toolbox. "
            "Use the File Search tool to look up clinical guidelines and evidence-based recommendations. "
            "Use the Code Interpreter tool to run Python code for data analysis and calculations. "
            "Use the summarize_findings tool to compile your results. "
            "Always cite sources and remind the user your answers are informational only."
        ),
        tools=[summarize_findings, toolbox],
        default_options={"store": False},
    )

    server = ResponsesHostServer(agent)
    async with agent:
        await server.run_async()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## Step-by-step walkthrough

### 1. Toolbox authentication

```python
_TOOLBOX_FEATURES = "Toolboxes=V1Preview"


class _ToolboxAuth(httpx.Auth):
    def __init__(self, token_provider):
        self._get_token = token_provider

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self._get_token()}"
        yield request


token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
http_client = httpx.AsyncClient(
    auth=_ToolboxAuth(token_provider),
    headers={"Foundry-Features": _TOOLBOX_FEATURES},
    timeout=120.0,
)
```

The Toolbox MCP endpoint requires:

1. An Azure AD bearer token scoped to `https://ai.azure.com/.default`.
2. The feature header `Foundry-Features: Toolboxes=V1Preview` on every request.

`get_bearer_token_provider` handles token caching and refresh automatically. The custom `httpx.Auth` class injects the token into each outbound request.

### 2. Build the Toolbox endpoint URL

```python
def resolve_toolbox_endpoint() -> str:
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"].rstrip("/")
    toolbox_name = os.environ["TOOLBOX_NAME"]
    return f"{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1"
```

The Toolbox MCP endpoint follows a predictable URL pattern. The `?api-version=v1` query parameter is **required** — omitting it returns a 400 error.

### 3. Create the MCP tool

```python
toolbox = MCPStreamableHTTPTool(
    name="toolbox",
    url=resolve_toolbox_endpoint(),
    http_client=http_client,
    load_prompts=False,
)
```

`MCPStreamableHTTPTool` is MAF's built-in MCP client. It connects to the Toolbox and automatically discovers all available tools (Code Interpreter, Web Search, etc.).

- `load_prompts=False` — **required**; the Toolbox MCP server does not implement `prompts/list`.
- The `http_client` carries both the authentication and the feature header.

### 4. Mix local and Toolbox tools

```python
agent = Agent(
    client=client,
    instructions="...",
    tools=[summarize_findings, toolbox],
    ...
)
```

You can combine local `@tool` functions and MCP tools in the same `tools` list. The agent sees all of them as callable tools.

### 5. Async context manager

```python
server = ResponsesHostServer(agent)
async with agent:
    await server.run_async()
```

MCP tools require async initialization (to discover available tools from the server). The `async with agent` context manager connects to the Toolbox, discovers tools, then starts the server. On exit it cleanly disconnects.

### 6. `agent.yaml` with `TOOLBOX_NAME`

```yaml
environment_variables:
  - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
    value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
  - name: AZURE_AI_PROJECT_ENDPOINT
    value: ${AZURE_AI_PROJECT_ENDPOINT}
  - name: TOOLBOX_NAME
    value: ${TOOLBOX_NAME}
```

The `TOOLBOX_NAME` environment variable is mapped from your Foundry project environment, just like the model deployment name.

---

## Try it

### Initialize the agent

```bash
cd examples/04-toolbox
azd ai agent init
```

The wizard will ask you to:

1. **Use the code in the current directory**
2. Allow `agent.yaml` overwrite
3. Choose **Container Image (Docker)**
4. Select your subscription and Foundry project
5. Enter your ACR login server (e.g. `foundrywsadvaullah.azurecr.io`)
6. Select your existing model deployment

!!! warning "Fix `agent.yaml` after init"
    `azd ai agent init` overwrites `agent.yaml` and removes custom environment variables.
    After running init, ensure your `agent.yaml` includes **all three** env vars:

    ```yaml
    environment_variables:
        - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
          value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
        - name: AZURE_AI_PROJECT_ENDPOINT
          value: ${AZURE_AI_PROJECT_ENDPOINT}
        - name: TOOLBOX_NAME
          value: ${TOOLBOX_NAME}
    ```

    Without `AZURE_AI_PROJECT_ENDPOINT`, the Toolbox endpoint cannot be resolved.
    Without `TOOLBOX_NAME`, the agent won't know which Toolbox to connect to.

### Set the Toolbox name in your environment

Make sure the Toolbox exists in your Foundry project and the name matches:

```bash
azd env set TOOLBOX_NAME workshop-toolbox
```

This registers the variable in your azd environment so it gets injected into the agent at deploy time. For local testing, also add it to your `.env` file:

```bash
# .env (for local testing with azd ai agent run)
TOOLBOX_NAME=workshop-toolbox
```

### Run locally

```bash
azd ai agent run
```

!!! note "Toolbox tools require cloud connectivity"
    Unlike lessons 01–03, the Toolbox MCP endpoint is a remote service. Even when running locally, your agent makes outbound calls to the Toolbox endpoint. Ensure you are authenticated (`az login`) and the Toolbox exists in your project.

### Invoke (in a separate terminal)

```bash
cd examples/04-toolbox
azd ai agent invoke --local "Use Code Interpreter to calculate the average BMI from this data: weights = [72, 85, 68, 95, 78], heights = [1.75, 1.82, 1.60, 1.90, 1.68]"
```

Expected: the agent writes and executes Python code, returns the computed averages.

**File Search:**

```bash
azd ai agent invoke --local "What are the LDL-C targets for a very high risk patient with established cardiovascular disease?"
```

Expected: the agent searches the clinical guidelines document and returns the target (< 1.4 mmol/L and ≥ 50% reduction).

**Combining both tools:**

```bash
azd ai agent invoke --local "Look up the CHA2DS2-VASc scoring criteria, then use code interpreter to calculate the score for a 70-year-old woman with hypertension and diabetes."
```

Expected: the agent retrieves the scoring table via File Search, then uses Code Interpreter to compute the score.

### Deploy to the cloud

```bash
azd deploy toolbox-agent
```

This builds the container remotely, pushes to ACR, and deploys the agent to Foundry.

After the first deploy, assign the **Foundry User** role to the agent's managed identity:

```bash
AGENT_NAME=toolbox-agent
PROJECT_NAME=${BASE_NAME}-project

AGENT_IDENTITY=$(az ad sp list \
  --display-name "${BASE_NAME}-${PROJECT_NAME}-${AGENT_NAME}-AgentIdentity" \
  --query "[0].id" -o tsv)

az role assignment create \
  --assignee-object-id "$AGENT_IDENTITY" \
  --assignee-principal-type ServicePrincipal \
  --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
  --scope "$ACCOUNT_ID"
```

!!! tip "Stale conversation after RBAC errors"
    If you invoke the agent **before** the role assignment propagates, `azd` caches a
    conversation ID that was never persisted server-side. Subsequent calls will fail with
    `404 Conversation not found`. Fix it by forcing a new conversation:

    ```bash
    azd ai agent invoke --new-conversation "your prompt here"
    ```

Then invoke remotely:

```bash
azd ai agent invoke "What are the first-line medications for hypertension according to the guidelines? Use Code Interpreter to create a comparison table."
```

---

## Key takeaways

- A **Toolbox** bundles managed tools (Code Interpreter, File Search, Web Search) behind an MCP endpoint.
- `MCPStreamableHTTPTool` discovers and connects to Toolbox tools automatically.
- Authentication uses `get_bearer_token_provider` with scope `https://ai.azure.com/.default`.
- The `Foundry-Features: Toolboxes=V1Preview` header is **required** on all requests.
- The endpoint URL must include `?api-version=v1`.
- `load_prompts=False` is mandatory (Toolbox doesn't implement `prompts/list`).
- File Search requires a vector store with uploaded documents.
- Local `@tool` functions and Toolbox MCP tools can be mixed in the same agent.

---

## Official references

- [Foundry Toolbox overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/toolbox)
- [Foundry samples — 06-files (Toolbox example)](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/microsoft-agent-framework/06-files)
- [MCPStreamableHTTPTool](https://learn.microsoft.com/en-us/agent-framework/concepts/tools/#mcp-tools)
- [Code Interpreter tool](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/tools/code-interpreter)
- [Web Search tool](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/tools/web-search)
