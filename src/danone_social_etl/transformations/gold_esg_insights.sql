-- ============================================================
-- Gold Layer: ESG Insights — per-article categorization
-- Danone Social Impact Analyzer
-- ============================================================
-- For each scored article, calls ai_query() to produce a full
-- ESG classification with category, sub-theme, confidence,
-- extracted claims, and a 2-sentence impact summary.
-- This is the primary table powering the Insights Explorer.
-- ============================================================

CREATE OR REPLACE MATERIALIZED VIEW gold_esg_insights
COMMENT 'Per-article ESG classification, extracted claims, and impact summary — powers the Insights Explorer UI'
TBLPROPERTIES (
  'quality'      = 'gold',
  'pipelines.autoOptimize.managed' = 'true'
)
AS
WITH sentiment_parsed AS (
  SELECT
    *,
    -- Parse the sentiment JSON returned by the LLM
    from_json(sentiment_json_raw, 'STRUCT<
      sentiment STRING,
      score DOUBLE,
      confidence DOUBLE,
      key_topics ARRAY<STRING>,
      danone_stance STRING
    >')                                              AS sentiment_struct
  FROM LIVE.silver_sentiment_scored
),
esg_classified AS (
  SELECT
    article_id,
    url,
    url_hash,
    title,
    content_preview,
    clean_content,
    content_length,
    source_type,
    search_topic,
    esg_hint,
    language,
    published_at,
    scraped_date,
    scraper,
    _scrape_run_id,
    scraped_at,
    sentiment_struct,
    sentiment_json_raw,
    -- ── Deep ESG Classification via ai_query() ────────────────────────────
    -- Returns JSON matching schema below
    ai_query(
      '${ai_endpoint_name}',
      CONCAT(
        'You are a senior ESG analyst specialising in corporate social responsibility for FMCG companies, ',
        'with deep expertise in Danone''s dual mission (economic performance + social progress). ',
        'Classify the following text and extract structured ESG intelligence. ',
        'Respond ONLY with valid JSON (no markdown, no code fences) in exactly this schema: ',
        '{"esg_category": "Environmental|Social|Governance|Cross-ESG|Not-ESG", ',
        '"esg_sub_theme": "<one specific sub-theme, e.g. Carbon Footprint, Worker Wellbeing, Board Diversity>", ',
        '"confidence": <0.0-1.0>, ',
        '"key_claims": [<up to 3 specific factual claims or data points extracted>], ',
        '"is_official_csr": <true if from Danone official source, false if public/watchdog>, ',
        '"impact_summary": "<2 sentences: what this means for Danone''s social impact>", ',
        '"credibility_score": <0-10, 10=highly credible primary source, 0=anonymous rumour>} ',
        'SOURCE TYPE: ', source_type, ' | TOPIC: ', search_topic, ' | TITLE: ', title, ' ',
        'TEXT: ', LEFT(clean_content, 3000)
      )
    )                                                AS esg_json_raw
  FROM sentiment_parsed
)
SELECT
  article_id,
  url,
  title,
  content_preview,
  clean_content,
  source_type,
  search_topic,
  esg_hint,
  language,
  published_at,
  scraped_date,
  scraper,
  _scrape_run_id,
  scraped_at,

  -- ── Sentiment fields (flattened) ──────────────────────────────────────────
  sentiment_struct.sentiment                         AS sentiment_label,
  sentiment_struct.score                             AS sentiment_score,
  sentiment_struct.confidence                        AS sentiment_confidence,
  sentiment_struct.key_topics                        AS sentiment_topics,
  sentiment_struct.danone_stance                     AS danone_stance,
  sentiment_json_raw,

  -- ── ESG Classification fields (parsed) ───────────────────────────────────
  from_json(esg_json_raw, 'STRUCT<
    esg_category    STRING,
    esg_sub_theme   STRING,
    confidence      DOUBLE,
    key_claims      ARRAY<STRING>,
    is_official_csr BOOLEAN,
    impact_summary  STRING,
    credibility_score INT
  >')                                                AS esg_struct,
  esg_json_raw,

  -- ── Convenience flat columns ──────────────────────────────────────────────
  get_json_object(esg_json_raw, '$.esg_category')         AS esg_category,
  get_json_object(esg_json_raw, '$.esg_sub_theme')        AS esg_sub_theme,
  TRY_CAST(get_json_object(esg_json_raw, '$.confidence') AS DOUBLE)
                                                          AS esg_confidence,
  TRY_CAST(get_json_object(esg_json_raw, '$.is_official_csr') AS BOOLEAN)
                                                          AS is_official_csr,
  get_json_object(esg_json_raw, '$.impact_summary')       AS impact_summary,
  TRY_CAST(get_json_object(esg_json_raw, '$.credibility_score') AS INT)
                                                          AS credibility_score,

  current_timestamp()                                AS _gold_at
FROM esg_classified;
