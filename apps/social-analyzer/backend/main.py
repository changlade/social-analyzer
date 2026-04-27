"""
Danone Social Analyzer — FastAPI application entry point.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import insights, sentiment, impact_delta, sources, reports, chat, news_events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("danone.social.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Danone Social Analyzer API starting up")
    yield
    logger.info("Danone Social Analyzer API shutting down")


app = FastAPI(
    title="Danone Social Impact Analyzer",
    description="Marketing-facing API for ESG insights, sentiment analysis, and CSR impact delta.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ────────────────────────────────────────────────────────────────
app.include_router(insights.router,      prefix="/api/insights",      tags=["Insights"])
app.include_router(sentiment.router,     prefix="/api/sentiment",     tags=["Sentiment"])
app.include_router(impact_delta.router,  prefix="/api/impact-delta",  tags=["Impact Delta"])
app.include_router(sources.router,       prefix="/api/sources",       tags=["Sources"])
app.include_router(reports.router,       prefix="/api/reports",       tags=["Reports"])
app.include_router(chat.router,          prefix="/api/chat",          tags=["Chat"])
app.include_router(news_events.router,   prefix="/api/news-events",   tags=["News Events"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "danone-social-analyzer"}


@app.get("/api/health/db")
def health_db() -> dict:
    """Diagnostic: test SQL warehouse connectivity and return table row counts."""
    import os
    from databricks_client import execute_query, CATALOG, SCHEMA, WAREHOUSE_ID

    host = os.getenv("DATABRICKS_HOST", "NOT_SET")
    has_token = bool(os.getenv("DATABRICKS_TOKEN", ""))

    tables = [
        "gold_esg_insights", "gold_csr_claims",
        "gold_daily_summary", "gold_impact_delta", "gold_public_sentiment",
        "silver_sentiment_scored", "bronze_raw_scraped_content",
    ]
    counts = {}
    error = None
    try:
        for t in tables:
            rows = execute_query(f"SELECT COUNT(*) AS cnt FROM {t}")
            counts[t] = int(rows[0]["cnt"]) if rows else -1
    except Exception as e:
        error = str(e)

    return {
        "host": host,
        "has_token": has_token,
        "catalog": CATALOG,
        "schema": SCHEMA,
        "warehouse_id": WAREHOUSE_ID,
        "counts": counts,
        "error": error,
    }


# ── Serve built React frontend (SPA) ──────────────────────────────────────────
_frontend_dist = os.path.join(os.path.dirname(__file__), "static")
_index_html    = os.path.join(_frontend_dist, "index.html")

if os.path.isdir(_frontend_dist):
    # Serve static assets (JS, CSS, images) under /assets
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    # Catch-all: any path not matched by the API routers serves index.html
    # so React Router can handle client-side navigation (e.g. /chat, /insights)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Serve actual files if they exist (favicon.ico, manifest, etc.)
        candidate = os.path.join(_frontend_dist, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(_index_html)
