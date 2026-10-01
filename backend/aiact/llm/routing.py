"""OpenRouter provider routing and config checks shared by the chat and embedding clients.

OpenRouter reads a `provider` object in the request body (chat and embeddings alike).
`data_collection: "deny"` skips providers that may store or train on prompts, and
`zdr: true` restricts routing to zero-data-retention endpoints. Every request sends both.
See https://openrouter.ai/docs/guides/routing/provider-selection.
"""

from collections.abc import Sequence

from openrouter.utils import BackoffStrategy, RetryConfig
from pydantic import SecretStr

from aiact.settings import Settings

APP_TITLE = "AI Act Classification Assistant"
"""Sent as the attribution title, so usage shows under this app in the OpenRouter dashboard."""


NO_RETRIES = RetryConfig(
    strategy="none",
    backoff=BackoffStrategy(initial_interval=0, max_interval=0, exponent=1.0, max_elapsed_time=0),
    retry_connection_errors=False,
)
"""An SDK retry config that makes exactly one attempt. Leaving `retry_config` unset is not the
same: the SDK then retries 5XX and network errors with backoff for up to an hour."""


class LLMConfigError(RuntimeError):
    """A model call can't be made because a setting (model id, provider, API key) is missing."""


def provider_preferences(
    order: Sequence[str] | None = None, *, allow_fallbacks: bool = True
) -> dict[str, object]:
    """Build the `provider` body for a request: privacy flags, plus an optional pinned order.

    With `allow_fallbacks=False` the request fails instead of going to a provider outside
    `order`, which is how the embeddings stay on one provider.
    """
    if not allow_fallbacks and not order:
        raise LLMConfigError("allow_fallbacks=False needs a provider order to pin to")
    preferences: dict[str, object] = {"data_collection": "deny", "zdr": True}
    if order:
        preferences["order"] = list(order)
        preferences["allow_fallbacks"] = allow_fallbacks
    return preferences


def require_setting(value: str | None, env_var: str) -> str:
    """Return a configured value, or raise a config error that names the env var to set."""
    if not value:
        raise LLMConfigError(f"{env_var} is not set; add it to backend/.env or pass it explicitly")
    return value


def require_api_key(settings: Settings) -> SecretStr:
    """Return the OpenRouter API key, or raise a config error if it is missing."""
    key = settings.openrouter_api_key
    if key is None or not key.get_secret_value():
        raise LLMConfigError("OPENROUTER_API_KEY is not set; add it to backend/.env")
    return key
