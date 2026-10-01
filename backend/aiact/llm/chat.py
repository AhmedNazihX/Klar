"""LangChain chat models over OpenRouter.

The model id comes from settings by role (`ENGINE_MODEL`, `JUDGE_MODEL`, …), so switching a
model for a baseline or a judge is a setting, not a code change. Every model is built with
the privacy routing flags from `aiact.llm.routing`.
"""

from collections.abc import Sequence
from typing import Literal

from langchain_openrouter import ChatOpenRouter

from aiact.llm.routing import APP_TITLE, provider_preferences, require_api_key, require_setting
from aiact.settings import Settings, get_settings

ModelRole = Literal["engine", "judge", "judge_backup", "label_filter", "ragas"]
"""Which configured model to use; `<role>` reads the `<ROLE>_MODEL` setting."""

DEFAULT_TEMPERATURE = 0.0
"""Classification and judging want repeatable answers."""
DEFAULT_MAX_RETRIES = 2
"""ChatOpenRouter's own default; 0 makes every billed attempt one the caller's callbacks see."""


def chat_model(
    role: ModelRole = "engine",
    *,
    model: str | None = None,
    provider_order: Sequence[str] | None = None,
    allow_fallbacks: bool = True,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    settings: Settings | None = None,
) -> ChatOpenRouter:
    """Build a chat model for `role`, or for an explicit OpenRouter `model` slug.

    Raises `LLMConfigError` when the model id for the role or the API key is not set.
    """
    settings = settings or get_settings()
    model_id = model or require_setting(getattr(settings, f"{role}_model"), f"{role.upper()}_MODEL")
    return ChatOpenRouter(
        model=model_id,
        api_key=require_api_key(settings),
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        openrouter_provider=provider_preferences(provider_order, allow_fallbacks=allow_fallbacks),
        app_title=APP_TITLE,
    )


def engine_chat_model(
    *, max_tokens: int, max_retries: int = DEFAULT_MAX_RETRIES, settings: Settings | None = None
) -> ChatOpenRouter:
    """The engine model, pinned to its `ENGINE_PROVIDER` endpoint with fallbacks off (decision
    005), so descriptions stay in the EU. Every engine node builds its model here.

    Raises `LLMConfigError` when `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set.
    """
    settings = settings or get_settings()
    model_id = require_setting(settings.engine_model, "ENGINE_MODEL")
    provider = require_setting(settings.engine_provider, "ENGINE_PROVIDER")
    return chat_model(
        model=model_id,
        provider_order=[provider],
        allow_fallbacks=False,
        max_tokens=max_tokens,
        max_retries=max_retries,
        settings=settings,
    )
