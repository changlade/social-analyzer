-- ============================================================
-- Gold Layer: CSR Claims extracted from official Danone sources
-- Danone Social Impact Analyzer
-- ============================================================
-- Filters gold_esg_insights to only official/benchmark sources,
-- then uses ai_query() to extract structured, verifiable CSR claims
-- in a format that can be compared against public sentiment data.
-- One row per specific claim (exploded from the array).
-- ============================================================

CREATE OR REPLACE MATERIALIZED VIEW gold_csr_claims
COMMENT 'Structured CSR claims extracted from Danone official sources and benchmarks — one row per claim'
TBLPROPERTIES ('quality' = 'gold')
AS
WITH official_articles AS (
  SELECT
    article_id,
    url,
    title,
    clean_content,
    source_type,
    search_topic,
    esg_category,
    esg_sub_theme,
    published_at,
    scraped_date,
    credibility_score,
    -- ── Extract individual CSR claims ───────────────────────────────────────
    -- Returns a JSON array of claim objects
    ai_query(
      '${ai_endpoint_name}',
      CONCAT(
        'You are an ESG claims extraction specialist. From the following Danone official document or benchmark report, ',
        'extract every specific, verifiable CSR/ESG claim made by or about Danone. ',
        'For each claim, identify the ESG category and a measurable target if present. ',
        'Respond ONLY with a valid JSON array (no markdown). Each element must match: ',
        '{"claim_text": "<exact or paraphrased claim>", ',
        '"esg_category": "Environmental|Social|Governance", ',
        '"sub_theme": "<specific sub-theme>", ',
        '"metric": "<quantitative target or null>", ',
        '"timeframe": "<year or period or null>", ',
        '"claim_type": "commitment|achievement|target|certification"} ',
        'Return an empty array [] if no specific claims are found. ',
        'SOURCE: ', source_type, ' | URL: ', url, ' ',
        'TEXT: ', LEFT(clean_content, 4000)
      )
    )                                                AS claims_json_raw
  FROM LIVE.gold_esg_insights
  WHERE source_type IN ('official', 'benchmark')
    AND credibility_score >= 6
    AND clean_content IS NOT NULL
),
exploded_claims AS (
  SELECT
    article_id,
    url,
    title,
    source_type,
    search_topic,
    esg_category,
    esg_sub_theme,
    published_at,
    scraped_date,
    credibility_score,
    -- Explode the JSON array of claims into individual rows
    claim_obj
  FROM official_articles
  LATERAL VIEW explode(
    from_json(claims_json_raw, 'ARRAY<STRUCT<
      claim_text  STRING,
      esg_category STRING,
      sub_theme   STRING,
      metric      STRING,
      timeframe   STRING,
      claim_type  STRING
    >>')
  ) AS claim_obj
  WHERE claim_obj IS NOT NULL
)
SELECT
  -- Unique claim ID
  SHA2(CONCAT(article_id, '|', claim_obj.claim_text), 256)  AS claim_id,
  article_id,
  url,
  title,
  source_type,
  search_topic,
  -- Prefer the LLM-extracted category over the article-level one
  COALESCE(claim_obj.esg_category, esg_category)            AS esg_category,
  COALESCE(claim_obj.sub_theme, esg_sub_theme)              AS sub_theme,
  claim_obj.claim_text                                       AS claim_text,
  claim_obj.metric                                           AS metric,
  claim_obj.timeframe                                        AS timeframe,
  claim_obj.claim_type                                       AS claim_type,
  published_at,
  scraped_date,
  credibility_score,
  current_timestamp()                                        AS _gold_at
FROM exploded_claims;
