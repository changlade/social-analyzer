-- ============================================================
-- Bronze Layer: Scraper run observability log
-- Danone Social Impact Analyzer
-- ============================================================
-- Reads from the Delta table written by run_scraper.py at the
-- end of each scraping job, giving a per-run record count by source.
-- Used by the exploration app's admin / monitoring view.
-- Ingested via read_files in JSON format (scraper writes JSONL to volume).
-- ============================================================

CREATE OR REPLACE STREAMING TABLE bronze_scraper_run_log
COMMENT 'Per-run scraping statistics: record counts by source type'
TBLPROPERTIES ('quality' = 'bronze')
AS
SELECT
  source_type,
  CAST(count AS INT)             AS record_count,
  run_ts,
  current_timestamp()            AS _ingested_at
FROM STREAM read_files(
  '${social_landing_path}',
  format       => 'json',
  inferSchema  => false,
  schemaHints  => 'source_type STRING, count STRING, run_ts STRING',
  mode         => 'PERMISSIVE'
)
WHERE source_type IS NOT NULL
  AND source_type != 'total';
