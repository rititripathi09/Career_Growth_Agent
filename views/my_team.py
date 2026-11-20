import plotly.graph_objects as go
import streamlit as st

from core import db
from core.access import AccessDenied
from core.readiness import BANDS
from core.ui import access, tax

a, t = access(), tax()
if not a.has_team_view:
    st.stop()

st.title("My team" if a.viewer["band"] == "B2" else "My teams")
st.info("You see team-level patterns only. Individual profiles, documents and chats stay private "
        "unless someone chooses to share.", icon=":material/lock:")

for name, ids in a.groups():
    g = a.group_view(name, ids)
    st.header(f"{name} · {g.size} people")
    if g.coverage is None:
        st.warning("This group has fewer than 5 people, so its data is hidden to protect privacy.")
        continue

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Skill coverage")
        rows = sorted(g.coverage.items(), key=lambda kv: kv[1]["share"])
        fig = go.Figure(go.Bar(
            x=[r["share"] * 100 for _, r in rows], y=[t.skill_name(s) for s, _ in rows], orientation="h",
            text=[f"{r['met']}/{r['needed_by']}" for _, r in rows], textposition="auto",
        ))
        fig.update_layout(height=40 + 26 * len(rows), margin={"t": 10, "b": 30, "l": 10, "r": 10},
                          xaxis={"title": "% of people at the required level", "range": [0, 100]})
        st.plotly_chart(fig, width="stretch")
    with right:
        with st.container(border=True):
            st.subheader("Top team gaps")
            for skill, below, needed in g.top_gaps:
                st.markdown(f"**{t.skill_name(skill)}** · {below} of {needed} below the required level")
        with st.container(border=True):
            st.subheader("Promotion readiness bands")
            for b in BANDS:
                st.progress(g.bands[b] / g.size, text=f"{b}: {g.bands[b]}")
            if g.shared:
                st.caption("Shared with you (opted in): " + ", ".join(f"{n} · {band}" for n, band in g.shared))
        if g.exploring_other_roles:
            st.caption(f"{g.exploring_other_roles} people are exploring other roles. Names stay hidden.")

st.divider()
st.subheader("Privacy check")
members = [db.get_employee(a.conn, i) for _, ids in a.groups() for i in ids]
pick = st.selectbox("Try opening a team member's full profile", [m["name"] for m in members], index=None)
if pick:
    target = next(m for m in members if m["name"] == pick)
    try:
        a.profile(owner_id=target["id"])
    except AccessDenied as exc:
        st.error(f"{pick}: {exc} You can see their role and team only.", icon=":material/lock:")
