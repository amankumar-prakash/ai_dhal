"""Builds the correct LangChain chat model for the configured LLM.

OpenAI's reasoning-tier models (the gpt-5.x / "luna" family, o1/o3/o4, etc.)
reject function-tool calls combined with `reasoning_effort` on the legacy
`/v1/chat/completions` endpoint:

    Error code: 400 - {'error': {'message': "Function tools with
    reasoning_effort are not supported for gpt-5.6-luna in
    /v1/chat/completions. To use function tools, use /v1/responses or set
    reasoning_effort to 'none'.", ...}}

They must instead be routed through OpenAI's newer `/v1/responses` API
(`ChatOpenAI(..., use_responses_api=True)`). Non-reasoning models
(gpt-4o-mini, gpt-4o, gpt-3.5-turbo, ...) keep using the classic
`/v1/chat/completions` endpoint via LangChain's `"openai:<model>"` shorthand.
"""
from __future__ import annotations

import re
from typing import Union

from app.settings import WorkerSettings

# Model-name patterns that require the Responses API. Matched against the
# start of the (lower-cased) model name, so "gpt-5.6-luna", "gpt-5", "o1",
# "o1-mini", "o3-mini", "o4-mini", etc. all match.
_RESPONSES_API_MODEL_PATTERNS = (
    re.compile(r"^gpt-5"),
    re.compile(r"^o1\b"),
    re.compile(r"^o3\b"),
    re.compile(r"^o4\b"),
)


def uses_responses_api(model_name: str) -> bool:
    """True if `model_name` is a reasoning-tier model that needs /v1/responses."""
    name = (model_name or "").strip().lower()
    return any(pattern.match(name) for pattern in _RESPONSES_API_MODEL_PATTERNS)


def build_agent_model(settings: WorkerSettings) -> Union[str, "ChatOpenAI"]:  # noqa: F821
    """Return the model argument to hand to `langchain.agents.create_agent`.

    Always return a `ChatOpenAI` instance so the API key from WorkerSettings is
    used (supervisord does not export OPENAI_API_KEY into the process env).

    - Reasoning models -> `/v1/responses` (`use_responses_api=True`).
    - Everything else (e.g. gpt-4o-mini) -> classic `/v1/chat/completions`.
    """
    from langchain_openai import ChatOpenAI

    model_name = settings.llm_model
    kwargs: dict = {
        "model": model_name,
        "api_key": settings.openai_api_key or None,
        "base_url": settings.llm_base_url or None,
    }
    if uses_responses_api(model_name):
        kwargs["use_responses_api"] = True
    return ChatOpenAI(**kwargs)
