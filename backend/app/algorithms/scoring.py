"""
Candidate Scoring Algorithm
=============================
Scores each valid pond candidate on 5 terrain/hydrology factors,
normalises each factor to 0-100 across all candidates, then computes
a weighted final score.

Factors and weights (all configurable via settings):
  - catchment_area (larger = better)       weight 0.35
  - flow_accumulation (higher = better)    weight 0.25
  - slope (lower = better)                 weight 0.20
  - terrain relief (lower = better)        weight 0.10
  - depression_delta (higher = better)     weight 0.10

A transparent score breakdown is stored with every candidate so the
recommendation can be explained.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np

from app.models.candidate import PondCandidate, ScoreBreakdown, CandidateStatus

logger = logging.getLogger(__name__)


def _min_max_normalise(values: List[float], invert: bool = False) -> List[float]:
    """Normalise a list of values to [0, 100]. If invert=True, lower = better."""
    arr = np.array(values, dtype=float)
    lo, hi = arr.min(), arr.max()

    if hi == lo:
        # All candidates identical on this factor — give neutral score
        return [50.0] * len(values)

    normalised = (arr - lo) / (hi - lo) * 100.0

    if invert:
        normalised = 100.0 - normalised

    return normalised.tolist()


def score_and_rank_candidates(
    candidates: List[PondCandidate],
    w_catchment: float = 0.35,
    w_flow_acc: float = 0.25,
    w_slope: float = 0.20,
    w_relief: float = 0.10,
    w_depression: float = 0.10,
) -> List[PondCandidate]:
    """
    Score all accepted candidates and assign ranks.

    Args:
        candidates: List of PondCandidate objects (including rejected ones).
        w_*: Scoring weights for each factor (should sum to 1.0).

    Returns:
        The same list with score, rank, score_breakdown, and reasoning filled in
        for accepted candidates.
    """
    accepted = [c for c in candidates if c.status == CandidateStatus.ACCEPTED]

    if not accepted:
        logger.warning("No accepted candidates to score.")
        return candidates

    # ── Factor extraction ─────────────────────────────────────────────────
    catchment_vals = [c.catchment_area_km2 for c in accepted]
    flow_acc_vals  = [float(c.flow_accumulation) for c in accepted]
    slope_vals     = [c.slope_deg for c in accepted]
    relief_vals    = [c.elevation_m for c in accepted]    # lower = better (lower lying)
    depression_vals = [c.depression_delta_m for c in accepted]

    # ── Normalise (0-100) ─────────────────────────────────────────────────
    norm_catchment   = _min_max_normalise(catchment_vals, invert=False)
    norm_flow_acc    = _min_max_normalise(flow_acc_vals,  invert=False)
    norm_slope       = _min_max_normalise(slope_vals,     invert=True)   # lower slope = higher score
    norm_relief      = _min_max_normalise(relief_vals,    invert=True)   # lower elevation = higher score
    norm_depression  = _min_max_normalise(depression_vals, invert=False)

    # ── Weighted final score ──────────────────────────────────────────────
    for i, candidate in enumerate(accepted):
        cs = norm_catchment[i]
        fs = norm_flow_acc[i]
        ss = norm_slope[i]
        rs = norm_relief[i]
        ds = norm_depression[i]

        final = (
            w_catchment  * cs
            + w_flow_acc * fs
            + w_slope    * ss
            + w_relief   * rs
            + w_depression * ds
        )

        candidate.score_breakdown = ScoreBreakdown(
            catchment_score=round(cs, 1),
            flow_score=round(fs, 1),
            slope_score=round(ss, 1),
            relief_score=round(rs, 1),
            depression_score=round(ds, 1),
            final_score=round(final, 1),
        )
        candidate.score = round(final, 1)
        candidate.reasoning = _build_reasoning(candidate)

    # ── Rank by final score ───────────────────────────────────────────────
    accepted.sort(key=lambda c: c.score, reverse=True)
    for rank, candidate in enumerate(accepted, start=1):
        candidate.rank = rank

    logger.info(
        "Scored %d candidates. Top score: %.1f (rank 1 = %s at %.4f°N, %.4f°E).",
        len(accepted),
        accepted[0].score,
        accepted[0].candidate_id,
        accepted[0].latitude,
        accepted[0].longitude,
    )

    return candidates


def _build_reasoning(c: PondCandidate) -> List[str]:
    """Generate human-readable reasoning strings for a candidate."""
    reasons: List[str] = []

    if c.catchment_area_km2 >= 1.0:
        reasons.append(f"Large contributing catchment ({c.catchment_area_km2:.2f} km²)")
    elif c.catchment_area_km2 >= 0.5:
        reasons.append(f"Moderate contributing catchment ({c.catchment_area_km2:.2f} km²)")
    else:
        reasons.append(f"Small contributing catchment ({c.catchment_area_km2:.2f} km²)")

    if c.flow_accumulation > 1000:
        reasons.append("Strong drainage convergence point")
    elif c.flow_accumulation > 200:
        reasons.append("Moderate drainage convergence")

    if c.slope_deg < 5:
        reasons.append(f"Very gentle slope ({c.slope_deg:.1f}°) — well suited for pond construction")
    elif c.slope_deg < 10:
        reasons.append(f"Gentle slope ({c.slope_deg:.1f}°) — suitable for construction")
    else:
        reasons.append(f"Moderate slope ({c.slope_deg:.1f}°) — construction feasible but requires assessment")

    if c.depression_delta_m > 0.5:
        reasons.append(f"Terrain naturally forms a depression (depth ≈ {c.depression_delta_m:.1f} m)")

    reasons.append(f"Elevation: {c.elevation_m:.1f} m above mean sea level")
    reasons.append(f"Candidate seed type: {c.seed_type.replace('_', ' ')}")

    return reasons
