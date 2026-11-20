"""Builds notebooks/02_synthetic_dataset_and_eval.ipynb (open the result in Google Colab)."""
import json
from pathlib import Path

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text})


def code(text):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text})


md("""# Nimbus Tech synthetic dataset: explore it and score the AI extractor (Google Colab)

The dataset is **synthetic**: 27 fictional employees, 4 teams, bands B1-B4. Every resume and review was
generated *from* the person's true skill levels, so `skills_ground_truth.csv` is an answer key.

1. On your laptop run `uv run python scripts/export_dataset.py`, then zip the `data/synthetic` folder
   as `synthetic.zip` (or use the copy that came with the starter project).
2. In Colab, add `GEMINI_API_KEY` under the key icon (Secrets) and allow notebook access.
3. Run the cells top to bottom.""")

code("""from google.colab import files
import zipfile, io
uploaded = files.upload()  # choose synthetic.zip
zipfile.ZipFile(io.BytesIO(next(iter(uploaded.values())))).extractall("synthetic")
!find synthetic -maxdepth 2 -name "*.csv" | sort""")

code("""import glob, os, pandas as pd
base = os.path.dirname(glob.glob("synthetic/**/employees.csv", recursive=True)[0])
emp = pd.read_csv(f"{base}/employees.csv")
truth = pd.read_csv(f"{base}/skills_ground_truth.csv")
reqs = pd.read_csv(f"{base}/role_requirements.csv")
teams = pd.read_csv(f"{base}/teams.csv")
print(emp.groupby(["band"]).size().rename("people"))
emp.head(10)""")

md("## Team skill coverage (the same numbers the lead's dashboard shows)")

code("""ics = emp[emp.band == "B1"].merge(teams[["id", "name"]], left_on="team_id", right_on="id", suffixes=("", "_team"))
need = ics.merge(reqs, on="role_id")[["id", "name_team", "skill", "required_level"]]
have = need.merge(truth, left_on=["id", "skill"], right_on=["employee_id", "skill"], how="left").fillna({"level": 0})
have["met"] = have.level >= have.required_level
coverage = have.pivot_table(index="name_team", columns="skill", values="met", aggfunc="mean")
coverage.style.format("{:.0%}", na_rep="").background_gradient(cmap="Blues", axis=None)""")

md("""## Score the extractor against the answer key

Uses the free Gemini tier, so it checks a small sample with a pause between calls.""")

code("""!pip install -q openai
from google.colab import userdata
from openai import OpenAI
import json, time

client = OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=userdata.get("GEMINI_API_KEY"))
MODEL = "gemini-flash-latest"  # check AI Studio for the current free Flash model name

SKILLS = sorted(truth.skill.unique())
SYSTEM = (
    "You read an employee's resume and extract evidence-backed skills.\\n"
    "Use ONLY these skill ids: " + ", ".join(SKILLS) + ".\\n"
    "Levels: 0=None, 1=Aware, 2=Working, 3=Strong, 4=Expert. A course alone is level 1; production work is 2-3; "
    "leading others or deep expertise is 3-4. Skip skills with no evidence.\\n"
    'Reply with ONLY JSON: {"skills": [{"skill": id, "level": int, "evidence": str}]}'
)

def extract(text):
    resp = client.chat.completions.create(
        model=MODEL, temperature=0.1, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}])
    return {s["skill"]: s["level"] for s in json.loads(resp.choices[0].message.content)["skills"] if s["skill"] in SKILLS}""")

code("""rows = []
for emp_id in emp[emp.band == "B1"].id.sample(8, random_state=1):
    text = open(f"{base}/documents/{emp_id}_resume.txt").read()
    got = extract(text)
    true = truth[(truth.employee_id == emp_id) & (truth.level > 0)].set_index("skill").level.to_dict()
    for skill in set(true) | set(got):
        rows.append({"employee": emp_id, "skill": skill, "true": true.get(skill, 0), "ai": got.get(skill, 0)})
    time.sleep(5)  # stay under the free-tier per-minute limit

res = pd.DataFrame(rows)
res["exact"] = res.true == res.ai
res["within_1"] = (res.true - res.ai).abs() <= 1
print(f"Exact level match: {res.exact.mean():.0%}   Within one level: {res.within_1.mean():.0%}")
print(f"Missed skills: {((res.true > 0) & (res.ai == 0)).sum()}   Invented skills: {((res.true == 0) & (res.ai > 0)).sum()}")
res[~res.exact].sort_values(["employee", "skill"])""")

md("""**Use the result:** if levels are too high or too low, tune the level rules in the prompt, re-run, then copy
the improved wording into `core/extract.py`. This accuracy number is also a strong slide for the pitch.""")

nb = {
    "cells": cells,
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python"}, "colab": {"provenance": []}},
    "nbformat": 4,
    "nbformat_minor": 5,
}
out = Path(__file__).resolve().parent.parent / "notebooks" / "02_synthetic_dataset_and_eval.ipynb"
out.write_text(json.dumps(nb, indent=1))
print("wrote", out)
