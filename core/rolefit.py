"""Role-fit detection: does another role suit this person better than their current one?"""
from __future__ import annotations

from dataclasses import dataclass

from core.gaps import compute_gaps
from core.taxonomy import Taxonomy

# Roles people can move into sideways; leadership roles are a promotion path, not a fit suggestion.
IC_ROLES = ("data_engineer", "cloud_engineer", "frontend_engineer", "ml_engineer")
INTEREST_BOOST = 0.10  # an interest that matches the role's area adds up to 10 points


@dataclass(frozen=True)
class RoleFit:
    role_id: str
    match: float          # 0..1
    current_match: float  # 0..1 for the person's current role
    to_learn: list[str]   # top missing skills for the suggested role


def role_match(profile: dict[str, int], role_id: str, tax: Taxonomy) -> float:
    """Weighted partial credit across ALL requirements (mandatory counts double)."""
    total = got = 0.0
    for r in tax.requirements(role_id):
        w = 2.0 if r.type == "mandatory" else 1.0
        total += w
        got += w * min(profile.get(r.skill, 0) / r.level, 1.0)
    return got / total if total else 0.0


def suggest_role(
    profile: dict[str, int],
    current_role: str,
    interests: dict[str, float],
    tax: Taxonomy,
    min_match: float = 0.6,
) -> RoleFit | None:
    """Return the best other IC role if it is a good match AND fits the person's interests.

    interests maps a role id to a strength 0..1 (from the mentor questionnaire).
    """
    if current_role not in IC_ROLES:
        return None
    current = role_match(profile, current_role, tax)
    best: RoleFit | None = None
    for role_id in IC_ROLES:
        if role_id == current_role:
            continue
        base = role_match(profile, role_id, tax)
        score = min(base + INTEREST_BOOST * interests.get(role_id, 0.0), 1.0)
        if score < min_match or interests.get(role_id, 0.0) < 0.5:
            continue
        if best is None or score > best.match:
            to_learn = [g.skill for g in compute_gaps(profile, role_id, tax)[:3]]
            best = RoleFit(role_id, score, current, to_learn)
    return best
