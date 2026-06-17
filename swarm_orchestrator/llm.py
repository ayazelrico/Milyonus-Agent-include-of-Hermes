"""Small adapters around Hermes' existing LLM clients."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol


class LLMCaller(Protocol):
    def __call__(self, messages: list[dict[str, str]], *, model: str | None = None) -> str: ...


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from a model response that should be JSON-only."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def make_agent_llm_caller(agent: Any) -> LLMCaller:
    """Return a caller that uses an existing ``AIAgent`` OpenAI-compatible client.

    This avoids creating a new provider/client path: callers pass the already
    configured Hermes agent and the council sends short chat-completion requests
    through that agent's existing SDK client and model defaults.
    """

    def call(messages: list[dict[str, str]], *, model: str | None = None) -> str:
        client = getattr(agent, "client", None)
        if client is None:
            raise RuntimeError("AIAgent has no configured client for swarm council LLM calls")
        selected_model = model or getattr(agent, "model", "")
        response = client.chat.completions.create(model=selected_model, messages=messages)
        choice = response.choices[0]
        content = getattr(choice.message, "content", None)
        return content if isinstance(content, str) else str(content or "")

    return call
