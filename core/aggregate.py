"""Team and org metrics. Every function returns None for groups smaller than MIN_GROUP,
so an aggregate can never point at one person."""
from __future__ import annotations

from collections import Counter

from core.readiness import BANDS
from core.taxonomy import Taxonomy

MIN_GROUP = 5


def big_enough(n: int) -> bool:
    return n >= MIN_GROUP


def skill_coverage(
    profiles: list[dict[str, int]], role_ids: list[str], tax: Taxonomy
) -> dict[str, dict] | None:
    """For each skill any member's role requires: how many members meet it.

    Returns {skill: {"met": int, "needed_by": int, "share": float}} or None if the group is too small.
    """
    if not big_enough(len(profiles)):
        return None
    out: dict[str, dict] = {}
    for profile, role_id in zip(profiles, role_ids, strict=True):
        for req in tax.requirements(role_id):
            row = out.setdefault(req.skill, {"met": 0, "needed_by": 0})
            row["needed_by"] += 1
            if profile.get(req.skill, 0) >= req.level:
                row["met"] += 1
    for row in out.values():
        row["share"] = row["met"] / row["needed_by"]
    return out


def top_gaps(coverage: dict[str, dict] | None, n: int = 3) -> list[tuple[str, int, int]]:
    """[(skill, below_count, needed_by)] for the skills most members are below."""
    if coverage is None:
        return []
    rows = [(s, r["needed_by"] - r["met"], r["needed_by"]) for s, r in coverage.items()]
    rows = [r for r in rows if r[1] > 0]
    return sorted(rows, key=lambda r: (-r[1] / r[2], -r[1], r[0]))[:n]


def readiness_bands(bands: list[str]) -> dict[str, int] | None:
    if not big_enough(len(bands)):
        return None
    counts = Counter(bands)
    return {b: counts.get(b, 0) for b in BANDS}


def count_if(values: list[bool]) -> int | None:
    """A count over a group (e.g. people exploring another role), hidden for small groups."""
    if not big_enough(len(values)):
        return None
    return sum(values)
