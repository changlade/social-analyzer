"""
News Events router — breaking news, recalls, regulatory actions, and crises.
Queries the gold_news_events table which adds AI-powered event classification
(type, severity, region, affected product, recommended response) on top of
the base gold_esg_insights data.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter
from databricks_client import execute_query

logger = logging.getLogger("danone.social.news_events")

router = APIRouter()

_NEWS_TOPICS = (
    "'product_recall','regulatory_action','crisis_apac','crisis_media','market_impact'"
)


@router.get("")
def get_news_events(
    severity:   Optional[str] = None,
    event_type: Optional[str] = None,
    days:       int = 90,
    limit:      int = 50,
    offset:     int = 0,
) -> dict:
    """
    Return recent breaking news events with AI classification.
    Filterable by severity (low/medium/high/critical) and event_type
    (recall/regulatory/financial/reputational/positive/other).
    """
    conditions = [f"scraped_date >= CURRENT_DATE() - INTERVAL {min(days, 365)} DAYS"]
    if severity:
        conditions.append(f"severity = '{severity}'")
    if event_type:
        conditions.append(f"event_type = '{event_type}'")

    where = " AND ".join(conditions)

    sql = f"""
    SELECT
      article_id,
      url,
      title,
      content_preview,
      source_type,
      search_topic,
      scraped_date,
      published_at,
      sentiment_label,
      sentiment_score,
      danone_stance,
      esg_category,
      impact_summary,
      credibility_score,
      event_type,
      severity,
      affected_region,
      affected_product,
      financial_impact_estimate,
      recommended_response
    FROM gold_news_events
    WHERE {where}
    ORDER BY
      CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high'     THEN 2
        WHEN 'medium'   THEN 3
        WHEN 'low'      THEN 4
        ELSE 5
      END,
      scraped_date DESC,
      credibility_score DESC
    LIMIT {limit} OFFSET {offset}
    """

    count_sql = f"SELECT COUNT(*) AS total FROM gold_news_events WHERE {where}"

    rows  = execute_query(sql)
    total_rows = execute_query(count_sql)
    total = int(total_rows[0]["total"]) if total_rows else 0

    return {"total": total, "offset": offset, "limit": limit, "items": rows}


@router.get("/summary")
def get_news_events_summary(days: int = 30) -> dict:
    """
    Aggregate count of events by severity and by event_type for the last N days.
    Used for the severity badge cards on the News Events dashboard.
    """
    by_severity_sql = f"""
    SELECT
      COALESCE(severity, 'unknown')   AS severity,
      COUNT(*)                        AS count
    FROM gold_news_events
    WHERE scraped_date >= CURRENT_DATE() - INTERVAL {min(days, 365)} DAYS
    GROUP BY severity
    ORDER BY
      CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high'     THEN 2
        WHEN 'medium'   THEN 3
        WHEN 'low'      THEN 4
        ELSE 5
      END
    """

    by_type_sql = f"""
    SELECT
      COALESCE(event_type, 'other')   AS event_type,
      COUNT(*)                        AS count,
      ROUND(AVG(sentiment_score), 3)  AS avg_sentiment
    FROM gold_news_events
    WHERE scraped_date >= CURRENT_DATE() - INTERVAL {min(days, 365)} DAYS
    GROUP BY event_type
    ORDER BY count DESC
    """

    by_region_sql = f"""
    SELECT
      COALESCE(affected_region, 'Unknown') AS region,
      COUNT(*)                             AS count,
      COLLECT_LIST(
        CASE WHEN severity IN ('critical','high') THEN title ELSE NULL END
      )                                    AS critical_headlines
    FROM gold_news_events
    WHERE scraped_date >= CURRENT_DATE() - INTERVAL {min(days, 365)} DAYS
    GROUP BY affected_region
    ORDER BY count DESC
    LIMIT 15
    """

    return {
        "days": days,
        "by_severity": execute_query(by_severity_sql),
        "by_type":     execute_query(by_type_sql),
        "by_region":   execute_query(by_region_sql),
    }


@router.get("/timeline")
def get_news_events_timeline(days: int = 30) -> dict:
    """
    Daily event count broken down by severity for the last N days.
    Used for the area/bar sparkline chart on the News Events page.
    """
    sql = f"""
    SELECT
      scraped_date,
      COUNT(*)                                                    AS total,
      SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END)     AS critical,
      SUM(CASE WHEN severity = 'high'     THEN 1 ELSE 0 END)     AS high,
      SUM(CASE WHEN severity = 'medium'   THEN 1 ELSE 0 END)     AS medium,
      SUM(CASE WHEN severity = 'low'      THEN 1 ELSE 0 END)     AS low,
      ROUND(AVG(sentiment_score), 3)                              AS avg_sentiment
    FROM gold_news_events
    WHERE scraped_date >= CURRENT_DATE() - INTERVAL {min(days, 90)} DAYS
    GROUP BY scraped_date
    ORDER BY scraped_date ASC
    """
    return {"days": days, "timeline": execute_query(sql)}


@router.get("/latest-critical")
def get_latest_critical(limit: int = 5) -> dict:
    """
    The most recent critical/high severity events.
    Used for the alert banner on the Overview page (if any critical events exist).
    """
    sql = f"""
    SELECT
      article_id, url, title, scraped_date, severity, event_type,
      affected_region, affected_product, recommended_response,
      sentiment_score, impact_summary
    FROM gold_news_events
    WHERE severity IN ('critical', 'high')
      AND scraped_date >= CURRENT_DATE() - INTERVAL 14 DAYS
    ORDER BY
      CASE severity WHEN 'critical' THEN 1 ELSE 2 END,
      scraped_date DESC
    LIMIT {limit}
    """
    rows = execute_query(sql)
    return {"items": rows, "has_alerts": len(rows) > 0}
