"""
Async MCP client for the two Databricks-proxied MCP gateways.

Gateways:
  - you-danone  → https://fevm-danonedemo.cloud.databricks.com/api/2.0/mcp/external/you-danone
  - danone-bright → https://fevm-danonedemo.cloud.databricks.com/api/2.0/mcp/external/danone-bright

Both require:
  Authorization: Bearer <DATABRICKS_TOKEN>
  Accept: application/json, text/event-stream    (SSE + JSON)
  Content-Type: application/json

The MCP gateway sends a JSON-RPC 2.0 response as an SSE stream.
We parse the first "data: ..." line to extract the payload.
"""

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("danone.social.mcp_client")

_DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://fevm-danonedemo.cloud.databricks.com")

YOUCOM_MCP_URL   = f"{_DATABRICKS_HOST}/api/2.0/mcp/external/you-danone"
BRIGHTDATA_MCP_URL = f"{_DATABRICKS_HOST}/api/2.0/mcp/external/danone-bright"

_TIMEOUT = 45.0  # seconds


def _token() -> str:
    tok = os.environ.get("DATABRICKS_TOKEN", "")
    if not tok:
        raise RuntimeError("DATABRICKS_TOKEN not set")
    return tok


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _parse_sse(raw: str) -> dict:
    """Extract JSON payload from an MCP SSE response."""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(raw)


def _unwrap(parsed: dict) -> Any:
    """Unwrap the MCP result envelope → inner data."""
    result = parsed.get("result", {})
    content = result.get("content", [])
    if content and isinstance(content, list) and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except json.JSONDecodeError:
            return content[0]["text"]
    return result


async def _call(url: str, tool_name: str, arguments: dict) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": 1,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
    return _unwrap(_parse_sse(resp.text))


# ── You.com tools ─────────────────────────────────────────────────────────────

async def youcom_search(
    query: str,
    count: int = 10,
    freshness: str = "month",
    livecrawl: str = "all",
) -> dict:
    """
    Semantic web search via You.com.
    Returns a dict with keys: results.web[], results.news[]
    Each item may include a 'contents.markdown' key if livecrawl succeeded.
    """
    logger.info(f"you-search: '{query[:80]}'")
    result = await _call(YOUCOM_MCP_URL, "you-search", {
        "query": query,
        "count": count,
        "freshness": freshness,
        "livecrawl": livecrawl,
        "livecrawl_formats": "markdown",
        "safesearch": "off",
    })
    return result if isinstance(result, dict) else {}


async def youcom_contents(urls: list[str]) -> dict:
    """
    Extract full Markdown from a list of URLs via You.com Contents API.
    Returns a dict with key: items[]
    """
    logger.info(f"you-contents: {len(urls)} URLs")
    result = await _call(YOUCOM_MCP_URL, "you-contents", {
        "urls": urls,
        "formats": ["markdown"],
        "crawl_timeout": 30,
    })
    return result if isinstance(result, dict) else {}


# ── Brightdata tools ──────────────────────────────────────────────────────────

async def brightdata_scrape(url: str) -> str:
    """
    Scrape a single URL as Markdown via Brightdata.
    Returns markdown string or empty string on failure.
    """
    logger.info(f"brightdata scrape: {url}")
    result = await _call(BRIGHTDATA_MCP_URL, "scrape_as_markdown", {"url": url})
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("markdown", result.get("content", ""))
    return ""


async def brightdata_search(query: str, engine: str = "google") -> dict:
    """
    Search via Brightdata's search engine tool.
    Returns a dict with organic results.
    """
    logger.info(f"brightdata search: '{query[:80]}'")
    result = await _call(BRIGHTDATA_MCP_URL, "search_engine", {
        "query": query,
        "engine": engine,
    })
    return result if isinstance(result, dict) else {}
