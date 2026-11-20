"""Smoke tests: every page each persona can see renders without an exception.

Uses a temporary seeded database (never career_agent.db) and never calls an LLM.
"""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import db, llm, ui  # noqa: E402
from core.seed import seed  # noqa: E402

APP = str(ROOT / "app.py")
ME = ["views/my_growth.py", "views/upload.py", "views/roadmap.py", "views/mentor.py"]
PERSONA_PAGES = {
    "priya": ME,                               # B1: own pages only
    "arjun": ME + ["views/my_team.py"],        # B2 team lead
    "meera": ME + ["views/my_team.py"],        # B3 manager
    "vikram": ME + ["views/org.py"],           # B4 leadership
}


@pytest.fixture()
def app(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "pages.db")
    seed(conn)
    monkeypatch.setattr(ui, "get_conn", lambda: conn)

    def no_llm(*args, **kwargs):
        raise AssertionError("Page smoke tests must not call the LLM")

    for name in ("chat", "stream_chat", "chat_json"):
        monkeypatch.setattr(llm, name, no_llm)

    def make(viewer_id: str) -> AppTest:
        at = AppTest.from_file(APP, default_timeout=30)
        at.session_state["viewer_id"] = viewer_id
        return at

    return make


@pytest.mark.parametrize("viewer_id", list(PERSONA_PAGES))
def test_every_visible_page_renders(app, viewer_id):
    at = app(viewer_id).run()
    assert not at.exception, f"{viewer_id} home: {at.exception}"
    for page in PERSONA_PAGES[viewer_id]:
        at.switch_page(page).run()
        assert not at.exception, f"{viewer_id} {page}: {at.exception}"
        assert at.title, f"{viewer_id} {page}: page rendered no title"


def test_lead_is_blocked_from_member_profile(app):
    at = app("arjun").run()
    at.switch_page("views/my_team.py").run()
    picker = next(s for s in at.selectbox if s.label.startswith("Try opening"))
    picker.set_value("Priya Sharma").run()
    assert not at.exception
    assert any("private to its owner" in e.value for e in at.error)


@pytest.mark.parametrize("page", ["views/my_team.py", "views/org.py"])
def test_employee_has_no_team_pages(app, page):
    at = app("priya").run()
    with pytest.raises(ValueError, match="Could not find a navigation page"):
        at.switch_page(page)  # not registered in Priya's navigation at all
