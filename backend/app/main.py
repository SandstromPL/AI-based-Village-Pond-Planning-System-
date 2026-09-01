"""
FastAPI Application Factory
============================
Creates the FastAPI app with:
  - CORS middleware
  - Structured JSON logging
  - Global exception handlers
  - API router mounts
  - OpenAPI metadata
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analysis as analysis_router
from app.api import health as health_router
from app.config import settings

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.app_log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── App factory ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info(
        "Village Pond Planning API v0.2.0 started. "
        "Docs: http://%s:%d/docs",
        settings.app_host,
        settings.app_port,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Village Pond Planning API",
        description=(
            "AI-based geospatial decision-support system for identifying suitable "
            "pond locations in rural areas. Analyzes terrain from KML/KMZ contour "
            "maps and recommends pond sites based on catchment, drainage, rainfall, "
            "and terrain suitability analysis."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
        contact={
            "name": "CSD Assignment 1",
            "url": "https://github.com/your-repo",
        },
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ─────────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed = round(time.perf_counter() - t0, 3)
        response.headers["X-Process-Time-Seconds"] = str(elapsed)
        return response

    # ── Global exception handlers ─────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "detail": str(exc)},
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(health_router.router, prefix="/api/v1")
    app.include_router(analysis_router.router, prefix="/api/v1")

    return app


app = create_app()
