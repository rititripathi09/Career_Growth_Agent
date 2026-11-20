"""The privacy layer: the ONLY way pages read or write personal data.

Rules
1. Owner-only: personal data (documents, skills, chats, interests, roadmap, readiness) is
   returned only to the person it belongs to.
2. Upward views are aggregates over at least MIN_GROUP people (see core/aggregate.py).
3. A name appears upward only when that person has opted in (share_consent).
"""
from __future__ import annotations

from dataclasses import dataclass

from core import aggregate, db
from core.readiness import Readiness, compute_readiness
from core.taxonomy import Taxonomy, load_taxonomy

LEADERSHIP_BANDS = ("B2", "B3", "B4")


class AccessDenied(Exception):
    """Raised when someone asks for another person's private data."""


@dataclass
class GroupView:
    name: str
    size: int
    coverage: dict | None          # aggregate.skill_coverage(...) or None if group too small
    top_gaps: list
    bands: dict | None             # readiness band counts or None
    shared: list[tuple[str, str]]  # (name, band) only for people who opted in
    exploring_other_roles: int | None


class Access:
    def __init__(self, conn, viewer_id: str, tax: Taxonomy | None = None):
        self.conn = conn
        self.viewer = db.get_employee(conn, viewer_id)
        if self.viewer is None:
            raise ValueError(f"Unknown employee {viewer_id}")
        self.tax = tax or load_taxonomy()

    # ------------------------------------------------------------------ own data
    def _own(self, owner_id: str | None) -> str:
        owner_id = owner_id or self.viewer["id"]
        if owner_id != self.viewer["id"]:
            raise AccessDenied("This profile is private to its owner.")
        return owner_id

    def profile(self, owner_id: str | None = None) -> dict[str, int]:
        return db._skills(self.conn, self._own(owner_id))

    def skill_rows(self, owner_id: str | None = None):
        return db._skill_rows(self.conn, self._own(owner_id))

    def interests(self, owner_id: str | None = None) -> dict[str, float]:
        return db._interests(self.conn, self._own(owner_id))

    def roadmap(self, owner_id: str | None = None):
        return db._roadmap(self.conn, self._own(owner_id))

    def chat_history(self, owner_id: str | None = None):
        return db._chat(self.conn, self._own(owner_id))

    def documents(self, owner_id: str | None = None):
        return db._documents(self.conn, self._own(owner_id))

    def shares_readiness(self) -> bool:
        return db._consent(self.conn, self.viewer["id"])

    def readiness(self, owner_id: str | None = None) -> Readiness:
        return _readiness_of(self.conn, self.viewer if owner_id is None else
                             db.get_employee(self.conn, self._own(owner_id)), self.tax)

    # ------------------------------------------------------------------ own writes
    def set_share_readiness(self, value: bool) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO share_consent(employee_id, share_readiness) VALUES (?,?)",
            (self.viewer["id"], int(value)),
        )
        self.conn.commit()

    def add_document(self, kind: str, text: str) -> None:
        """Save a source document for the viewer. An identical re-upload is not stored twice."""
        if self.conn.execute(
            "SELECT 1 FROM document WHERE employee_id=? AND kind=? AND text=?", (self.viewer["id"], kind, text)
        ).fetchone():
            return
        self.conn.execute(
            "INSERT INTO document(employee_id, kind, text) VALUES (?,?,?)",
            (self.viewer["id"], kind, text),
        )
        self.conn.commit()

    def save_skill(self, skill: str, level: int, evidence: str, source: str, confidence: float) -> None:
        db._upsert_skill(self.conn, self.viewer["id"], skill, level, evidence, source, confidence)
        self.conn.commit()

    def set_performance_rating(self, rating: float) -> None:
        self.conn.execute(
            "UPDATE employee SET performance_rating=? WHERE id=?", (rating, self.viewer["id"])
        )
        self.conn.commit()
        self.viewer = db.get_employee(self.conn, self.viewer["id"])

    def set_interest(self, topic: str, strength: float) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO interest(employee_id, topic, strength) VALUES (?,?,?)",
            (self.viewer["id"], topic, strength),
        )
        self.conn.commit()

    def add_chat(self, role: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO chat_message(employee_id, role, content) VALUES (?,?,?)",
            (self.viewer["id"], role, content),
        )
        self.conn.commit()

    def replace_roadmap(self, items: list[dict]) -> None:
        self.conn.execute("DELETE FROM roadmap_item WHERE employee_id=?", (self.viewer["id"],))
        for it in items:
            self.conn.execute(
                "INSERT INTO roadmap_item(employee_id, title, horizon, catalog_id, url) VALUES (?,?,?,?,?)",
                (self.viewer["id"], it["title"], it["horizon"], it.get("catalog_id"), it.get("url")),
            )
        self.conn.commit()

    def set_roadmap_done(self, item_id: int, done: bool) -> None:
        self.conn.execute(
            "UPDATE roadmap_item SET done=? WHERE id=? AND employee_id=?",
            (int(done), item_id, self.viewer["id"]),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ upward views
    @property
    def has_team_view(self) -> bool:
        return self.viewer["band"] in LEADERSHIP_BANDS

    def groups(self) -> list[tuple[str, list[str]]]:
        """The groups this viewer may see aggregates for: [(group name, member ids)]."""
        band, vid = self.viewer["band"], self.viewer["id"]
        if band == "B2":
            teams = self.conn.execute("SELECT * FROM team WHERE lead_id=?", (vid,)).fetchall()
        elif band == "B3":
            teams = self.conn.execute("SELECT * FROM team WHERE manager_id=?", (vid,)).fetchall()
        elif band == "B4":
            teams = db.all_teams(self.conn)
        else:
            return []
        out = []
        for t in teams:
            ids = [r["id"] for r in self.conn.execute(
                "SELECT id FROM employee WHERE team_id=? AND band='B1' ORDER BY id", (t["id"],))]
            out.append((t["name"], ids))
        return out

    def group_view(self, name: str, member_ids: list[str]) -> GroupView:
        allowed = {i for _, ids in self.groups() for i in ids}
        if not set(member_ids) <= allowed:
            raise AccessDenied("You can only see groups you lead or manage.")
        members = [db.get_employee(self.conn, i) for i in member_ids]
        profiles = [db._skills(self.conn, m["id"]) for m in members]
        roles = [m["role_id"] for m in members]
        readiness = [_readiness_of(self.conn, m, self.tax) for m in members]
        exploring = [_explores_other_role(self.conn, m, self.tax) for m in members]
        coverage = aggregate.skill_coverage(profiles, roles, self.tax)
        return GroupView(
            name=name,
            size=len(members),
            coverage=coverage,
            top_gaps=aggregate.top_gaps(coverage),
            bands=aggregate.readiness_bands([r.band for r in readiness]),
            shared=[(m["name"], r.band) for m, r in zip(members, readiness)
                    if db._consent(self.conn, m["id"])],
            exploring_other_roles=aggregate.count_if(exploring),
        )

    def mobility_by_role(self) -> dict[str, int] | None:
        """Leadership only: how many people are exploring each target role (no names)."""
        if self.viewer["band"] != "B4":
            raise AccessDenied("Organisation view is for leadership.")
        members = [db.get_employee(self.conn, i) for _, g in self.groups() for i in g]
        if not aggregate.big_enough(len(members)):
            return None
        counts: dict[str, int] = {}
        for m in members:
            for topic, strength in db._interests(self.conn, m["id"]).items():
                if strength >= 0.5 and topic != m["role_id"] and topic in self.tax.roles:
                    counts[topic] = counts.get(topic, 0) + 1
        return counts

    def org_view(self) -> GroupView:
        if self.viewer["band"] != "B4":
            raise AccessDenied("Organisation view is for leadership.")
        ids = [i for _, g in self.groups() for i in g]
        return self.group_view("Organisation", ids)


# ---------------------------------------------------------------------- helpers
def _readiness_of(conn, emp, tax: Taxonomy) -> Readiness:
    roadmap = db._roadmap(conn, emp["id"])
    return compute_readiness(
        profile=db._skills(conn, emp["id"]),
        role_id=emp["role_id"],
        tax=tax,
        performance_rating=emp["performance_rating"],
        evidence_count=db._evidence_count(conn, emp["id"]),
        roadmap_done=sum(1 for r in roadmap if r["done"]),
        roadmap_total=len(roadmap),
    )


def _explores_other_role(conn, emp, tax: Taxonomy) -> bool:
    interests = db._interests(conn, emp["id"])
    return any(strength >= 0.5 and topic != emp["role_id"] and topic in tax.roles
               for topic, strength in interests.items())
