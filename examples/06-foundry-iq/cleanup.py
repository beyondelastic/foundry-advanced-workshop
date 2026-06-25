"""Cleanup script — removes Knowledge Base, Knowledge Sources, index, and blob data."""

import os

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
STORAGE_ACCOUNT_NAME = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
CONTAINER_NAME = "knowledge-docs"
KNOWLEDGE_SOURCE_BLOB = "clinical-docs-ks"
KNOWLEDGE_SOURCE_INDEX = "lab-reference-ks"
LAB_INDEX_NAME = "lab-reference-index"
KNOWLEDGE_BASE_NAME = "clinical-kb"


def main():
    credential = DefaultAzureCredential()
    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)

    # 1. Delete the knowledge base (must be deleted before knowledge sources)
    try:
        index_client.delete_knowledge_base(KNOWLEDGE_BASE_NAME)
        print(f"✓ Knowledge base '{KNOWLEDGE_BASE_NAME}' deleted.")
    except Exception as e:
        print(f"  Knowledge base '{KNOWLEDGE_BASE_NAME}' not found or already deleted: {e}")

    # 2. Delete both knowledge sources
    for ks_name in [KNOWLEDGE_SOURCE_BLOB, KNOWLEDGE_SOURCE_INDEX]:
        try:
            index_client.delete_knowledge_source(ks_name)
            print(f"✓ Knowledge source '{ks_name}' deleted.")
        except Exception as e:
            print(f"  Knowledge source '{ks_name}' not found or already deleted: {e}")

    # 3. Delete the lab reference index (created manually, not auto-managed)
    try:
        index_client.delete_index(LAB_INDEX_NAME)
        print(f"✓ Search index '{LAB_INDEX_NAME}' deleted.")
    except Exception as e:
        print(f"  Search index '{LAB_INDEX_NAME}' not found or already deleted: {e}")

    # 4. Delete blobs from the container
    try:
        account_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        blob_service = BlobServiceClient(account_url=account_url, credential=credential)
        container = blob_service.get_container_client(CONTAINER_NAME)
        blobs = list(container.list_blobs())
        for blob in blobs:
            container.delete_blob(blob.name)
        print(f"✓ Deleted {len(blobs)} blobs from container '{CONTAINER_NAME}'.")
    except Exception as e:
        print(f"  Blob cleanup error: {e}")

    print("\nCleanup complete.")


if __name__ == "__main__":
    main()
