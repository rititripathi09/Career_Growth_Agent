"""Builds notebooks/01_extraction_playground.ipynb (run once; the notebook is what you open in Colab)."""
import json
from pathlib import Path

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text})


def code(text):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text})


md("""# Career Growth Agent: skill-extraction playground (Google Colab)

Use this free notebook to **try prompts on real public resumes** before putting them in the app.

1. In Colab, open the key icon (Secrets) on the left and add `GEMINI_API_KEY` (free from Google AI Studio). Turn on notebook access.
2. Run the cells top to bottom.
3. When the extraction looks right, copy your prompt changes into `core/extract.py`.

Dataset: the public Kaggle *Resume Dataset* (962 resumes, 25 tech job categories such as Data Science, DevOps, Testing).
It's used only for testing extraction. The app itself runs on the synthetic Nimbus Tech data.""")

code("!pip install -q openai pydantic kagglehub pandas")

code("""from google.colab import userdata
from openai import OpenAI

client = OpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=userdata.get("GEMINI_API_KEY"),
)
MODEL = "gemini-flash-latest"  # check AI Studio for the current free Flash model name

print(client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": "Say hi in 3 words"}])
      .choices[0].message.content)""")

code("""import kagglehub, pandas as pd, glob

path = kagglehub.dataset_download("gauravduttakiit/resume-dataset")
csv = glob.glob(f"{path}/**/*.csv", recursive=True)[0]
df = pd.read_csv(csv)
print(df.shape)
df["Category"].value_counts().head(15)""")

code("""SKILLS = {
    "python": "Python", "sql": "SQL", "data_modeling": "Data modeling",
    "cloud_platform": "Cloud platform (Azure / AWS / GCP)", "orchestration": "Workflow orchestration",
    "streaming": "Streaming data", "containers": "Containers and Kubernetes",
    "infrastructure_as_code": "Infrastructure as code", "ci_cd": "CI/CD", "monitoring": "Monitoring",
    "javascript": "JavaScript / TypeScript", "react": "React", "html_css": "HTML and CSS",
    "testing": "Automated testing", "ml_fundamentals": "Machine learning fundamentals",
    "feature_engineering": "Feature engineering", "deep_learning": "Deep learning", "mlops": "MLOps",
    "data_security": "Data security basics", "git": "Git and code review",
    "communication": "Communication and presenting",
}

SYSTEM = (
    "You read an employee's resume and extract evidence-backed skills.\\n"
    "Use ONLY these skill ids:\\n" + "\\n".join(f"- {k}: {v}" for k, v in SKILLS.items()) +
    "\\nLevels: 0=None, 1=Aware, 2=Working, 3=Strong, 4=Expert. Be conservative: a course alone is level 1; "
    "production work is 2-3; leading others or deep expertise is 3-4.\\n"
    "Every skill needs concrete evidence from the text. Skip skills with no evidence.\\n"
    'Reply with ONLY JSON: {"skills": [{"skill": id, "level": int, "evidence": str, "confidence": 0-1}]}'
)""")

code("""import json

def extract(text):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": text[:12000]}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    data = json.loads(resp.choices[0].message.content)
    return [s for s in data["skills"] if s["skill"] in SKILLS]  # drop invented ids

sample = df[df["Category"] == "Data Science"].iloc[0]["Resume"]
pd.DataFrame(extract(sample))""")

md("""## Try it on a few categories

The free tier is rate-limited, so test a handful of resumes, not hundreds.""")

code("""import time
for cat in ["DevOps Engineer", "Testing", "Python Developer"]:
    rows = df[df["Category"] == cat]
    if rows.empty:
        continue
    print("\\n==", cat)
    print(pd.DataFrame(extract(rows.iloc[0]["Resume"]))[["skill", "level", "evidence"]].to_string(index=False))
    time.sleep(5)  # stay under the free-tier per-minute limit""")

nb = {
    "cells": cells,
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python"}, "colab": {"provenance": []}},
    "nbformat": 4,
    "nbformat_minor": 5,
}
out = Path(__file__).resolve().parent.parent / "notebooks" / "01_extraction_playground.ipynb"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(nb, indent=1))
print("wrote", out)
