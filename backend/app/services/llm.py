"""Опциональная LLM с открытыми весами через OpenAI-совместимый API
(Ollama, vLLM, llama.cpp server). По умолчанию выключена (LLM_PROVIDER=none):
основной сценарий не зависит от модели, а при её недоступности используется
детерминированный ответ."""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


def enabled() -> bool:
    return get_settings().llm_provider == "openai_compatible"


def chat(system: str, user: str, max_tokens: int = 400) -> str | None:
    s = get_settings()
    if not enabled():
        return None
    try:
        r = httpx.post(f"{s.llm_base_url.rstrip('/')}/chat/completions", timeout=s.llm_timeout_sec, json={
            "model": s.llm_model, "temperature": 0.2, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, ValueError) as e:
        log.warning("llm unavailable, falling back to template: %s", e)
        return None
