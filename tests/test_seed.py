"""Seed safety tests: the demo story depends on these facts about the mock company.

If one fails after changing core/seed.py, data/taxonomy.yaml or data/catalog.yaml, the demo
(Priya -> Arjun -> Meera -> Vikram) would tell a different story. Fix the data, not the test.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import aggregate, db  # noqa: E402
from core.access import Access  # noqa: E402
from core.seed import seed  # noqa: E402
from core.taxonomy import load_catalog, load_taxonomy  # noqa: E402

TAX = load_taxonomy()
CAT = load_catalog()


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "seed.db")
    seed(c)
    return c


def test_every_team_has_at_least_5_b1_employees(conn):
    teams = db.all_teams(conn)
    assert len(teams) == 4
    for team in teams:
        n = conn.execute(
            "SELECT COUNT(*) FROM employee WHERE team_id=? AND band='B1'", (team["id"],)
        ).fetchone()[0]
        assert n >= aggregate.MIN_GROUP == 5, f"{team['name']} has only {n} B1 employees"


def test_priya_readiness_band_is_nearly_ready(conn):
    assert Access(conn, "priya").readiness().band == "Nearly ready"


def test_4_of_5_data_engineering_ics_below_cloud_requirement(conn):
    required = next(r.level for r in TAX.requirements("data_engineer") if r.skill == "cloud_platform")
    rows = conn.execute(
        """SELECT e.id, COALESCE(s.level, 0) AS level FROM employee e
           LEFT JOIN skill s ON s.employee_id = e.id AND s.skill = 'cloud_platform'
           WHERE e.team_id = 'de' AND e.band = 'B1'"""
    ).fetchall()
    below = {r["id"] for r in rows if r["level"] < required}
    assert len(rows) == 5
    assert len(below) == 4
    assert "priya" in below and "rahul" not in below


def test_only_rahul_and_sneha_share_readiness(conn):
    sharing = {r[0] for r in conn.execute("SELECT employee_id FROM share_consent WHERE share_readiness = 1")}
    assert sharing == {"rahul", "sneha"}


def test_catalog_and_seeded_skills_exist_in_taxonomy(conn):
    catalog_unknown = {s for c in CAT for s in c.skills} - set(TAX.skills)
    seeded_unknown = {r[0] for r in conn.execute("SELECT DISTINCT skill FROM skill")} - set(TAX.skills)
    assert not catalog_unknown, f"catalog uses unknown skills: {catalog_unknown}"
    assert not seeded_unknown, f"seed uses unknown skills: {seeded_unknown}"
    # roles used by employees and interests must exist too
    roles = {r[0] for r in conn.execute("SELECT role_id FROM employee")}
    roles |= {r[0] for r in conn.execute("SELECT topic FROM interest")}
    assert roles <= set(TAX.roles)


def test_every_required_skill_has_a_free_course():
    required = set(TAX.org_wide)
    for role in TAX.roles.values():
        required |= set(role.get("mandatory", {}))
    free = {s for c in CAT if c.cost == "free" for s in c.skills}
    assert required <= free, f"no free course for: {required - free}"
