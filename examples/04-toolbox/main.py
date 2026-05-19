"""Lesson 04 — Foundry Toolbox.

Demonstrates connecting a hosted agent to a Foundry Toolbox for
Code Interpreter and Web Search via MCP (Streamable HTTP).
"""

import os
from typing import Annotated

import httpx
from azure.identity import DefaultAzureCredential
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


# ---------------------------------------------------------------------------
# Toolbox authentication
# ---------------------------------------------------------------------------


class ToolboxAuth(httpx.Auth):
    """Injects a bearer token into requests to the Toolbox MCP endpoint."""

    def __init__(self, credential: DefaultAzureCredential) -> None:
        self._credential = credential

    def auth_flow(self, request: httpx.Request):
        token = self._credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        request.headers["Authorization"] = f"Bearer {token.token}"
        yield request


# ---------------------------------------------------------------------------
# Toolbox MCP endpoint
# ---------------------------------------------------------------------------


def resolve_toolbox_endpoint() -> str:
    """Build the Toolbox MCP endpoint URL from environment variables."""
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"].rstrip("/")
    toolbox_name = os.environ["TOOLBOX_NAME"]
    return f"{project_endpoint}/toolboxes/{toolbox_name}/mcp"


auth = ToolboxAuth(credential)
http_client = httpx.AsyncClient(auth=auth, timeout=120)

toolbox = MCPStreamableHTTPTool(
    name="foundry_toolbox",
    url=resolve_toolbox_endpoint(),
    http_client=http_client,
    load_prompts=False,
)


# ---------------------------------------------------------------------------
# Local tool (to show mixing local + Toolbox tools)
# ---------------------------------------------------------------------------


@tool(approval_mode="never_require")
def summarize_findings(
    findings: Annotated[str, Field(description="The findings text to summarize")],
) -> str:
    """Summarize a set of findings into a concise bullet list."""
    return f"Summary of findings:\n{findings}"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


async def main() -> None:
    """Start the agent with both local and Toolbox tools."""
    agent = Agent(
        client=client,
        instructions=(
            "You are a healthcare research assistant with access to a Foundry Toolbox. "
            "Use the Code Interpreter tool to run Python code for data analysis and visualization. "
            "Use the Web Search tool to find recent medical research and guidelines. "
            "Use the summarize_findings tool to compile your results. "
            "Always cite sources and remind the user your answers are informational only."
        ),
        tools=[summarize_findings, toolbox],
        default_options={"store": False},
    )

    async with agent:
        server = ResponsesHostServer(agent)
        server.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
