"""
Insights router — ESG article explorer with filters.
Powers the "Insights" page in the frontend.
"""

from typing import Optional, List
from fastapi import APIRouter, Query
from databricks_client import execute_query

router = APIRouter()


@router.get("")
def get_insights(
    esg_category: Optional[str]  = Query(None, description="Environmental|Social|Governance|Cross-ESG"),
    source_type:  Optional[str]  = Query(None, description="official|news|ngo|social|benchmark"),
    sentiment:    Optional[str]  = Query(None, description="positive|neutral|negative"),
    stance:       Optional[str]  = Query(None, description="supportive|critical|neutral|mixed"),
    date_from:    Optional[str]  = Query(None, description="YYYY-MM-DD"),
    date_to:      Optional[str]  = Query(None, description="YYYY-MM-DD"),
    search:       Optional[str]  = Query(None, description="Full-text keyword search on title"),
    limit:        int            = Query(50, ge=1, le=200),
    offset:       int            = Query(0,  ge=0),
) -> dict:
    """Return paginated ESG-classified articles with filters."""

    conditions = ["1=1"]
    if esg_category: conditions.append(f"esg_category = '{esg_category}'")
    if source_type:  conditions.append(f"source_type = '{source_type}'")
    if sentiment:    conditions.append(f"sentiment_label = '{sentiment}'")
    if stance:       conditions.append(f"danone_stance = '{stance}'")
    if date_from:    conditions.append(f"scraped_date >= '{date_from}'")
    if date_to:      conditions.append(f"scraped_date <= '{date_to}'")
    if search:       conditions.append(f"lower(title) LIKE '%{search.lower()}%'")

    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      article_id,
      url,
      title,
      content_preview,
      source_type,
      search_topic,
      esg_category,
      esg_sub_theme,
      sentiment_label,
      ROUND(sentiment_score, 3)      AS sentiment_score,
      danone_stance,
      credibility_score,
      is_official_csr,
      impact_summary,
      scraped_date,
      published_at,
      language,
      scraper
    FROM gold_esg_insights
    WHERE {where}
    ORDER BY scraped_date DESC, credibility_score DESC
    LIMIT {limit} OFFSET {offset}
    """
    rows = execute_query(sql)

    count_sql = f"SELECT COUNT(*) AS total FROM gold_esg_insights WHERE {where}"
    count = execute_query(count_sql)
    total = count[0]["total"] if count else 0

    return {"total": total, "offset": offset, "limit": limit, "items": rows}


@router.get("/breakdown")
def get_esg_breakdown(
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
) -> List[dict]:
    """Return article counts and avg sentiment grouped by ESG category."""
    conditions = ["esg_category IS NOT NULL", "esg_category != 'Not-ESG'"]
    if date_from: conditions.append(f"scraped_date >= '{date_from}'")
    if date_to:   conditions.append(f"scraped_date <= '{date_to}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      esg_category,
      COUNT(*)                           AS article_count,
      ROUND(AVG(sentiment_score), 3)     AS avg_sentiment,
      SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) AS positive_count,
      SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) AS negative_count,
      SUM(CASE WHEN danone_stance='critical'   THEN 1 ELSE 0 END) AS critical_count,
      ROUND(AVG(credibility_score), 1)   AS avg_credibility
    FROM gold_esg_insights
    WHERE {where}
    GROUP BY esg_category
    ORDER BY article_count DESC
    """
    return execute_query(sql)


@router.get("/sub-themes")
def get_sub_themes(
    esg_category: Optional[str] = Query(None),
    date_from:    Optional[str] = Query(None),
    date_to:      Optional[str] = Query(None),
) -> List[dict]:
    """Return article counts by ESG sub-theme."""
    conditions = ["esg_sub_theme IS NOT NULL"]
    if esg_category: conditions.append(f"esg_category = '{esg_category}'")
    if date_from:    conditions.append(f"scraped_date >= '{date_from}'")
    if date_to:      conditions.append(f"scraped_date <= '{date_to}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      esg_category,
      esg_sub_theme,
      COUNT(*) AS article_count,
      ROUND(AVG(sentiment_score), 3) AS avg_sentiment
    FROM gold_esg_insights
    WHERE {where}
    GROUP BY esg_category, esg_sub_theme
    ORDER BY article_count DESC
    LIMIT 30
    """
    return execute_query(sql)
