"""Cleanup script — removes the knowledge base vector store and registered index."""

import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
INDEX_NAME = "clinical-knowledge-base"


def main():
    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
    oai = project_client.get_openai_client()

    # Delete the registered index
    try:
        project_client.indexes.delete(name=INDEX_NAME, version="1")
        print(f"✓ Index '{INDEX_NAME}' deleted from project.")
    except Exception as e:
        print(f"Index '{INDEX_NAME}' not found or already deleted: {e}")

    # Delete the vector store (this also removes file associations)
    deleted = False
    for store in oai.vector_stores.list():
        if store.name == INDEX_NAME:
            # List and delete files first
            files = oai.vector_stores.files.list(vector_store_id=store.id)
            for f in files:
                oai.files.delete(f.id)
            oai.vector_stores.delete(store.id)
            print(f"✓ Vector store '{INDEX_NAME}' (id={store.id}) and files deleted.")
            deleted = True
            break

    if not deleted:
        print(f"Vector store '{INDEX_NAME}' not found.")


if __name__ == "__main__":
    main()
