"""
Async MCP client for the two Databricks-proxied MCP gateways.

Uses standard httpx + JSON-RPC over HTTP (MCP Streamable HTTP transport).
Authentication via DATABRICKS_TOKEN which is automatically injected by
the Databricks App runtime.

Gateways:
  - you-danone    → /api/2.0/mcp/external/you-danone
  - danone-bright → /api/2.0/mcp/external/danone-bright

Ref: https://learn.microsoft.com/en-us/azure/databricks/generative-ai/mcp/external-mcp
"""

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("danone.social.mcp_client")

_DATABRICKS_HOST = os.environ.get(
    "DATABRICKS_HOST", "https://fevm-danonedemo.cloud.databricks.com"
).rstrip("/")

YOUCOM_MCP_URL    = f"{_DATABRICKS_HOST}/api/2.0/mcp/external/you-danone"
BRIGHTDATA_MCP_URL = f"{_DATABRICKS_HOST}/api/2.0/mcp/external/danone-bright"

_TIMEOUT = 60.0


def _token() -> str:
    tok = os.environ.get("DATABRICKS_TOKEN", "")
    if not tok:
        raise RuntimeError("DATABRICKS_TOKEN not set in environment")
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
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _unwrap(parsed: dict) -> Any:
    """Unwrap the MCP result envelope → inner data."""
    result = parsed.get("result", {})
    content = result.get("content", [])
    if content and isinstance(content, list) and isinstance(content[0], dict):
        item = content[0]
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (json.JSONDecodeError, KeyError):
                return item.get("text", "")
    return result


async def _call(url: str, tool_name: str, arguments: dict) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "method":  "tools/call",
        "params":  {"name": tool_name, "arguments": arguments},
        "id": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, headers=_headers(), json=payload)
            resp.raise_for_status()
        return _unwrap(_parse_sse(resp.text))
    except Exception as exc:
        logger.error(f"MCP call {tool_name} failed: {exc}")
        return {} if tool_name != "scrape_as_markdown" else ""


# ── You.com tools ──────────────────────────────────────────────────────────────

async def youcom_search(
    query: str,
    count: int = 10,
    freshness: str = "month",
    livecrawl: str = "all",
) -> dict:
    logger.info(f"you-search: '{query[:80]}'")
    result = await _call(YOUCOM_MCP_URL, "you-search", {
        "query":             query,
        "count":             count,
        "freshness":         freshness,
        "livecrawl":         livecrawl,
        "livecrawl_formats": "markdown",
        "safesearch":        "off",
    })
    return result if isinstance(result, dict) else {"raw": result}


async def youcom_contents(urls: list[str]) -> dict:
    logger.info(f"you-contents: {len(urls)} URLs")
    result = await _call(YOUCOM_MCP_URL, "you-contents", {
        "urls":          urls,
        "formats":       ["markdown"],
        "crawl_timeout": 30,
    })
    return result if isinstance(result, dict) else {}


# ── Brightdata tools ───────────────────────────────────────────────────────────

async def brightdata_scrape(url: str) -> str:
    logger.info(f"brightdata scrape: {url}")
    result = await _call(BRIGHTDATA_MCP_URL, "scrape_as_markdown", {"url": url})
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("markdown", result.get("content", ""))
    return ""


async def brightdata_search(query: str, engine: str = "google") -> dict:
    logger.info(f"brightdata search: '{query[:80]}'")
    result = await _call(BRIGHTDATA_MCP_URL, "search_engine", {
        "query":  query,
        "engine": engine,
    })
    return result if isinstance(result, dict) else {}
