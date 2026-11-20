"""Pick courses and certifications for a person's gaps, ONLY from the curated free catalog."""
from __future__ import annotations

from dataclasses import dataclass

from core.gaps import Gap
from core.taxonomy import CatalogItem


@dataclass(frozen=True)
class Recommendation:
    item: CatalogItem
    gap: Gap


def recommend(
    gaps: list[Gap], catalog: list[CatalogItem], max_items: int = 5, include_paid: bool = False
) -> list[Recommendation]:
    """One item per gap (most important gaps first), spread across platforms.

    For each gap: prefer free items whose level reaches the requirement, then the platform used
    least so far, so suggestions come from at least two learning platforms when the catalog allows.
    """
    picks: list[Recommendation] = []
    used_ids: set[str] = set()
    platform_use: dict[str, int] = {}
    for gap in gaps:
        if len(picks) >= max_items:
            break
        options = [
            c for c in catalog
            if gap.skill in c.skills and c.id not in used_ids and (include_paid or c.cost == "free")
        ]
        if not options:
            continue
        options.sort(key=lambda c: (
            c.level < gap.required,           # items that reach the target level first
            platform_use.get(c.platform, 0),  # then less-used platforms
            abs(c.level - gap.required),
            c.id,
        ))
        choice = options[0]
        picks.append(Recommendation(choice, gap))
        used_ids.add(choice.id)
        platform_use[choice.platform] = platform_use.get(choice.platform, 0) + 1
    return picks


def certification_goals(gaps: list[Gap], catalog: list[CatalogItem]) -> list[Recommendation]:
    """Paid certifications shown only as optional goals, tagged with their cost."""
    out = []
    for gap in gaps:
        for c in catalog:
            if c.kind == "certification" and c.cost != "free" and gap.skill in c.skills:
                if all(r.item.id != c.id for r in out):
                    out.append(Recommendation(c, gap))
    return out
