import streamlit as st

from core.extract import extract_profile, merge_skills, read_document
from core.github import repo_languages, skills_from_languages
from core.llm import LLMError
from core.ui import access, tax

a, t = access(), tax()

st.title("Your sources")
st.caption("The agent reads these to build your skill profile. Everything here stays private to you.")

left, right = st.columns(2)
with left:
    resume = st.file_uploader("Resume (PDF, DOCX or TXT)", type=["pdf", "docx", "txt"])
    cv = st.file_uploader("Detailed CV", type=["pdf", "docx", "txt"])
    review = st.file_uploader("Latest performance review", type=["pdf", "docx", "txt"])
    transcript = st.file_uploader("Call / demo transcript (optional)", type=["txt", "pdf", "docx"])
with right:
    linkedin = st.text_area("LinkedIn profile (paste your About and Experience sections)", height=120)
    self_eval = st.text_area("Self-evaluation: what went well, what you want to grow in", height=120)
    github_user = st.text_input("GitHub username")

if st.button("Analyse with AI", type="primary"):
    sources = []
    for kind, f in (("resume", resume), ("cv", cv), ("review", review), ("transcript", transcript)):
        if f is not None:
            sources.append((kind, read_document(f.getvalue(), f.name)))
    if linkedin.strip():
        sources.append(("linkedin", linkedin))
    if self_eval.strip():
        sources.append(("self_eval", self_eval))

    added = 0
    with st.status("Reading your sources…", expanded=True) as status:
        for kind, text in sources:
            st.write(f"Analysing {kind.replace('_', ' ')}…")
            a.add_document(kind, text)
            try:
                result = extract_profile(text, kind, t, conn=a.conn)
            except LLMError as exc:
                st.error(f"The AI couldn't read your {kind}: {exc}")
                continue
            for s in merge_skills(a.profile(), result.skills):
                a.save_skill(s.skill, s.level, s.evidence, kind, s.confidence)
                added += 1
            if kind == "review" and result.performance_rating:
                a.set_performance_rating(result.performance_rating)
        if github_user.strip():
            st.write("Checking public GitHub repos…")
            try:
                found = skills_from_languages(repo_languages(github_user.strip()))
                a.add_document("github", f"GitHub {github_user}: " + "; ".join(e for _, _, e in found))
                current = a.profile()
                for skill, level, evidence in found:
                    if level > current.get(skill, -1):
                        a.save_skill(skill, level, evidence, "github", 0.7)
                        added += 1
            except Exception as exc:
                st.error(f"GitHub lookup failed: {exc}")
        status.update(label=f"Done: {added} skill update(s)", state="complete")

st.subheader("Your skill profile")
rows = a.skill_rows()
if rows:
    st.dataframe(
        [{"Skill": t.skill_name(r["skill"]), "Level (0-4)": r["level"], "Evidence": r["evidence"],
          "Source": r["source"]} for r in rows],
        width="stretch", hide_index=True,
    )
else:
    st.info("No skills yet. Upload your resume to start.")
