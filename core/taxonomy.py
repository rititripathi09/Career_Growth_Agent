"""Load the role-skill taxonomy and the learning catalog from YAML."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MANDATORY = "mandatory"
GOOD_TO_HAVE = "good_to_have"
ORG_WIDE = "org_wide"


@dataclass(frozen=True)
class Requirement:
    skill: str
    level: int
    type: str  # mandatory | good_to_have | org_wide


@dataclass
class Taxonomy:
    skills: dict[str, dict]
    roles: dict[str, dict]
    org_wide: dict[str, int]
    levels: dict[int, str]
    dated_tech: dict[str, dict] = field(default_factory=dict)

    def skill_name(self, skill_id: str) -> str:
        return self.skills.get(skill_id, {}).get("name", skill_id)

    def role_name(self, role_id: str) -> str:
        return self.roles.get(role_id, {}).get("name", role_id)

    def requirements(self, role_id: str) -> list[Requirement]:
        """All requirements for a role: its own mandatory + good-to-have, plus org-wide skills.

        If a role lists an org-wide skill itself, the higher level wins and it counts as mandatory.
        """
        role = self.roles[role_id]
        reqs: dict[str, Requirement] = {}
        for skill, level in self.org_wide.items():
            reqs[skill] = Requirement(skill, level, ORG_WIDE)
        for skill, level in role.get("mandatory", {}).items():
            prev = reqs.get(skill)
            reqs[skill] = Requirement(skill, max(level, prev.level if prev else 0), MANDATORY)
        for skill, level in role.get("good_to_have", {}).items():
            if skill not in reqs:
                reqs[skill] = Requirement(skill, level, GOOD_TO_HAVE)
        return list(reqs.values())


@dataclass(frozen=True)
class CatalogItem:
    id: str
    title: str
    platform: str
    url: str
    skills: tuple[str, ...]
    level: int
    kind: str
    cost: str


def _load_yaml(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def load_taxonomy() -> Taxonomy:
    raw = _load_yaml("taxonomy.yaml")
    return Taxonomy(
        skills=raw["skills"],
        roles=raw["roles"],
        org_wide=raw.get("org_wide", {}),
        levels={int(k): v for k, v in raw.get("levels", {}).items()},
        dated_tech=raw.get("dated_tech", {}),
    )


@lru_cache(maxsize=1)
def load_catalog() -> list[CatalogItem]:
    raw = _load_yaml("catalog.yaml")
    return [
        CatalogItem(
            id=i["id"],
            title=i["title"],
            platform=i["platform"],
            url=i["url"],
            skills=tuple(i["skills"]),
            level=int(i["level"]),
            kind=i["kind"],
            cost=i["cost"],
        )
        for i in raw["items"]
    ]
