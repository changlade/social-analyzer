-- ============================================================
-- Silver Layer: Pre-scored sentiment (lightweight gate)
-- Danone Social Impact Analyzer
-- ============================================================
-- Uses Databricks ai_query() with the GPT 5.4 endpoint to run
-- a fast, structured sentiment scoring pass on every cleaned article.
-- Output feeds gold_public_sentiment and the impact delta analysis.
--
-- The structured prompt enforces a JSON response so the result
-- can be parsed directly in Gold SQL using from_json().
--
-- Cost optimisation: only articles with content_length >= 150 chars
-- and non-English or high-priority topics get the full LLM call.
-- Short snippets use the esg_hint as a lightweight pre-filter.
-- ============================================================

CREATE OR REPLACE MATERIALIZED VIEW silver_sentiment_scored
COMMENT 'Every cleaned article scored for sentiment (compound -1 to +1) and key topics via ai_query()'
TBLPROPERTIES (
  'quality'      = 'silver',
  'pipelines.autoOptimize.managed' = 'true'
)
AS
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
  _silver_at,

  -- ── LLM Sentiment Analysis ────────────────────────────────────────────────
  -- Returns JSON: {"sentiment": "positive|neutral|negative",
  --                "score": <float -1.0 to 1.0>,
  --                "confidence": <float 0.0 to 1.0>,
  --                "key_topics": ["...", "..."],
  --                "danone_stance": "supportive|critical|neutral|mixed"}
  ai_query(
    '${ai_endpoint_name}',
    CONCAT(
      'You are an ESG analyst specialising in Danone. Analyse the sentiment of the following text ',
      'about Danone (or related to Danone''s social/environmental impact). ',
      'Respond ONLY with valid JSON (no markdown, no explanation) in this exact schema: ',
      '{"sentiment": "positive|neutral|negative", ',
      '"score": <float between -1.0 and 1.0>, ',
      '"confidence": <float between 0.0 and 1.0>, ',
      '"key_topics": [<up to 5 short topic strings>], ',
      '"danone_stance": "supportive|critical|neutral|mixed"} ',
      'TEXT: ', LEFT(clean_content, 3000)
    )
  )                                                  AS sentiment_json_raw,

  current_timestamp()                                AS _scored_at
FROM LIVE.silver_cleaned_articles
WHERE clean_content IS NOT NULL
  AND content_length >= 150;
