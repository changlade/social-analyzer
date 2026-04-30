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

_DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://fe-vm-vdm-serverless-nmmvdg.cloud.databricks.com").rstrip("/")
_SERVING_ENDPOINT = os.environ.get("AI_ENDPOINT_NAME", "databricks-gpt-5-4")
_AI_ENDPOINT_URL  = f"{_DATABRICKS_HOST}/serving-endpoints/{_SERVING_ENDPOINT}/invocations"
_AI_ENDPOINT_NAME = _SERVING_ENDPOINT
_CATALOG = os.environ.get("CATALOG", "canglade_demos")
_SCHEMA  = os.environ.get("SCHEMA", "social_analyzer")

# ── Table schema documentation for the LLM ───────────────────────────────────
# Injected into tool descriptions so the model generates correct SQL.

_GOLD_TABLES_DOC = f"""
All tables are in catalog `{_CATALOG}`, schema `{_SCHEMA}`.
Always qualify table names fully: `{_CATALOG}.{_SCHEMA}.<table>` — or just `<table>` since the catalog/schema context is set.

Available gold tables and their key columns:

**gold_esg_insights** — one row per article, ESG-classified
  article_id, url, title, content_preview, clean_content,
  source_type (official|news|social|ngo|benchmark|rss),
  search_topic (e.g. bcorp_profile, greenwashing, worker_sentiment, general_news),
  esg_category (Environmental|Social|Governance|Cross-ESG|Crisis|Unknown),
  esg_sub_theme, impact_summary, credibility_score (0-1),
  sentiment_label (positive|neutral|negative),
  sentiment_score (-1.0 to +1.0),
  danone_stance (supportive|critical|neutral|mixed),
  published_at (timestamp), scraped_date (date)

**gold_csr_claims** — official CSR claims from Danone docs/filings
  claim_id, esg_category, sub_theme, claim_text, metric, timeframe,
  claim_type (target|achievement|policy|commitment),
  credibility_score, url, scraped_date

**gold_public_sentiment** — weekly public sentiment aggregated by ESG category
  week_start (date), esg_category, avg_sentiment (-1 to +1),
  mention_count, key_topics (array<string>),
  positive_count, negative_count, critical_count

**gold_impact_delta** — gap analysis between CSR claims and public perception
  delta_id, esg_category, sub_theme, claim_count, total_articles,
  period_avg_sentiment, pct_critical, dominant_sentiment,
  alignment_score_quick (0-100), alignment_label (aligned|mixed|divergent|critical),
  gap_headline, official_narrative, public_narrative,
  marketing_opportunity, risk_level (low|medium|high|critical),
  analysis_date

**gold_daily_summary** — daily AI executive brief (one row per day)
  report_date, total_articles, unique_sources, avg_sentiment,
  top_esg_themes (array), reputational_risks (array),
  opportunities (array), headline, executive_brief, top_risk,
  top_opportunity, esg_pulse_json, recommended_actions (array)

**gold_news_events** — breaking news events with AI crisis classification
  article_id, url, title, content_preview, source_type, search_topic,
  scraped_date, published_at, sentiment_label, sentiment_score,
  danone_stance, esg_category, impact_summary, credibility_score,
  event_type (recall|regulatory|financial|reputational|positive|other),
  severity (low|medium|high|critical),
  affected_region, affected_product,
  financial_impact_estimate, recommended_response
"""

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
                f"Run a read-only SQL query against the Gold-layer Delta tables "
                f"(catalog: {_CATALOG}, schema: {_SCHEMA}). "
                "Use this for ESG insights, sentiment trends, CSR claims, impact delta analysis, or daily summaries.\n\n"
                + _GOLD_TABLES_DOC
                + "\nAlways use bare table names (no catalog/schema prefix) and include LIMIT ≤ 50."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "SELECT-only SQL. Use bare table names (gold_esg_insights, gold_csr_claims, etc.). "
                            "Always include LIMIT. Example: SELECT title, sentiment_score, esg_category FROM gold_esg_insights ORDER BY scraped_date DESC LIMIT 10"
                        ),
                    },
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_news_events",
            "description": (
                f"Query the gold_news_events table (catalog: {_CATALOG}, schema: {_SCHEMA}) "
                "for breaking news events, product recalls, regulatory sanctions, and crises.\n"
                "Columns: article_id, url, title, content_preview, source_type, search_topic, "
                "scraped_date, published_at, sentiment_label, sentiment_score, danone_stance, "
                "esg_category, impact_summary, credibility_score, "
                "event_type (recall|regulatory|financial|reputational|positive|other), "
                "severity (low|medium|high|critical), "
                "affected_region, affected_product, financial_impact_estimate, recommended_response.\n"
                "Use for: recalls, APAC crises, regulatory fines, media controversies, market impact. "
                "Always include LIMIT."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "SELECT-only SQL. Use bare table name: gold_news_events. Always include LIMIT. "
                            "Example: SELECT title, severity, event_type, affected_region, recommended_response FROM gold_news_events ORDER BY scraped_date DESC LIMIT 10"
                        ),
                    },
                },
                "required": ["sql"],
            },
        },
    },
]

SYSTEM_PROMPT = f"""You are an expert ESG and crisis communications analyst for Danone, powered by AI.

Your role is to help marketing and strategy teams understand:
- Danone's official CSR/ESG claims and commitments
- What the public, NGOs, employees, and media actually think about Danone's social impact
- Gaps between corporate narrative and public perception (the "Impact Delta")
- Breaking news events: product recalls, regulatory actions, APAC crises, reputational risks
- ESG risks and marketing opportunities

**Data catalog:** All pipeline tables are in `{_CATALOG}.{_SCHEMA}`.
When writing SQL, use bare table names only (e.g. `gold_esg_insights`, NOT `{_CATALOG}.{_SCHEMA}.gold_esg_insights`) — the database context is set automatically.

**Tool selection guidelines:**

For structured data (use first — it's fast and always available):
- General ESG analysis, sentiment trends → query_gold_layer (gold_esg_insights, gold_public_sentiment)
- CSR claims, what Danone officially says → query_gold_layer (gold_csr_claims)
- Gap between claims and public reality → query_gold_layer (gold_impact_delta)
- Daily executive summary → query_gold_layer (gold_daily_summary)
- Recalls, regulatory actions, crises → query_news_events (gold_news_events)

For live web search (use when structured data is insufficient or stale):
- youcom_search with freshness="year" for annual reports, B Corp scores, strategy
- youcom_search with freshness="month" for recent news
- youcom_search with freshness="week" or "day" for active crises, breaking news
- brightdata_search / brightdata_scrape for Glassdoor, LinkedIn, paywalled pages

**SQL rules — CRITICAL:**
- ALWAYS use bare table names: `gold_esg_insights`, `gold_csr_claims`, etc.
- NEVER include catalog/schema prefix in SQL
- ALWAYS include LIMIT (max 50)
- Use ONLY columns that exist in the table schema (see tool descriptions)
- For text search: use LIKE or LOWER(column) LIKE '%keyword%'
- For date filters: scraped_date >= CURRENT_DATE() - INTERVAL 30 DAYS

**General guidelines:**
- Start with query_gold_layer or query_news_events before going to web search
- If a SQL query returns no results, try broadening the filter (remove WHERE clauses, increase LIMIT)
- If structured data is empty or insufficient, supplement with youcom_search
- Never fabricate statistics or events. Cite URLs when referencing web content.
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

        elif name in ("query_gold_layer", "query_news_events"):
            sql = args["sql"].strip()
            # Safety guard: only allow SELECT statements
            if not sql.upper().lstrip().startswith("SELECT"):
                return "Error: only SELECT statements are allowed."
            # Strip any fully-qualified prefixes the model may have added
            import re as _re
            sql_clean = _re.sub(
                rf'\b{_re.escape(_CATALOG)}\.{_re.escape(_SCHEMA)}\.',
                '',
                sql,
                flags=_re.IGNORECASE
            )
            rows = execute_query(sql_clean)
            if not rows:
                return (
                    "Query returned no results. "
                    "Try: (1) remove or broaden WHERE filters, "
                    "(2) increase LIMIT, "
                    "(3) check column names match the schema in the tool description, "
                    f"(4) confirm the table has data by running: SELECT COUNT(*) FROM gold_esg_insights"
                )
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

    max_iterations = 8  # prevent infinite loops
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
