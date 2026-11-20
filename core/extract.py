"""Turn uploaded documents into a structured skill profile."""
from __future__ import annotations

import io

from pydantic import BaseModel, Field

from core.llm import chat_json
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


def _system_prompt(tax: Taxonomy, kind: str) -> str:
    skills = "\n".join(f"- {sid}: {s['name']}" for sid, s in tax.skills.items())
    levels = ", ".join(f"{k}={v}" for k, v in tax.levels.items())
    dated = ", ".join(tax.dated_tech)
    return (
        f"You read an employee's {kind} and extract evidence-backed skills.\n"
        f"Use ONLY these skill ids:\n{skills}\n"
        f"Levels: {levels}. Be conservative: a course alone is level 1; production work is 2-3; "
        "leading others or deep expertise is 3-4.\n"
        "Every skill needs concrete evidence from the text. Skip skills with no evidence.\n"
        f"Also list any of these dated tools if mentioned: {dated}."
    )


def extract_profile(text: str, kind: str, tax: Taxonomy, conn=None) -> ExtractedProfile:
    result = chat_json(_system_prompt(tax, kind), text[:MAX_CHARS], ExtractedProfile, conn=conn)
    result.skills = [s for s in result.skills if s.skill in tax.skills]  # drop invented ids
    return result


def merge_skills(current: dict[str, int], new: list[ExtractedSkill]) -> list[ExtractedSkill]:
    """Keep a new finding only if it raises the level or adds a skill we didn't have."""
    return [s for s in new if s.level > current.get(s.skill, -1)]


def find_dated_tech(text: str, tax: Taxonomy) -> list[tuple[str, dict]]:
    """Cheap keyword check that needs no AI call."""
    low = text.lower()
    return [(tool, info) for tool, info in tax.dated_tech.items() if tool in low]
