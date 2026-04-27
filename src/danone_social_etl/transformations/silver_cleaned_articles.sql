-- ============================================================
-- Silver Layer: Cleaned articles (streaming)
-- Danone Social Impact Analyzer
-- ============================================================
-- Reads from bronze streaming table, applies:
--   1. Text cleaning: strip HTML, normalise whitespace
--   2. Metadata normalisation: publish date, language
--   3. Content quality gate: minimum 150 chars
--   4. Source category mapping
--
-- Note: URL-level deduplication is handled by the Python scraper
-- before writing to the landing zone, so duplicates within a single
-- run are already eliminated upstream. Cross-run deduplication is
-- handled in gold layer queries via GROUP BY / MAX().
-- ============================================================

CREATE OR REPLACE STREAMING TABLE silver_cleaned_articles (
  CONSTRAINT valid_content    EXPECT (clean_content IS NOT NULL AND length(clean_content) >= 150) ON VIOLATION DROP ROW,
  CONSTRAINT valid_url        EXPECT (url IS NOT NULL AND length(url) > 10)                       ON VIOLATION DROP ROW,
  CONSTRAINT valid_source     EXPECT (source_type IN ('official','news','social','ngo','benchmark','rss'))
)
CLUSTER BY (source_type, search_topic, scraped_date)
COMMENT 'Cleaned scraped articles with normalised metadata — ready for LLM enrichment'
TBLPROPERTIES (
  'quality'      = 'silver',
  'pipelines.autoOptimize.managed' = 'true'
)
AS
SELECT
  article_id,
  url,
  url_hash,
  -- Text cleaning: collapse whitespace, strip common HTML entities
  TRIM(
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(raw_content, '<[^>]+>', ' '),  -- strip HTML tags
        '&(amp|lt|gt|nbsp|quot);', ' '),              -- strip HTML entities
      '\\s+', ' ')                                    -- collapse whitespace
  )                                                  AS clean_content,
  -- Truncated preview for dashboards
  LEFT(TRIM(REGEXP_REPLACE(REGEXP_REPLACE(raw_content, '<[^>]+>', ' '), '\\s+', ' ')), 500)
                                                     AS content_preview,
  CAST(content_length AS INT)                        AS content_length,
  title,
  author,
  -- Normalise publish date: use scraped_at as fallback
  COALESCE(
    TRY_TO_TIMESTAMP(published_date),
    scraped_at
  )                                                  AS published_at,
  CAST(DATE(COALESCE(TRY_TO_TIMESTAMP(published_date), scraped_at)) AS DATE)
                                                     AS scraped_date,
  source_type,
  search_topic,
  -- Broad ESG category pre-hint from the search topic
  CASE
    WHEN search_topic IN ('environmental','environmental_commitments','greenwashing','water_rights') THEN 'Environmental'
    WHEN search_topic IN ('social_mission','worker_sentiment','worker_conditions','community_impact',
                          'supply_chain','human_rights','restructuring','nutrition_index') THEN 'Social'
    WHEN search_topic IN ('governance','bcorp_certification','bcorp_profile','bcorp_news',
                          'impact_investment','strategy') THEN 'Governance'
    WHEN search_topic IN ('wba_index','wba_food_agriculture','wba_just_transition','wba_benchmark',
                          'general_news','esg_news','esg_investor','food_industry','annual_report') THEN 'Cross-ESG'
    WHEN search_topic IN ('product_recall','crisis_apac','regulatory_action',
                          'crisis_media','market_impact') THEN 'Crisis'
    ELSE 'Unknown'
  END                                                AS esg_hint,
  COALESCE(NULLIF(language, ''), 'en')               AS language,
  scraper,
  _scrape_run_id,
  scraped_at,
  run_timestamp,
  _ingested_at,
  current_timestamp()                                AS _silver_at
FROM STREAM(LIVE.bronze_raw_scraped_content)
WHERE raw_content IS NOT NULL
  AND LENGTH(TRIM(raw_content)) >= 150;
