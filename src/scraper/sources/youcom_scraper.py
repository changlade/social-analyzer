"""
You.com MCP scraper — primary data collection source.

Uses the official Databricks MCP client (databricks-mcp) to call the
you-danone Unity Catalog connection via the Databricks-managed proxy.
Authentication is handled automatically by WorkspaceClient.

The you-search MCP tool returns LLM-friendly formatted text (not JSON).
We parse that text format here.

Ref: https://learn.microsoft.com/en-us/azure/databricks/generative-ai/mcp/external-mcp
"""

import concurrent.futures
import logging
import re
import time
import random
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient

from utils.delta_writer import build_record

logger = logging.getLogger(__name__)

YOU_CONNECTION_NAME = "you-danone"

# ── Topic definitions ──────────────────────────────────────────────────────────

YOUCOM_TOPICS: list[dict[str, Any]] = [
    {
        "query": "Danone B Corp impact score assessment bcorporation.net",
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
        "query": "Danone one planet one health social mission impact 2024 2025",
        "freshness": "year", "count": 8,
        "source_type": "official", "topic": "social_mission",
    },
    {
        "query": "Danone worldbenchmarkingalliance.org food agriculture benchmark",
        "freshness": "year", "count": 10,
        "source_type": "benchmark", "topic": "wba_benchmark",
    },
    {
        "query": "Danone accesstonutrition.org nutrition index score",
        "freshness": "year", "count": 10,
        "source_type": "benchmark", "topic": "nutrition_index",
    },
    {
        "query": "Danone Corporate Human Rights Benchmark ranking score",
        "freshness": "year", "count": 8,
        "source_type": "benchmark", "topic": "human_rights_benchmark",
    },
    {
        "query": "Danone employee review working conditions glassdoor indeed 2024 2025",
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
        "query": "Danone community impact developing countries Africa Asia social 2024",
        "freshness": "year", "count": 8,
        "source_type": "ngo", "topic": "community_impact",
    },
    {
        "query": "Danone Evian water rights controversy criticism",
        "freshness": "year", "count": 8,
        "source_type": "news", "topic": "water_rights",
    },
    {
        "query": "Danone layoffs restructuring employees France 2024 2025",
        "freshness": "month", "count": 8,
        "source_type": "news", "topic": "restructuring",
    },
    {
        "query": "Danone ESG social impact news 2025 2026",
        "freshness": "month", "count": 10,
        "source_type": "news", "topic": "general_news",
    },
    {
        "query": "Danone CEO Antoine de Saint-Affrique strategy social 2025",
        "freshness": "month", "count": 6,
        "source_type": "news", "topic": "strategy",
    },
]

# ── Breaking news / crisis topics (short freshness — day/week) ────────────────
# These are scraped in addition to the ESG strategy topics above and feed
# the gold_news_events table for crisis monitoring and recall tracking.

NEWS_EVENTS_TOPICS: list[dict[str, Any]] = [
    {
        "query": "Danone product recall contamination safety alert withdrawal 2026",
        "freshness": "week", "count": 10,
        "source_type": "news", "topic": "product_recall",
    },
    {
        "query": "Danone infant formula recall Asia Pacific APAC baby milk safety 2026",
        "freshness": "week", "count": 10,
        "source_type": "news", "topic": "crisis_apac",
    },
    {
        "query": "Danone regulatory fine sanction FDA EFSA ANSES investigation 2026",
        "freshness": "week", "count": 8,
        "source_type": "news", "topic": "regulatory_action",
    },
    {
        "query": "Danone controversy scandal criticism media backlash 2026",
        "freshness": "day", "count": 10,
        "source_type": "news", "topic": "crisis_media",
    },
    {
        "query": "Danone share price stock earnings investor reaction analyst 2026",
        "freshness": "week", "count": 8,
        "source_type": "news", "topic": "market_impact",
    },
]

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

# ── Thread pool for MCP calls (avoids asyncio.run() conflict with IPython loop) ─

_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _call_tool(client: DatabricksMCPClient, tool_name: str, arguments: dict):
    """
    Call an MCP tool in a ThreadPoolExecutor worker so DatabricksMCPClient
    can use asyncio.run() without conflicting with the running IPython event loop
    in Databricks serverless compute.
    """
    future = _THREAD_POOL.submit(client.call_tool, tool_name, arguments)
    return future.result(timeout=120)


def _get_text(raw_result) -> str:
    """Extract the text payload from a DatabricksMCPClient call_tool response."""
    if hasattr(raw_result, "content") and raw_result.content:
        return raw_result.content[0].text or ""
    return ""


# ── Text-format parser for you-search MCP output ─────────────────────────────
#
# The you-search MCP tool returns LLM-friendly formatted text, not JSON.
# Each result block is prefixed by "WEB RESULTS:" or "NEWS RESULTS:".
# Format:
#   WEB RESULTS:
#
#   Title: <title>
#   URL: <url>
#   Published: <date>
#   Description: <description>
#   Snippets:
#   - <snippet 1>
#   - <snippet 2>
#   Content:               ← optional livecrawl markdown
#   <full page content>
#

_RESULT_BLOCK_RE = re.compile(
    r'(?P<section_type>WEB|NEWS) RESULTS:\s*\n',
    re.IGNORECASE,
)
_FIELD_RE = re.compile(r'^(?P<key>Title|URL|Published|Description):\s*(?P<val>.+)$', re.IGNORECASE)


def _parse_result_block(block: str, section_type: str) -> dict:
    """Parse one result block into a dict with url, title, date, body."""
    url = title = published = ""
    snippets: list[str] = []
    content_lines: list[str] = []
    in_snippets = False
    in_content = False

    for line in block.split("\n"):
        stripped = line.strip()

        if not stripped:
            if in_content:
                content_lines.append("")
            in_snippets = False
            continue

        # Section transitions
        if stripped.lower().startswith("snippets:"):
            in_snippets = True
            in_content = False
            continue
        if re.match(r'^(content|page content|markdown|livecrawl content)[:：]?\s*$', stripped, re.IGNORECASE):
            in_snippets = False
            in_content = True
            continue

        if in_snippets and stripped.startswith("- "):
            snippets.append(stripped[2:])
            continue

        if in_content:
            content_lines.append(line)
            continue

        # Key-value fields
        m = _FIELD_RE.match(stripped)
        if m:
            key = m.group("key").lower()
            val = m.group("val").strip()
            if key == "url":
                url = val
            elif key == "title":
                title = val
            elif key == "published":
                published = val
            elif key == "description" and not snippets and not content_lines:
                snippets.append(val)

    # Build content: prefer livecrawl content, then snippets, then description
    full_content = "\n".join(content_lines).strip()
    body = full_content if len(full_content) > 200 else "\n\n".join(snippets)

    return {
        "url": url,
        "title": title,
        "published": published,
        "body": body,
        "section_type": section_type,
    }


def _parse_youcom_text(
    text: str,
    source_type: str,
    topic: str,
    query: str,
) -> list[dict[str, Any]]:
    """Parse You.com MCP text-format search results into Delta Lake records."""
    records = []
    if not text or text.strip().startswith("Error:"):
        return records

    # Split on section headers; each "WEB RESULTS:" or "NEWS RESULTS:" starts a new result
    parts = _RESULT_BLOCK_RE.split(text)
    # parts = [pre, section_type1, block1, section_type2, block2, ...]
    # After the split, items alternate: text, section_type, text, section_type, ...
    # Actually re.split with groups gives: [before, group1, after1, group2, after2, ...]

    i = 1  # skip leading text before first match
    while i < len(parts):
        section_type = parts[i].upper()   # "WEB" or "NEWS"
        block = parts[i + 1] if i + 1 < len(parts) else ""
        i += 2

        parsed = _parse_result_block(block, section_type)
        url = parsed["url"]
        body = parsed["body"]

        if not url or len(body) < 80:
            continue

        records.append(build_record(
            url=url,
            title=parsed["title"] or url,
            content=body[:20_000],
            source_type=source_type,
            search_topic=topic,
            published_date=parsed["published"],
            extra={
                "result_section": section_type.lower(),
                "scraper": "you-search",
                "you_query": query,
                "livecrawled": len(parsed["body"]) > 500,
            },
        ))

    return records


# ── Contents-format parser for you-contents MCP output ───────────────────────

def _parse_youcom_contents(text: str, url_meta: dict[str, dict]) -> list[dict[str, Any]]:
    """
    Parse You.com MCP you-contents text output into records.
    The format varies but typically has URL, Title, and Content sections.
    """
    records = []
    if not text or text.strip().startswith("Error:"):
        return records

    # Split on URL: lines to get per-URL blocks
    url_blocks = re.split(r'\nURL:\s*', "\n" + text)
    for raw_block in url_blocks[1:]:
        lines = raw_block.split("\n")
        url = lines[0].strip()
        if not url:
            continue

        title = ""
        content_lines = []
        in_content = False

        for line in lines[1:]:
            stripped = line.strip()
            if re.match(r'^Title:\s*', stripped, re.IGNORECASE):
                title = re.sub(r'^Title:\s*', "", stripped, flags=re.IGNORECASE)
                continue
            if re.match(r'^(content|markdown|page content)[:：]?\s*$', stripped, re.IGNORECASE):
                in_content = True
                continue
            if in_content:
                content_lines.append(line)
            elif stripped and not title:
                title = stripped

        content = "\n".join(content_lines).strip()
        if not content or len(content) < 80:
            continue

        meta = url_meta.get(url, {"source_type": "official", "topic": "direct_fetch"})
        records.append(build_record(
            url=url,
            title=title or url,
            content=content[:20_000],
            source_type=meta["source_type"],
            search_topic=meta["topic"],
            extra={"scraper": "you-contents"},
        ))

    return records


# ── MCP client factory ────────────────────────────────────────────────────────

def _make_client() -> DatabricksMCPClient:
    ws = WorkspaceClient()
    host = ws.config.host.rstrip("/")
    server_url = f"{host}/api/2.0/mcp/external/{YOU_CONNECTION_NAME}"
    logger.info(f"You.com MCP server URL: {server_url}")
    return DatabricksMCPClient(server_url=server_url, workspace_client=ws)


# ── Search scraper ─────────────────────────────────────────────────────────────

def scrape_topic(client: DatabricksMCPClient, topic: dict[str, Any]) -> list[dict[str, Any]]:
    """Run one you-search call and return Delta Lake records."""
    query       = topic["query"]
    source_type = topic["source_type"]
    topic_name  = topic["topic"]
    freshness   = topic.get("freshness", "year")
    count       = topic.get("count", 10)

    logger.info(f"you-search: '{query[:70]}' [freshness={freshness}]")

    try:
        raw = _call_tool(client, "you-search", {
            "query":            query,
            "count":            count,
            "freshness":        freshness,
            "livecrawl":        "all",
            "livecrawl_formats": "markdown",
            "safesearch":       "off",
        })
        text = _get_text(raw)
    except Exception as exc:
        logger.error(f"  you-search failed for '{query[:50]}': {exc}")
        return []

    records = _parse_youcom_text(text, source_type, topic_name, query)
    logger.info(f"  → {len(records)} records (response {len(text)} chars)")
    return records


# ── Direct URL extractor ───────────────────────────────────────────────────────

def extract_direct_urls(client: DatabricksMCPClient) -> list[dict[str, Any]]:
    """Batch-extract known high-value URLs via you-contents."""
    urls = [e["url"] for e in DIRECT_URLS]
    url_meta = {e["url"]: e for e in DIRECT_URLS}
    logger.info(f"you-contents: {len(urls)} direct URLs")

    try:
        raw = _call_tool(client, "you-contents", {
            "urls":          urls,
            "formats":       ["markdown"],
            "crawl_timeout": 30,
        })
        text = _get_text(raw)
    except Exception as exc:
        logger.error(f"  you-contents failed: {exc}")
        return []

    records = _parse_youcom_contents(text, url_meta)
    logger.info(f"  → {len(records)} records from direct URLs (response {len(text)} chars)")
    return records


# ── Main entry point ───────────────────────────────────────────────────────────

def run_youcom_scraper() -> list[dict[str, Any]]:
    """
    Run all You.com topic searches + direct URL extractions.
    Uses DatabricksMCPClient with auto-detected WorkspaceClient credentials.

    Runs two passes:
      1. ESG strategy topics (YOUCOM_TOPICS) — yearly/monthly freshness
      2. Breaking news / crisis topics (NEWS_EVENTS_TOPICS) — daily/weekly freshness
    """
    client = _make_client()
    all_records: list[dict] = []

    # 1. ESG strategy topic searches
    all_topics = YOUCOM_TOPICS + NEWS_EVENTS_TOPICS
    for i, topic in enumerate(all_topics):
        records = scrape_topic(client, topic)
        all_records.extend(records)
        if i < len(all_topics) - 1:
            time.sleep(random.uniform(0.5, 1.5))

    # 2. Direct URL extraction
    direct_records = extract_direct_urls(client)
    all_records.extend(direct_records)

    esg_count  = sum(1 for r in all_records if r.get("search_topic") not in
                     {t["topic"] for t in NEWS_EVENTS_TOPICS})
    news_count = sum(1 for r in all_records if r.get("search_topic") in
                     {t["topic"] for t in NEWS_EVENTS_TOPICS})
    logger.info(f"You.com scraper total: {len(all_records)} records "
                f"(ESG strategy: {esg_count}, breaking news: {news_count})")
    return all_records
