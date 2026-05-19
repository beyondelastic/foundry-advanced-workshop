"""Lesson 01 — Your First Hosted Agent.

A minimal hosted agent using Microsoft Agent Framework that answers
healthcare-related questions.
"""

import os

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

load_dotenv()

credential = DefaultAzureCredential()

client = FoundryChatClient(
    project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=credential,
)

agent = Agent(
    client=client,
    instructions=(
        "You are a helpful healthcare assistant. "
        "You answer questions about general health, wellness, and medical terminology. "
        "Always remind the user that your answers are for informational purposes only "
        "and not a substitute for professional medical advice."
    ),
    default_options={"store": False},
)

server = ResponsesHostServer(agent)
server.run()
