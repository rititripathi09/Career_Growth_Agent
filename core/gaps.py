"""Skill gap analysis: compare a person's skill levels with what their role requires."""
from __future__ import annotations

from dataclasses import dataclass

from core.taxonomy import GOOD_TO_HAVE, MANDATORY, ORG_WIDE, Taxonomy

# Mandatory and org-wide gaps come before good-to-have ones.
_TYPE_ORDER = {MANDATORY: 0, ORG_WIDE: 1, GOOD_TO_HAVE: 2}


@dataclass(frozen=True)
class Gap:
    skill: str
    required: int
    current: int
    type: str

    @property
    def size(self) -> int:
        return max(self.required - self.current, 0)


def compute_gaps(profile: dict[str, int], role_id: str, tax: Taxonomy) -> list[Gap]:
    """Return only the skills below the required level, most important first."""
    gaps = [
        Gap(r.skill, r.level, profile.get(r.skill, 0), r.type)
        for r in tax.requirements(role_id)
        if profile.get(r.skill, 0) < r.level
    ]
    return sorted(gaps, key=lambda g: (_TYPE_ORDER[g.type], -g.size, g.skill))


def mandatory_coverage(profile: dict[str, int], role_id: str, tax: Taxonomy) -> tuple[int, int]:
    """(covered, total) for mandatory + org-wide requirements."""
    reqs = [r for r in tax.requirements(role_id) if r.type in (MANDATORY, ORG_WIDE)]
    covered = sum(1 for r in reqs if profile.get(r.skill, 0) >= r.level)
    return covered, len(reqs)


def coverage_ratio(profile: dict[str, int], role_id: str, tax: Taxonomy) -> float:
    """Partial-credit coverage 0..1 across mandatory + org-wide skills (level 2 of 3 counts 2/3)."""
    reqs = [r for r in tax.requirements(role_id) if r.type in (MANDATORY, ORG_WIDE)]
    if not reqs:
        return 1.0
    return sum(min(profile.get(r.skill, 0) / r.level, 1.0) for r in reqs) / len(reqs)
