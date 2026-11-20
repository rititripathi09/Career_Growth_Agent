"""Build a 30/60/90-day roadmap from gaps and catalog recommendations (no AI call needed)."""
from __future__ import annotations

from core.gaps import Gap
from core.recommend import Recommendation
from core.taxonomy import Taxonomy


def build_roadmap(gaps: list[Gap], recs: list[Recommendation], tax: Taxonomy) -> list[dict]:
    """First gap → days 1-30, second → 31-60, the rest and a review → 61-90.

    Each gap gets a learning item (from the catalog) and a practice item, because a course
    alone only reaches level 1.
    """
    items: list[dict] = []
    horizons = [30, 60, 90]
    for i, rec in enumerate(recs):
        h = horizons[min(i, 2)]
        name = tax.skill_name(rec.gap.skill)
        items.append({
            "title": f"{rec.item.title} ({rec.item.platform})",
            "horizon": h,
            "catalog_id": rec.item.id,
            "url": rec.item.url,
        })
        if i < 2:
            items.append({"title": f"Apply {name} in one real task and show it at a team demo", "horizon": h})
    if gaps:
        items.append({"title": "Review progress with the AI mentor and update your sources", "horizon": 90})
    return items
