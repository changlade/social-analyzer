"""
Delta Lake writer utilities.
Writes scraping output records as JSON files into the volume landing zone.
The DLT pipeline picks them up via Spark Auto Loader.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_records_to_volume(
    records: List[Dict[str, Any]],
    volume_path: str,
    sub_dir: str,
    batch_tag: str = "",
) -> str:
    """
    Serialize a list of record dicts to a single JSON-lines file in the volume.

    Args:
        records:     List of dicts (one per scraped article/result).
        volume_path: Root volume path (e.g. /Volumes/catalog/schema/vol).
        sub_dir:     Sub-directory inside the volume (e.g. 'raw_scrapes').
        batch_tag:   Optional label embedded in the file name for traceability.

    Returns:
        The full path of the written file.
    """
    if not records:
        logger.warning("write_records_to_volume called with empty records list — skipping")
        return ""

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_id = str(uuid.uuid4())[:8]
    tag = f"_{batch_tag}" if batch_tag else ""
    filename = f"{ts}{tag}_{batch_id}.jsonl"

    out_dir = Path(volume_path) / sub_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            # Ensure every record has standard envelope fields
            rec.setdefault("_scrape_run_id", batch_id)
            rec.setdefault("_scraped_at", _now_iso())
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    logger.info(f"Wrote {len(records)} records → {out_path}")
    return str(out_path)


def build_record(
    url: str,
    title: str,
    content: str,
    source_type: str,
    search_topic: str,
    *,
    author: str = "",
    published_date: str = "",
    language: str = "en",
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Construct a standardised scraping record envelope.

    source_type values: official | news | social | ngo | benchmark | rss
    """
    record = {
        "article_id": str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
        "url": url,
        "url_hash": str(abs(hash(url))),
        "title": title,
        "content": content,
        "source_type": source_type,
        "search_topic": search_topic,
        "author": author,
        "published_date": published_date,
        "language": language,
        "content_length": len(content),
    }
    if extra:
        record.update(extra)
    return record
