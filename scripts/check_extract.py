"""Live US-04 check: run the real AI extraction on a resume and time it (no cache).

    uv run python scripts/check_extract.py
    uv run python scripts/check_extract.py path/to/resume.txt

Uses .streamlit/secrets.toml. Never prints API keys.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import llm  # noqa: E402
from core.extract import extract_profile, find_dated_tech  # noqa: E402
from core.taxonomy import load_taxonomy  # noqa: E402


def main() -> int:
    llm.load_local_secrets()
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "sample_docs" / "priya_resume.txt"
    text = path.read_text(encoding="utf-8")
    tax = load_taxonomy()
    provider = llm._provider_chain()[0]
    print(f"Provider: {provider} | model: {llm._model(provider)} | file: {path.name}")
    start = time.perf_counter()
    try:
        out = extract_profile(text, "resume", tax)  # conn=None: always a live call
    except llm.LLMError as exc:
        print(f"FAILED after {time.perf_counter() - start:.1f} s: {str(exc)[:300]}")
        return 1
    secs = time.perf_counter() - start
    print(f"Time: {secs:.1f} s ({'OK' if secs < 30 else 'SLOW'}: target under 30 s)\n")
    for s in sorted(out.skills, key=lambda s: (-s.level, s.skill)):
        print(f"  {s.skill:22} {s.level}  {s.evidence[:80]}")
    keyword = [t for t, _ in find_dated_tech(text, tax)]
    print(f"\nDated tech (AI): {out.dated_tech or 'none'} | (keyword check): {keyword or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
