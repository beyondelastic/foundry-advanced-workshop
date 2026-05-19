# Microsoft Foundry Advanced Workshop

Welcome to an advanced, docs-first Microsoft Foundry workshop focused on **hosted agents**.

This workshop is the sequel to the [beginner Foundry workshop](https://beyondelastic.github.io/foundry-workshop/). It assumes you already have a Foundry resource, project, and model deployment. If you don't, complete the beginner workshop first.

The examples use lightweight healthcare and life-sciences scenarios so the workshop stays consistent across all lessons. Every exercise is based on official Microsoft documentation and the [microsoft-foundry/foundry-samples](https://github.com/microsoft-foundry/foundry-samples) repository.

Workshop source repository: [beyondelastic/foundry-advanced-workshop](https://github.com/beyondelastic/foundry-advanced-workshop)

This workshop is intentionally small, practical, and tied to official Microsoft documentation. Each section includes:

- a clear goal
- official reference links
- one or more runnable Python examples
- expected results
- a short verification checklist

### Official by default

Every core exercise is mapped to Microsoft Learn or the official Foundry samples repository.

### Python only

The examples stay in one language so you can focus on Foundry concepts instead of SDK translation.

### Built for practitioners

Each exercise builds on the previous one. The agent evolves from a basic assistant to a tool-equipped, cloud-connected hosted agent.

## What this workshop covers

|     | Lesson                     | Topic                                                                 |
|-----|----------------------------|-----------------------------------------------------------------------|
| 00  | Prerequisites              | azd CLI, agent extension, supported regions, environment setup        |
| 01  | Your First Hosted Agent    | Deploy a containerized agent with Microsoft Agent Framework           |
| 02  | Tools & File Persistence   | `@tool` decorator, per-session sandbox filesystem, session isolation  |
| 03  | LangGraph Hosted Agent     | Same hosted agent concepts rebuilt with LangGraph                     |
| 04  | Foundry Toolbox            | Code Interpreter, Web Search via Toolbox MCP endpoint                 |

## Design goals

- Keep the flow easy to follow.
- Favour official documentation over custom theory.
- Keep examples short and runnable.
- Use a lightweight docs-first web UI.

## Official sources used

- [Microsoft Foundry documentation](https://learn.microsoft.com/en-us/azure/foundry/)
- [Hosted agents concept](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent?pivots=azd)
- [Foundry samples — hosted agents](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents)
- [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)

## Repository layout

```
.
├── docs/           ← lesson pages (served by MkDocs)
├── examples/
│   ├── 01-first-hosted-agent/
│   ├── 02-tools-and-files/
│   ├── 03-langgraph/
│   └── 04-toolbox/
├── infra/           ← Bicep for ACR + role assignment
├── mkdocs.yml
├── requirements.txt
├── .env.example
└── SETUP.md
```

## Quick start

1.
Clone the repository and set up the Python environment:

```bash
git clone https://github.com/beyondelastic/foundry-advanced-workshop.git
cd foundry-advanced-workshop
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

2.
Sign in to Azure:

```bash
az login
azd auth login
```

3.
Configure your environment variables:

```bash
cp .env.example .env   # fill in your values
```

4.
Follow the lessons on this site starting with [Prerequisites](00-prereqs.md).

Full setup instructions are in [SETUP.md](https://github.com/beyondelastic/foundry-advanced-workshop/blob/main/SETUP.md).
