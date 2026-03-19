-- ============================================================
-- Bronze Layer: Raw scraped content
-- Danone Social Impact Analyzer
-- ============================================================
-- Explicit schema avoids CF_EMPTY_DIR_FOR_SCHEMA_INFERENCE when the
-- landing volume is empty at pipeline start. DLT will wait for files.
-- ============================================================

CREATE OR REPLACE STREAMING TABLE bronze_raw_scraped_content (
  article_id          STRING,
  url                 STRING,
  url_hash            STRING,
  title               STRING,
  raw_content         STRING,
  content_length      INT,
  source_type         STRING,
  search_topic        STRING,
  author              STRING,
  published_date      STRING,
  language            STRING,
  scraper             STRING,
  _scrape_run_id      STRING,
  scraped_at          TIMESTAMP,
  run_timestamp       TIMESTAMP,
  _ingested_at        TIMESTAMP,
  _source_file        STRING,
  _file_modified_at   TIMESTAMP
)
CLUSTER BY (source_type, search_topic)
COMMENT 'Raw scraped content from You.com MCP and RSS scrapers — one row per article, ingested via Auto Loader'
TBLPROPERTIES (
  'quality'      = 'bronze',
  'pipelines.autoOptimize.managed' = 'true'
)
AS
SELECT
  article_id,
  url,
  url_hash,
  title,
  content                                        AS raw_content,
  CAST(content_length AS INT)                    AS content_length,
  source_type,
  search_topic,
  author,
  published_date,
  language,
  scraper,
  _scrape_run_id,
  CAST(_scraped_at AS TIMESTAMP)                 AS scraped_at,
  CAST(_run_timestamp AS TIMESTAMP)              AS run_timestamp,
  current_timestamp()                            AS _ingested_at,
  _metadata.file_path                            AS _source_file,
  _metadata.file_modification_time               AS _file_modified_at
FROM STREAM read_files(
  '${social_landing_path}',
  format      => 'json',
  schema      => '
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
    _scrape_run_id  STRING,
    _scraped_at     STRING,
    _run_timestamp  STRING
  ',
  mode        => 'PERMISSIVE'
)
WHERE url IS NOT NULL
  AND content IS NOT NULL;
