"""One client for three FREE model providers, all OpenAI-compatible:

  gemini  Google AI Studio free tier  (key: GEMINI_API_KEY)
  groq    Groq free tier              (key: GROQ_API_KEY)
  ollama  local models via Ollama     (no key; run `ollama serve`)

Set LLM_PROVIDER (and optionally LLM_MODEL) in .streamlit/secrets.toml or the environment.
If the primary provider fails (e.g. daily quota reached), LLM_FALLBACK is tried next.

Free tiers change often: check the current model names and limits in Google AI Studio and the
Groq console. Free-tier prompts may be used to improve the provider's products, so send mock data only.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator

from pydantic import BaseModel, ValidationError

PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-flash-latest",  # check AI Studio for the current free Flash model name
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model": "openai/gpt-oss-120b",  # llama-3.3-70b-versatile was retired; check the Groq console
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "key_env": None,
        "model": "llama3.2",
    },
}


class LLMError(RuntimeError):
    pass


def _setting(name: str, default: str | None = None) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    try:  # Streamlit secrets, when running inside the app
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default


def _provider_chain() -> list[str]:
    primary = _setting("LLM_PROVIDER", "gemini")
    fallback = _setting("LLM_FALLBACK", "groq")
    chain = [primary] + ([fallback] if fallback and fallback != primary else [])
    return [p for p in chain if p in PROVIDERS]


def _client(provider: str):
    from openai import OpenAI  # imported lazily so tests run without the package

    cfg = PROVIDERS[provider]
    key = _setting(cfg["key_env"]) if cfg["key_env"] else "ollama"
    if not key:
        raise LLMError(f"No API key for {provider}: set {cfg['key_env']}")
    # Fail fast on an overloaded provider (e.g. Gemini 503) so the fallback takes over
    return OpenAI(base_url=cfg["base_url"], api_key=key, timeout=60, max_retries=1)


def _model(provider: str) -> str:
    if provider == _setting("LLM_PROVIDER", "gemini") and _setting("LLM_MODEL"):
        return _setting("LLM_MODEL")
    return PROVIDERS[provider]["model"]


def chat(messages: list[dict], temperature: float = 0.4, json_mode: bool = False) -> str:
    """Send a chat request, trying the fallback provider if the primary fails."""
    errors = []
    for provider in _provider_chain():
        try:
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            resp = _client(provider).chat.completions.create(
                model=_model(provider), messages=messages, temperature=temperature, **kwargs
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:  # rate limit, network, bad key...
            errors.append(f"{provider}: {exc}")
    raise LLMError("All providers failed. " + " | ".join(errors))


def stream_chat(messages: list[dict], temperature: float = 0.6) -> Iterator[str]:
    """Yield text chunks (for st.write_stream). Falls back to a non-streamed answer on error."""
    provider = _provider_chain()[0]
    try:
        stream = _client(provider).chat.completions.create(
            model=_model(provider), messages=messages, temperature=temperature, stream=True
        )
        for part in stream:
            if part.choices and part.choices[0].delta.content:
                yield part.choices[0].delta.content
    except Exception:
        yield chat(messages, temperature)


def chat_json(system: str, user: str, schema: type[BaseModel], conn=None) -> BaseModel:
    """Ask for JSON matching `schema`; validate it, retry once with the error, cache the result."""
    schema_hint = json.dumps(schema.model_json_schema())
    messages = [
        {"role": "system", "content": f"{system}\n\nReply with ONLY a JSON object matching this JSON schema:\n{schema_hint}"},
        {"role": "user", "content": user},
    ]
    key = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
    if conn is not None:
        from core.db import cache_get

        cached = cache_get(conn, key)
        if cached is not None:
            return schema.model_validate(cached)

    last_error = ""
    for _ in range(2):
        raw = chat(messages, temperature=0.1, json_mode=True)
        try:
            result = schema.model_validate_json(_strip_fences(raw))
            if conn is not None:
                from core.db import cache_set

                cache_set(conn, key, result.model_dump())
            return result
        except ValidationError as exc:
            last_error = str(exc)
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"That JSON was invalid: {last_error[:800]}. Send corrected JSON only."},
            ]
    raise LLMError(f"Model did not return valid JSON: {last_error[:300]}")


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()
