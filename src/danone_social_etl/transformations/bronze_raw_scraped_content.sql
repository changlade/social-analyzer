-- ============================================================
-- Bronze Layer: Raw scraped content
-- Danone Social Impact Analyzer
-- ============================================================
-- Ingests JSON-lines files written by the daily scraping job
-- into the social_landing UC volume.
-- Each row is one scraped article / search result, kept raw.
-- social_landing_path is injected via pipeline configuration.
-- ============================================================

CREATE OR REPLACE STREAMING TABLE bronze_raw_scraped_content
CLUSTER BY (source_type, search_topic)
COMMENT 'Raw scraped content from DDG+Jina, Playwright, and RSS scrapers — one row per article, ingested via Auto Loader'
TBLPROPERTIES (
  'quality'      = 'bronze',
  'pipelines.autoOptimize.managed' = 'true'
)
AS
SELECT
  -- Core identity
  article_id,
  url,
  url_hash,
  title,
  -- Content (raw, uncleaned)
  content                                        AS raw_content,
  CAST(content_length AS INT)                    AS content_length,
  -- Classification hints from the scraper
  source_type,
  search_topic,
  -- Author / publication metadata
  author,
  published_date,
  language,
  -- Scraper provenance
  scraper,
  _scrape_run_id,
  CAST(_scraped_at AS TIMESTAMP)                 AS scraped_at,
  CAST(_run_timestamp AS TIMESTAMP)              AS run_timestamp,
  -- Pipeline ingestion metadata
  current_timestamp()                            AS _ingested_at,
  _metadata.file_path                            AS _source_file,
  _metadata.file_modification_time               AS _file_modified_at
FROM STREAM read_files(
  '${social_landing_path}',
  format          => 'json',
  inferSchema     => false,
  schemaHints     => '
    article_id      STRING,
    url             STRING,
    url_hash        STRING,
    title           STRING,
    content         STRING,
    content_length  STRING,
    source_type     STRING,
    search_topic    STRING,
    author          STRING,
    published_date  STRING,
    language        STRING,
    scraper         STRING,
    ddg_snippet     STRING,
    feed_name       STRING,
    _scrape_run_id  STRING,
    _scraped_at     STRING,
    _run_timestamp  STRING
  ',
  mode            => 'PERMISSIVE'
)
WHERE url IS NOT NULL
  AND content IS NOT NULL;
