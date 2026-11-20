"""Harder accuracy test: does extraction still work on messy, human-sounding resumes?

    uv run python scripts/eval_realistic.py            # reuses saved rewrites (saves free quota)
    uv run python scripts/eval_realistic.py --fresh    # asks the model to rewrite them again

1. Takes 8 synthetic B1 resumes from data/synthetic/documents/.
2. Asks the live model to rewrite each one as a messy, realistic resume with the SAME facts
   (no new skills, same strength of wording) and saves it to data/synthetic/realistic/.
3. Runs core.extract on the clean and the realistic versions and scores both against
   skills_ground_truth.csv: exact %, within-one %, missed and invented skills.

Run scripts/export_dataset.py first. Uses .streamlit/secrets.toml; never prints keys.
Only synthetic data is sent to the free AI tier.
"""
import argparse
import csv
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import llm  # noqa: E402
from core.extract import extract_profile  # noqa: E402
from core.taxonomy import load_taxonomy  # noqa: E402

DATA = ROOT / "data" / "synthetic"
OUT = DATA / "realistic"
N, PAUSE = 8, 5  # seconds between calls, to stay under free-tier per-minute limits

REWRITE = """Rewrite this resume so it reads like a real person wrote it: a short summary, a job with
dates and team context, bullets of uneven length, some merged or split points, natural wording, maybe a
"Tools" line. It may be a little messy.

Strict rules:
- Keep EXACTLY the same facts. Do not add any skill, tool, project, certificate or achievement.
- Keep the strength of each skill the same: a course stays a course with no work use; "used regularly"
  stays everyday work use WITHOUT ownership or leadership; "strong for over a year; led work on" stays
  ownership over time; "go-to expert, set standards, mentored others" stays expert.
- Keep any mention of dated tools (cron, jQuery, Jenkins freestyle) if present.
- Never write level numbers or words like "level", "aware", "working".
Return only the resume as plain text."""


def ground_truth() -> dict[str, dict[str, int]]:
    truth: dict[str, dict[str, int]] = {}
    with open(DATA / "skills_ground_truth.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if int(row["level"]) > 0:
                truth.setdefault(row["employee_id"], {})[row["skill"]] = int(row["level"])
    return truth


def sample_ids() -> list[str]:
    with open(DATA / "employees.csv", encoding="utf-8") as fh:
        ids = sorted(r["id"] for r in csv.DictReader(fh) if r["band"] == "B1" and r["id"] != "priya")
    return random.Random(1).sample(ids, N)  # Priya's resume is hand-written, so she is left out


def score(rows: list[dict]) -> dict:
    n = len(rows) or 1
    return {
        "exact": sum(r["true"] == r["ai"] for r in rows) / n,
        "within_1": sum(abs(r["true"] - r["ai"]) <= 1 for r in rows) / n,
        "missed": sum(r["true"] > 0 and r["ai"] == 0 for r in rows),
        "invented": sum(r["true"] == 0 and r["ai"] > 0 for r in rows),
    }


def compare(emp_id: str, true: dict[str, int], got: dict[str, int], version: str) -> list[dict]:
    return [{"employee": emp_id, "version": version, "skill": s, "true": true.get(s, 0), "ai": got.get(s, 0)}
            for s in sorted(set(true) | set(got))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="rewrite resumes again even if saved")
    args = parser.parse_args()

    llm.load_local_secrets()
    tax, truth = load_taxonomy(), ground_truth()
    OUT.mkdir(parents=True, exist_ok=True)
    provider = llm._provider_chain()[0]
    print(f"Provider: {provider} | model: {llm._model(provider)}\n")

    rows: list[dict] = []
    for i, emp_id in enumerate(sample_ids(), 1):
        clean = (DATA / "documents" / f"{emp_id}_resume.txt").read_text(encoding="utf-8")
        target = OUT / f"{emp_id}_resume.txt"
        try:
            if args.fresh or not target.exists():
                messy = llm.chat([{"role": "system", "content": REWRITE}, {"role": "user", "content": clean}],
                                 temperature=0.8)
                target.write_text(messy.strip() + "\n", encoding="utf-8")
                time.sleep(PAUSE)
            messy = target.read_text(encoding="utf-8")
            for version, text in (("clean", clean), ("realistic", messy)):
                got = {s.skill: s.level for s in extract_profile(text, "resume", tax).skills}
                rows += compare(emp_id, truth.get(emp_id, {}), got, version)
                time.sleep(PAUSE)
        except llm.LLMError as exc:
            print(f"[{i}/{N}] {emp_id}: AI failed, skipped ({str(exc)[:120]})")
            continue
        print(f"[{i}/{N}] {emp_id}: done")

    with open(OUT / "scores.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["employee", "version", "skill", "true", "ai"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'version':10} {'people':>6} {'exact':>6} {'within 1':>9} {'missed':>7} {'invented':>9}")
    for version in ("clean", "realistic"):
        part = [r for r in rows if r["version"] == version]
        s = score(part)
        print(f"{version:10} {len({r['employee'] for r in part}):>6} {s['exact']:>6.0%} {s['within_1']:>9.0%} "
              f"{s['missed']:>7} {s['invented']:>9}")
    wrong = [r for r in rows if r["version"] == "realistic" and r["true"] != r["ai"]]
    if wrong:
        print("\nRealistic misses (true -> ai):")
        for r in wrong:
            print(f"  {r['employee']:10} {r['skill']:22} {r['true']} -> {r['ai']}")
    print(f"\nSaved rewrites and {OUT / 'scores.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
