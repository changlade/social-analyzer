"""
Reports router — ad-hoc AI report generation for marketing users.
Calls the GPT-5.4 AI Gateway directly (not via ai_query SQL) to avoid
batch-inference limitations and produce rich structured narrative reports.
"""

import json
import os
import logging
from typing import Optional, List

import httpx
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from databricks_client import execute_query

logger = logging.getLogger("danone.social.reports")

router = APIRouter()

# ── AI config ──────────────────────────────────────────────────────────────────
_DATABRICKS_HOST = os.getenv(
    "DATABRICKS_HOST", "https://fevm-danonedemo.cloud.databricks.com"
).rstrip("/")
# Use the workspace serving endpoint directly — GPT-5.4 handles long-form generation well
_SERVING_ENDPOINT = os.getenv("REPORT_LLM_ENDPOINT", "databricks-gpt-5-4")
_GPT5_URL = f"{_DATABRICKS_HOST}/serving-endpoints/{_SERVING_ENDPOINT}/invocations"
_TIMEOUT = 120.0


def _ai_token() -> str:
    """Return the Bearer token for the AI Gateway call."""
    return (
        os.getenv("DATABRICKS_TOKEN")
        or os.getenv("DATABRICKS_PAT", "")
    )


def _call_gpt(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    """Call GPT-5.4 AI Gateway and return the assistant message text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                _GPT5_URL,
                headers={
                    "Authorization": f"Bearer {_ai_token()}",
                    "Content-Type": "application/json",
                },
                json={
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
            )
            if resp.status_code != 200:
                logger.error(f"GPT call failed {resp.status_code}: {resp.text[:300]}")
                return ""
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error(f"GPT call error: {exc}")
        return ""


def _parse_summaries(raw) -> list:
    """Parse COLLECT_LIST result — may come back as JSON string or Python list."""
    if isinstance(raw, list):
        return [s for s in raw if s]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return [s for s in parsed if s]
        except Exception:
            return [raw] if raw else []
    return []


class ReportRequest(BaseModel):
    report_type: str = Field(
        description="executive_brief|esg_deep_dive|csr_vs_reality|source_analysis|custom",
        examples=["executive_brief"],
    )
    esg_categories: List[str] = Field(
        default=["Environmental", "Social", "Governance"],
        description="ESG categories to include",
    )
    date_from: Optional[str] = Field(None, description="YYYY-MM-DD")
    date_to:   Optional[str] = Field(None, description="YYYY-MM-DD")
    audience:  str = Field(
        default="marketing",
        description="marketing|executive|investor|communications",
    )
    custom_prompt: Optional[str] = Field(None, description="Custom instructions for the AI")
    max_articles:  int = Field(default=50, ge=10, le=200)


@router.get("/daily-brief")
def get_daily_brief(date: Optional[str] = None) -> dict:
    """Retrieve the pre-computed daily executive brief from gold_daily_summary."""
    date_filter = f"report_date = '{date}'" if date else "report_date = CURRENT_DATE()"
    sql = f"""
    SELECT
      report_date,
      total_articles,
      unique_sources,
      avg_sentiment,
      positive_count,
      neutral_count,
      negative_count,
      critical_count,
      env_count,
      social_count,
      gov_count,
      headline,
      brief_json_raw
    FROM gold_daily_summary
    WHERE {date_filter}
    ORDER BY report_date DESC
    LIMIT 1
    """
    rows = execute_query(sql)
    if not rows:
        # Fall back to latest available brief
        rows = execute_query(
            "SELECT report_date, total_articles, unique_sources, avg_sentiment, "
            "positive_count, neutral_count, negative_count, critical_count, "
            "env_count, social_count, gov_count, headline, brief_json_raw "
            "FROM gold_daily_summary ORDER BY report_date DESC LIMIT 1"
        )
    if not rows:
        return {"message": "No daily brief available", "date": date, "brief": {}}

    row = rows[0]
    try:
        row["brief"] = json.loads(row.get("brief_json_raw") or "{}")
    except Exception:
        row["brief"] = {}
    return row


@router.post("/generate")
def generate_report(request: ReportRequest = Body(...)) -> dict:
    """
    Generate an on-demand AI report by querying the gold layer and calling GPT-5.4.
    Returns a structured narrative report tailored to the specified audience.
    """
    cat_filter = "', '".join(request.esg_categories)
    conditions = [f"esg_category IN ('{cat_filter}')"]
    if request.date_from: conditions.append(f"scraped_date >= '{request.date_from}'")
    if request.date_to:   conditions.append(f"scraped_date <= '{request.date_to}'")
    where = " AND ".join(conditions)

    # ── 1. Aggregate ESG stats from gold layer ────────────────────────────────
    stats_sql = f"""
    SELECT
      esg_category,
      COUNT(*)                                AS article_count,
      ROUND(AVG(sentiment_score), 3)          AS avg_sentiment,
      SUM(CASE WHEN danone_stance='critical'   THEN 1 ELSE 0 END) AS critical_count,
      SUM(CASE WHEN danone_stance='supportive' THEN 1 ELSE 0 END) AS supportive_count,
      COLLECT_LIST(
        CASE WHEN credibility_score >= 6
          THEN LEFT(impact_summary, 250) ELSE NULL END
      )                                       AS impact_summaries,
      MAX(scraped_date)                       AS latest_date
    FROM gold_esg_insights
    WHERE {where}
    GROUP BY esg_category
    ORDER BY article_count DESC
    """
    stats = execute_query(stats_sql)

    # ── 2. Also pull CSR claims for context ───────────────────────────────────
    claims_sql = f"""
    SELECT esg_category, sub_theme, claim_text, metric, timeframe, claim_type
    FROM gold_csr_claims
    WHERE esg_category IN ('{cat_filter}')
    ORDER BY credibility_score DESC
    LIMIT 15
    """
    claims = execute_query(claims_sql)

    # ── 3. Pull impact delta insights ─────────────────────────────────────────
    delta_sql = f"""
    SELECT
      esg_category, sub_theme, alignment_score_quick,
      get_json_object(delta_json_raw, '$.gap_headline')      AS gap_headline,
      get_json_object(delta_json_raw, '$.official_narrative') AS official_narrative,
      get_json_object(delta_json_raw, '$.public_narrative')   AS public_narrative,
      get_json_object(delta_json_raw, '$.risk_level')         AS risk_level
    FROM gold_impact_delta
    WHERE esg_category IN ('{cat_filter}')
    ORDER BY alignment_score_quick ASC NULLS LAST
    LIMIT 10
    """
    deltas = execute_query(delta_sql)

    if not stats:
        raise HTTPException(status_code=404, detail="No ESG data found for the specified filters")

    # ── 4. Build rich context string for GPT ──────────────────────────────────
    context_parts = []
    for row in stats:
        summaries = _parse_summaries(row.get("impact_summaries"))[:3]
        context_parts.append(
            f"\n[{row['esg_category'].upper()}] "
            f"{row['article_count']} articles | "
            f"Avg sentiment: {row['avg_sentiment']} | "
            f"Critical: {row['critical_count']} | Supportive: {row['supportive_count']}\n"
            f"Key insights: {'; '.join(summaries)}"
        )

    if claims:
        context_parts.append("\n\n[CSR CLAIMS FROM OFFICIAL SOURCES]")
        for c in claims[:8]:
            metric = f" ({c['metric']})" if c.get('metric') else ""
            context_parts.append(f"• [{c['esg_category']}] {c['claim_text']}{metric}")

    if deltas:
        context_parts.append("\n\n[GAP ANALYSIS: OFFICIAL vs PUBLIC PERCEPTION]")
        for d in deltas[:6]:
            context_parts.append(
                f"• {d['esg_category']}/{d['sub_theme']}: "
                f"Alignment {d['alignment_score_quick']}/10 | "
                f"Gap: {d.get('gap_headline', 'N/A')}"
            )

    context = "\n".join(context_parts)[:4000]

    # ── 5. Define audience and report type instructions ───────────────────────
    audience_instructions = {
        "marketing": "Focus on narrative opportunities, communication gaps, and brand positioning for marketing campaigns.",
        "executive": "Focus on strategic risks, board-level ESG commitments, regulatory exposure, and financial materiality.",
        "investor":  "Focus on ESG rating implications, regulatory compliance, long-term value creation, and risk disclosure.",
        "communications": "Focus on messaging consistency, tone-of-voice risks, crisis scenarios, and stakeholder management.",
    }.get(request.audience, "Focus on actionable, data-driven insights.")

    report_type_instructions = {
        "executive_brief": (
            "Write a concise 4-paragraph executive brief. "
            "Sections: 1) Situation Overview 2) Key ESG Findings 3) Risks & Opportunities 4) Recommended Actions."
        ),
        "esg_deep_dive": (
            "Write a detailed ESG analysis with separate sections for Environmental, Social, and Governance. "
            "For each pillar: current state, key claims, public perception gap, and specific recommendations."
        ),
        "csr_vs_reality": (
            "Compare Danone's official CSR claims against public perception data point-by-point. "
            "Highlight where alignment is strong and where significant gaps exist. Be honest and balanced."
        ),
        "source_analysis": (
            "Analyse patterns by data source type (official Danone communications vs news vs NGO reports vs benchmarks). "
            "Identify which sources are most credible and what narrative each source type emphasises."
        ),
        "custom": request.custom_prompt or "Write a comprehensive ESG intelligence report.",
    }.get(request.report_type, "Write a comprehensive ESG report.")

    system_prompt = (
        "You are a senior ESG communications consultant specialising in FMCG companies, with deep expertise in Danone's "
        "dual mission (economic performance + social progress). You produce evidence-based, actionable reports. "
        "Always respond with ONLY valid JSON, no markdown fences, no preamble."
    )

    user_prompt = (
        f"Produce a {request.report_type.replace('_', ' ')} for Danone's {request.audience} team.\n"
        f"{audience_instructions}\n"
        f"{report_type_instructions}\n\n"
        f"RESPOND WITH THIS EXACT JSON STRUCTURE:\n"
        f'{{"title": "...", "executive_summary": "2-3 sentences", '
        f'"sections": [{{"heading": "...", "content": "3-5 sentences"}}], '
        f'"key_findings": ["finding 1", "finding 2", "finding 3"], '
        f'"recommendations": ["action 1", "action 2", "action 3"], '
        f'"risk_flags": ["risk 1", "risk 2"]}}\n\n'
        f"DATA:\n{context}"
    )

    # ── 6. Call GPT-5.4 ───────────────────────────────────────────────────────
    raw_result = _call_gpt(user_prompt, system=system_prompt, max_tokens=2500)

    try:
        # Strip potential markdown fences
        clean = raw_result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        report_data = json.loads(clean)
    except Exception:
        report_data = {
            "title": f"Danone ESG Report — {request.report_type.replace('_', ' ').title()}",
            "executive_summary": raw_result[:500] if raw_result else "Report generation failed.",
            "sections": [],
            "key_findings": [],
            "recommendations": [],
            "risk_flags": [],
        }

    return {
        "report_type": request.report_type,
        "audience": request.audience,
        "date_range": {"from": request.date_from, "to": request.date_to},
        "esg_categories": request.esg_categories,
        "report": report_data,
    }


@router.get("/history")
def get_report_history(limit: int = 20) -> dict:
    """Placeholder for stored report history (future enhancement)."""
    return {"message": "Report history storage coming soon", "limit": limit}
