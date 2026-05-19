"""Lesson 02 — Hosted Agent with Tools & File Persistence.

Extends the healthcare agent with custom tools (@tool decorator) and
demonstrates per-session file persistence on the hosted agent sandbox.
"""

import json
import os
from datetime import datetime
from typing import Annotated

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from pydantic import Field

from agent_framework import Agent, tool
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
# Custom tools
# ---------------------------------------------------------------------------


@tool(approval_mode="never_require")
def lookup_patient_record(
    patient_id: Annotated[str, Field(description="The patient identifier, e.g., P-1001")],
) -> str:
    """Look up a patient record by ID. Returns basic demographics and vitals."""
    records = {
        "P-1001": {
            "name": "Alice Johnson",
            "age": 34,
            "blood_type": "A+",
            "last_visit": "2025-06-10",
            "conditions": ["asthma"],
        },
        "P-1002": {
            "name": "Bob Martinez",
            "age": 58,
            "blood_type": "O-",
            "last_visit": "2025-07-22",
            "conditions": ["type 2 diabetes", "hypertension"],
        },
        "P-1003": {
            "name": "Carol Lee",
            "age": 45,
            "blood_type": "B+",
            "last_visit": "2025-08-05",
            "conditions": [],
        },
    }
    record = records.get(patient_id)
    if record is None:
        return f"No patient found with ID {patient_id}."
    return json.dumps(record, indent=2)


@tool(approval_mode="never_require")
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


@tool(approval_mode="never_require")
def save_session_note(
    note: Annotated[str, Field(description="The note text to save")],
) -> str:
    """Save a note to the per-session sandbox filesystem.

    Files saved here persist for the lifetime of the session but are
    isolated from other sessions.
    """
    notes_dir = "/mnt/user/notes"
    os.makedirs(notes_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(notes_dir, f"note_{timestamp}.txt")
    with open(filepath, "w") as f:
        f.write(note)
    return f"Note saved to {filepath}"


@tool(approval_mode="never_require")
def list_session_notes() -> str:
    """List all notes saved in the current session."""
    notes_dir = "/mnt/user/notes"
    if not os.path.exists(notes_dir):
        return "No notes found."
    files = sorted(os.listdir(notes_dir))
    if not files:
        return "No notes found."
    results = []
    for fname in files:
        filepath = os.path.join(notes_dir, fname)
        with open(filepath, "r") as f:
            content = f.read()
        results.append(f"--- {fname} ---\n{content}")
    return "\n\n".join(results)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = Agent(
    client=client,
    instructions=(
        "You are a healthcare assistant with access to patient records and health tools. "
        "Use the lookup_patient_record tool when asked about a patient. "
        "Use calculate_bmi when asked about BMI. "
        "Use save_session_note and list_session_notes to manage session notes. "
        "Always remind the user your answers are informational only."
    ),
    tools=[lookup_patient_record, calculate_bmi, save_session_note, list_session_notes],
    default_options={"store": False},
)

server = ResponsesHostServer(agent)
server.run()
