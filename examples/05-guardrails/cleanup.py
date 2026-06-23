"""Cleanup script — removes the blocklist created by the guardrails demo."""

import os
import re

import httpx
from azure.ai.contentsafety import BlocklistClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
ACCOUNT_ENDPOINT = PROJECT_ENDPOINT.split("/api/projects")[0]
BLOCKLIST_NAME = "healthcare-prohibited"


def _delete_arm_blocklist(credential):
    """Delete blocklist from ARM API (Foundry portal)."""
    token = credential.get_token("https://management.azure.com/.default").token
    headers = {"Authorization": f"Bearer {token}"}

    account_name = re.match(r"https://([^.]+)\.services", ACCOUNT_ENDPOINT).group(1)

    # Find the ARM resource ID
    r = httpx.get(
        "https://management.azure.com/subscriptions?api-version=2022-01-01",
        headers=headers,
    )
    for sub in r.json().get("value", []):
        sub_id = sub["subscriptionId"]
        r2 = httpx.get(
            f"https://management.azure.com/subscriptions/{sub_id}/providers/"
            f"Microsoft.CognitiveServices/accounts?api-version=2024-10-01",
            headers=headers,
        )
        for acct in r2.json().get("value", []):
            if acct["name"] == account_name:
                resource_id = acct["id"]
                r3 = httpx.delete(
                    f"https://management.azure.com{resource_id}/raiBlocklists/"
                    f"{BLOCKLIST_NAME}?api-version=2024-10-01",
                    headers=headers,
                )
                if r3.status_code in (200, 202, 204):
                    print(f"✓ ARM blocklist '{BLOCKLIST_NAME}' deleted (Foundry portal).")
                else:
                    print(f"  ARM blocklist delete: {r3.status_code}")
                return

    print(f"  ARM resource not found for '{account_name}'.")


def main():
    credential = DefaultAzureCredential()

    # 1. Delete from Content Safety API
    client = BlocklistClient(endpoint=ACCOUNT_ENDPOINT, credential=credential)
    try:
        client.delete_text_blocklist(blocklist_name=BLOCKLIST_NAME)
        print(f"✓ Content Safety blocklist '{BLOCKLIST_NAME}' deleted.")
    except Exception as e:
        print(f"  Content Safety blocklist not found or already deleted: {e}")

    # 2. Delete from ARM API (Foundry portal)
    try:
        _delete_arm_blocklist(credential)
    except Exception as e:
        print(f"  ARM blocklist cleanup failed: {e}")


if __name__ == "__main__":
    main()
