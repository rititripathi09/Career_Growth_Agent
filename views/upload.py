import time

import streamlit as st

from core.extract import Analysis, SkillChange, analyse_source, read_document
from core.github import repo_languages, skills_from_languages
from core.ui import access, tax

a, t = access(), tax()
RESULTS_KEY = f"upload_results_{a.viewer['id']}"  # last analysis, shown until the next one

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


def _github(username: str) -> Analysis:
    start, out = time.perf_counter(), Analysis(kind="github")
    try:
        found = skills_from_languages(repo_languages(username))
    except Exception:
        out.error = "We couldn't read public repos for that username. Check the spelling and try again."
        return out
    a.add_document("github", f"GitHub {username}: " + "; ".join(e for _, _, e in found))
    current = a.profile()
    for skill, level, evidence in found:
        if level > current.get(skill, -1):
            a.save_skill(skill, level, evidence, "github", 0.7)
            out.changes.append(SkillChange(skill, current.get(skill), level, evidence))
    out.seconds = time.perf_counter() - start
    return out


if st.button("Analyse with AI", type="primary"):
    sources: list[tuple[str, str, str]] = []  # (kind, label, text)
    for kind, f in (("resume", resume), ("cv", cv), ("review", review), ("transcript", transcript)):
        if f is not None:
            try:
                sources.append((kind, f"{kind} ({f.name})", read_document(f.getvalue(), f.name)))
            except Exception:
                st.error(f"We couldn't open {f.name}. Try saving it as TXT or DOCX and upload it again.")
    if linkedin.strip():
        sources.append(("linkedin", "LinkedIn profile", linkedin))
    if self_eval.strip():
        sources.append(("self_eval", "self-evaluation", self_eval))

    results: list[tuple[str, Analysis]] = []
    if not sources and not github_user.strip():
        st.warning("Add at least one source first, for example your resume.")
    else:
        with st.status("Reading your sources…", expanded=True) as status:
            for kind, label, text in sources:
                with st.spinner(f"Reading your {label}…"):
                    res = analyse_source(a, kind, text, t)
                results.append((label, res))
                if res.error:
                    st.write(f":orange[{label}: saved, not analysed yet]")
                else:
                    how = "from cache, no AI call" if res.cached else "AI"
                    st.write(f"{label}: {len(res.changes)} update(s) in {res.seconds:.1f} s ({how})")
            if github_user.strip():
                with st.spinner("Checking public GitHub repos…"):
                    res = _github(github_user.strip())
                results.append(("GitHub", res))
                st.write("GitHub: " + ("lookup failed" if res.error else f"{len(res.changes)} update(s)"))
            total = sum(len(r.changes) for _, r in results)
            failed = any(r.error for _, r in results)
            status.update(label=f"Done: {total} skill update(s)", state="error" if failed and not total else "complete")
        st.session_state[RESULTS_KEY] = results

for label, res in st.session_state.get(RESULTS_KEY, []):
    if res.error:
        st.warning(f"**{label}**: {res.error} Your file is saved, so you can simply press *Analyse with AI* again.")
        continue
    st.subheader(f"What changed from your {label}")
    st.caption(f"Took {res.seconds:.1f} s" + (" (answered from cache, no AI call)" if res.cached else ""))
    if res.changes:
        st.dataframe(
            [{"Skill": t.skill_name(c.skill),
              "Change": "New" if c.old is None else "Raised",
              "Level": f"{c.old} → {c.new}" if c.old is not None else str(c.new),
              "Evidence": c.evidence} for c in res.changes],
            width="stretch", hide_index=True,
        )
    else:
        st.info("No new skills or higher levels found. Your profile already reflects this document.")
    for tool in res.dated_tech:
        info = t.dated_tech[tool]
        st.caption(f":material/update: Dated tech spotted: **{tool}**. Consider {info['suggest']}.")

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
