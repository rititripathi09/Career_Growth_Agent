"""Turn uploaded documents into a structured skill profile."""
from __future__ import annotations

import io
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from core import llm
from core.taxonomy import Taxonomy

MAX_CHARS = 12000  # keep prompts small for free-tier token limits


class ExtractedSkill(BaseModel):
    skill: str = Field(description="one skill id from the allowed list")
    level: int = Field(ge=0, le=4)
    evidence: str = Field(description="short quote or fact from the document that shows this skill")
    confidence: float = Field(ge=0, le=1)


class ExtractedProfile(BaseModel):
    skills: list[ExtractedSkill]
    performance_rating: float | None = Field(
        default=None, description="overall rating on a 1-5 scale, only if the document is a performance review"
    )
    dated_tech: list[str] = Field(default_factory=list, description="outdated tools or versions mentioned")


def read_document(data: bytes, filename: str) -> str:
    """Extract plain text from PDF, DOCX or TXT bytes."""
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith(".docx"):
        import docx

        return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="ignore")


LEVEL_RULES = """Level rules (be conservative; when unsure pick the LOWER level):
- 1 Aware: a course, certificate, tutorial or side project only; no work use.
- 2 Working: used it at work, even often. Vague wording is ALWAYS 2: "used X regularly", "worked with X",
  "familiar with X", "hands-on with X", "exposure to X", "contributed to", "helped with", or X only in a
  skills list next to work experience.
- 3 Strong: needs OWNERSHIP or PRODUCTION RESPONSIBILITY OVER TIME: owned, led, designed or built and ran
  something in production for months or more (e.g. "led", "owned", "for over a year", "on call for").
  Frequent use alone is NOT 3.
- 4 Expert: sets team or org standards, mentors others in it, or is the recognised go-to person.
A skill listed only under SKILLS with no experience line is at most 2.
Count a tool under the skill it serves, even if the tool is dated: cron, Airflow or Data Factory
scheduling -> orchestration; pandas -> python; pytest -> testing; Docker -> containers; Terraform ->
infrastructure_as_code; GitHub pull requests -> git; LLM, RAG or prompt work -> generative_ai."""


def _system_prompt(tax: Taxonomy, kind: str) -> str:
    skills = "\n".join(f"- {sid}: {s['name']}" for sid, s in tax.skills.items())
    levels = ", ".join(f"{k}={v}" for k, v in tax.levels.items())
    dated = ", ".join(tax.dated_tech)
    return (
        f"You read an employee's {kind} and extract evidence-backed skills.\n"
        f"Use ONLY these skill ids:\n{skills}\n"
        f"Levels: {levels}.\n{LEVEL_RULES}\n"
        "Every skill needs concrete evidence from the text: quote the phrase that decided the level. "
        "Skip skills with no evidence.\n"
        f"Also list any of these dated tools if mentioned: {dated}."
    )


def extract_profile(text: str, kind: str, tax: Taxonomy, conn=None) -> ExtractedProfile:
    result = llm.chat_json(_system_prompt(tax, kind), text[:MAX_CHARS], ExtractedProfile, conn=conn)
    result.skills = [s for s in result.skills if s.skill in tax.skills]  # drop invented ids
    return result


def merge_skills(current: dict[str, int], new: list[ExtractedSkill]) -> list[ExtractedSkill]:
    """Keep a new finding only if it raises the level or adds a skill we didn't have.

    If the AI lists a skill twice, only the highest level counts, so a level never goes down.
    """
    best: dict[str, ExtractedSkill] = {}
    for s in new:
        if s.level > current.get(s.skill, -1) and (s.skill not in best or s.level > best[s.skill].level):
            best[s.skill] = s
    return list(best.values())


def find_dated_tech(text: str, tax: Taxonomy) -> list[tuple[str, dict]]:
    """Cheap keyword check that needs no AI call."""
    low = text.lower()
    return [(tool, info) for tool, info in tax.dated_tech.items() if tool in low]


# ---------------------------------------------------------------------- upload pipeline
@dataclass
class SkillChange:
    skill: str
    old: int | None  # None = new skill
    new: int
    evidence: str


@dataclass
class Analysis:
    kind: str
    seconds: float = 0.0
    cached: bool = False
    changes: list[SkillChange] = field(default_factory=list)
    dated_tech: list[str] = field(default_factory=list)
    error: str | None = None  # friendly message; the document is still saved


def friendly_error(exc: Exception) -> str:
    """Turn a provider error into a message for the employee (never includes keys or raw output)."""
    msg = str(exc).lower()
    if "no api key" in msg:
        return "No AI key is set up yet. Add GEMINI_API_KEY to .streamlit/secrets.toml, then try again."
    if "429" in msg or "quota" in msg or "rate limit" in msg or "resource_exhausted" in msg:
        return "The free AI quota is used up for now. Try again in a minute (or tomorrow if the daily limit is hit)."
    if "503" in msg or "overloaded" in msg or "unavailable" in msg:
        return "The AI service is busy right now (503). Please try again in a minute."
    if "valid json" in msg:
        return "The AI sent back an answer we couldn't read. Please try again."
    if "timed out" in msg or "timeout" in msg or "connection" in msg:
        return "We couldn't reach the AI service. Check your internet connection and try again."
    return "The AI couldn't analyse this document right now. Please try again in a minute."


def analyse_source(access, kind: str, text: str, tax: Taxonomy) -> Analysis:
    """Save a document for the owner, extract skills, keep only new or raised levels.

    All reads and writes go through `access` (core/access.py), so only the owner's profile changes.
    Never raises: AI failures come back as `Analysis.error`, and the document stays saved.
    """
    start = time.perf_counter()
    out = Analysis(kind=kind)
    if not text.strip():
        out.error = "No text could be read from this file. If it is a scanned PDF, upload a TXT or DOCX instead."
        return out
    access.add_document(kind, text)  # saved first, so a failed analysis keeps the file
    out.dated_tech = [tool for tool, _ in find_dated_tech(text, tax)]
    try:
        out.cached = llm.is_cached(_system_prompt(tax, kind), text[:MAX_CHARS], ExtractedProfile, access.conn)
        result = extract_profile(text, kind, tax, conn=access.conn)
    except Exception as exc:  # quota, 503, invalid JSON, network...
        out.error = friendly_error(exc)
        out.seconds = time.perf_counter() - start
        return out
    before = access.profile()
    for s in merge_skills(before, result.skills):
        access.save_skill(s.skill, s.level, s.evidence, kind, s.confidence)
        out.changes.append(SkillChange(s.skill, before.get(s.skill), s.level, s.evidence))
    if kind == "review" and result.performance_rating:
        access.set_performance_rating(result.performance_rating)
    known = {t.lower() for t in result.dated_tech}
    out.dated_tech += [t for t in tax.dated_tech if t in known and t not in out.dated_tech]
    out.seconds = time.perf_counter() - start
    return out
