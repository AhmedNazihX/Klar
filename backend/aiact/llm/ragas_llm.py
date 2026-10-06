"""The RAGAS model (V6): Gemini 3.1 Flash-Lite on its EU endpoint, as RAGAS's metrics want it.

RAGAS 0.4's metrics take an instructor-based LLM built from an OpenAI SDK client, so this is the
one place the app reaches OpenRouter through the OpenAI SDK rather than LangChain. Every request
carries the privacy routing flags and the pinned EU endpoint (decision 005) in its body, and every
reply's cost and tokens (OpenRouter's `usage`) go to the caller's `on_usage` from an HTTP response
hook, so retries and every metric's calls are counted whichever library made them.

RAGAS sends usage telemetry to its vendor by default; importing this module switches it off.
"""

import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI
from ragas.llms import InstructorBaseRagasLLM, llm_factory

from aiact.llm.routing import APP_TITLE, provider_preferences, require_api_key
from aiact.settings import Settings, get_settings

# RAGAS reads this on its first telemetry event; nothing here has sent one yet.
os.environ["RAGAS_DO_NOT_TRACK"] = "true"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_RAGAS_MODEL = "google/gemini-3.1-flash-lite"
"""INIT > Tech stack (RAGAS: Gemini 3.1 Flash-Lite); `RAGAS_MODEL` overrides it."""
RAGAS_PROVIDER = "google-vertex/eu"
"""Flash-Lite's EU zero-data-retention endpoint, pinned with fallbacks off (decision 005)."""
MAX_OUTPUT_TOKENS = 2048
"""Room for RAGAS's statement lists and verdicts; Flash-Lite doesn't reason, so no more."""
MAX_RETRIES = 2
"""The OpenAI SDK's own default. Every attempt that gets a reply is counted by the usage hook."""
TIMEOUT_SECONDS = 120.0

UsageCallback = Callable[[float | None, int], None]
"""Called with one reply's cost (None when OpenRouter sent none) and its total tokens."""


@dataclass(frozen=True)
class RagasModel:
    """The RAGAS metrics' LLM and the raw client it wraps (for other calls on the same route)."""

    llm: InstructorBaseRagasLLM
    client: AsyncOpenAI
    model: str
    provider: str


def routing_body(provider: str) -> dict[str, object]:
    """The OpenRouter body fields: privacy flags plus the one endpoint allowed."""
    return {"provider": provider_preferences([provider], allow_fallbacks=False)}


def ragas_model(on_usage: UsageCallback, *, settings: Settings | None = None) -> RagasModel:
    """The RAGAS model on its pinned EU endpoint, with every reply's usage sent to `on_usage`.

    Raises `LLMConfigError` when the OpenRouter API key is not set.
    """
    settings = settings or get_settings()
    model = settings.ragas_model or DEFAULT_RAGAS_MODEL
    client = AsyncOpenAI(
        api_key=require_api_key(settings).get_secret_value(),
        base_url=OPENROUTER_BASE_URL,
        default_headers={"X-Title": APP_TITLE},
        max_retries=MAX_RETRIES,
        timeout=TIMEOUT_SECONDS,
        http_client=httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, event_hooks={"response": [usage_hook(on_usage)]}
        ),
    )
    llm = llm_factory(
        model,
        client=client,
        max_tokens=MAX_OUTPUT_TOKENS,
        extra_body=routing_body(RAGAS_PROVIDER),
    )
    return RagasModel(llm=llm, client=client, model=model, provider=RAGAS_PROVIDER)


def usage_hook(on_usage: UsageCallback) -> Callable[[httpx.Response], Awaitable[None]]:
    """An httpx response hook that reports each successful reply's `usage` to `on_usage`."""

    async def report(response: httpx.Response) -> None:
        if response.is_error:
            return
        await response.aread()
        on_usage(*reply_usage(response.content))

    return report


def reply_usage(body: bytes) -> tuple[float | None, int]:
    """A chat completion body's cost (None when absent) and total tokens (0 when absent)."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, 0
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return None, 0
    cost = usage.get("cost")
    tokens = usage.get("total_tokens")
    return (
        float(cost) if isinstance(cost, int | float) else None,
        tokens if isinstance(tokens, int) else 0,
    )
