"""Cleanup script — removes the blocklist created by the guardrails demo."""

import os

from azure.ai.contentsafety import BlocklistClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
ACCOUNT_ENDPOINT = PROJECT_ENDPOINT.split("/api/projects")[0]
BLOCKLIST_NAME = "healthcare-prohibited"


def main():
    credential = DefaultAzureCredential()
    client = BlocklistClient(endpoint=ACCOUNT_ENDPOINT, credential=credential)

    try:
        client.delete_text_blocklist(blocklist_name=BLOCKLIST_NAME)
        print(f"✓ Blocklist '{BLOCKLIST_NAME}' deleted.")
    except Exception as e:
        print(f"Blocklist '{BLOCKLIST_NAME}' not found or already deleted: {e}")


if __name__ == "__main__":
    main()
