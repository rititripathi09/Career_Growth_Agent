import plotly.graph_objects as go
import streamlit as st

from core import db
from core.extract import find_dated_tech
from core.gaps import compute_gaps, mandatory_coverage
from core.rolefit import suggest_role
from core.ui import access, tax, type_badge

a, t = access(), tax()
emp = a.viewer
profile = a.profile()
gaps = compute_gaps(profile, emp["role_id"], t)
covered, total = mandatory_coverage(profile, emp["role_id"], t)
r = a.readiness()
roadmap = a.roadmap()
team = db.get_team(a.conn, emp["team_id"]) if emp["team_id"] else None

st.title(f"Welcome back, {emp['name'].split()[0]}")
st.caption(f"{t.role_name(emp['role_id'])} · {team['name'] if team else 'Leadership'} · Band {emp['band']}")

c1, c2, c3 = st.columns(3)
c1.metric("Mandatory skills covered", f"{covered} / {total}")
c2.metric("Promotion readiness (private)", f"{r.score}", r.band, delta_color="off")
c3.metric("Roadmap progress", f"{sum(1 for i in roadmap if i['done'])} of {len(roadmap)}")

left, right = st.columns(2)
with left, st.container(border=True):
    st.subheader("Skill gaps for your role")
    reqs = t.requirements(emp["role_id"])
    names = [t.skill_name(q.skill) for q in reqs]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=[q.level for q in reqs] + [reqs[0].level], theta=names + [names[0]],
                                  name="Required", line={"dash": "dot"}))
    fig.add_trace(go.Scatterpolar(r=[profile.get(q.skill, 0) for q in reqs] + [profile.get(reqs[0].skill, 0)],
                                  theta=names + [names[0]], name="You", fill="toself"))
    fig.update_layout(polar={"radialaxis": {"range": [0, 4], "tickvals": [1, 2, 3, 4]}},
                      height=340, margin={"t": 20, "b": 20, "l": 40, "r": 40}, legend={"orientation": "h"})
    st.plotly_chart(fig, width="stretch")
    if not gaps:
        st.success("You meet every requirement for your role.")
    for g in gaps:
        st.markdown(f"**{t.skill_name(g.skill)}** · {g.current} → {g.required} {type_badge(g.type)}")

with right:
    with st.container(border=True):
        st.subheader("Readiness breakdown")
        st.caption("Only you can see this score.")
        labels = {"coverage": "Mandatory skill coverage · 40%", "performance": "Performance rating · 25%",
                  "evidence": "Evidence sources · 20%", "roadmap": "Roadmap progress · 15%"}
        for key, label in labels.items():
            st.progress(r.breakdown[key], text=label)
        shared = st.toggle("Share my readiness band with my team lead", value=a.shares_readiness())
        if shared != a.shares_readiness():
            a.set_share_readiness(shared)
            st.toast("Saved. You can change this any time.")

    fit = suggest_role(profile, emp["role_id"], a.interests(), t)
    if fit:
        with st.container(border=True):
            st.subheader("A role that may fit you")
            st.markdown(f"**{t.role_name(fit.role_id)} · {fit.match:.0%} match** "
                        f"(your current role: {fit.current_match:.0%})")
            st.caption("To get there: " + ", ".join(t.skill_name(s) for s in fit.to_learn))
            st.page_link("views/mentor.py", label="Ask the mentor about it", icon=":material/chat:")

    dated = find_dated_tech(" ".join(d["text"] for d in a.documents()), t)
    if dated:
        with st.container(border=True):
            st.subheader("Tech-stack check")
            for tool, info in dated:
                st.markdown(f"Your documents mention **{tool}**. Consider {info['suggest']}.")
