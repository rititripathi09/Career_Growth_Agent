"""Tests for the parts that must never be wrong: privacy, aggregates, scoring, recommendations."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import aggregate, db  # noqa: E402
from core.access import Access, AccessDenied  # noqa: E402
from core.gaps import compute_gaps, mandatory_coverage  # noqa: E402
from core.readiness import compute_readiness  # noqa: E402
from core.recommend import recommend  # noqa: E402
from core.rolefit import suggest_role  # noqa: E402
from core.seed import seed  # noqa: E402
from core.taxonomy import load_catalog, load_taxonomy  # noqa: E402

TAX = load_taxonomy()
CAT = load_catalog()


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    seed(c)
    return c


# ---------------------------------------------------------------- seed
def test_seed_shape(conn):
    bands = [r["band"] for r in db.all_employees(conn)]
    assert len(bands) == 27
    assert (bands.count("B1"), bands.count("B2"), bands.count("B3"), bands.count("B4")) == (20, 4, 2, 1)
    for team in db.all_teams(conn):
        n = conn.execute("SELECT COUNT(*) FROM employee WHERE team_id=? AND band='B1'", (team["id"],)).fetchone()[0]
        assert n >= aggregate.MIN_GROUP


# ---------------------------------------------------------------- privacy
def test_employee_sees_only_own_data(conn):
    priya = Access(conn, "priya")
    assert priya.profile()  # own data works
    with pytest.raises(AccessDenied):
        priya.profile(owner_id="rahul")
    with pytest.raises(AccessDenied):
        priya.chat_history(owner_id="rahul")
    assert priya.groups() == []
    assert not priya.has_team_view


@pytest.mark.parametrize("viewer", ["arjun", "meera", "vikram"])
def test_leaders_cannot_open_individual_profiles(conn, viewer):
    with pytest.raises(AccessDenied):
        Access(conn, viewer).profile(owner_id="priya")
    with pytest.raises(AccessDenied):
        Access(conn, viewer).documents(owner_id="priya")


def test_lead_sees_only_own_team(conn):
    arjun = Access(conn, "arjun")
    groups = arjun.groups()
    assert [name for name, _ in groups] == ["Data Engineering"]
    with pytest.raises(AccessDenied):
        arjun.group_view("Cloud Platform", ["aditya", "sneha", "vivek", "pooja", "imran"])


def test_manager_and_vp_scope(conn):
    assert {n for n, _ in Access(conn, "meera").groups()} == {"Data Engineering", "Cloud Platform"}
    assert len(Access(conn, "vikram").groups()) == 4
    with pytest.raises(AccessDenied):
        Access(conn, "meera").org_view()


def test_names_only_with_consent(conn):
    view = Access(conn, "arjun").group_view(*Access(conn, "arjun").groups()[0])
    assert [n for n, _ in view.shared] == ["Rahul Tiwari"]  # Priya has not opted in
    Access(conn, "priya").set_share_readiness(True)
    view = Access(conn, "arjun").group_view(*Access(conn, "arjun").groups()[0])
    assert "Priya Sharma" in [n for n, _ in view.shared]


# ---------------------------------------------------------------- aggregates
def test_small_groups_are_hidden():
    profiles = [{"python": 3}] * 4
    assert aggregate.skill_coverage(profiles, ["data_engineer"] * 4, TAX) is None
    assert aggregate.readiness_bands(["Ready"] * 4) is None
    assert aggregate.count_if([True] * 4) is None
    assert aggregate.readiness_bands(["Ready"] * 5) == {"Ready": 5, "Nearly ready": 0, "Developing": 0}


def test_demo_story_team_cloud_gap(conn):
    view = Access(conn, "arjun").group_view(*Access(conn, "arjun").groups()[0])
    assert view.top_gaps[0][:3] == ("cloud_platform", 4, 5)


# ---------------------------------------------------------------- gaps & readiness
def test_gaps_order_mandatory_first():
    gaps = compute_gaps({"python": 3, "sql": 3}, "data_engineer", TAX)
    types = [g.type for g in gaps]
    assert types == sorted(types, key=lambda x: {"mandatory": 0, "org_wide": 1, "good_to_have": 2}[x])
    assert mandatory_coverage({"python": 3, "sql": 3}, "data_engineer", TAX) == (2, 8)


def test_readiness_bounds_and_bands():
    full = {r.skill: 4 for r in TAX.requirements("data_engineer")}
    top = compute_readiness(full, "data_engineer", TAX, 5, 5, 4, 4)
    assert top.score == 100 and top.band == "Ready"
    low = compute_readiness({}, "data_engineer", TAX, 1, 0, 0, 0)
    assert low.score == 0 and low.band == "Developing"


def test_priya_is_nearly_ready(conn):
    assert Access(conn, "priya").readiness().band == "Nearly ready"


# ---------------------------------------------------------------- recommendations & role fit
def test_recommendations_free_known_and_multi_platform():
    gaps = compute_gaps({"python": 1, "sql": 1}, "data_engineer", TAX)
    recs = recommend(gaps, CAT)
    ids = {c.id for c in CAT}
    assert recs and all(r.item.id in ids and r.item.cost == "free" for r in recs)
    assert len({r.item.platform for r in recs}) >= 2


def test_catalog_uses_known_skills_and_three_platforms():
    assert all(s in TAX.skills for c in CAT for s in c.skills)
    assert {c.platform for c in CAT} >= {"Microsoft Learn", "freeCodeCamp", "Kaggle Learn"}


def test_role_fit_needs_interest(conn):
    profile = Access(conn, "priya").profile()
    assert suggest_role(profile, "data_engineer", {}, TAX) is None
    fit = suggest_role(profile, "data_engineer", {"ml_engineer": 0.8}, TAX)
    assert fit and fit.role_id == "ml_engineer"


# ---------------------------------------------------------------- AI layer (model call faked)
def test_extract_validates_and_drops_unknown_skills(monkeypatch, conn):
    from core import extract, llm

    replies = iter([
        "not json at all",  # first answer invalid -> retried
        '{"skills": [{"skill": "python", "level": 3, "evidence": "4 pipelines", "confidence": 0.9},'
        ' {"skill": "basket_weaving", "level": 4, "evidence": "x", "confidence": 1}],'
        ' "dated_tech": ["cron"]}',
    ])
    monkeypatch.setattr(llm, "chat", lambda *a, **k: next(replies))
    out = extract.extract_profile("resume text", "resume", TAX, conn=conn)
    assert [s.skill for s in out.skills] == ["python"]
    # second identical call is served from the cache (no more replies needed)
    assert [s.skill for s in extract.extract_profile("resume text", "resume", TAX, conn=conn).skills] == ["python"]


def test_dated_tech_keyword_check():
    from core.extract import find_dated_tech

    text = (Path(__file__).resolve().parent.parent / "data/sample_docs/priya_resume.txt").read_text()
    assert [tool for tool, _ in find_dated_tech(text, TAX)] == ["cron"]
