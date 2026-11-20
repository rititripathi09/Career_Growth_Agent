import plotly.graph_objects as go
import streamlit as st

from core.readiness import BANDS, READY
from core.ui import access, tax

a, t = access(), tax()
if a.viewer["band"] != "B4":
    st.stop()

org = a.org_view()
st.title("Organisation")
st.caption(f"{org.size} people across {len(a.groups())} teams · aggregated view, no individual data")

covered = sum(r["met"] for r in org.coverage.values())
needed = sum(r["needed_by"] for r in org.coverage.values())
mobility = a.mobility_by_role() or {}
c1, c2, c3 = st.columns(3)
c1.metric("Skill requirements met", f"{covered / needed:.0%}")
c2.metric("Ready for promotion", org.bands[READY])
c3.metric("Exploring another role", sum(mobility.values()))

# teams x skills heatmap
teams = [(name, a.group_view(name, ids)) for name, ids in a.groups()]
skills = sorted({s for _, g in teams if g.coverage for s in g.coverage})
z = [[(g.coverage[s]["share"] * 100 if g.coverage and s in g.coverage else None) for s in skills] for _, g in teams]
with st.container(border=True):
    st.subheader("Skill coverage: teams × skills")
    fig = go.Figure(go.Heatmap(z=z, x=[t.skill_name(s) for s in skills], y=[n for n, _ in teams],
                               colorscale="Blues", zmin=0, zmax=100, colorbar={"title": "% at level"}))
    fig.update_layout(height=320, margin={"t": 10, "b": 10, "l": 10, "r": 10})
    st.plotly_chart(fig, width="stretch")

left, right = st.columns(2)
with left, st.container(border=True):
    st.subheader("Biggest organisation gaps")
    for skill, below, need in org.top_gaps:
        st.markdown(f"**{t.skill_name(skill)}** · {below} of {need} people below the required level")
    st.subheader("Readiness bands")
    for b in BANDS:
        st.progress(org.bands[b] / org.size, text=f"{b}: {org.bands[b]}")
with right, st.container(border=True):
    st.subheader("Internal mobility pipeline")
    if mobility:
        fig = go.Figure(go.Bar(x=list(mobility.values()), y=[t.role_name(r) for r in mobility], orientation="h"))
        fig.update_layout(height=60 + 40 * len(mobility), margin={"t": 10, "b": 10, "l": 10, "r": 10})
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("Nobody is exploring another role yet.")
