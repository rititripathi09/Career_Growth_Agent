"""Career Growth Agent: run with `uv run streamlit run app.py`."""
import streamlit as st

from core import db
from core.access import Access
from core.ui import get_conn, tax

st.set_page_config(page_title="Career Growth Agent", page_icon=":material/trending_up:", layout="wide")

conn = get_conn()
employees = db.all_employees(conn)
labels = {e["id"]: f"{e['name']} · {tax().role_name(e['role_id'])} · {e['band']}" for e in employees}

st.session_state.setdefault("viewer_id", "priya")
with st.sidebar:
    st.markdown("### Career Growth Agent")
    st.selectbox(
        "Viewing as (demo persona switcher)",
        options=list(labels),
        format_func=labels.get,
        key="viewer_id",
        help="In the real product this comes from login. Here it lets you show every level.",
    )

viewer = Access(conn, st.session_state["viewer_id"])

me = [
    st.Page("views/my_growth.py", title="My growth", icon=":material/trending_up:", default=True),
    st.Page("views/upload.py", title="Upload and sources", icon=":material/upload_file:"),
    st.Page("views/roadmap.py", title="Roadmap and learning", icon=":material/route:"),
    st.Page("views/mentor.py", title="AI mentor", icon=":material/chat:"),
]
team = []
if viewer.viewer["band"] in ("B2", "B3"):
    team.append(st.Page("views/my_team.py", title="My team", icon=":material/groups:"))
if viewer.viewer["band"] == "B4":
    team.append(st.Page("views/org.py", title="Organisation", icon=":material/apartment:"))

pg = st.navigation({"Me": me, "Team": team} if team else me)

with st.sidebar:
    if viewer.has_team_view:
        st.caption("Team views are aggregates over 5 or more people. Names appear only when someone opts in.")
    else:
        st.caption("Private to you. Your lead and manager see only team-level trends, never your documents or chats.")

pg.run()
