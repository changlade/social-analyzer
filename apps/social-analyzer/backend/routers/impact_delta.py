"""
Impact Delta router — CSR claims vs public reality.
Powers the "Impact Delta" page: the core differentiator of the app.
"""

from typing import Optional, List
from fastapi import APIRouter, Query
from databricks_client import execute_query

router = APIRouter()


@router.get("")
def get_impact_delta(
    esg_category: Optional[str] = Query(None),
    min_alignment: Optional[int] = Query(None, ge=0, le=10, description="Min alignment score"),
    max_alignment: Optional[int] = Query(None, ge=0, le=10, description="Max alignment score (use low values to find gaps)"),
    risk_level:   Optional[str]  = Query(None, description="Low|Medium|High|Critical"),
) -> List[dict]:
    """
    Return ESG impact delta records: official Danone claims vs public reality.
    Lower alignment_score = bigger gap between what Danone says and what public thinks.
    """
    conditions = ["1=1"]
    if esg_category:   conditions.append(f"esg_category = '{esg_category}'")
    if min_alignment is not None: conditions.append(f"alignment_score_quick >= {min_alignment}")
    if max_alignment is not None: conditions.append(f"alignment_score_quick <= {max_alignment}")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      delta_id,
      esg_category,
      sub_theme,
      claim_count,
      total_articles,
      ROUND(period_avg_sentiment, 3) AS period_avg_sentiment,
      ROUND(avg_pct_critical, 1)     AS pct_critical,
      dominant_sentiment,
      alignment_score_quick,
      latest_claim_date,
      latest_week,
      analysis_date,
      -- Parse the rich delta JSON for the response
      TRY(get_json_object(delta_json_raw, '$.alignment_label'))        AS alignment_label,
      TRY(get_json_object(delta_json_raw, '$.gap_headline'))           AS gap_headline,
      TRY(get_json_object(delta_json_raw, '$.official_narrative'))     AS official_narrative,
      TRY(get_json_object(delta_json_raw, '$.public_narrative'))       AS public_narrative,
      TRY(get_json_object(delta_json_raw, '$.marketing_opportunity'))  AS marketing_opportunity,
      TRY(get_json_object(delta_json_raw, '$.risk_level'))             AS risk_level,
      delta_json_raw
    FROM gold_impact_delta
    WHERE {where}
    ORDER BY alignment_score_quick ASC NULLS LAST
    """
    rows = execute_query(sql)

    # Apply risk_level filter in Python (avoids escaping issues with parsed JSON column)
    if risk_level:
        rows = [r for r in rows if r.get("risk_level") == risk_level]

    return rows


@router.get("/claims")
def get_csr_claims(
    esg_category: Optional[str] = Query(None),
    claim_type:   Optional[str] = Query(None, description="commitment|achievement|target|certification"),
    limit: int = Query(50, ge=1, le=200),
) -> List[dict]:
    """Return individual CSR claims extracted from official Danone sources."""
    conditions = ["claim_text IS NOT NULL"]
    if esg_category: conditions.append(f"esg_category = '{esg_category}'")
    if claim_type:   conditions.append(f"claim_type = '{claim_type}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      claim_id,
      esg_category,
      sub_theme,
      claim_text,
      metric,
      timeframe,
      claim_type,
      credibility_score,
      source_type,
      url,
      title,
      scraped_date
    FROM gold_csr_claims
    WHERE {where}
    ORDER BY credibility_score DESC, scraped_date DESC
    LIMIT {limit}
    """
    return execute_query(sql)


@router.get("/summary")
def get_delta_summary() -> List[dict]:
    """High-level alignment summary per ESG category — for the Overview donut."""
    sql = """
    SELECT
      esg_category,
      ROUND(AVG(alignment_score_quick), 1)          AS avg_alignment,
      COUNT(*)                                       AS theme_count,
      SUM(CASE WHEN alignment_score_quick <= 4 THEN 1 ELSE 0 END) AS divergent_themes,
      TRY(get_json_object(MAX(delta_json_raw), '$.risk_level'))   AS max_risk_level
    FROM gold_impact_delta
    WHERE alignment_score_quick IS NOT NULL
    GROUP BY esg_category
    ORDER BY avg_alignment ASC
    """
    return execute_query(sql)
