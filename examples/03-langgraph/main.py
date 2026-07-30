"""Lesson 03 — LangGraph Hosted Agent.

A hosted agent built with LangGraph instead of Microsoft Agent Framework.
Uses the supported ``langchain-azure-ai[hosting]`` package: you build a
compiled LangGraph graph and ``ResponsesHostServer`` handles all the Responses
protocol plumbing (history, threading, streaming) — no hand-written adapter.
"""

import json
import os
from typing import Annotated, Any

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from langchain_azure_ai.agents.hosting import ResponsesHostServer
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import Field
from typing_extensions import TypedDict

load_dotenv()

credential = DefaultAzureCredential()

# ---------------------------------------------------------------------------
# Tools (same healthcare domain as Lesson 02)
# ---------------------------------------------------------------------------


@tool
def lookup_patient_record(
    patient_id: Annotated[str, Field(description="Patient ID, e.g. P-1001")],
) -> str:
    """Look up a patient record by ID."""
    records = {
        "P-1001": {
            "name": "Alice Johnson",
            "age": 34,
            "blood_type": "A+",
            "conditions": ["asthma"],
        },
        "P-1002": {
            "name": "Bob Martinez",
            "age": 58,
            "blood_type": "O-",
            "conditions": ["type 2 diabetes", "hypertension"],
        },
    }
    record = records.get(patient_id)
    if record is None:
        return f"No patient found with ID {patient_id}."
    return json.dumps(record, indent=2)


@tool
def calculate_bmi(
    weight_kg: Annotated[float, Field(description="Weight in kilograms")],
    height_m: Annotated[float, Field(description="Height in metres")],
) -> str:
    """Calculate Body Mass Index (BMI) from weight and height."""
    if height_m <= 0:
        return "Height must be greater than zero."
    bmi = weight_kg / (height_m ** 2)
    category = (
        "underweight" if bmi < 18.5
        else "normal weight" if bmi < 25
        else "overweight" if bmi < 30
        else "obese"
    )
    return f"BMI: {bmi:.1f} ({category})"


tools = [lookup_patient_record, calculate_bmi]

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

llm = AzureAIOpenAIApiChatModel(
    project_endpoint=os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=credential,
).bind_tools(tools)

# ---------------------------------------------------------------------------
# LangGraph state and graph
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a helpful healthcare assistant. "
    "You can look up patient records and calculate BMI. "
    "Always remind the user your answers are informational only."
)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def chatbot(state: AgentState) -> dict[str, Any]:
    """Call the LLM with the current message history."""
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """Route to tools if the last message has tool calls, otherwise end."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


# Build the graph
graph_builder = StateGraph(AgentState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools))

graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", should_continue, {"tools": "tools", END: END})
graph_builder.add_edge("tools", "chatbot")

graph = graph_builder.compile()

# ---------------------------------------------------------------------------
# Responses API host
# ---------------------------------------------------------------------------
# ResponsesHostServer (from langchain-azure-ai[hosting]) takes the compiled
# graph directly and handles Responses history, threading, and streaming.
# The old hand-written request/response adapter is no longer needed.

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8088"))
    ResponsesHostServer(graph).run(port=port)
