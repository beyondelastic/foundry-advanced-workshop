"""Lesson 06 — Foundry IQ: Real Knowledge Base with Agentic Retrieval.

Demonstrates the full lifecycle of a Foundry IQ Knowledge Base — a managed
agentic retrieval service hosted on Azure AI Search that orchestrates:
  • Query planning & decomposition
  • Multi-source retrieval with parallel sub-queries
  • Hybrid search + semantic reranking
  • Answer synthesis with citations

Architecture:
  Azure Blob Storage → Knowledge Source (auto-indexes) → Knowledge Base → MCP endpoint
                                                                          ↕
  Foundry Agent ←─── MCPTool ─────────────────────────────────────────────┘

Phases:
  1. Upload documents to Azure Blob Storage
  2. Create a Blob Knowledge Source on Azure AI Search (triggers auto-indexing)
  3. Create a Knowledge Base referencing the source (with LLM, reasoning, instructions)
  4. Wait for ingestion to complete
  5. Query the Knowledge Base via the Retrieve API
  6. Connect to a Foundry Agent via MCPTool for end-to-end agentic RAG
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    AzureBlobKnowledgeSource,
    AzureBlobKnowledgeSourceParameters,
    AzureOpenAIVectorizerParameters,
    KnowledgeBase,
    KnowledgeBaseAzureOpenAIModel,
    KnowledgeSourceAzureOpenAIVectorizer,
    KnowledgeSourceContentExtractionMode,
    KnowledgeSourceIngestionParameters,
    KnowledgeSourceReference,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchIndexKnowledgeSource,
    SearchIndexKnowledgeSourceParameters,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    AzureOpenAIVectorizer as IndexAzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters as IndexAzureOpenAIVectorizerParameters,
)
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────────────────

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]

# The Foundry account endpoint is the project endpoint without the
# /api/projects/<project> path — derive it instead of requiring a separate var.
# e.g. https://my-resource.services.ai.azure.com/api/projects/my-project
#   →  https://my-resource.services.ai.azure.com/
_parsed = urlparse(PROJECT_ENDPOINT)
FOUNDRY_ENDPOINT = f"{_parsed.scheme}://{_parsed.netloc}/"

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
STORAGE_ACCOUNT_NAME = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
STORAGE_RESOURCE_ID = os.environ["AZURE_STORAGE_RESOURCE_ID"]
MODEL_DEPLOYMENT = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-5-mini")
EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")

# Blob knowledge source (clinical guidelines, drug interactions, patient FAQ)
CONTAINER_NAME = "knowledge-docs"
KNOWLEDGE_SOURCE_BLOB = "clinical-docs-ks"

# Index knowledge source (lab reference ranges — pre-built search index)
LAB_INDEX_NAME = "lab-reference-index"
KNOWLEDGE_SOURCE_INDEX = "lab-reference-ks"

KNOWLEDGE_BASE_NAME = "clinical-kb"
DATA_DIR = Path(__file__).parent / "data"


# ─── Phase 1: Upload Documents to Blob Storage ──────────────────────────────


def upload_documents():
    """Upload markdown documents to the blob container."""
    print("\n┌─ Phase 1: Upload Documents to Blob Storage")

    credential = DefaultAzureCredential()
    account_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
    container = blob_service.get_container_client(CONTAINER_NAME)

    # Ensure container exists
    try:
        container.get_container_properties()
        print(f"│  Container '{CONTAINER_NAME}' exists")
    except Exception:
        container.create_container()
        print(f"│  Created container '{CONTAINER_NAME}'")

    # Upload each document
    data_files = sorted(DATA_DIR.glob("*.md"))
    for filepath in data_files:
        blob_name = filepath.name
        blob_client = container.get_blob_client(blob_name)

        # Check if already uploaded
        try:
            props = blob_client.get_blob_properties()
            if props.size == filepath.stat().st_size:
                print(f"│  ✓ {blob_name} (already uploaded, {props.size:,} bytes)")
                continue
        except Exception:
            pass

        with open(filepath, "rb") as f:
            blob_client.upload_blob(f, overwrite=True)
        print(f"│  ↑ {blob_name} ({filepath.stat().st_size:,} bytes)")

    print("└─ Done\n")


# ─── Phase 1b: Create Search Index for Lab Reference Ranges ─────────────────


def create_lab_index(index_client: SearchIndexClient):
    """Create a search index and populate it with lab reference data.

    Unlike the blob knowledge source (which auto-creates its index), the
    SearchIndexKnowledgeSource points to a pre-existing index. This shows
    the BYOI (bring-your-own-index) pattern for structured data.
    """
    print("┌─ Phase 1b: Create Lab Reference Index")

    # Check if index already has data
    try:
        index_client.get_index(LAB_INDEX_NAME)
        credential = DefaultAzureCredential()
        search_client = SearchClient(
            endpoint=SEARCH_ENDPOINT,
            index_name=LAB_INDEX_NAME,
            credential=credential,
        )
        count = search_client.get_document_count()
        if count > 0:
            print(f"│  Index '{LAB_INDEX_NAME}' exists with {count} documents")
            print("└─ Done\n")
            return
    except Exception:
        pass

    # Define the index schema with vector search + semantic configuration
    fields = [
        SimpleField(name="test_id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="test_name", type=SearchFieldDataType.String),
        SearchableField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="unit", type=SearchFieldDataType.String),
        SimpleField(name="normal_range_low", type=SearchFieldDataType.Double),
        SimpleField(name="normal_range_high", type=SearchFieldDataType.Double),
        SearchableField(name="interpretation", type=SearchFieldDataType.String),
        SearchableField(name="clinical_notes", type=SearchFieldDataType.String),
        # Combined text field for embedding
        SearchableField(name="content", type=SearchFieldDataType.String),
        # Vector field
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072,
            vector_search_profile_name="lab-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="lab-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="lab-vector-profile",
                algorithm_configuration_name="lab-hnsw",
                vectorizer_name="lab-vectorizer",
            )
        ],
        vectorizers=[
            IndexAzureOpenAIVectorizer(
                vectorizer_name="lab-vectorizer",
                parameters=IndexAzureOpenAIVectorizerParameters(
                    resource_url=FOUNDRY_ENDPOINT,
                    deployment_name=EMBEDDING_DEPLOYMENT,
                    model_name="text-embedding-3-large",
                ),
            )
        ],
    )

    semantic_config = SemanticConfiguration(
        name="lab-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="test_name"),
            content_fields=[
                SemanticField(field_name="content"),
                SemanticField(field_name="clinical_notes"),
            ],
            keywords_fields=[SemanticField(field_name="category")],
        ),
    )

    index = SearchIndex(
        name=LAB_INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=SemanticSearch(
            default_configuration_name="lab-semantic-config",
            configurations=[semantic_config],
        ),
    )

    print(f"│  Creating index '{LAB_INDEX_NAME}'...")
    index_client.create_or_update_index(index)
    print(f"│  ✓ Index created with vector search + semantic config")

    # Load and prepare documents
    lab_data = json.loads((DATA_DIR / "lab-reference-ranges.json").read_text())

    documents = []
    for item in lab_data:
        # Combine fields into a rich content field for embedding + search
        content = (
            f"{item['test_name']} ({item['test_id']}). "
            f"Category: {item['category']}. "
            f"Unit: {item['unit']}. "
            f"{item['interpretation']} "
            f"{item['clinical_notes']}"
        )
        doc = {
            "test_id": item["test_id"],
            "test_name": item["test_name"],
            "category": item["category"],
            "unit": item["unit"] or "",
            "normal_range_low": item.get("normal_range_low"),
            "normal_range_high": item.get("normal_range_high"),
            "interpretation": item["interpretation"],
            "clinical_notes": item["clinical_notes"],
            "content": content,
        }
        documents.append(doc)

    # Generate embeddings via the Foundry endpoint
    print(f"│  Generating embeddings for {len(documents)} lab tests...")
    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token
    embed_url = f"{FOUNDRY_ENDPOINT}openai/deployments/{EMBEDDING_DEPLOYMENT}/embeddings?api-version=2024-06-01"

    contents = [doc["content"] for doc in documents]
    embed_response = httpx.post(
        embed_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"input": contents},
        timeout=30,
    )
    embed_response.raise_for_status()
    embeddings = embed_response.json()["data"]

    for doc, emb in zip(documents, embeddings):
        doc["content_vector"] = emb["embedding"]

    # Upload documents to the index
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=LAB_INDEX_NAME,
        credential=credential,
    )
    result = search_client.upload_documents(documents)
    succeeded = sum(1 for r in result if r.succeeded)
    print(f"│  ✓ Uploaded {succeeded}/{len(documents)} documents")
    print("└─ Done\n")


# ─── Phase 2: Create Knowledge Sources ──────────────────────────────────────


def create_knowledge_source(index_client: SearchIndexClient):
    """Create a Blob Knowledge Source on Azure AI Search.

    This triggers automatic creation of: data source, skillset, indexer, and index.
    The embedding model vectorizes content; the chat model handles image verbalization.
    """
    print("┌─ Phase 2a: Create Blob Knowledge Source")

    # Check if already exists
    try:
        existing = index_client.get_knowledge_source(KNOWLEDGE_SOURCE_BLOB)
        print(f"│  Knowledge source '{existing.name}' already exists (kind={existing.kind})")
        print("└─ Done\n")
        return
    except Exception:
        pass

    # Model parameters for embedding (vectorization during indexing + query time)
    embedding_params = AzureOpenAIVectorizerParameters(
        resource_url=FOUNDRY_ENDPOINT,
        deployment_name=EMBEDDING_DEPLOYMENT,
        model_name="text-embedding-3-large",
    )

    # Build the knowledge source — uses resource ID for managed identity auth
    # Format: "ResourceId=/subscriptions/.../storageAccounts/{name};"
    blob_connection = f"ResourceId={STORAGE_RESOURCE_ID};"

    knowledge_source = AzureBlobKnowledgeSource(
        name=KNOWLEDGE_SOURCE_BLOB,
        description=(
            "Clinical knowledge documents including treatment guidelines, "
            "drug interaction references, and patient FAQ sheets."
        ),
        azure_blob_parameters=AzureBlobKnowledgeSourceParameters(
            connection_string=blob_connection,
            container_name=CONTAINER_NAME,
            is_adls_gen2=False,
            ingestion_parameters=KnowledgeSourceIngestionParameters(
                disable_image_verbalization=True,
                embedding_model=KnowledgeSourceAzureOpenAIVectorizer(
                    azure_open_ai_parameters=embedding_params,
                ),
                content_extraction_mode=KnowledgeSourceContentExtractionMode.MINIMAL,
            ),
        ),
    )

    print(f"│  Creating knowledge source '{KNOWLEDGE_SOURCE_BLOB}'...")
    index_client.create_or_update_knowledge_source(knowledge_source)
    print(f"│  ✓ Knowledge source created — auto-indexing pipeline started")
    print("└─ Done\n")


def create_index_knowledge_source(index_client: SearchIndexClient):
    """Create an Index Knowledge Source pointing at the lab reference index.

    Unlike the blob source (which auto-creates its own index), this source
    references a pre-existing search index — the BYOI pattern.
    """
    print("┌─ Phase 2b: Create Index Knowledge Source")

    # Check if already exists
    try:
        existing = index_client.get_knowledge_source(KNOWLEDGE_SOURCE_INDEX)
        print(f"│  Knowledge source '{existing.name}' already exists (kind={existing.kind})")
        print("└─ Done\n")
        return
    except Exception:
        pass

    knowledge_source = SearchIndexKnowledgeSource(
        name=KNOWLEDGE_SOURCE_INDEX,
        description=(
            "Lab reference ranges including normal values, interpretation guidance, "
            "and drug-related effects on lab results (e.g. ACE inhibitors raising "
            "creatinine, lithium monitoring thresholds)."
        ),
        search_index_parameters=SearchIndexKnowledgeSourceParameters(
            search_index_name=LAB_INDEX_NAME,
            semantic_configuration_name="lab-semantic-config",
        ),
    )

    print(f"│  Creating knowledge source '{KNOWLEDGE_SOURCE_INDEX}'...")
    print(f"│    → Points to index: {LAB_INDEX_NAME}")
    index_client.create_or_update_knowledge_source(knowledge_source)
    print(f"│  ✓ Index knowledge source created")
    print("└─ Done\n")


# ─── Phase 3: Create Knowledge Base ─────────────────────────────────────────


def create_knowledge_base(index_client: SearchIndexClient):
    """Create a Knowledge Base that references the knowledge source.

    The KB configures:
    - retrieval_instructions: how to route queries across sources
    - answer_instructions: how to format synthesized answers
    - output_mode: answerSynthesis (LLM generates a cited answer)
    - models: which LLM to use for planning and synthesis
    """
    print("┌─ Phase 3: Create Knowledge Base")

    # Check if already exists
    try:
        existing = index_client.get_knowledge_base(KNOWLEDGE_BASE_NAME)
        print(f"│  Knowledge base '{existing.name}' already exists")
        print("└─ Done\n")
        return
    except Exception:
        pass

    # LLM for query planning and answer synthesis
    kb_model_params = AzureOpenAIVectorizerParameters(
        resource_url=FOUNDRY_ENDPOINT,
        deployment_name=MODEL_DEPLOYMENT,
        model_name=MODEL_DEPLOYMENT,
    )

    knowledge_base = KnowledgeBase(
        name=KNOWLEDGE_BASE_NAME,
        description=(
            "Clinical decision-support knowledge base covering treatment guidelines, "
            "drug interactions, patient education materials, and lab reference ranges."
        ),
        retrieval_instructions=(
            "This knowledge base has two knowledge sources:\n\n"
            "SOURCE 1 — clinical-docs-ks (Azure Blob, unstructured documents):\n"
            "  • Clinical practice guidelines (treatment protocols, BP/HbA1c targets, monitoring)\n"
            "  • Drug interaction references (contraindications, dose adjustments, severity)\n"
            "  • Patient FAQ sheets (lifestyle advice, patient-facing explanations)\n\n"
            "SOURCE 2 — lab-reference-ks (Search Index, structured data):\n"
            "  • Lab test reference ranges (normal values, units, critical thresholds)\n"
            "  • Lab interpretation guidance (what abnormal results mean)\n"
            "  • Drug effects on lab values (e.g. ACE inhibitors raising creatinine)\n\n"
            "ROUTING:\n"
            "  • For treatment protocols and targets → prefer clinical-docs-ks\n"
            "  • For drug interactions and safety → prefer clinical-docs-ks\n"
            "  • For lab reference ranges and interpretation → prefer lab-reference-ks\n"
            "  • For questions combining drugs and lab monitoring → query BOTH sources\n"
            "  • For patient questions about their lab results → query BOTH sources"
        ),
        answer_instructions=(
            "Provide a clear, evidence-based answer. Structure your response with:\n"
            "- A direct answer to the question\n"
            "- Supporting evidence from the retrieved documents\n"
            "- Source attribution (which document the information came from)\n"
            "- A reminder that this is for informational purposes only"
        ),
        output_mode="answerSynthesis",
        knowledge_sources=[
            KnowledgeSourceReference(name=KNOWLEDGE_SOURCE_BLOB),
            KnowledgeSourceReference(name=KNOWLEDGE_SOURCE_INDEX),
        ],
        models=[KnowledgeBaseAzureOpenAIModel(azure_open_ai_parameters=kb_model_params)],
    )

    print(f"│  Creating knowledge base '{KNOWLEDGE_BASE_NAME}'...")
    index_client.create_or_update_knowledge_base(knowledge_base)
    print(f"│  ✓ Knowledge base created")
    print(f"│    • Output mode: answerSynthesis")
    print(f"│    • Model: {MODEL_DEPLOYMENT}")
    print(f"│    • Sources: {KNOWLEDGE_SOURCE_BLOB}, {KNOWLEDGE_SOURCE_INDEX}")
    print("└─ Done\n")


# ─── Phase 4: Wait for Ingestion ─────────────────────────────────────────────


def wait_for_ingestion(index_client: SearchIndexClient, timeout_minutes: int = 10):
    """Poll the blob knowledge source status until ingestion completes.

    Only the blob source needs polling — the index source is already populated.
    """
    print("┌─ Phase 4: Wait for Ingestion")
    print(f"│  Checking status of '{KNOWLEDGE_SOURCE_BLOB}'...")

    deadline = time.time() + (timeout_minutes * 60)
    last_status = None

    while time.time() < deadline:
        try:
            status = index_client.get_knowledge_source_status(KNOWLEDGE_SOURCE_BLOB)
            status_dict = status.as_dict()
            sync_status = status_dict.get("synchronization_status", "unknown")

            if sync_status != last_status:
                print(f"│  Status: {sync_status}")
                last_status = sync_status

            # Check if there's a completed last sync (means ingestion finished at least once)
            last_state = status_dict.get("last_synchronization_state", {})
            if last_state and last_state.get("end_time"):
                items_processed = last_state.get("items_updates_processed", 0)
                items_failed = last_state.get("items_updates_failed", 0)
                final_status = last_state.get("status", sync_status)
                print(f"│  ✓ Ingestion complete: {final_status}")
                print(f"│    • Items processed: {items_processed}")
                if items_failed:
                    print(f"│    ⚠ Items failed: {items_failed}")
                print("└─ Done\n")
                return True

            # If there's an active sync in progress, show progress
            current_state = status_dict.get("current_synchronization_state", {})
            if current_state:
                items = current_state.get("item_updates_processed", "?")
                print(f"│  Indexing in progress... (items processed: {items})")

        except Exception as e:
            print(f"│  (status check error: {e})")

        time.sleep(10)

    print(f"│  ⚠ Timed out after {timeout_minutes} minutes — ingestion may still be running")
    print("└─ Done\n")
    return False


# ─── Phase 5: Query the Knowledge Base ───────────────────────────────────────


def query_knowledge_base(question: str):
    """Query the Knowledge Base via the Retrieve REST API."""
    print(f"\n{'─'*70}")
    print(f"  QUESTION: {question}")
    print(f"{'─'*70}")

    credential = DefaultAzureCredential()
    token = credential.get_token("https://search.azure.com/.default").token

    url = (
        f"{SEARCH_ENDPOINT}/knowledgebases/{KNOWLEDGE_BASE_NAME}/retrieve"
        f"?api-version=2026-05-01-preview"
    )

    # The retrieve API expects messages in OpenAI chat-completion format
    body = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": question}]}
        ]
    }

    response = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=60,
    )

    if response.status_code == 200:
        data = response.json()

        # Display synthesized answer
        for resp_item in data.get("response", []):
            for content_block in resp_item.get("content", []):
                if content_block.get("type") == "text":
                    print(f"\n  ANSWER:\n")
                    for line in content_block["text"].split("\n"):
                        print(f"  {line}")

        # Display activity (query planning, search, synthesis)
        activity = data.get("activity", [])
        if activity:
            print(f"\n  ⚙ Activity pipeline:")
            for step in activity:
                step_type = step.get("type", "unknown")
                elapsed = step.get("elapsedMs", 0)
                if step_type == "modelQueryPlanning":
                    print(f"    1. Query planning ({elapsed}ms, {step.get('outputTokens', 0)} tokens)")
                elif step_type == "azureBlob":
                    count = step.get("count", 0)
                    ks_name = step.get("knowledgeSourceName", "")
                    search_q = step.get("azureBlobArguments", {}).get("search", "")
                    print(f"    2. Search '{ks_name}' → {count} results ({elapsed}ms)")
                    if search_q:
                        print(f"       Query: \"{search_q}\"")
                elif step_type == "modelAnswerSynthesis":
                    print(f"    3. Answer synthesis ({elapsed}ms, {step.get('outputTokens', 0)} tokens)")

        # Display references
        references = data.get("references", [])
        if references:
            print(f"\n  📎 References ({len(references)} chunks):")
            for ref in references[:5]:
                blob_url = ref.get("blobUrl", "")
                score = ref.get("rerankerScore", 0)
                filename = blob_url.split("/")[-1] if blob_url else ref.get("id", "?")
                print(f"    • {filename} (reranker score={score:.3f})")
    else:
        print(f"  Error {response.status_code}: {response.text[:300]}")


# ─── Phase 6: Connect to Foundry Agent via MCP ───────────────────────────────


def demo_agent_with_mcp():
    """Use the Responses API with the Knowledge Base's MCP endpoint.

    The Knowledge Base exposes an MCP endpoint:
      {search_endpoint}/knowledgebases/{name}/mcp?api-version=2026-05-01-preview

    The model connects via the MCP tool type and calls 'knowledge_base_retrieve'
    automatically when it needs information from the KB.
    """
    print("\n┌─ Phase 6: Agent Integration via MCP")

    from azure.ai.projects import AIProjectClient

    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)
    oai = project_client.get_openai_client()

    # The MCP endpoint for the knowledge base
    mcp_url = (
        f"{SEARCH_ENDPOINT}/knowledgebases/{KNOWLEDGE_BASE_NAME}"
        f"/mcp?api-version=2026-05-01-preview"
    )

    # Get a token for AI Search so the model can authenticate to the MCP endpoint
    search_token = credential.get_token("https://search.azure.com/.default").token

    print(f"│  MCP endpoint: {mcp_url}")
    print(f"│  Using Responses API with MCP tool...")

    question = "What are the drug interactions for amlodipine with NSAIDs?"
    print(f"│  Question: {question}")

    response = oai.responses.create(
        model=MODEL_DEPLOYMENT,
        input=question,
        tools=[{
            "type": "mcp",
            "server_label": "clinical-kb",
            "server_url": mcp_url,
            "require_approval": "never",
            "headers": {"Authorization": f"Bearer {search_token}"},
        }],
        instructions=(
            "You are a clinical decision-support assistant. Use the knowledge_base_retrieve "
            "tool to find information from the clinical knowledge base. Always cite sources "
            "and remind users this is for informational purposes only."
        ),
    )

    print(f"│  Status: {response.status}")

    # Show tool calls the model made
    for item in response.output:
        if item.type == "mcp_list_tools":
            print(f"│  ⚙ Discovered MCP tools from KB endpoint")
        elif item.type == "mcp_call":
            print(f"│  ⚙ Called: {item.name}")
        elif item.type == "message":
            print(f"│")
            print(f"│  AGENT RESPONSE:")
            for block in item.content:
                if hasattr(block, "text"):
                    for line in block.text.split("\n"):
                        print(f"│  {line}")

    print("└─ Done\n")


# ─── Entry Point ─────────────────────────────────────────────────────────────


def main():
    """Full Knowledge Base lifecycle demo."""
    credential = DefaultAzureCredential()
    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)

    print("=" * 70)
    print("  Lesson 06 — Foundry IQ: Knowledge Base with Agentic Retrieval")
    print("=" * 70)

    # Phase 1: Upload documents to blob storage
    upload_documents()

    # Phase 1b: Create search index for lab reference data (BYOI pattern)
    create_lab_index(index_client)

    # Phase 2a: Create blob knowledge source (triggers auto-indexing)
    create_knowledge_source(index_client)

    # Phase 2b: Create index knowledge source (points to pre-existing index)
    create_index_knowledge_source(index_client)

    # Phase 3: Create knowledge base referencing both sources
    create_knowledge_base(index_client)

    # Phase 4: Wait for blob ingestion (index source is already populated)
    ingestion_complete = wait_for_ingestion(index_client)

    if not ingestion_complete:
        print("⚠ Ingestion not yet complete. You can re-run later to query.")
        print("  The knowledge source is indexing in the background.")
        return

    # Phase 5: Query the knowledge base
    queries = [
        # Query hitting blob source (clinical guidelines)
        "What are the HbA1c targets for type 2 diabetes management?",
        # Query hitting index source (lab reference ranges)
        "What is the normal range for serum potassium, and what drugs affect it?",
        # Cross-source query: drug interactions (blob) + lab monitoring (index)
        (
            "A patient on ramipril is starting lithium. What drug interactions "
            "should I watch for, and which lab tests need monitoring?"
        ),
    ]

    for question in queries:
        query_knowledge_base(question)

    # Phase 6: Agent integration via MCP (requires project endpoint)
    if os.environ.get("AZURE_AI_PROJECT_ENDPOINT"):
        demo_agent_with_mcp()
    else:
        print("\n┌─ Phase 6: Agent Integration via MCP (skipped)")
        print("│  Set AZURE_AI_PROJECT_ENDPOINT in .env to enable agent demo")
        print("└─ Done\n")

    print("=" * 70)
    print("  Demo complete.")
    print(f"  Knowledge Base: {KNOWLEDGE_BASE_NAME}")
    print(f"  Knowledge Sources: {KNOWLEDGE_SOURCE_BLOB}, {KNOWLEDGE_SOURCE_INDEX}")
    print(f"  Search endpoint: {SEARCH_ENDPOINT}")
    print(f"\n  To clean up: python cleanup.py")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--query":
        # Custom query: python main.py --query "your question here"
        question = " ".join(sys.argv[2:])
        query_knowledge_base(question)
    else:
        main()
