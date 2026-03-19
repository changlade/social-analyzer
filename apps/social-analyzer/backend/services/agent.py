"""
Agentic chatbot backed by GPT 5.4 (via the Databricks AI Gateway).

Tools available to the agent:
  1. youcom_search  — semantic web search + livecrawl
  2. youcom_scrape  — extract full content from specific URLs
  3. brightdata_scrape — deep scrape of a single URL via Brightdata
  4. query_gold_layer — execute read-only SQL against Gold Delta tables

The agent follows the OpenAI function-calling loop:
  user message → GPT (with tool defs) → tool calls → results → GPT → answer

Responses are yielded as SSE tokens for streaming to the frontend.
"""

import json
import logging
import os
from typing import AsyncIterator, Any

import httpx

from services.mcp_client import (
    youcom_search,
    youcom_contents,
    brightdata_scrape,
    brightdata_search,
)
from databricks_client import execute_query

logger = logging.getLogger("danone.social.agent")

_DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://fevm-danonedemo.cloud.databricks.com")
_AI_ENDPOINT_URL = os.environ.get(
    "GPT5_ENDPOINT_URL",
    "https://7474655187458913.ai-gateway.cloud.databricks.com/mlflow/v1/chat/completions",
)
_AI_ENDPOINT_NAME = os.environ.get("AI_ENDPOINT_NAME", "danone-gpt5")
_CATALOG = os.environ.get("CATALOG", "danonedemo_catalog")
_SCHEMA  = os.environ.get("SCHEMA", "marketing")

# ── Tool definitions (OpenAI function format) ─────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "youcom_search",
            "description": (
                "Search the web for recent information about Danone's ESG, "
                "sustainability, CSR claims, employee sentiment, NGO reports, "
                "news articles, or any other topic. Returns full Markdown content "
                "via livecrawl when available."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query":     {"type": "string",  "description": "Search query"},
                    "count":     {"type": "integer", "description": "Number of results (1–20)", "default": 8},
                    "freshness": {"type": "string",  "description": "Freshness filter: day, week, month, year"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "youcom_scrape",
            "description": (
                "Extract the full Markdown content from one or more specific URLs. "
                "Use when you know the exact URL of a relevant page (e.g. a Danone "
                "report, B Corp page, NGO finding)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of URLs to extract content from",
                    },
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "brightdata_scrape",
            "description": (
                "Deep-scrape a single URL via Brightdata's residential proxy network. "
                "Use for sites that block standard crawlers (e.g. Glassdoor, LinkedIn, "
                "paywalled pages)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "brightdata_search",
            "description": (
                "Search via Brightdata's search engine (Google). Use as a complement "
                "to You.com search when you need Google-ranked results specifically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query":  {"type": "string", "description": "Search query"},
                    "engine": {"type": "string", "description": "Search engine: google, bing", "default": "google"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_gold_layer",
            "description": (
                "Run a read-only SQL query against the Gold-layer Delta tables in the "
                "danonedemo_catalog.marketing schema. Available tables:\n"
                "  - gold_esg_insights: per-article ESG classification + sentiment\n"
                "  - gold_csr_claims: structured CSR claims from official sources\n"
                "  - gold_public_sentiment: weekly public sentiment by ESG category\n"
                "  - gold_impact_delta: alignment/gap analysis between CSR and public reality\n"
                "  - gold_daily_summary: daily executive brief\n"
                "Use LIMIT to avoid returning too many rows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Read-only SQL (SELECT only). Always include LIMIT.",
                    },
                },
                "required": ["sql"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are an expert ESG and sustainability analyst for Danone, powered by AI.

Your role is to help marketing and strategy teams understand:
- Danone's official CSR/ESG claims and commitments
- What the public, NGOs, employees, and media actually think about Danone's social impact
- Gaps between corporate narrative and public perception (the "Impact Delta")
- ESG risks and marketing opportunities

You have access to four tools:
1. youcom_search — search the web for real-time information
2. youcom_scrape — extract full content from specific URLs
3. brightdata_scrape — scrape difficult sites (Glassdoor, LinkedIn, paywalled sources)
4. query_gold_layer — query pre-processed ESG insights from our Delta Lake gold layer

Guidelines:
- Always use tools to ground your answers in real data. Don't make up statistics.
- For quantitative questions, prefer query_gold_layer first (it has processed data).
- For recent news or specific URLs, use youcom_search or youcom_scrape.
- For paywalled / blocked sites, use brightdata_scrape.
- Cite your sources. Include URLs when referencing web content.
- Be concise but insightful. Flag risks and opportunities clearly.
- Respond in the same language as the user's question."""


# ── Tool dispatcher ───────────────────────────────────────────────────────────

async def _dispatch_tool(name: str, args: dict) -> str:
    """Execute a tool call and return the result as a string."""
    try:
        if name == "youcom_search":
            result = await youcom_search(
                query=args["query"],
                count=args.get("count", 8),
                freshness=args.get("freshness", "month"),
            )
            # Flatten to readable markdown for the model
            items = []
            results_dict = result.get("results", {})
            for section in ("web", "news"):
                for item in results_dict.get(section, []):
                    title    = item.get("title", "")
                    url      = item.get("url", "")
                    contents = item.get("contents", {}) or {}
                    markdown = contents.get("markdown", "")
                    snippets = item.get("snippets", []) or []
                    body     = markdown[:3000] if markdown else "\n".join(snippets[:3])
                    items.append(f"### {title}\nURL: {url}\n{body}")
            return "\n\n---\n\n".join(items[:10]) if items else "No results found."

        elif name == "youcom_scrape":
            result = await youcom_contents(args["urls"])
            pages = []
            for item in result.get("items", []):
                url      = item.get("url", "")
                title    = item.get("title", url)
                markdown = item.get("markdown", "")
                pages.append(f"### {title}\nURL: {url}\n{markdown[:5000]}")
            return "\n\n---\n\n".join(pages) if pages else "Could not extract content from the given URLs."

        elif name == "brightdata_scrape":
            markdown = await brightdata_scrape(args["url"])
            return markdown[:8000] if markdown else "Brightdata could not retrieve content from this URL."

        elif name == "brightdata_search":
            result = await brightdata_search(args["query"], args.get("engine", "google"))
            organic = result.get("organic", [])
            items = []
            for item in organic[:8]:
                title   = item.get("title", "")
                url     = item.get("url", item.get("link", ""))
                snippet = item.get("snippet", item.get("description", ""))
                items.append(f"- **{title}**\n  {url}\n  {snippet}")
            return "\n".join(items) if items else "No search results."

        elif name == "query_gold_layer":
            sql = args["sql"].strip()
            # Safety guard: only allow SELECT statements
            if not sql.upper().lstrip().startswith("SELECT"):
                return "Error: only SELECT statements are allowed."
            rows = execute_query(sql)
            if not rows:
                return "Query returned no results."
            # Format as markdown table
            headers = list(rows[0].keys())
            header_row = " | ".join(headers)
            sep_row    = " | ".join(["---"] * len(headers))
            data_rows  = [" | ".join(str(row.get(h, "")) for h in headers) for row in rows[:50]]
            return f"| {header_row} |\n| {sep_row} |\n" + "\n".join(f"| {r} |" for r in data_rows)

        else:
            return f"Unknown tool: {name}"

    except Exception as exc:
        logger.error(f"Tool {name} error: {exc}", exc_info=True)
        return f"Tool error ({name}): {exc}"


# ── GPT 5.4 API call ──────────────────────────────────────────────────────────

def _token() -> str:
    tok = os.environ.get("DATABRICKS_TOKEN", "")
    if not tok:
        raise RuntimeError("DATABRICKS_TOKEN not set")
    return tok


async def _chat_completion(messages: list[dict], stream: bool = False, tools: list | None = None) -> Any:
    """Call the GPT 5.4 endpoint via the Databricks AI Gateway."""
    payload: dict[str, Any] = {
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if stream:
        payload["stream"] = True

    headers = {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(_AI_ENDPOINT_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


# ── Main agent loop ───────────────────────────────────────────────────────────

async def run_agent(user_message: str, history: list[dict] | None = None) -> AsyncIterator[str]:
    """
    Agentic loop: runs until GPT stops calling tools.

    Yields SSE-formatted strings:
      data: {"type": "token",     "content": "..."}
      data: {"type": "tool_call", "name": "...", "args": {...}}
      data: {"type": "tool_result", "name": "...", "content": "..."}
      data: {"type": "done"}
      data: {"type": "error",    "content": "..."}
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Include prior conversation history (last 10 turns)
    if history:
        messages.extend(history[-10:])

    messages.append({"role": "user", "content": user_message})

    max_iterations = 6  # prevent infinite loops
    iteration = 0

    try:
        while iteration < max_iterations:
            iteration += 1

            response = await _chat_completion(messages, tools=TOOL_DEFINITIONS)
            choice   = response["choices"][0]
            message  = choice["message"]
            messages.append(message)

            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                # Final answer — stream token by token (word-level simulation)
                content = message.get("content", "")
                words   = content.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                break

            # ── Execute tool calls ─────────────────────────────────────────────
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = json.loads(tc["function"].get("arguments", "{}"))

                yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'args': tool_args})}\n\n"

                tool_result = await _dispatch_tool(tool_name, tool_args)

                yield f"data: {json.dumps({'type': 'tool_result', 'name': tool_name, 'content': tool_result[:500]})}\n\n"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as exc:
        logger.error(f"Agent error: {exc}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
