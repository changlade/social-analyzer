-- ============================================================
-- Gold Layer: Public Sentiment — aggregated by ESG category & period
-- Danone Social Impact Analyzer
-- ============================================================
-- Aggregates scored public/NGO/news articles by ESG category
-- and calendar week to produce sentiment trends over time.
-- Also provides the most cited evidence snippets per category.
-- ============================================================

CREATE OR REPLACE MATERIALIZED VIEW gold_public_sentiment
COMMENT 'Weekly aggregated public sentiment by ESG category — news, NGO, social sources only'
TBLPROPERTIES ('quality' = 'gold')
AS
WITH public_articles AS (
  SELECT
    article_id,
    url,
    title,
    content_preview,
    source_type,
    esg_category,
    esg_sub_theme,
    sentiment_label,
    sentiment_score,
    danone_stance,
    credibility_score,
    published_at,
    scraped_date,
    DATE_TRUNC('week', scraped_date)                 AS week_start,
    YEAR(scraped_date)                               AS year,
    MONTH(scraped_date)                              AS month
  FROM LIVE.gold_esg_insights
  -- Public sources only: exclude official Danone communications
  WHERE source_type IN ('news', 'ngo', 'social', 'benchmark')
    AND esg_category IS NOT NULL
    AND esg_category != 'Not-ESG'
    AND sentiment_score IS NOT NULL
),
weekly_agg AS (
  SELECT
    esg_category,
    esg_sub_theme,
    week_start,
    year,
    month,
    COUNT(*)                                         AS article_count,
    AVG(sentiment_score)                             AS avg_sentiment_score,
    PERCENTILE(sentiment_score, 0.5)                 AS median_sentiment_score,
    SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) AS positive_count,
    SUM(CASE WHEN sentiment_label = 'neutral'  THEN 1 ELSE 0 END) AS neutral_count,
    SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative_count,
    SUM(CASE WHEN danone_stance = 'critical'   THEN 1 ELSE 0 END) AS critical_count,
    SUM(CASE WHEN danone_stance = 'supportive' THEN 1 ELSE 0 END) AS supportive_count,
    -- Top evidence snippets (most credible articles)
    COLLECT_LIST(
      STRUCT(content_preview AS snippet, url AS url, credibility_score AS score)
    )                                                AS evidence_list,
    -- Overall stance ratio
    ROUND(
      100.0 * SUM(CASE WHEN danone_stance = 'critical' THEN 1 ELSE 0 END) / COUNT(*), 1
    )                                                AS pct_critical
  FROM public_articles
  GROUP BY esg_category, esg_sub_theme, week_start, year, month
)
SELECT
  -- Composite period key for joining with CSR claims
  CONCAT(esg_category, '_', DATE_FORMAT(week_start, 'yyyy-MM-dd')) AS period_key,
  esg_category,
  esg_sub_theme,
  week_start,
  year,
  month,
  article_count,
  ROUND(avg_sentiment_score, 4)                      AS avg_sentiment_score,
  ROUND(median_sentiment_score, 4)                   AS median_sentiment_score,
  positive_count,
  neutral_count,
  negative_count,
  critical_count,
  supportive_count,
  pct_critical,
  -- Sentiment label for easy bucketing
  CASE
    WHEN avg_sentiment_score >= 0.05  THEN 'positive'
    WHEN avg_sentiment_score <= -0.05 THEN 'negative'
    ELSE 'neutral'
  END                                                AS overall_sentiment_label,
  -- Keep top 5 most credible evidence snippets
  SLICE(ARRAY_SORT(evidence_list, (l, r) -> r.score - l.score), 1, 5)
                                                     AS top_evidence,
  current_timestamp()                                AS _gold_at
FROM weekly_agg;
