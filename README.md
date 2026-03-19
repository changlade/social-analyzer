# Danone Social Impact Analyzer

A Databricks Asset Bundle that scrapes, transforms, and analyses Danone's ESG footprint — comparing official CSR claims against public perception using GPT 5.4 via Databricks AI Gateway.

## Architecture

```
Scraping Job (daily)
  ├── DuckDuckGo + Jina Reader  → news, NGO reports, benchmarks
  ├── Playwright headless        → B Corp, WBA, Danone.com
  └── RSS feeds                  → Danone newsroom, ESG media
          │
          ▼ JSON-lines files → UC Volume (social_landing)
          │
DLT Pipeline (danonedemo_catalog.marketing)
  ├── Bronze  → bronze_raw_scraped_content
  ├── Silver  → silver_cleaned_articles, silver_sentiment_scored
  └── Gold    → gold_esg_insights, gold_csr_claims,
                gold_public_sentiment, gold_impact_delta,
                gold_daily_summary
          │
          ▼ SQL Warehouse (50e0bc7f9918a201)
          │
Databricks App (danone-social-analyzer)
  ├── FastAPI backend  (routers: insights, sentiment, impact-delta, sources, reports)
  └── React frontend   (Overview, Insights, Impact Delta, Sources, Report Builder)
```

## Quick Start

### 1. Deploy the bundle

```bash
cd social-analyzer
databricks bundle deploy --profile DEFAULT
```

### 2. Run the one-time setup job

```bash
databricks bundle run danone_social_setup --profile DEFAULT
```

This creates:
- `danonedemo_catalog.marketing` schema
- `social_landing` UC volume (with `raw_scrapes/`, `raw_rss/` sub-dirs)
- `danone-gpt5` external model endpoint (GPT 5.4 AI Gateway)
- `social-analyzer-secrets` secret scope

### 3. Run the first scraping job

```bash
databricks bundle run danone_social_scraper --profile DEFAULT
```

The scraper runs three phases:
1. **DuckDuckGo + Jina Reader** — 17 topic queries, ~136 articles/run
2. **Playwright headless** — 7 static JS-heavy targets (B Corp, WBA, Danone.com)
3. **RSS feeds** — 7 feeds filtered for Danone keywords

After scraping, it automatically triggers the DLT pipeline update.

### 4. Build and deploy the app

```bash
# Build the React frontend into backend/static/
./scripts/build_frontend.sh

# Deploy the Databricks App
databricks bundle deploy --profile DEFAULT
```

Then open the app from the Databricks workspace UI under **Apps**.

## Data Flow Details

### Bronze Layer
- `bronze_raw_scraped_content` — All scraped articles as-is (Auto Loader streaming from volume)
- `bronze_scraper_run_log` — Per-run statistics (articles by source type)

### Silver Layer
- `silver_cleaned_articles` — Deduped, HTML-stripped, metadata-normalised, with ESG hint
- `silver_sentiment_scored` — Every article scored by `ai_query()`: sentiment + Danone stance

### Gold Layer
- `gold_esg_insights` — Full ESG classification per article: category, sub-theme, claims, impact summary
- `gold_csr_claims` — Individual CSR claims extracted from official sources (one row per claim)
- `gold_public_sentiment` — Weekly aggregated public sentiment by ESG category
- `gold_impact_delta` — **The key table**: CSR claims vs public reality gap analysis with alignment score (0–10)
- `gold_daily_summary` — Daily AI executive brief with ESG pulse scores

### AI Endpoint

All `ai_query()` calls use the `danone-gpt5` endpoint pointing to:
```
https://7474655187458913.ai-gateway.cloud.databricks.com/mlflow/v1/chat/completions
```

### Exploration App Pages

| Page | Description |
|------|-------------|
| **Overview** | KPIs, weekly sentiment timeline (official vs public), ESG donut, daily AI brief |
| **Insights** | Filterable article explorer (ESG category, source, stance, date, keyword) |
| **Impact Delta** | CSR claims vs public reality cards with alignment scores and risk flags |
| **Sources** | Coverage breakdown by source type and topic |
| **Report Builder** | Generate on-demand AI reports for different audiences (marketing, executive, investor) |

## Local Development

```bash
# Backend
cd apps/social-analyzer/backend
pip install -r requirements.txt
DATABRICKS_HOST=https://fevm-danonedemo.cloud.databricks.com \
DATABRICKS_TOKEN=<your-token> \
uvicorn main:app --reload

# Frontend (in another terminal)
cd apps/social-analyzer/frontend
npm install
npm run dev   # proxies /api to localhost:8000
```

## Scheduling

The scraping job runs daily at **04:00 UTC** (configurable via `scraper_schedule_cron` variable).
It writes to the volume, then automatically triggers the DLT pipeline update.

## Anti-Detection Strategy

The scraper avoids blocks without paid proxy services by:
- Rotating User-Agents (10 realistic browser strings)
- Random jitter between requests (2–10s between items, 5–15s between sources)
- DuckDuckGo instead of Google for search (much more lenient)
- Jina Reader proxy (`r.jina.ai`) for page-to-Markdown conversion
- Playwright headless with viewport randomisation for JS-heavy pages
- RSS feeds for the most reliable, block-free data
