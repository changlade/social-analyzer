"""
Sources router — breakdown by data source, scraper run logs, coverage map.
"""

from typing import Optional, List
from fastapi import APIRouter, Query
from databricks_client import execute_query

router = APIRouter()


@router.get("")
def get_source_breakdown(
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
) -> List[dict]:
    """Return article counts and sentiment by source_type and search_topic."""
    conditions = ["1=1"]
    if date_from: conditions.append(f"scraped_date >= '{date_from}'")
    if date_to:   conditions.append(f"scraped_date <= '{date_to}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      source_type,
      search_topic,
      COUNT(*)                           AS article_count,
      ROUND(AVG(sentiment_score), 3)     AS avg_sentiment,
      ROUND(AVG(credibility_score), 1)   AS avg_credibility,
      SUM(CASE WHEN danone_stance='critical'   THEN 1 ELSE 0 END) AS critical_count,
      SUM(CASE WHEN danone_stance='supportive' THEN 1 ELSE 0 END) AS supportive_count,
      COUNT(DISTINCT scraped_date)       AS active_days,
      MAX(scraped_date)                  AS last_seen
    FROM gold_esg_insights
    WHERE {where}
    GROUP BY source_type, search_topic
    ORDER BY source_type, article_count DESC
    """
    return execute_query(sql)


@router.get("/run-log")
def get_scraper_run_log(limit: int = Query(30, ge=1, le=100)) -> List[dict]:
    """Return recent scraper run statistics."""
    sql = f"""
    SELECT
      source_type,
      record_count,
      run_ts,
      _ingested_at
    FROM bronze_scraper_run_log
    WHERE source_type = 'total'
    ORDER BY run_ts DESC
    LIMIT {limit}
    """
    return execute_query(sql)


@router.get("/coverage")
def get_coverage_by_date(
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
) -> List[dict]:
    """Return daily article counts per source_type for coverage heatmap."""
    conditions = ["1=1"]
    if date_from: conditions.append(f"scraped_date >= '{date_from}'")
    if date_to:   conditions.append(f"scraped_date <= '{date_to}'")
    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      scraped_date,
      source_type,
      COUNT(*) AS article_count
    FROM gold_esg_insights
    WHERE {where}
    GROUP BY scraped_date, source_type
    ORDER BY scraped_date ASC, source_type
    """
    return execute_query(sql)
