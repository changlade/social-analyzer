"""
Reports router — ad-hoc AI report generation for marketing users.
Calls ai_query() via SQL to produce structured narrative reports
that marketing teams can export or copy into presentations.
"""

import json
from typing import Optional, List
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from databricks_client import execute_query, execute_ai_query, AI_ENDPOINT

router = APIRouter()


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
        return {"message": "No daily brief available for this date", "date": date}

    row = rows[0]
    # Parse the brief JSON
    try:
        row["brief"] = json.loads(row.get("brief_json_raw") or "{}")
    except Exception:
        row["brief"] = {}
    return row


@router.post("/generate")
def generate_report(request: ReportRequest = Body(...)) -> dict:
    """
    Generate an on-demand AI report by querying the gold layer and running ai_query().
    Returns a structured narrative report tailored to the specified audience.
    """
    cat_filter = "', '".join(request.esg_categories)
    conditions = [f"esg_category IN ('{cat_filter}')"]
    if request.date_from: conditions.append(f"scraped_date >= '{request.date_from}'")
    if request.date_to:   conditions.append(f"scraped_date <= '{request.date_to}'")
    where = " AND ".join(conditions)

    # Gather aggregated stats for the prompt
    stats_sql = f"""
    SELECT
      esg_category,
      COUNT(*)                           AS article_count,
      ROUND(AVG(sentiment_score), 3)     AS avg_sentiment,
      SUM(CASE WHEN danone_stance='critical'   THEN 1 ELSE 0 END) AS critical_count,
      SUM(CASE WHEN danone_stance='supportive' THEN 1 ELSE 0 END) AS supportive_count,
      COLLECT_LIST(
        CASE WHEN credibility_score >= 7
          THEN LEFT(impact_summary, 200) ELSE NULL END
      )                                  AS impact_summaries,
      MAX(scraped_date)                  AS latest_date
    FROM gold_esg_insights
    WHERE {where}
    GROUP BY esg_category
    """
    stats = execute_query(stats_sql)

    if not stats:
        raise HTTPException(status_code=404, detail="No data found for the specified filters")

    # Build context string for the LLM
    context_parts = []
    for row in stats:
        summaries_raw = row.get("impact_summaries") or []
        summaries = [s for s in (summaries_raw if isinstance(summaries_raw, list) else []) if s]
        context_parts.append(
            f"{row['esg_category']}: {row['article_count']} articles, "
            f"avg sentiment={row['avg_sentiment']}, "
            f"critical={row['critical_count']}, supportive={row['supportive_count']}. "
            f"Sample insights: {'; '.join(summaries[:3])}"
        )
    context = " | ".join(context_parts)

    audience_instructions = {
        "marketing": "Focus on narrative opportunities, communication gaps, and brand positioning.",
        "executive": "Focus on strategic risks, board-level ESG commitments, and financial materiality.",
        "investor":  "Focus on ESG rating implications, regulatory compliance, and long-term value.",
        "communications": "Focus on messaging, tone, crisis risks, and stakeholder management.",
    }.get(request.audience, "Focus on actionable insights.")

    report_type_instructions = {
        "executive_brief": "Write a 4-paragraph executive brief.",
        "esg_deep_dive": "Write a detailed 8-paragraph ESG analysis with sub-themes.",
        "csr_vs_reality": "Compare Danone's official ESG narrative against public perception data.",
        "source_analysis": "Analyse patterns by source type (official vs news vs NGO vs benchmarks).",
        "custom": request.custom_prompt or "Write a comprehensive ESG report.",
    }.get(request.report_type, "Write an ESG report.")

    prompt = (
        f"You are a senior ESG communications consultant producing a report for Danone's {request.audience} team. "
        f"{audience_instructions} {report_type_instructions} "
        f"Respond with valid JSON only: "
        f'{{"title": "<report title>", '
        f'"executive_summary": "<2-3 sentences>", '
        f'"sections": [{{"heading": "...", "content": "..."}}], '
        f'"key_findings": ["...", "..."], '
        f'"recommendations": ["...", "..."], '
        f'"risk_flags": ["...", "..."]}} '
        f"BASE THIS ON: {context[:3000]}"
    )

    raw_result = execute_ai_query(prompt)

    try:
        report_data = json.loads(raw_result)
    except Exception:
        report_data = {"raw": raw_result}

    return {
        "report_type": request.report_type,
        "audience": request.audience,
        "date_range": {"from": request.date_from, "to": request.date_to},
        "esg_categories": request.esg_categories,
        "stats_summary": stats,
        "report": report_data,
    }


@router.get("/history")
def get_report_history(limit: int = 20) -> dict:
    """Placeholder for stored report history (future enhancement)."""
    return {"message": "Report history storage coming soon", "limit": limit}
