"""
RSS feed scraper for Danone-related content.

RSS feeds are the most reliable, bot-friendly data source — no anti-detection
tricks needed. They provide structured metadata (title, date, author, summary)
and are updated continuously.

Sources:
- Danone official newsroom RSS
- ESG / sustainability news aggregators
- Food industry news with Danone coverage
"""

import logging
import requests
import feedparser
from typing import List, Dict, Any
from datetime import datetime, timezone

from utils.anti_detect import random_headers, polite_jitter
from utils.delta_writer import build_record

logger = logging.getLogger(__name__)

RSS_FEEDS: List[Dict[str, Any]] = [
    # ── Official Danone ──────────────────────────────────────────────────────
    {
        "url": "https://www.danone.com/rss/all-news.xml",
        "source_type": "official",
        "topic": "danone_press",
        "name": "Danone Official Newsroom",
    },
    # ── ESG / Sustainability ─────────────────────────────────────────────────
    {
        "url": "https://www.esgtoday.com/feed/",
        "source_type": "news",
        "topic": "esg_news",
        "name": "ESG Today",
        "filter_keywords": ["danone", "dairy", "food", "nutrition", "b corp"],
    },
    {
        "url": "https://www.responsible-investor.com/rss/",
        "source_type": "news",
        "topic": "esg_investor",
        "name": "Responsible Investor",
        "filter_keywords": ["danone"],
    },
    # ── Food & FMCG Industry ─────────────────────────────────────────────────
    {
        "url": "https://www.foodnavigator.com/rss/site/foodnavigator.com/Headlines",
        "source_type": "news",
        "topic": "food_industry",
        "name": "FoodNavigator",
        "filter_keywords": ["danone", "alpro", "evian", "activia", "nutricia"],
    },
    {
        "url": "https://www.fooddive.com/feeds/news/",
        "source_type": "news",
        "topic": "food_industry",
        "name": "Food Dive",
        "filter_keywords": ["danone"],
    },
    # ── Human Rights / Labour ────────────────────────────────────────────────
    {
        "url": "https://www.business-humanrights.org/en/rss/latest-news/",
        "source_type": "ngo",
        "topic": "human_rights",
        "name": "Business & Human Rights Resource Centre",
        "filter_keywords": ["danone"],
    },
    # ── B Corp / Impact Economy ──────────────────────────────────────────────
    {
        "url": "https://bcorporation.net/news/rss/",
        "source_type": "official",
        "topic": "bcorp_news",
        "name": "B Lab Global News",
        "filter_keywords": ["danone", "food", "consumer"],
    },
]


def _parse_date(entry) -> str:
    """Extract and normalise published date from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                dt = datetime(*val[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    return ""


def _entry_matches_filter(entry, keywords: List[str]) -> bool:
    """Return True if the entry title/summary contains any of the keywords."""
    if not keywords:
        return True
    text = (
        getattr(entry, "title", "")
        + " "
        + getattr(entry, "summary", "")
    ).lower()
    return any(kw.lower() in text for kw in keywords)


def scrape_feed(feed_cfg: Dict[str, Any], max_items: int = 20) -> List[Dict[str, Any]]:
    """Fetch and parse a single RSS feed, returning structured records."""
    url = feed_cfg["url"]
    name = feed_cfg.get("name", url)
    filter_kw = feed_cfg.get("filter_keywords", [])
    records = []

    logger.info(f"RSS: {name}")
    try:
        resp = requests.get(url, headers=random_headers(), timeout=20)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as exc:
        logger.warning(f"  RSS fetch failed for {name}: {exc}")
        return []

    for entry in feed.entries[:max_items]:
        if not _entry_matches_filter(entry, filter_kw):
            continue

        entry_url = getattr(entry, "link", "")
        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
        author = getattr(entry, "author", "")
        pub_date = _parse_date(entry)

        if not entry_url or not summary:
            continue

        # Clean basic HTML from summary
        import re
        clean_summary = re.sub(r"<[^>]+>", " ", summary).strip()

        records.append(
            build_record(
                url=entry_url,
                title=title,
                content=clean_summary,
                source_type=feed_cfg["source_type"],
                search_topic=feed_cfg["topic"],
                author=author,
                published_date=pub_date,
                extra={"feed_name": name, "scraper": "rss"},
            )
        )
        polite_jitter()

    logger.info(f"  → {len(records)} matching items from {name}")
    return records


def run_rss_scraper(max_items_per_feed: int = 20) -> List[Dict[str, Any]]:
    """Scrape all configured RSS feeds."""
    all_records: List[Dict[str, Any]] = []
    for feed_cfg in RSS_FEEDS:
        records = scrape_feed(feed_cfg, max_items=max_items_per_feed)
        all_records.extend(records)
        polite_jitter()
    logger.info(f"RSS scraper total: {len(all_records)} records")
    return all_records
