-- ============================================================
-- Gold Layer: Daily Executive Summary
-- Danone Social Impact Analyzer
-- ============================================================
-- Produces one row per day with an AI-generated executive brief
-- covering all ESG categories. Designed for the Overview page
-- "Today's Insights" widget and for export to marketing reports.
-- ============================================================

CREATE OR REPLACE MATERIALIZED VIEW gold_daily_summary
COMMENT 'AI-generated daily ESG executive brief across all categories — for the Overview dashboard'
TBLPROPERTIES ('quality' = 'gold')
AS
WITH daily_stats AS (
  SELECT
    scraped_date                                     AS report_date,
    COUNT(*)                                         AS total_articles,
    COUNT(DISTINCT url)                              AS unique_sources,
    COUNT(DISTINCT source_type)                      AS source_types,
    AVG(sentiment_score)                             AS avg_sentiment,
    SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) AS positive_count,
    SUM(CASE WHEN sentiment_label = 'neutral'  THEN 1 ELSE 0 END) AS neutral_count,
    SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative_count,
    SUM(CASE WHEN danone_stance = 'critical'   THEN 1 ELSE 0 END) AS critical_count,
    SUM(CASE WHEN esg_category = 'Environmental' THEN 1 ELSE 0 END) AS env_count,
    SUM(CASE WHEN esg_category = 'Social'        THEN 1 ELSE 0 END) AS social_count,
    SUM(CASE WHEN esg_category = 'Governance'    THEN 1 ELSE 0 END) AS gov_count,
    -- Top headlines of the day (highest credibility)
    CONCAT_WS(' || ',
      COLLECT_LIST(
        CASE WHEN credibility_score >= 7
          THEN CONCAT('[', source_type, '] ', LEFT(title, 80))
          ELSE NULL END
      )
    )                                                AS top_headlines,
    -- Key topics across all articles
    FLATTEN(COLLECT_LIST(COALESCE(sentiment_topics, ARRAY())))
                                                     AS all_topics_flat
  FROM LIVE.gold_esg_insights
  WHERE scraped_date = CURRENT_DATE()
  GROUP BY scraped_date
),
topic_counts AS (
  SELECT
    report_date,
    total_articles,
    unique_sources,
    source_types,
    ROUND(avg_sentiment, 4)                          AS avg_sentiment,
    positive_count,
    neutral_count,
    negative_count,
    critical_count,
    env_count,
    social_count,
    gov_count,
    top_headlines,
    all_topics_flat
  FROM daily_stats
)
SELECT
  report_date,
  total_articles,
  unique_sources,
  source_types,
  avg_sentiment,
  positive_count,
  neutral_count,
  negative_count,
  critical_count,
  env_count,
  social_count,
  gov_count,
  top_headlines,

  -- ── AI Executive Brief ────────────────────────────────────────────────────
  ai_query(
    '${ai_endpoint_name}',
    CONCAT(
      'You are Danone''s ESG communications director. Write a concise daily intelligence brief ',
      'for the marketing leadership team based on today''s scraped data. ',
      'Tone: professional, direct, actionable. Highlight surprises and risks. ',
      'Respond ONLY with valid JSON (no markdown): ',
      '{"headline": "<one compelling sentence summarising the day>", ',
      '"executive_brief": "<3-4 sentences covering main ESG developments>", ',
      '"top_risk": "<biggest reputational or ESG risk today>", ',
      '"top_opportunity": "<best marketing or communication opportunity today>", ',
      '"esg_pulse": {"environmental": <0-10>, "social": <0-10>, "governance": <0-10>}, ',
      '"recommended_actions": [<up to 3 specific, actionable recommendations for the marketing team>]} ',
      'TODAY''S DATA: ',
      CAST(total_articles AS STRING), ' articles from ', CAST(unique_sources AS STRING), ' sources. ',
      'Sentiment avg=', CAST(ROUND(avg_sentiment, 2) AS STRING),
      ' (', CAST(positive_count AS STRING), ' pos / ',
      CAST(neutral_count AS STRING), ' neutral / ',
      CAST(negative_count AS STRING), ' neg). ',
      'Critical coverage: ', CAST(critical_count AS STRING), ' articles. ',
      'ESG split — Environmental: ', CAST(env_count AS STRING),
      ', Social: ', CAST(social_count AS STRING),
      ', Governance: ', CAST(gov_count AS STRING), '. ',
      'TOP HEADLINES: ', LEFT(COALESCE(top_headlines, 'No headlines today'), 1500)
    )
  )                                                  AS brief_json_raw,

  -- Flat parsed fields for quick dashboard display
  TRY(get_json_object(
    ai_query('${ai_endpoint_name}',
      CONCAT('Return only JSON: {"headline": "<one sentence>"}. ',
             'Summarise ', CAST(total_articles AS STRING), ' articles about Danone ESG today, ',
             'sentiment=', CAST(ROUND(avg_sentiment,2) AS STRING))
    ), '$.headline'))                                AS headline,

  current_timestamp()                                AS _gold_at
FROM topic_counts;
