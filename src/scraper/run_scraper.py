"""
Main PySpark scraping job.

Orchestrates You.com MCP-based scraping + RSS feeds, deduplicates records
by URL, and writes JSON-lines files to the Delta Lake volume landing zone
so the DLT pipeline can pick them up via Auto Loader.

Usage (invoked by the Databricks job):
    spark-submit run_scraper.py \
        --catalog danonedemo_catalog \
        --schema marketing \
        --volume social_landing
"""

import argparse
import logging
import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

# Ensure local modules are importable when executed via spark-submit
sys.path.insert(0, os.path.dirname(__file__))

from pyspark.sql import SparkSession
import pyspark.sql.functions as F

from sources.youcom_scraper import run_youcom_scraper
from sources.rss_scraper import run_rss_scraper
from utils.delta_writer import write_records_to_volume

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("danone.scraper.main")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Danone Social Analyzer — Daily Scraper")
    p.add_argument("--catalog", default="danonedemo_catalog")
    p.add_argument("--schema", default="marketing")
    p.add_argument("--volume", default="social_landing")
    return p.parse_args()


def deduplicate(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate records by URL — keeps first occurrence."""
    seen: set = set()
    unique = []
    for rec in records:
        url = rec.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(rec)
    return unique


def main() -> None:
    args = parse_args()
    volume_path = f"/Volumes/{args.catalog}/{args.schema}/{args.volume}"

    logger.info("=== Danone Social Analyzer — Scraping Run ===")
    logger.info(f"Target volume: {volume_path}")

    spark = SparkSession.builder.appName("DanoneSocialScraper").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    run_ts = datetime.now(timezone.utc).isoformat()
    all_records: List[Dict[str, Any]] = []

    # ── 1. You.com MCP (search + direct URL extraction) ──────────────────────
    logger.info("--- Phase 1: You.com MCP (search + livecrawl + direct URLs) ---")
    youcom_records = run_youcom_scraper()
    logger.info(f"You.com collected: {len(youcom_records)}")
    all_records.extend(youcom_records)

    # ── 2. RSS Feeds ─────────────────────────────────────────────────────────
    logger.info("--- Phase 2: RSS Feeds ---")
    rss_records = run_rss_scraper()
    logger.info(f"RSS collected: {len(rss_records)}")
    all_records.extend(rss_records)

    # ── Deduplication ─────────────────────────────────────────────────────────
    logger.info(f"Total before dedup: {len(all_records)}")
    all_records = deduplicate(all_records)
    logger.info(f"Total after dedup:  {len(all_records)}")

    if not all_records:
        logger.warning("No records collected — pipeline will not be triggered")
        return

    # Stamp every record with the run timestamp
    for rec in all_records:
        rec["_run_timestamp"] = run_ts

    # ── Write to volume as JSON-lines ─────────────────────────────────────────
    written_path = write_records_to_volume(
        records=all_records,
        volume_path=volume_path,
        sub_dir="raw_scrapes",
        batch_tag="full_run",
    )
    logger.info(f"Written: {written_path}")

    # ── Log summary via Spark ─────────────────────────────────────────────────
    summary = [
        {"source_type": "you_search", "count": len(youcom_records), "run_ts": run_ts},
        {"source_type": "rss",        "count": len(rss_records),    "run_ts": run_ts},
        {"source_type": "total",      "count": len(all_records),    "run_ts": run_ts},
    ]
    summary_df = spark.createDataFrame(summary)
    (
        summary_df
        .withColumn("run_ts", F.to_timestamp("run_ts"))
        .write
        .format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .saveAsTable(f"`{args.catalog}`.`{args.schema}`.scraper_run_log")
    )
    logger.info("Run summary written to scraper_run_log")
    logger.info("=== Scraping run complete ===")


if __name__ == "__main__":
    main()
