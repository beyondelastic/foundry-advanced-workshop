"""Lesson 07 — Microsoft Web IQ: AI-Native Web Grounding.

Demonstrates Microsoft Web IQ — a high-performance grounding API that provides
fresh, structured web intelligence to AI applications. Unlike the Responses API's
built-in `web_search` tool (Grounding with Bing), Web IQ gives YOU the results
so you control exactly what context reaches the model.

The script:
1. Uses the `webiq` Python SDK for web search with passage extraction
2. Shows news search for time-sensitive medical updates
3. Demonstrates URL browsing for deep page content
4. Builds a grounded agent that combines Web IQ results with model reasoning
5. Compares Web IQ SDK vs Responses API `web_search` tool
"""

import os
import sys
import time

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from webiq import WebIQClient
from webiq.types import ContentFormat

load_dotenv()

# --- Configuration ---

PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
MODEL = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")
WEBIQ_API_KEY = os.environ["WEBIQ_API_KEY"]

SYSTEM_INSTRUCTIONS = """You are a clinical decision-support assistant.
You will be provided with web search results as context. Use ONLY the provided context to answer.

When answering:
1. Synthesise information from the provided sources
2. Cite sources by [number] matching the provided references
3. Note the recency/date of sources when relevant
4. If the context doesn't contain enough information, say so clearly
5. Remind users this is for informational purposes only

Format responses clearly with headers and bullet points where appropriate."""


# --- Web IQ Searches ---


def demo_web_search(webiq: WebIQClient):
    """Demo 1: Web search with passage extraction — the core capability."""
    print(f"\n{'='*70}")
    print("DEMO 1: Web Search with Passage Extraction")
    print(f"{'='*70}")

    query = "NICE guidelines hypertension diagnosis and management 2024 update"
    print(f"\n  Query: {query}")

    start = time.time()
    result = webiq.web.search(
        query,
        max_results=5,
        content_format=ContentFormat.passage,  # AI-optimised: relevant passages only
        language="en",
        region="GB",
    )
    elapsed = (time.time() - start) * 1000

    print(f"  ⚡ Response time: {elapsed:.0f}ms")
    print(f"  📄 Results: {len(result.webResults or [])}")

    for i, r in enumerate(result.webResults or [], 1):
        print(f"\n  [{i}] {r.title}")
        print(f"      URL: {r.url}")
        content_preview = (r.content or "")[:150].replace("\n", " ")
        print(f"      Passage: {content_preview}...")

    return result


def demo_news_search(webiq: WebIQClient):
    """Demo 2: News search — time-sensitive medical updates."""
    print(f"\n{'='*70}")
    print("DEMO 2: News Search — Latest Medical Updates")
    print(f"{'='*70}")

    query = "GLP-1 receptor agonist cardiovascular outcomes 2024 2025"
    print(f"\n  Query: {query}")

    start = time.time()
    news = webiq.news.search(
        query,
        max_results=5,
        content_format=ContentFormat.passage,
    )
    elapsed = (time.time() - start) * 1000

    print(f"  ⚡ Response time: {elapsed:.0f}ms")
    print(f"  📰 Results: {len(news.newsResults or [])}")

    for i, n in enumerate(news.newsResults or [], 1):
        source = getattr(n, "source", "Unknown")
        print(f"\n  [{i}] {n.title}")
        print(f"      Source: {source}")
        print(f"      URL: {n.url}")

    return news


def demo_browse(webiq: WebIQClient):
    """Demo 3: Browse — fetch and extract content from a specific URL."""
    print(f"\n{'='*70}")
    print("DEMO 3: Browse — Deep Page Content Extraction")
    print(f"{'='*70}")

    url = "https://www.nice.org.uk/guidance/ng136"
    print(f"\n  URL: {url}")

    start = time.time()
    page = webiq.browse.fetch(
        url,
        max_length=5000,
        content_format="markdown",
    )
    elapsed = (time.time() - start) * 1000

    print(f"  ⚡ Response time: {elapsed:.0f}ms")
    print(f"  📖 Title: {page.title}")
    content_preview = (page.content or "")[:300].replace("\n", " ")
    print(f"  Content: {content_preview}...")

    return page


# --- Grounded Agent ---


def grounded_agent_query(webiq: WebIQClient, oai_client, question: str):
    """Demo 4: Full grounded agent — Web IQ search → inject context → model reasoning."""
    print(f"\n{'='*70}")
    print(f"GROUNDED AGENT QUERY: {question}")
    print(f"{'='*70}")

    # Step 1: Search with Web IQ
    print("\n  Step 1: Searching with Web IQ...")
    start = time.time()
    results = webiq.web.search(
        question,
        max_results=5,
        content_format=ContentFormat.passage,
        max_length=3000,
    )
    search_ms = (time.time() - start) * 1000
    print(f"  ⚡ Web IQ: {search_ms:.0f}ms — {len(results.webResults or [])} results")

    # Step 2: Format results as context for the model
    context_parts = []
    for i, r in enumerate(results.webResults or [], 1):
        content = (r.content or "").strip()
        if content:
            context_parts.append(f"[{i}] Source: {r.title}\n    URL: {r.url}\n    Content: {content}")

    context = "\n\n".join(context_parts)

    # Step 3: Send to model with grounding context
    print("  Step 2: Generating grounded response...")
    start = time.time()
    response = oai_client.responses.create(
        model=MODEL,
        instructions=SYSTEM_INSTRUCTIONS,
        input=f"## Web Search Results (grounding context)\n\n{context}\n\n## User Question\n\n{question}",
    )
    model_ms = (time.time() - start) * 1000
    print(f"  ⚡ Model: {model_ms:.0f}ms")
    print(f"  📊 Total: {search_ms + model_ms:.0f}ms (search + reasoning)")

    # Step 4: Display the grounded answer
    print(f"\nANSWER:\n{response.output_text}")

    # Show the sources used
    print(f"\n  📎 Sources provided to model:")
    for i, r in enumerate(results.webResults or [], 1):
        print(f"     [{i}] {r.title}")
        print(f"         {r.url}")


# --- Comparison ---


def compare_approaches(webiq: WebIQClient, oai_client, question: str):
    """Demo 5: Compare Web IQ SDK grounding vs Responses API web_search tool."""
    print(f"\n{'='*70}")
    print("COMPARISON: Web IQ SDK vs Responses API web_search")
    print(f"{'='*70}")
    print(f"\n  Question: {question}")

    # Approach 1: Web IQ SDK (you control everything)
    print(f"\n{'─'*50}")
    print("▶ APPROACH 1: Web IQ SDK (explicit grounding)")
    print(f"{'─'*50}")

    start = time.time()
    results = webiq.web.search(question, max_results=5, content_format=ContentFormat.passage, max_length=2000)
    search_ms = (time.time() - start) * 1000

    context_parts = []
    total_chars = 0
    for i, r in enumerate(results.webResults or [], 1):
        content = (r.content or "").strip()
        if content:
            context_parts.append(f"[{i}] {r.title}: {content}")
            total_chars += len(content)

    context = "\n\n".join(context_parts)

    start = time.time()
    response = oai_client.responses.create(
        model=MODEL,
        instructions="Answer based ONLY on the provided context. Cite sources by [number].",
        input=f"Context:\n{context}\n\nQuestion: {question}",
    )
    model_ms = (time.time() - start) * 1000

    print(f"  ⚡ Search: {search_ms:.0f}ms | Model: {model_ms:.0f}ms | Total: {search_ms + model_ms:.0f}ms")
    print(f"  📊 Context tokens: ~{total_chars // 4} (passage-extracted, minimal waste)")
    print(f"  ✅ You control: query, result count, content format, what enters the prompt")
    print(f"\n  Answer: {response.output_text[:300]}...")

    # Approach 2: Responses API web_search tool (model manages everything)
    print(f"\n{'─'*50}")
    print("▶ APPROACH 2: Responses API web_search (model-managed)")
    print(f"{'─'*50}")

    start = time.time()
    response2 = oai_client.responses.create(
        model=MODEL,
        instructions="Search the web and answer with citations.",
        input=question,
        tools=[{"type": "web_search"}],
    )
    total_ms = (time.time() - start) * 1000

    print(f"  ⚡ Total (search + model): {total_ms:.0f}ms")
    print(f"  📊 Context tokens: unknown (platform-managed, may include full pages)")
    print(f"  ✅ Simpler code: just add the tool, model handles search + citation")
    print(f"\n  Answer: {response2.output_text[:300]}...")

    # Summary
    print(f"\n{'─'*50}")
    print("📋 SUMMARY")
    print(f"{'─'*50}")
    print(f"  Web IQ SDK:     {search_ms + model_ms:.0f}ms | ~{total_chars // 4} context tokens | Full control")
    print(f"  web_search:     {total_ms:.0f}ms | Unknown context size | Zero-code grounding")


# --- Entry Point ---


def main():
    """Run all Web IQ demos."""
    webiq = WebIQClient(api_key=WEBIQ_API_KEY)

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
    oai = project_client.get_openai_client()

    print("=" * 70)
    print("  LESSON 07 — Microsoft Web IQ: AI-Native Web Grounding")
    print("=" * 70)

    # Demo 1: Web search with passage extraction
    demo_web_search(webiq)

    # Demo 2: News search for time-sensitive updates
    demo_news_search(webiq)

    # Demo 3: Browse a specific URL
    demo_browse(webiq)

    # Demo 4: Full grounded agent pipeline
    grounded_agent_query(
        webiq, oai,
        "What are the current blood pressure targets for adults with hypertension, "
        "and what is the first-line treatment recommendation?",
    )

    # Demo 5: Compare Web IQ SDK vs Responses API web_search
    compare_approaches(
        webiq, oai,
        "What are the latest SGLT2 inhibitor approvals and cardiovascular safety updates?",
    )

    print(f"\n\n{'='*70}")
    print("Demo complete.")
    print("\nKey differences — Web IQ SDK vs Responses API web_search:")
    print("  • Web IQ: YOU get the results → control context, format, token budget")
    print("  • Web IQ: Passage extraction = fewer tokens, less noise")
    print("  • Web IQ: 164ms p95 latency (2.5x faster than alternatives)")
    print("  • Web IQ: Separate search APIs (web, news, video, images, browse)")
    print("  • web_search: Simpler (one tool declaration, model manages everything)")
    print("  • web_search: Built-in citations (url_citation annotations)")
    print("  • web_search: Uses Grounding with Bing under the hood")
    print(f"{'='*70}")


if __name__ == "__main__":
    webiq = WebIQClient(api_key=WEBIQ_API_KEY)

    if len(sys.argv) > 1:
        credential = DefaultAzureCredential()
        project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
        oai = project_client.get_openai_client()
        grounded_agent_query(webiq, oai, " ".join(sys.argv[1:]))
    else:
        main()
