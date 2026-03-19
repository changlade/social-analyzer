-- ============================================================
-- Bronze Layer: Scraper run observability log
-- Danone Social Impact Analyzer
-- ============================================================
-- The scraper job writes run metrics directly to a Delta table
-- (danonedemo_catalog.marketing.scraper_run_log) via Spark saveAsTable.
-- This materialized view surfaces those metrics inside the DLT pipeline
-- for downstream observability queries.
-- ============================================================

CREATE OR REPLACE MATERIALIZED VIEW bronze_scraper_run_log
COMMENT 'Per-run scraping statistics: record counts by source type'
TBLPROPERTIES ('quality' = 'bronze')
AS
SELECT
  source_type,
  CAST(count AS INT)  AS record_count,
  run_ts,
  current_timestamp() AS _ingested_at
FROM `${catalog}`.`${schema}`.scraper_run_log
WHERE source_type IS NOT NULL
  AND source_type != 'total';
