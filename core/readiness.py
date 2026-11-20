"""Promotion readiness score. Private to the employee; only band counts go upward."""
from __future__ import annotations

from dataclasses import dataclass

from core.gaps import coverage_ratio
from core.taxonomy import Taxonomy

WEIGHTS = {"coverage": 40, "performance": 25, "evidence": 20, "roadmap": 15}
READY, NEARLY, DEVELOPING = "Ready", "Nearly ready", "Developing"
BANDS = (READY, NEARLY, DEVELOPING)
EVIDENCE_TARGET = 5  # distinct evidence sources (resume, review, self-eval, GitHub, transcript)


@dataclass(frozen=True)
class Readiness:
    score: int
    band: str
    breakdown: dict[str, float]  # each part as 0..1 before weighting


def band_for(score: float) -> str:
    if score >= 75:
        return READY
    if score >= 55:
        return NEARLY
    return DEVELOPING


def compute_readiness(
    profile: dict[str, int],
    role_id: str,
    tax: Taxonomy,
    performance_rating: float | None,
    evidence_count: int,
    roadmap_done: int,
    roadmap_total: int,
) -> Readiness:
    parts = {
        "coverage": coverage_ratio(profile, role_id, tax),
        # rating on a 1-5 scale; missing rating counts as neutral (3/5)
        "performance": max(min(((performance_rating or 3) - 1) / 4, 1.0), 0.0),
        "evidence": min(evidence_count / EVIDENCE_TARGET, 1.0),
        "roadmap": (roadmap_done / roadmap_total) if roadmap_total else 0.0,
    }
    score = sum(parts[k] * WEIGHTS[k] for k in WEIGHTS)
    return Readiness(round(score), band_for(score), parts)
