"""GitHub signals: public repo languages become skill evidence. Uses the free REST API
(60 requests/hour without a token; set GITHUB_TOKEN for 5,000/hour)."""
from __future__ import annotations

import os
from collections import Counter

LANG_TO_SKILL = {
    "Python": "python",
    "Jupyter Notebook": "ml_fundamentals",
    "JavaScript": "javascript",
    "TypeScript": "javascript",
    "HTML": "html_css",
    "CSS": "html_css",
    "HCL": "infrastructure_as_code",
    "Bicep": "infrastructure_as_code",
    "Dockerfile": "containers",
    "Shell": "ci_cd",
    "PLpgSQL": "sql",
    "TSQL": "sql",
}


def repo_languages(username: str, max_repos: int = 20) -> Counter:
    import httpx

    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    resp = httpx.get(
        f"https://api.github.com/users/{username}/repos",
        params={"per_page": max_repos, "sort": "pushed"},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return Counter(r["language"] for r in resp.json() if r.get("language") and not r.get("fork"))


def skills_from_languages(langs: Counter) -> list[tuple[str, int, str]]:
    """[(skill, level, evidence)]: 1 repo → level 1, 3+ repos → level 2. Repos alone never prove 3+."""
    out: dict[str, tuple[int, str]] = {}
    for lang, n in langs.items():
        skill = LANG_TO_SKILL.get(lang)
        if not skill:
            continue
        level = 2 if n >= 3 else 1
        if level >= out.get(skill, (0, ""))[0]:
            out[skill] = (level, f"{n} public repo(s) in {lang}")
    return [(s, lvl, ev) for s, (lvl, ev) in out.items()]
