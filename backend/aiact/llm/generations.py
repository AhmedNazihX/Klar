"""Which provider served a chat completion, from OpenRouter's generation record (X2).

A chat reply carries its generation id (`gen-…`), but not the provider that served it: the SDK
drops the response's `provider` field. `GET /api/v1/generation?id=…` returns it as
`provider_name` (for example `Azure` for Luna on `azure/eu`, `Google` for Gemini on Vertex, where
Google AI Studio would be `Google AI Studio`). The record shows up a few seconds after the reply,
so a 404 (and a 429) is retried here, and only here: the SDK client makes one attempt per request
with a timeout, so a lookup takes at most `LOOKUP_ATTEMPTS` requests of `LOOKUP_TIMEOUT_MS` each,
`LOOKUP_WAIT_SECONDS` apart. The lookup itself is free. The name doesn't include the region: the
region comes from the pinned endpoint with fallbacks off (decision 005).
"""

import time
from collections.abc import Callable
from typing import Protocol

import httpx
import openrouter
from openrouter.components import GenerationResponse
from openrouter.errors import NoResponseError, OpenRouterError

from aiact.llm.routing import APP_TITLE, NO_RETRIES, require_api_key
from aiact.settings import Settings, get_settings

LOOKUP_ATTEMPTS = 12
LOOKUP_WAIT_SECONDS = 1.5
"""A record appeared 4-8 s after the reply in a check on 2026-10-01; this waits up to ~18 s
between attempts."""
LOOKUP_TIMEOUT_MS = 5000
"""Each request's own bound, so the attempts and waits above are the only other limit."""
TRY_AGAIN = frozenset({404, 429})
"""Not there yet, or rate-limited: both are retried by the loop."""


class GenerationLookupError(RuntimeError):
    """The generation record couldn't be read, or names no provider."""


class _Generations(Protocol):
    def get_generation(self, *, id: str) -> GenerationResponse: ...


class _Client(Protocol):
    @property
    def generations(self) -> _Generations: ...


class GenerationLookup:
    """Reads the provider that served a generation; `client` and `sleep` are replaced in tests."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: _Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = LOOKUP_ATTEMPTS,
    ) -> None:
        """Raises `LLMConfigError` when no client is given and the API key is not set."""
        if client is None:
            key = require_api_key(settings or get_settings()).get_secret_value()
            client = openrouter.OpenRouter(
                api_key=key,
                x_open_router_title=APP_TITLE,
                retry_config=NO_RETRIES,
                timeout_ms=LOOKUP_TIMEOUT_MS,
            )
        self._client = client
        self._sleep = sleep
        self._attempts = attempts

    def served_by(self, generation_id: str) -> str:
        """The provider name of `generation_id`; retries while the record isn't there yet or the
        lookup is rate-limited."""
        for attempt in range(self._attempts):
            if attempt:
                self._sleep(LOOKUP_WAIT_SECONDS)
            try:
                response = self._client.generations.get_generation(id=generation_id)
            except OpenRouterError as error:
                if error.status_code in TRY_AGAIN:
                    continue
                raise GenerationLookupError(
                    f"generation lookup failed: {type(error).__name__} (HTTP {error.status_code})"
                ) from error
            except (NoResponseError, httpx.HTTPError) as error:
                raise GenerationLookupError(
                    f"generation lookup failed: {type(error).__name__}"
                ) from error
            name = response.data.provider_name
            if not name:
                raise GenerationLookupError(f"generation {generation_id} names no provider")
            return name
        raise GenerationLookupError(
            f"generation {generation_id} not found after {self._attempts} attempts"
        )
