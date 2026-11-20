"""The AI mentor: a system prompt grounded in the employee's own private data, plus the
interest questionnaire that feeds role-fit detection."""
from __future__ import annotations

from core.gaps import Gap
from core.readiness import Readiness
from core.taxonomy import Taxonomy

# Each answer maps to the role it signals interest in (stored as interest[role_id] = strength).
QUESTIONNAIRE = [
    {
        "q": "Which kind of work gives you the most energy?",
        "options": {
            "Building data pipelines": "data_engineer",
            "Training and improving models": "ml_engineer",
            "Running reliable cloud infrastructure": "cloud_engineer",
            "Building user interfaces": "frontend_engineer",
            "Helping people grow": "team_lead",
        },
    },
    {
        "q": "Which project would you volunteer for first?",
        "options": {
            "Speeding up a slow data job": "data_engineer",
            "A recommendation or prediction feature": "ml_engineer",
            "Moving a service to Kubernetes": "cloud_engineer",
            "Redesigning a dashboard": "frontend_engineer",
            "Onboarding new joiners": "team_lead",
        },
    },
    {
        "q": "What would you like to be known for in two years?",
        "options": {
            "Data quality and modeling": "data_engineer",
            "Machine learning expertise": "ml_engineer",
            "Platform reliability": "cloud_engineer",
            "Great product experiences": "frontend_engineer",
            "Leading a team": "team_lead",
        },
    },
]


def system_prompt(
    name: str, role_id: str, profile: dict[str, int], gaps: list[Gap],
    readiness: Readiness, roadmap_titles: list[str], interests: dict[str, float], tax: Taxonomy,
) -> str:
    strengths = ", ".join(f"{tax.skill_name(s)} ({lvl})" for s, lvl in
                          sorted(profile.items(), key=lambda x: -x[1])[:5]) or "none recorded yet"
    gap_txt = "; ".join(f"{tax.skill_name(g.skill)} {g.current}→{g.required} ({g.type})" for g in gaps[:5]) or "none"
    interest_txt = ", ".join(f"{tax.role_name(r)} {v:.1f}" for r, v in interests.items()) or "unknown"
    road = "; ".join(roadmap_titles[:6]) or "not created yet"
    return f"""You are a supportive, practical career mentor inside a company's growth tool.
You are talking privately with {name}, a {tax.role_name(role_id)}. Nothing they say is shared with their manager.

What you know (use it, don't recite it all):
- Strengths (level 0-4): {strengths}
- Gaps for their role: {gap_txt}
- Promotion readiness (private): {readiness.score}/100, {readiness.band}
- Roadmap: {road}
- Interests by role (0-1): {interest_txt}

Rules:
- Give specific, small next steps tied to their gaps and roadmap.
- Recommend learning only from their roadmap or the free platforms Microsoft Learn, freeCodeCamp
  and Kaggle Learn; never invent course names or links.
- If their interests point to another role, say so gently and explain what they'd need to learn.
- Never claim to see other employees' data. Keep answers under 150 words unless asked for more."""
