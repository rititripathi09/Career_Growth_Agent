import streamlit as st

from core.gaps import compute_gaps
from core.plan import build_roadmap
from core.recommend import certification_goals, recommend
from core.ui import access, catalog, tax, type_badge

a, t, cat = access(), tax(), catalog()
gaps = compute_gaps(a.profile(), a.viewer["role_id"], t)
recs = recommend(gaps, cat)

st.title("Your 90-day roadmap")
st.caption(f"Built from your top gaps for {t.role_name(a.viewer['role_id'])}.")

if st.button("Rebuild my roadmap from my current gaps"):
    a.replace_roadmap(build_roadmap(gaps, recs, t))
    st.rerun()

items = a.roadmap()
cols = st.columns(3)
for col, (h, label) in zip(cols, [(30, "First 30 days"), (60, "Days 31-60"), (90, "Days 61-90")]):
    with col, st.container(border=True):
        st.markdown(f"**{label}**")
        for it in [i for i in items if i["horizon"] == h]:
            text = f"[{it['title']}]({it['url']})" if it["url"] else it["title"]
            done = st.checkbox(text, value=bool(it["done"]), key=f"rm{it['id']}")
            if done != bool(it["done"]):
                a.set_roadmap_done(it["id"], done)
                st.rerun()

st.subheader("Recommended free courses")
platforms = sorted({r.item.platform for r in recs})
st.caption("From " + ", ".join(platforms) + " — all free and publicly accessible." if platforms else "")
grid = st.columns(3)
for i, rec in enumerate(recs):
    with grid[i % 3], st.container(border=True):
        st.caption(f"{rec.item.platform} · {rec.item.kind}")
        st.markdown(f"**{rec.item.title}**")
        st.markdown(f"Closes: {t.skill_name(rec.gap.skill)} {type_badge(rec.gap.type)}")
        st.link_button("Open course", rec.item.url)

certs = certification_goals(gaps, cat)
if certs:
    with st.expander("Optional certification goals (exam fee)"):
        for c in certs:
            st.markdown(f"- [{c.item.title}]({c.item.url}) · {c.item.platform} · prepare with the free courses above first")
