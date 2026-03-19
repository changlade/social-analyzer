"""
Sentiment router — timeline and trend analysis.
Powers the sentiment trend charts in the Overview and Insights pages.
"""

from typing import Optional, List
from fastapi import APIRouter, Query
from databricks_client import execute_query

router = APIRouter()


@router.get("/timeline")
def get_sentiment_timeline(
    esg_category: Optional[str] = Query(None),
    source_type:  Optional[str] = Query(None),
    granularity:  str           = Query("week", description="day|week|month"),
    date_from:    Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to:      Optional[str] = Query(None, description="YYYY-MM-DD"),
) -> List[dict]:
    """
    Return sentiment trend over time, aggregated by the requested granularity.
    Includes both official (CSR) and public source breakdown when not filtered.
    """
    trunc_expr = {
        "day":   "DATE_TRUNC('day',   scraped_date)",
        "week":  "DATE_TRUNC('week',  scraped_date)",
        "month": "DATE_TRUNC('month', scraped_date)",
    }.get(granularity, "DATE_TRUNC('week', scraped_date)")

    conditions = ["sentiment_score IS NOT NULL"]
    if esg_category: conditions.append(f"esg_category = '{esg_category}'")
    if source_type:  conditions.append(f"source_type = '{source_type}'")
    if date_from:    conditions.append(f"scraped_date >= '{date_from}'")
    if date_to:      conditions.append(f"scraped_date <= '{date_to}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      {trunc_expr}                               AS period,
      ROUND(AVG(sentiment_score), 4)             AS avg_sentiment,
      ROUND(AVG(CASE WHEN source_type IN ('official','benchmark')
                     THEN sentiment_score END), 4) AS official_sentiment,
      ROUND(AVG(CASE WHEN source_type IN ('news','ngo','social')
                     THEN sentiment_score END), 4) AS public_sentiment,
      COUNT(*)                                   AS article_count,
      SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) AS positive_count,
      SUM(CASE WHEN sentiment_label='neutral'  THEN 1 ELSE 0 END) AS neutral_count,
      SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) AS negative_count,
      SUM(CASE WHEN danone_stance='critical'   THEN 1 ELSE 0 END) AS critical_count
    FROM gold_esg_insights
    WHERE {where}
    GROUP BY {trunc_expr}
    ORDER BY period ASC
    """
    return execute_query(sql)


@router.get("/by-source")
def get_sentiment_by_source(
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
) -> List[dict]:
    """Sentiment breakdown by source type."""
    conditions = ["sentiment_score IS NOT NULL"]
    if date_from: conditions.append(f"scraped_date >= '{date_from}'")
    if date_to:   conditions.append(f"scraped_date <= '{date_to}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      source_type,
      COUNT(*)                           AS article_count,
      ROUND(AVG(sentiment_score), 4)     AS avg_sentiment,
      SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) AS positive_count,
      SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) AS negative_count,
      ROUND(AVG(credibility_score), 1)   AS avg_credibility
    FROM gold_esg_insights
    WHERE {where}
    GROUP BY source_type
    ORDER BY article_count DESC
    """
    return execute_query(sql)


@router.get("/kpis")
def get_sentiment_kpis(
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
) -> dict:
    """High-level KPIs for the Overview page hero section."""
    conditions = ["1=1"]
    if date_from: conditions.append(f"scraped_date >= '{date_from}'")
    if date_to:   conditions.append(f"scraped_date <= '{date_to}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      COUNT(*)                                          AS total_articles,
      COUNT(DISTINCT url)                               AS unique_urls,
      COUNT(DISTINCT source_type)                       AS source_types,
      ROUND(AVG(sentiment_score), 3)                    AS overall_sentiment,
      ROUND(AVG(CASE WHEN source_type IN ('official','benchmark')
                     THEN sentiment_score END), 3)      AS official_sentiment,
      ROUND(AVG(CASE WHEN source_type IN ('news','ngo','social')
                     THEN sentiment_score END), 3)      AS public_sentiment,
      SUM(CASE WHEN danone_stance='critical' THEN 1 ELSE 0 END) AS critical_articles,
      COUNT(DISTINCT esg_category)                      AS esg_categories_covered,
      MAX(scraped_date)                                 AS latest_scrape_date
    FROM gold_esg_insights
    WHERE {where}
    """
    rows = execute_query(sql)
    return rows[0] if rows else {}
