"""LLM client wrapper. Works with any OpenAI-compatible endpoint:
OpenAI, OpenRouter, Together, Groq, vLLM, llama.cpp server, ollama (with
/v1 endpoint), etc. Pick model and base_url via .env.
"""

from __future__ import annotations

import os
from typing import Iterable

from openai import AsyncOpenAI


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("LLM_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("LLM_API_KEY is missing in env")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip() or None
        _client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return _client


async def chat(messages: list[dict]) -> str:
    """Non-streaming chat completion. Returns plain text."""
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.85"))
    max_tokens_env = os.getenv("LLM_MAX_TOKENS")
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens_env:
        kwargs["max_tokens"] = int(max_tokens_env)

    resp = await _get_client().chat.completions.create(**kwargs)
    content = resp.choices[0].message.content or ""
    return content.strip()
