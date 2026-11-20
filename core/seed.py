"""Seed the mock company "Nimbus Tech": 27 people, 4 teams, bands B1-B4, plus the demo story.

Run it with `uv run python scripts/seed.py`. Deterministic (fixed random seed), so every demo
starts from the same data. No AI calls.
"""
from __future__ import annotations

import random

from core import db
from core.gaps import compute_gaps
from core.plan import build_roadmap
from core.recommend import recommend
from core.taxonomy import load_catalog, load_taxonomy

VP = ("vikram", "Vikram Rao")
MANAGERS = {"meera": "Meera Krishnan", "rohan": "Rohan Bhatia"}
TEAMS = [
    # id, name, role of ICs, (lead id, lead name), manager id, ICs
    ("de", "Data Engineering", "data_engineer", ("arjun", "Arjun Mehra"), "meera",
     [("priya", "Priya Sharma"), ("rahul", "Rahul Tiwari"), ("neha", "Neha Gupta"),
      ("karan", "Karan Mehta"), ("divya", "Divya Iyer")]),
    ("cp", "Cloud Platform", "cloud_engineer", ("kavya", "Kavya Menon"), "meera",
     [("aditya", "Aditya Rao"), ("sneha", "Sneha Pillai"), ("vivek", "Vivek Nair"),
      ("pooja", "Pooja Desai"), ("imran", "Imran Khan")]),
    ("fe", "Frontend", "frontend_engineer", ("sameer", "Sameer Kulkarni"), "rohan",
     [("ishita", "Ishita Bose"), ("manish", "Manish Verma"), ("tanvi", "Tanvi Joshi"),
      ("arnav", "Arnav Kapoor"), ("riya", "Riya Sen")]),
    ("ml", "ML", "ml_engineer", ("ananya", "Ananya Ghosh"), "rohan",
     [("siddharth", "Siddharth Jain"), ("meghna", "Meghna Das"), ("nikhil", "Nikhil Reddy"),
      ("fatima", "Fatima Sheikh"), ("harsh", "Harsh Patel")]),
]

# The demo story's main character: strong in Python/SQL, weak in cloud and orchestration,
# curious about ML. See "Demo script" in the build plan.
PRIYA_SKILLS = {
    "python": 3, "sql": 3, "data_modeling": 2, "cloud_platform": 1, "orchestration": 1,
    "testing": 2, "ci_cd": 1, "data_security": 2, "git": 2, "communication": 2,
    "ml_fundamentals": 2, "feature_engineering": 2, "mlops": 1, "generative_ai": 1,
}
INTERESTS = {  # people exploring another role (feeds the mobility pipeline)
    "priya": {"ml_engineer": 0.8},
    "aditya": {"ml_engineer": 0.7},
    "manish": {"ml_engineer": 0.6},
    "vivek": {"data_engineer": 0.7},
    "riya": {"cloud_engineer": 0.6},
}
SHARES_READINESS = {"rahul", "sneha"}
EVIDENCE_KINDS = ["resume", "review", "self_eval", "github", "transcript"]


# Skills added after Day 2 draw from their own random stream, so adding them did not change
# anyone's existing levels (the demo numbers stay the same).
LATER_SKILLS = {"generative_ai", "system_design"}
_later_rng = random.Random(7)


def _skills_for(role_id: str, tax, rng: random.Random) -> dict[str, int]:
    out = {}
    for r in tax.requirements(role_id):
        pick = (_later_rng if r.skill in LATER_SKILLS else rng).choice([-2, -1, -1, 0, 0, 0, 1])
        out[r.skill] = max(0, min(4, r.level + pick))
    return out


def seed(conn, keep_cache: bool = False) -> None:
    global _later_rng
    tax, catalog = load_taxonomy(), load_catalog()
    rng = random.Random(42)
    _later_rng = random.Random(7)  # reset each run so seeding stays deterministic
    db.reset(conn, keep_cache=keep_cache)

    def add(emp_id, name, band, role, team, manager, rating, skills):
        conn.execute(
            "INSERT INTO employee(id,name,band,role_id,team_id,manager_id,performance_rating) VALUES (?,?,?,?,?,?,?)",
            (emp_id, name, band, role, team, manager, rating),
        )
        for skill, level in skills.items():
            db._upsert_skill(conn, emp_id, skill, level, "Seeded from mock resume and review", "seed", 0.8)

    add(VP[0], VP[1], "B4", "engineering_manager", None, None, 4.5,
        _skills_for("engineering_manager", tax, rng) | {"people_leadership": 4, "delivery_planning": 4})
    for mid, mname in MANAGERS.items():
        add(mid, mname, "B3", "engineering_manager", None, VP[0], round(rng.uniform(3.5, 4.6), 1),
            _skills_for("engineering_manager", tax, rng))

    for team_id, team_name, ic_role, (lead_id, lead_name), mgr_id, ics in TEAMS:
        conn.execute("INSERT INTO team(id,name,lead_id,manager_id) VALUES (?,?,?,?)",
                     (team_id, team_name, lead_id, mgr_id))
        add(lead_id, lead_name, "B2", "team_lead", team_id, mgr_id, round(rng.uniform(3.4, 4.6), 1),
            _skills_for("team_lead", tax, rng) | _skills_for(ic_role, tax, rng))
        for emp_id, name in ics:
            if emp_id == "priya":
                skills, rating = dict(PRIYA_SKILLS), 4.0
            else:
                skills, rating = _skills_for(ic_role, tax, rng), round(rng.uniform(2.6, 4.8), 1)
            if team_id == "de" and emp_id not in ("rahul",):
                skills["cloud_platform"] = min(skills.get("cloud_platform", 0), 2)  # the team-wide cloud gap
            if emp_id == "rahul":
                skills.update({"cloud_platform": 3, "orchestration": 3, "python": 4, "sql": 4})
                rating = 4.7
            add(emp_id, name, "B1", ic_role, team_id, lead_id, rating, skills)

            # evidence sources already on file (Priya adds resume + GitHub live in the demo)
            if emp_id == "priya":
                kinds = ["review"]
            elif emp_id == "rahul":
                kinds = EVIDENCE_KINDS
            else:
                kinds = rng.sample(EVIDENCE_KINDS, rng.randint(1, 4))
            for kind in kinds:
                conn.execute("INSERT INTO document(employee_id,kind,text) VALUES (?,?,?)",
                             (emp_id, kind, f"Seeded mock {kind} for {name}"))

            # every IC gets a roadmap from their gaps; some progress already made
            gaps = compute_gaps(skills, ic_role, tax)
            items = build_roadmap(gaps, recommend(gaps, catalog), tax)
            done_n = 2 if emp_id == "priya" else rng.randint(0, len(items))
            for i, it in enumerate(items):
                conn.execute(
                    "INSERT INTO roadmap_item(employee_id,title,horizon,catalog_id,url,done) VALUES (?,?,?,?,?,?)",
                    (emp_id, it["title"], it["horizon"], it.get("catalog_id"), it.get("url"), int(i < done_n)),
                )

    for emp_id, topics in INTERESTS.items():
        for topic, strength in topics.items():
            conn.execute("INSERT INTO interest(employee_id,topic,strength) VALUES (?,?,?)", (emp_id, topic, strength))
    for emp_id in SHARES_READINESS:
        conn.execute("INSERT INTO share_consent(employee_id,share_readiness) VALUES (?,1)", (emp_id,))
    conn.commit()
