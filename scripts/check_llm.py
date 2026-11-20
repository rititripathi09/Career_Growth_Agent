"""Smoke-test the LLM connection using .streamlit/secrets.toml.

    uv run python scripts/check_llm.py

Tests the primary provider only (fallback disabled) so a bad Gemini setup is not hidden
by Groq. Never prints API keys.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import llm  # noqa: E402

SECRETS = ROOT / ".streamlit" / "secrets.toml"


def main() -> int:
    if not SECRETS.exists():
        print(f"Missing {SECRETS}. Copy secrets.toml.example to secrets.toml first.")
        return 1
    llm.load_local_secrets(SECRETS)

    provider = os.environ.get("LLM_PROVIDER", "gemini")
    os.environ["LLM_FALLBACK"] = provider  # test the primary on its own
    key_env = llm.PROVIDERS.get(provider, {}).get("key_env")
    if key_env and not os.environ.get(key_env):
        print(f"{key_env} is empty in secrets.toml.")
        return 1

    print(f"Provider: {provider} | model: {llm._model(provider)}")
    try:
        reply = llm.chat([{"role": "user", "content": "Say hi in 3 words"}])
    except llm.LLMError as exc:
        print(f"FAILED: {exc}")
        return 1
    print(f"OK, reply: {reply.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
