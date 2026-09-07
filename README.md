# Microsoft Foundry Advanced Workshop

A docs-first advanced workshop covering **hosted agents**, **guardrails**, and **advanced retrieval & web grounding** in Microsoft Foundry.

This workshop builds on the [beginner Foundry workshop](https://beyondelastic.github.io/foundry-workshop/), but you do not need to complete it first. The [Prerequisites](docs/00-prereqs.md) lesson provisions the required Foundry account, project, model deployment, and supporting Azure resources using Bicep.

**Topics covered:**

| Lesson | Title | Topic |
|--------|-------|-------|
| 00 | Prerequisites | azd CLI, agent extension, Bicep infra, supported regions |
| 01 | Your First Hosted Agent | Deploy a containerized agent with Microsoft Agent Framework |
| 02 | Tools & File Persistence | `@tool` decorator, per-session sandbox, file persistence |
| 03 | LangGraph Hosted Agent | Same concepts rebuilt with LangGraph via `langchain-azure-ai[hosting]` |
| 04 | Foundry Toolbox | Code Interpreter & File Search via Toolbox MCP endpoint |
| 05 | Guardrails & Content Safety | Prompt Shields, content filtering, blocklists, groundedness |
| 06 | Foundry IQ Knowledge Base | Managed agentic retrieval over blob + search-index sources |
| 07 | Microsoft Web IQ | AI-native web grounding (private preview) |

## Quick start

```bash
git clone https://github.com/beyondelastic/foundry-advanced-workshop.git
cd foundry-advanced-workshop
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
mkdocs serve
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Full setup instructions are in [SETUP.md](SETUP.md).

Workshop site: [beyondelastic.github.io/foundry-advanced-workshop](https://beyondelastic.github.io/foundry-advanced-workshop/)
