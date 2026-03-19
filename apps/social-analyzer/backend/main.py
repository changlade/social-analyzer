"""
Danone Social Analyzer — FastAPI application entry point.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import insights, sentiment, impact_delta, sources, reports, chat

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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "danone-social-analyzer"}


# ── Serve built React frontend ─────────────────────────────────────────────────
_frontend_dist = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
