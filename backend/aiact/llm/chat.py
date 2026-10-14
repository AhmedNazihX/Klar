"""LangChain chat models over OpenRouter.

The model id comes from settings by role (`ENGINE_MODEL`, `LABEL_FILTER_MODEL`, …), so switching
a model for a baseline is a setting, not a code change. Every model is built with
the privacy routing flags from `aiact.llm.routing`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import openrouter
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, ValidationError

from aiact.llm.routing import (
    APP_TITLE,
    NO_RETRIES,
    provider_preferences,
    require_api_key,
    require_setting,
)
from aiact.llm.structured import ChatRoute, ProviderRefusalError, failure_metadata, parse_reply
from aiact.settings import Settings, get_settings

ModelRole = Literal["engine", "label_filter", "ragas"]
"""Which configured model to use; `<role>` reads the `<ROLE>_MODEL` setting."""

DEFAULT_TEMPERATURE = 0.0
"""Classification and judging want repeatable answers."""
DEFAULT_MAX_RETRIES = 2
"""ChatOpenRouter's own default. With 0, the model gets a client that makes exactly one attempt
(`client_without_retries`), so every billed attempt is one the caller's callbacks see:
ChatOpenRouter's own `max_retries=0` only leaves the SDK on its default retries."""


def reply_usage(reply: AIMessage) -> tuple[float | None, int]:
    """What a chat reply cost (OpenRouter's `usage.cost`; None when the reply has none)
    and how many tokens it used."""
    cost = reply.response_metadata.get("cost")
    tokens = reply.usage_metadata["total_tokens"] if reply.usage_metadata else 0
    return (float(cost) if isinstance(cost, int | float) else None), tokens


@dataclass(frozen=True)
class StructuredReply[M: BaseModel]:
    """One structured call: the answer, or what failed (`error`, metadata only; `cause`, the
    exception itself, for the caller's cause chain), and what the call spent."""

    answer: M | None
    error: str | None
    cause: Exception | None
    cost_usd: float
    tokens: int
    is_cost_estimated: bool
    """No cost came back with the reply, or no reply came back; the estimate was charged."""
    is_call_failed: bool
    """No reply came back (transport, auth, endpoint), as opposed to a reply that was refused or
    broke the schema."""


def invoke_structured[M: BaseModel](
    chat: BaseChatModel,
    messages: Sequence[BaseMessage],
    model: type[M],
    response_format: Mapping[str, object],
    estimate_usd: float,
) -> StructuredReply[M]:
    """Ask `chat` once for JSON matching `model`. Never raises for the call or its answer: a
    failed call is charged `estimate_usd`, as is a reply that reports no cost."""
    try:
        reply = chat.invoke(list(messages), response_format=response_format)
    except Exception as exc:
        return StructuredReply(None, failure_metadata(exc), exc, estimate_usd, 0, True, True)
    cost, tokens = reply_usage(reply)
    spent = estimate_usd if cost is None else cost
    try:
        answer = parse_reply(reply, model)
    except (ValidationError, ProviderRefusalError) as exc:
        return StructuredReply(None, failure_metadata(exc), exc, spent, tokens, cost is None, False)
    return StructuredReply(answer, None, None, spent, tokens, cost is None, False)


def reply_model(reply: AIMessage) -> str | None:
    """The model that wrote a chat reply, as OpenRouter names it (the response's `model`)."""
    name = reply.response_metadata.get("model_name")
    return name if isinstance(name, str) and name else None


def client_without_retries(settings: Settings) -> openrouter.OpenRouter:
    """An OpenRouter SDK client that never retries."""
    return openrouter.OpenRouter(
        api_key=require_api_key(settings).get_secret_value(),
        x_open_router_title=APP_TITLE,
        retry_config=NO_RETRIES,
    )


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
    """Build a chat model for `role`, or for an explicit OpenRouter `model` slug. With
    `max_retries=0` it makes exactly one attempt per call.

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
        client=client_without_retries(settings) if max_retries == 0 else None,
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
    return _pinned_chat_model(
        settings.engine_model,
        "ENGINE_MODEL",
        settings.engine_provider,
        "ENGINE_PROVIDER",
        max_tokens=max_tokens,
        max_retries=max_retries,
        settings=settings,
    )


def refusal_chat_model(
    *, max_tokens: int, max_retries: int = DEFAULT_MAX_RETRIES, settings: Settings | None = None
) -> ChatOpenRouter:
    """The second model a provider refusal goes to (decision 033), pinned to its
    `REFUSAL_PROVIDER` endpoint with fallbacks off like the engine model: an engine call of its
    own, never an OpenRouter fallback.

    Raises `LLMConfigError` when `REFUSAL_MODEL`, `REFUSAL_PROVIDER` or the API key is not set.
    """
    settings = settings or get_settings()
    return _pinned_chat_model(
        settings.refusal_model,
        "REFUSAL_MODEL",
        settings.refusal_provider,
        "REFUSAL_PROVIDER",
        max_tokens=max_tokens,
        max_retries=max_retries,
        settings=settings,
    )


def engine_route(
    *,
    max_tokens: int,
    settings: Settings | None = None,
    chat: BaseChatModel | None = None,
    refusal_chat: BaseChatModel | None = None,
) -> ChatRoute:
    """A node's models: the given `chat` and `refusal_chat` (the run's, or a test's; without a
    `refusal_chat` a refusal gets no second call), or, without a `chat`, the engine model and
    the refusal model, each with the node's output cap. A route with both models is a
    classification run's, and asks a reply cut off at the output cap once more
    (`ChatRoute.retry_cut_off`, E20); a given `chat` alone (the smoke harness's probes, decision
    004; tests) makes one call. Raises `LLMConfigError` when a model built here lacks its model,
    provider or API key setting."""
    if chat is not None:
        return ChatRoute(chat, refusal_chat, retry_cut_off=refusal_chat is not None)
    engine = engine_chat_model(max_tokens=max_tokens, settings=settings)
    second = refusal_chat or refusal_chat_model(max_tokens=max_tokens, settings=settings)
    return ChatRoute(engine, second, retry_cut_off=True)


def _pinned_chat_model(
    model: str | None,
    model_var: str,
    provider: str | None,
    provider_var: str,
    *,
    max_tokens: int,
    max_retries: int,
    settings: Settings,
) -> ChatOpenRouter:
    """`model` on `provider` only, fallbacks off; raises `LLMConfigError` naming the unset one."""
    return chat_model(
        model=require_setting(model, model_var),
        provider_order=[require_setting(provider, provider_var)],
        allow_fallbacks=False,
        max_tokens=max_tokens,
        max_retries=max_retries,
        settings=settings,
    )
