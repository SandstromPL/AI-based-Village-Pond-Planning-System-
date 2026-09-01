"""Health check endpoint."""

from fastapi import APIRouter
from app.models.responses import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    tags=["Health"],
)
async def health():
    return HealthResponse(
        status="ok",
        version="0.2.0",
        phase="Phase 2 — Terrain & Catchment Analysis",
    )
