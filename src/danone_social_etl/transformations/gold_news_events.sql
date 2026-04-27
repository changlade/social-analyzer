-- ============================================================
-- Gold Layer: Breaking News & Crisis Events
-- Danone Social Impact Analyzer
-- ============================================================
-- Reads from gold_esg_insights (articles scraped via NEWS_EVENTS_TOPICS)
-- and adds a structured AI event classification: type, severity, region,
-- affected product, financial impact estimate, and recommended response.
--
-- Feeds:
--   - GET /api/news-events (backend router)
--   - query_news_events tool (AI Assistant chatbot)
--   - NewsEvents.tsx dashboard page
-- ============================================================

CREATE OR REPLACE MATERIALIZED VIEW gold_news_events
COMMENT 'Breaking news and crisis events — recent Danone incidents with AI-powered impact classification'
TBLPROPERTIES (
  'quality'                              = 'gold',
  'pipelines.autoOptimize.managed'       = 'true'
)
AS
WITH news_articles AS (
  SELECT
    article_id,
    url,
    title,
    content_preview,
    clean_content,
    source_type,
    search_topic,
    published_at,
    scraped_date,
    sentiment_label,
    sentiment_score,
    danone_stance,
    esg_category,
    esg_sub_theme,
    impact_summary,
    credibility_score,
    _gold_at
  FROM LIVE.gold_esg_insights
  WHERE search_topic IN (
    'product_recall',
    'regulatory_action',
    'crisis_apac',
    'crisis_media',
    'market_impact'
  )
  AND scraped_date >= CURRENT_DATE() - INTERVAL 90 DAYS
  AND clean_content IS NOT NULL
),
classified AS (
  SELECT
    *,
    ai_query(
      '${ai_endpoint_name}',
      CONCAT(
        'You are a crisis communications analyst for Danone. ',
        'Classify the following news article as a structured event. ',
        'Respond ONLY with valid JSON, no markdown: ',
        '{',
        '"event_type": "<one of: recall, regulatory, financial, reputational, positive, other>",',
        '"severity": "<one of: low, medium, high, critical>",',
        '"affected_region": "<geographic region or global, e.g. APAC, Europe, France, Global>",',
        '"affected_product": "<specific product or product line, or null if not applicable>",',
        '"financial_impact_estimate": "<estimated financial impact or null if unknown>",',
        '"recommended_response": "<one concrete action Danone communications team should take>"',
        '} ',
        'Article title: ', title, '. ',
        'Article content: ', LEFT(clean_content, 2000)
      )
    ) AS event_json_raw
  FROM news_articles
)
SELECT
  article_id,
  url,
  title,
  content_preview,
  clean_content,
  source_type,
  search_topic,
  published_at,
  scraped_date,
  sentiment_label,
  sentiment_score,
  danone_stance,
  esg_category,
  esg_sub_theme,
  impact_summary,
  credibility_score,

  -- Parsed event classification fields
  event_json_raw,
  get_json_object(event_json_raw, '$.event_type')             AS event_type,
  get_json_object(event_json_raw, '$.severity')               AS severity,
  get_json_object(event_json_raw, '$.affected_region')        AS affected_region,
  get_json_object(event_json_raw, '$.affected_product')       AS affected_product,
  get_json_object(event_json_raw, '$.financial_impact_estimate') AS financial_impact_estimate,
  get_json_object(event_json_raw, '$.recommended_response')   AS recommended_response,

  _gold_at,
  current_timestamp()                                          AS _news_events_at
FROM classified;
