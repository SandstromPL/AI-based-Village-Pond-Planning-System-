"""
In-memory analysis result store.

Phase 2: simple dict-based store.
Phase 3 upgrade path: replace _store and the functions below with
PostgreSQL+PostGIS calls. The service and API layers do not change.
"""

from __future__ import annotations
from typing import Dict, Optional
from app.models.analysis import AnalysisResult

# ── In-memory store ──────────────────────────────────────────────────────────
_store: Dict[str, AnalysisResult] = {}


def save(result: AnalysisResult) -> None:
    """Persist an analysis result."""
    _store[result.analysis_id] = result


def get(analysis_id: str) -> Optional[AnalysisResult]:
    """Retrieve a result by ID. Returns None if not found."""
    return _store.get(analysis_id)


def list_ids() -> list:
    """Return all stored analysis IDs (most recent last by insertion order)."""
    return list(_store.keys())


def delete(analysis_id: str) -> bool:
    """Remove a result. Returns True if found and deleted."""
    if analysis_id in _store:
        del _store[analysis_id]
        return True
    return False
