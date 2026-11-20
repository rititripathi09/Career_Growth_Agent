"""Export the synthetic Nimbus Tech dataset as CSV files + text documents.

    uv run python scripts/export_dataset.py

Writes data/synthetic/:
  employees.csv, teams.csv, skills_ground_truth.csv, interests.csv, roadmap.csv, consent.csv,
  role_requirements.csv, catalog.csv, documents/<id>_resume.txt, documents/<id>_review.txt
Upload the folder (or the zip) to Google Colab to explore it or to evaluate the AI extractor.
"""
import csv
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import db  # noqa: E402
from core.seed import seed  # noqa: E402
from core.synthetic import make_resume, make_review  # noqa: E402
from core.taxonomy import load_catalog, load_taxonomy  # noqa: E402

OUT = ROOT / "data" / "synthetic"


def write_csv(name: str, rows: list[dict]) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    tax, cat = load_taxonomy(), load_catalog()
    conn = db.connect(":memory:")
    seed(conn)
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "documents").mkdir(parents=True)

    q = lambda sql: [dict(r) for r in conn.execute(sql)]  # noqa: E731
    write_csv("employees.csv", q("SELECT * FROM employee ORDER BY band DESC, team_id, id"))
    write_csv("teams.csv", q("SELECT * FROM team ORDER BY id"))
    write_csv("skills_ground_truth.csv", q("SELECT employee_id, skill, level FROM skill ORDER BY employee_id, skill"))
    write_csv("interests.csv", q("SELECT * FROM interest ORDER BY employee_id"))
    write_csv("roadmap.csv", q("SELECT employee_id, horizon, title, url, done FROM roadmap_item ORDER BY employee_id, id"))
    write_csv("consent.csv", q("SELECT * FROM share_consent ORDER BY employee_id"))
    write_csv("role_requirements.csv", [
        {"role_id": rid, "role": tax.role_name(rid), "skill": r.skill, "required_level": r.level, "type": r.type}
        for rid in tax.roles for r in tax.requirements(rid)
    ])
    write_csv("catalog.csv", [
        {"id": c.id, "title": c.title, "platform": c.platform, "url": c.url, "skills": ";".join(c.skills),
         "level": c.level, "kind": c.kind, "cost": c.cost} for c in cat
    ])

    rng = random.Random(7)
    priya_resume = (ROOT / "data" / "sample_docs" / "priya_resume.txt").read_text(encoding="utf-8")
    for e in conn.execute("SELECT * FROM employee"):
        skills = db._skills(conn, e["id"])
        resume = priya_resume if e["id"] == "priya" else make_resume(e["name"], tax.role_name(e["role_id"]), skills, tax, rng)
        (OUT / "documents" / f"{e['id']}_resume.txt").write_text(resume, encoding="utf-8")
        (OUT / "documents" / f"{e['id']}_review.txt").write_text(
            make_review(e["name"], e["performance_rating"], skills, tax), encoding="utf-8")

    n_docs = len(list((OUT / "documents").iterdir()))
    print(f"Wrote 8 CSV files and {n_docs} documents to {OUT}")


if __name__ == "__main__":
    main()
