import streamlit as st

from core.gaps import compute_gaps
from core.llm import LLMError, stream_chat
from core.mentor import QUESTIONNAIRE, system_prompt
from core.ui import access, tax

a, t = access(), tax()
emp = a.viewer

st.title("AI mentor")
st.caption("Uses your skill gaps, roadmap and interests. Your conversations are never visible to your lead, "
           "manager or leadership.")

with st.expander("Quick interest check (3 questions)", expanded=not a.interests()):
    with st.form("questionnaire"):
        answers = [st.radio(q["q"], list(q["options"]), index=None, key=f"q{i}") for i, q in enumerate(QUESTIONNAIRE)]
        if st.form_submit_button("Save my answers"):
            picked = [QUESTIONNAIRE[i]["options"][ans] for i, ans in enumerate(answers) if ans]
            for role_id in set(picked):
                a.set_interest(role_id, round(picked.count(role_id) / len(QUESTIONNAIRE), 2))
            st.success("Saved. The mentor and your role-fit card now use these.")

history = a.chat_history()
for m in history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask about your growth, a skill, or a role…"):
    a.add_chat("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
    profile = a.profile()
    system = system_prompt(
        emp["name"], emp["role_id"], profile, compute_gaps(profile, emp["role_id"], t),
        a.readiness(), [r["title"] for r in a.roadmap() if not r["done"]], a.interests(), t,
    )
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-10:]]
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant"):
        try:
            answer = st.write_stream(stream_chat(messages))
            a.add_chat("assistant", answer)
        except LLMError as exc:
            st.error(f"The mentor is unavailable right now: {exc}")
