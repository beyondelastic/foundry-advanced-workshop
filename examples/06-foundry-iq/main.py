"""Lesson 06 — FoundryIQ: Multi-Source Knowledge Retrieval.

Demonstrates creating a managed knowledge index (FoundryIQ) with multiple
document sources and using it for retrieval-augmented generation via the
Responses API.

The script:
1. Uploads multiple knowledge documents to a vector store
2. Registers the vector store as a ManagedAzureAISearchIndex
3. Queries the agent with questions that span multiple sources
4. Shows retrieval citations and source attribution
"""

import os
import sys
import time
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ManagedAzureAISearchIndex
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")
INDEX_NAME = "clinical-knowledge-base"
DATA_DIR = Path(__file__).parent / "data"

SYSTEM_INSTRUCTIONS = """You are a clinical decision-support assistant with access to a knowledge base
containing clinical guidelines, drug interaction data, and patient FAQ documents.

When answering questions:
1. Search the knowledge base for relevant information
2. Cite which source document the information comes from
3. If the question spans multiple topics (e.g., drug interactions for a guideline-recommended drug),
   synthesize information from multiple sources
4. If information is not in the knowledge base, say so clearly
5. Always remind users that this is for informational purposes only

Format your response clearly with headers and bullet points where appropriate."""


# --- Knowledge Base Setup ---


def create_knowledge_base(oai_client) -> str:
    """Create a vector store with multiple knowledge sources and return its ID."""

    # Check if vector store already exists
    existing_stores = oai_client.vector_stores.list()
    for store in existing_stores:
        if store.name == INDEX_NAME:
            print(f"  Vector store '{INDEX_NAME}' already exists (id={store.id})")
            print(f"  Files: {store.file_counts.completed} completed, {store.file_counts.total} total")
            return store.id

    # Create new vector store
    print(f"  Creating vector store '{INDEX_NAME}'...")
    vector_store = oai_client.vector_stores.create(name=INDEX_NAME)
    print(f"  Created: id={vector_store.id}")

    # Upload each document
    data_files = sorted(DATA_DIR.glob("*.md"))
    print(f"  Uploading {len(data_files)} documents...")

    for filepath in data_files:
        print(f"    ↳ {filepath.name} ({filepath.stat().st_size:,} bytes)")
        with open(filepath, "rb") as f:
            file_obj = oai_client.files.create(file=f, purpose="assistants")

        # Attach to vector store
        oai_client.vector_stores.files.create(
            vector_store_id=vector_store.id,
            file_id=file_obj.id,
        )

    # Wait for indexing to complete
    print("  Waiting for indexing to complete...")
    while True:
        store = oai_client.vector_stores.retrieve(vector_store.id)
        if store.file_counts.in_progress == 0:
            break
        time.sleep(2)

    print(f"  ✓ Indexing complete: {store.file_counts.completed} files indexed")
    return vector_store.id


def register_index(project_client: AIProjectClient, vector_store_id: str):
    """Register the vector store as a ManagedAzureAISearchIndex in the project."""
    try:
        existing = project_client.indexes.get(name=INDEX_NAME, version="1")
        print(f"  Index '{INDEX_NAME}' already registered (id={existing.id})")
        return
    except Exception:
        pass

    print(f"  Registering index '{INDEX_NAME}' in project...")
    index = project_client.indexes.create_or_update(
        name=INDEX_NAME,
        version="1",
        index=ManagedAzureAISearchIndex(
            name=INDEX_NAME,
            version="1",
            vector_store_id=vector_store_id,
            description="Multi-source clinical knowledge base: guidelines, drug interactions, patient FAQ",
        ),
    )
    print(f"  ✓ Index registered: {index.name} v{index.version}")


# --- Agent Query ---


def query_knowledge_base(oai_client, vector_store_id: str, question: str):
    """Ask a question using file_search over the knowledge base."""
    print(f"\n{'='*60}")
    print(f"QUESTION: {question}")
    print(f"{'='*60}")

    response = oai_client.responses.create(
        model=MODEL,
        instructions=SYSTEM_INSTRUCTIONS,
        input=question,
        tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
    )

    # Extract and display results
    for item in response.output:
        if hasattr(item, "type") and item.type == "file_search_call":
            queries = item.queries if hasattr(item, "queries") else []
            print(f"\n  [Search queries: {queries}]")
            if hasattr(item, "results") and item.results:
                print(f"  [Results: {len(item.results)} chunks retrieved]")
                for r in item.results[:3]:
                    print(f"    • {r.filename} (score={r.score:.3f})")

        elif hasattr(item, "content"):
            for block in item.content:
                if hasattr(block, "text"):
                    print(f"\nANSWER:\n{block.text}")

                    # Show file citations if any
                    if hasattr(block, "annotations") and block.annotations:
                        print("\n  📎 Citations:")
                        seen = set()
                        for ann in block.annotations:
                            if hasattr(ann, "filename") and ann.filename not in seen:
                                print(f"    • {ann.filename}")
                                seen.add(ann.filename)


# --- Entry Point ---


def main():
    """Set up the knowledge base and run demo queries."""
    credential = DefaultAzureCredential()

    project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
    oai = project_client.get_openai_client()

    # Step 1: Create/verify the knowledge base
    print("Setting up knowledge base...")
    vector_store_id = create_knowledge_base(oai)

    # Step 2: Register as a project index
    register_index(project_client, vector_store_id)

    # Step 3: Run demo queries that exercise multi-source retrieval
    queries = [
        # Single-source: clinical guidelines
        "What are the HbA1c targets for type 2 diabetes management?",
        # Single-source: drug interactions
        "What are the important drug interactions for amlodipine?",
        # Cross-source: guidelines + drug interactions
        "I'm prescribing ramipril for a hypertensive patient who is also on lithium. "
        "What is the recommended blood pressure target, and are there any drug interactions I should be aware of?",
        # Cross-source: guidelines + patient FAQ
        "A patient on amlodipine is asking about ankle swelling and whether they can take "
        "ibuprofen for the discomfort. What should I advise?",
    ]

    for question in queries:
        query_knowledge_base(oai, vector_store_id, question)

    print(f"\n{'='*60}")
    print("Demo complete.")
    print(f"\nKnowledge base: '{INDEX_NAME}' (vector_store_id={vector_store_id})")
    print("To clean up: python cleanup.py")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Allow custom query
        credential = DefaultAzureCredential()
        project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
        oai = project_client.get_openai_client()

        # Find existing vector store
        for store in oai.vector_stores.list():
            if store.name == INDEX_NAME:
                query_knowledge_base(oai, store.id, " ".join(sys.argv[1:]))
                break
        else:
            print(f"Knowledge base '{INDEX_NAME}' not found. Run 'python main.py' first to set it up.")
    else:
        main()
