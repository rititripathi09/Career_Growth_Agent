"""US-04 upload pipeline tests. No live AI calls: core.llm.chat is replaced by a fake."""
import json
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import db, llm, ui  # noqa: E402
from core.access import Access  # noqa: E402
from core.extract import ExtractedSkill, analyse_source, extract_profile, merge_skills  # noqa: E402
from core.seed import seed  # noqa: E402
from core.taxonomy import load_taxonomy  # noqa: E402

TAX = load_taxonomy()
RESUME = (ROOT / "data/sample_docs/priya_resume.txt").read_text(encoding="utf-8")
REPLY = json.dumps({"skills": [
    {"skill": "orchestration", "level": 2, "evidence": "Airflow DAGs for nightly loads", "confidence": 0.8},
    {"skill": "generative_ai", "level": 2, "evidence": "built a RAG prototype", "confidence": 0.7},
    {"skill": "python", "level": 2, "evidence": "Python scripts", "confidence": 0.9},  # lower than seeded 3
    {"skill": "telepathy", "level": 4, "evidence": "made up", "confidence": 1.0},     # not in taxonomy
], "dated_tech": ["cron"]})


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "upload.db")
    seed(c)
    return c


@pytest.fixture()
def fake_llm(monkeypatch):
    """Replace the model with a canned reply and count the calls."""
    calls = []

    def chat(messages, *args, **kwargs):
        calls.append(messages)
        return REPLY

    monkeypatch.setattr(llm, "chat", chat)
    return calls


def test_extraction_drops_invented_skill_ids(fake_llm):
    out = extract_profile(RESUME, "resume", TAX)
    assert "telepathy" not in {s.skill for s in out.skills}
    assert {s.skill for s in out.skills} <= set(TAX.skills)


def test_merge_skills_only_raises_levels():
    current = {"python": 3, "sql": 2}
    new = [
        ExtractedSkill(skill="python", level=2, evidence="", confidence=1),  # lower: ignored
        ExtractedSkill(skill="python", level=3, evidence="", confidence=1),  # same: ignored
        ExtractedSkill(skill="sql", level=3, evidence="a", confidence=1),    # raised
        ExtractedSkill(skill="sql", level=2, evidence="b", confidence=1),    # duplicate, lower: ignored
        ExtractedSkill(skill="git", level=1, evidence="", confidence=1),     # new skill
    ]
    kept = {s.skill: s.level for s in merge_skills(current, new)}
    assert kept == {"sql": 3, "git": 1}


def test_upload_saves_through_access_for_owner_only(conn, fake_llm):
    rahul_before = db._skills(conn, "rahul")
    priya = Access(conn, "priya")
    before = priya.profile()

    res = analyse_source(priya, "resume", RESUME, TAX)

    assert res.error is None
    after = priya.profile()
    assert after["orchestration"] == 2 and before["orchestration"] == 1  # raised
    assert after["python"] == before["python"] == 3                     # never lowered
    assert {(c.skill, c.old, c.new) for c in res.changes} == {("orchestration", 1, 2), ("generative_ai", 1, 2)}
    assert "cron" in res.dated_tech
    assert db._skills(conn, "rahul") == rahul_before  # nobody else's profile changed
    owners = {r[0] for r in conn.execute("SELECT employee_id FROM document WHERE kind='resume'")}
    assert "priya" in owners and conn.execute(
        "SELECT COUNT(*) FROM document WHERE employee_id='priya' AND text=?", (RESUME,)).fetchone()[0] == 1


def test_second_identical_upload_makes_zero_ai_calls(conn, fake_llm):
    priya = Access(conn, "priya")
    first = analyse_source(priya, "resume", RESUME, TAX)
    assert len(fake_llm) == 1 and not first.cached
    second = analyse_source(priya, "resume", RESUME, TAX)
    assert len(fake_llm) == 1, "second upload of the same text must come from the cache"
    assert second.cached and second.error is None
    assert conn.execute(  # and the document is not stored twice
        "SELECT COUNT(*) FROM document WHERE employee_id='priya' AND kind='resume'").fetchone()[0] == 1


@pytest.mark.parametrize("failure, hint", [
    (llm.LLMError("All providers failed. gemini: Error code: 503 - overloaded"), "busy"),
    (llm.LLMError("All providers failed. gemini: Error code: 429 RESOURCE_EXHAUSTED quota"), "quota"),
    ("not json", "couldn't read"),  # model keeps answering garbage
])
def test_llm_failure_is_handled_without_exception(conn, monkeypatch, failure, hint):
    def chat(*args, **kwargs):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(llm, "chat", chat)
    priya = Access(conn, "priya")
    before = priya.profile()
    res = analyse_source(priya, "resume", RESUME, TAX)
    assert res.error and hint in res.error.lower()
    assert priya.profile() == before  # nothing half-saved
    assert any(d["text"] == RESUME for d in priya.documents())  # the uploaded file is kept


# ---------------------------------------------------------------------- pages
@pytest.fixture()
def app(conn, monkeypatch):
    monkeypatch.setattr(ui, "get_conn", lambda: conn)

    def make(viewer_id: str) -> AppTest:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
        at.session_state["viewer_id"] = viewer_id
        return at

    return make


def test_upload_page_shows_friendly_message_on_ai_failure(app, monkeypatch):
    def chat(*args, **kwargs):
        raise llm.LLMError("All providers failed. gemini: Error code: 503")

    monkeypatch.setattr(llm, "chat", chat)
    at = app("priya").run()
    at.switch_page("views/upload.py").run()
    at.text_area[1].set_value("I used Python regularly and want to grow in cloud.").run()
    next(b for b in at.button if b.label == "Analyse with AI").click().run()
    assert not at.exception
    assert any("busy" in w.value for w in at.warning)


def test_upload_page_shows_what_changed(app, fake_llm):
    at = app("priya").run()
    at.switch_page("views/upload.py").run()
    at.text_area[1].set_value(RESUME).run()
    next(b for b in at.button if b.label == "Analyse with AI").click().run()
    assert not at.exception
    assert any("What changed" in s.value for s in at.subheader)


def test_reset_demo_button_reseeds(app, conn):
    Access(conn, "priya").add_document("resume", "rehearsal upload")
    db.cache_set(conn, "k", {"v": 1})
    at = app("priya").run()
    next(b for b in at.button if b.label == "Yes, reset the demo").click().run()
    assert not at.exception
    assert not any(d["text"] == "rehearsal upload" for d in Access(conn, "priya").documents())
    assert db.cache_get(conn, "k") == {"v": 1}  # saved AI answers survive the reset
