"""Synthetic documents for the Nimbus Tech dataset.

Each resume and review is written FROM a person's true skill levels, so the true levels act as a
ground-truth answer key: run the AI extractor on the text and compare (see notebooks/02_*.ipynb).
No AI call is needed to generate them.
"""
from __future__ import annotations

import random

from core.taxonomy import Taxonomy

EXAMPLES = {
    "python": "data pipelines and automation scripts",
    "sql": "warehouse queries and reporting views",
    "data_modeling": "star-schema models for finance reporting",
    "cloud_platform": "moving batch jobs to managed cloud services",
    "orchestration": "scheduled DAGs with retries and alerts",
    "streaming": "a Kafka-based event feed",
    "containers": "Docker images and Kubernetes deployments",
    "infrastructure_as_code": "Terraform modules for shared environments",
    "ci_cd": "build-and-deploy pipelines in GitHub Actions",
    "monitoring": "dashboards and alerts for service health",
    "javascript": "TypeScript components for the customer portal",
    "react": "a React design-system library",
    "html_css": "responsive, accessible page layouts",
    "testing": "unit and integration test suites",
    "ml_fundamentals": "classification models with scikit-learn",
    "feature_engineering": "feature pipelines for model training",
    "deep_learning": "a PyTorch image classifier",
    "mlops": "model versioning and automated retraining",
    "data_security": "access reviews and PII masking",
    "git": "code reviews and branching conventions",
    "communication": "monthly demos to stakeholders",
    "people_leadership": "1:1s, feedback and hiring for the team",
    "delivery_planning": "sprint planning and quarterly roadmaps",
}

LEVEL_TEMPLATES = {
    1: "Completed an introductory online course on {name}; no project work yet.",
    2: "Used {name} regularly in project work, including {example}.",
    3: "Strong in {name} for over a year; led work on {example}.",
    4: "Recognised go-to expert for {name}; set team standards and mentored others on {example}.",
}

DATED_LINES = {
    "orchestration": "Schedules nightly jobs with cron scripts on a Linux VM.",
    "react": "Maintains an older jQuery admin page.",
    "ci_cd": "Keeps a few legacy Jenkins freestyle jobs running.",
}


def make_resume(name: str, role_name: str, skills: dict[str, int], tax: Taxonomy, rng: random.Random) -> str:
    lines = [name.upper(), f"{role_name}, Nimbus Tech (synthetic profile)", "", "EXPERIENCE"]
    ordered = sorted(skills.items(), key=lambda kv: (-kv[1], kv[0]))
    for skill, level in ordered:
        if level == 0:
            continue
        lines.append("- " + LEVEL_TEMPLATES[level].format(
            name=tax.skill_name(skill), example=EXAMPLES.get(skill, "team projects")))
        if level <= 2 and skill in DATED_LINES and rng.random() < 0.5:
            lines.append("- " + DATED_LINES[skill])
    lines += ["", "SKILLS", ", ".join(tax.skill_name(s) for s, lvl in ordered if lvl >= 2)]
    return "\n".join(lines)


def make_review(name: str, rating: float, skills: dict[str, int], tax: Taxonomy) -> str:
    strong = [tax.skill_name(s) for s, lvl in skills.items() if lvl >= 3][:3]
    weak = [tax.skill_name(s) for s, lvl in skills.items() if lvl <= 1][:3]
    return "\n".join([
        f"PERFORMANCE REVIEW: {name} (synthetic)",
        f"Overall rating: {rating:.1f} / 5",
        "Strengths: " + (", ".join(strong) if strong else "steady delivery across the board") + ".",
        "Growth areas: " + (", ".join(weak) if weak else "broaden impact beyond the team") + ".",
    ])
