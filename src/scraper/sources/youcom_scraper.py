"""
You.com MCP scraper — primary data collection source.

Replaces: DDG + Jina Reader + Playwright (all three scrapers combined).

Uses the Databricks MCP gateway to call the you-danone UC connection,
which proxies to https://api.you.com/mcp with the stored bearer token.

Two You.com tools:
  - you-search: semantic search + livecrawl (returns full Markdown per result)
  - you-contents: direct URL batch extraction (used for known high-value URLs)

The MCP gateway requires:  Accept: application/json, text/event-stream
Response format: SSE stream — relevant data on lines starting with "data: "
"""

import json
import logging
import os
import time
import random
import requests
from typing import Any

from utils.delta_writer import build_record

logger = logging.getLogger(__name__)

YOUCOM_MCP_URL = "https://fevm-danonedemo.cloud.databricks.com/api/2.0/mcp/external/you-danone"

_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

# ── Topic definitions ─────────────────────────────────────────────────────────
# Each entry drives one you-search call.
# site: operators, freshness, and count are tuned per topic.

YOUCOM_TOPICS: list[dict[str, Any]] = [
    # Official / CSR — comprehensive coverage, yearly freshness
    {
        "query": "Danone B Corp impact score assessment site:bcorporation.net",
        "freshness": "year", "count": 10,
        "source_type": "official", "topic": "bcorp_profile",
    },
    {
        "query": "Danone ESG universal registration document annual report 2024 2025",
        "freshness": "year", "count": 10,
        "source_type": "official", "topic": "annual_report",
    },
    {
        "query": "Danone sustainability carbon neutral scope 3 climate commitment 2025",
        "freshness": "year", "count": 8,
        "source_type": "official", "topic": "environmental",
    },
    {
        "query": "Danone one planet one health social mission impact 2024",
        "freshness": "year", "count": 8,
        "source_type": "official", "topic": "social_mission",
    },
    # Benchmarks — target specific authoritative domains
    {
        "query": "Danone site:worldbenchmarkingalliance.org",
        "freshness": "year", "count": 10,
        "source_type": "benchmark", "topic": "wba_benchmark",
    },
    {
        "query": "Danone site:accesstonutrition.org",
        "freshness": "year", "count": 10,
        "source_type": "benchmark", "topic": "nutrition_index",
    },
    {
        "query": "Danone Corporate Human Rights Benchmark ranking score",
        "freshness": "year", "count": 8,
        "source_type": "benchmark", "topic": "human_rights_benchmark",
    },
    # Public / Watchdog — worker sentiment, shorter freshness for recency
    {
        "query": "Danone employee review working conditions salary site:glassdoor.com OR site:indeed.com",
        "freshness": "year", "count": 10,
        "source_type": "social", "topic": "worker_sentiment",
    },
    {
        "query": "Danone NGO criticism greenwashing plastic pollution 2024 2025",
        "freshness": "year", "count": 8,
        "source_type": "ngo", "topic": "greenwashing",
    },
    {
        "query": "Danone supply chain human rights violations allegations 2024",
        "freshness": "year", "count": 8,
        "source_type": "ngo", "topic": "supply_chain",
    },
    {
        "query": "Danone community impact developing countries Africa Asia social",
        "freshness": "year", "count": 8,
        "source_type": "ngo", "topic": "community_impact",
    },
    {
        "query": "Danone Evian water rights controversy criticism",
        "freshness": "year", "count": 8,
        "source_type": "news", "topic": "water_rights",
    },
    # News — use month freshness to capture breaking developments
    {
        "query": "Danone layoffs restructuring employees France 2024 2025",
        "freshness": "month", "count": 8,
        "source_type": "news", "topic": "restructuring",
    },
    {
        "query": "Danone ESG social impact news 2025",
        "freshness": "month", "count": 10,
        "source_type": "news", "topic": "general_news",
    },
    {
        "query": "Danone CEO Antoine de Saint-Affrique strategy social 2024 2025",
        "freshness": "month", "count": 6,
        "source_type": "news", "topic": "strategy",
    },
]

# High-value URLs to extract directly via you-contents (avoids search ranking noise)
DIRECT_URLS: list[dict[str, str]] = [
    {"url": "https://www.bcorporation.net/en-us/find-a-b-corp/company/danone/",
     "source_type": "official", "topic": "bcorp_profile"},
    {"url": "https://www.worldbenchmarkingalliance.org/publication/food-agriculture-benchmark/companies/danone/",
     "source_type": "benchmark", "topic": "wba_benchmark"},
    {"url": "https://accesstonutrition.org/company/danone/",
     "source_type": "benchmark", "topic": "nutrition_index"},
    {"url": "https://www.danone.com/impact/planet/danone-commitments-for-the-planet.html",
     "source_type": "official", "topic": "environmental"},
    {"url": "https://www.danone.com/impact/people/danone-commitments-for-people.html",
     "source_type": "official", "topic": "social_commitments"},
]


# ── MCP helpers ───────────────────────────────────────────────────────────────

def _get_token() -> str:
    token = os.environ.get("DATABRICKS_TOKEN") or os.environ.get("DATABRICKS_PAT", "")
    if not token:
        raise RuntimeError("DATABRICKS_TOKEN not set — cannot call You.com MCP")
    return token


def _parse_mcp_response(raw: str) -> dict:
    """Parse MCP SSE response: extract the JSON from the 'data: ...' line."""
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            return json.loads(line[6:])
    # Fallback: try parsing the whole body as JSON
    return json.loads(raw)


def _call_mcp(tool_name: str, arguments: dict, timeout: int = 45) -> dict:
    """Call a You.com MCP tool and return the parsed result dict."""
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": 1,
    }
    headers = {**_MCP_HEADERS, "Authorization": f"Bearer {_get_token()}"}
    resp = requests.post(YOUCOM_MCP_URL, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    parsed = _parse_mcp_response(resp.text)
    # Unwrap MCP result envelope
    content = parsed.get("result", {}).get("content", [])
    if content and content[0].get("type") == "text":
        return json.loads(content[0]["text"])
    return parsed.get("result", {})


# ── Search scraper ────────────────────────────────────────────────────────────

def scrape_topic(topic: dict[str, Any]) -> list[dict[str, Any]]:
    """Run one you-search call and convert results to Delta Lake records."""
    query       = topic["query"]
    source_type = topic["source_type"]
    topic_name  = topic["topic"]
    freshness   = topic.get("freshness", "year")
    count       = topic.get("count", 10)

    logger.info(f"you-search: '{query[:70]}' [freshness={freshness}]")

    try:
        result = _call_mcp("you-search", {
            "query": query,
            "count": count,
            "freshness": freshness,
            "livecrawl": "all",
            "livecrawl_formats": "markdown",
            "safesearch": "off",
        })
    except Exception as exc:
        logger.error(f"  you-search failed for '{query[:50]}': {exc}")
        return []

    records: list[dict] = []
    results_dict = result.get("results", {})

    for section_key in ("web", "news"):
        for item in results_dict.get(section_key, []):
            url     = item.get("url", "")
            title   = item.get("title", "")
            page_age = item.get("page_age", "")

            # Full Markdown content from livecrawl (may be absent if crawl failed)
            contents = item.get("contents", {}) or {}
            markdown = contents.get("markdown", "")

            # Fallback to snippets if livecrawl content is absent
            snippets = item.get("snippets", []) or []
            content  = markdown if len(markdown) > 200 else "\n\n".join(snippets)

            if not url or len(content) < 100:
                continue

            records.append(build_record(
                url=url,
                title=title,
                content=content[:20_000],
                source_type=source_type,
                search_topic=topic_name,
                published_date=page_age,
                extra={
                    "result_section": section_key,
                    "scraper": "you-search",
                    "you_query": query,
                    "livecrawled": bool(markdown),
                },
            ))

    logger.info(f"  → {len(records)} records")
    return records


# ── Direct URL extractor ──────────────────────────────────────────────────────

def extract_direct_urls() -> list[dict[str, Any]]:
    """
    Batch-fetch known high-value URLs via you-contents.
    Returns full Markdown for each URL that succeeds.
    """
    urls = [entry["url"] for entry in DIRECT_URLS]
    logger.info(f"you-contents: extracting {len(urls)} direct URLs")

    try:
        result = _call_mcp("you-contents", {
            "urls": urls,
            "formats": ["markdown"],
            "crawl_timeout": 30,
        })
    except Exception as exc:
        logger.error(f"  you-contents failed: {exc}")
        return []

    url_meta = {entry["url"]: entry for entry in DIRECT_URLS}
    records: list[dict] = []

    for item in result.get("items", []):
        url      = item.get("url", "")
        title    = item.get("title", "") or url
        markdown = item.get("markdown", "")
        if not url or len(markdown) < 100:
            continue
        meta = url_meta.get(url, {"source_type": "official", "topic": "direct_fetch"})
        records.append(build_record(
            url=url,
            title=title,
            content=markdown[:20_000],
            source_type=meta["source_type"],
            search_topic=meta["topic"],
            extra={"scraper": "you-contents"},
        ))

    logger.info(f"  → {len(records)} records from direct URLs")
    return records


# ── Main entry point ──────────────────────────────────────────────────────────

def run_youcom_scraper() -> list[dict[str, Any]]:
    """
    Run all You.com topic searches + direct URL extractions.
    Returns all collected records (not deduplicated — run_scraper.py handles that).
    """
    all_records: list[dict] = []

    # 1. Topic searches
    for i, topic in enumerate(YOUCOM_TOPICS):
        records = scrape_topic(topic)
        all_records.extend(records)
        # Polite pause between API calls (0.5–2s — far below rate limits)
        if i < len(YOUCOM_TOPICS) - 1:
            time.sleep(random.uniform(0.5, 2.0))

    # 2. Direct URL extraction (batch call — much faster than individual fetches)
    direct_records = extract_direct_urls()
    all_records.extend(direct_records)

    logger.info(f"You.com scraper total: {len(all_records)} records")
    return all_records
