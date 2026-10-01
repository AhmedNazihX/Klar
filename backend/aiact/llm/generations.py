"""Which provider served a chat completion, from OpenRouter's generation record (X2).

A chat reply carries its generation id (`gen-…`), but not the provider that served it: the SDK
drops the response's `provider` field. `GET /api/v1/generation?id=…` returns it as
`provider_name` (for example `Azure` for Luna on `azure/eu`, `Google` for Gemini on Vertex, where
Google AI Studio would be `Google AI Studio`). The record shows up a few seconds after the reply,
so a 404 (and a 429) is retried here, and only here: the SDK client makes one attempt per request
with a timeout, so a lookup takes at most `LOOKUP_ATTEMPTS` requests of `LOOKUP_TIMEOUT_MS` each,
`LOOKUP_WAIT_SECONDS` apart. The lookup itself is free. The name doesn't include the region: the
region comes from the pinned endpoint with fallbacks off (decision 005).

Under a real run's load, records showed up later than that window (X2's paid run, 2026-10-01), so
`served_by_all` waits much longer for many records at once: each round asks once for every record
still missing, the waits between rounds grow, and it stops when none is missing or
`DEFERRED_BUDGET_SECONDS` have passed. Each request keeps its own `LOOKUP_TIMEOUT_MS`. There a
transport error, a 5xx or a 429 is tried again in a later round too; a 429 also ends the round.
"""

import re
import time
from collections.abc import Callable, Mapping, Sequence
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
NOT_THERE_YET = 404
RATE_LIMITED = 429
"""Both are retried by the loops; any other 4xx is final."""
SERVER_ERROR = 500
"""From here on, an HTTP error is transient: `served_by_all` tries again in a later round."""

DEFERRED_BUDGET_SECONDS = 300.0
"""How long `served_by_all` waits in total for the records still missing (about 5 minutes): no
request starts after it, so the most it can take is this plus one request's timeout."""
DEFERRED_FIRST_WAIT_SECONDS = 5.0
DEFERRED_WAIT_GROWTH = 2.0
DEFERRED_MAX_WAIT_SECONDS = 60.0
"""The waits between rounds: 5, 10, 20, 40, then 60 s until the budget is spent."""

_MAY_COME_LATER = re.compile(
    r"^(generation \S+ not found (after \d+ attempts|within \d+ s)"
    r"|generation lookup failed: \w+( \(HTTP (5\d\d|429)\))?)$"
)
"""The stored messages of the errors below that a later lookup may still settle."""


class GenerationLookupError(RuntimeError):
    """The generation record couldn't be read, or names no provider."""


class GenerationPendingError(GenerationLookupError):
    """The record couldn't be read yet, but a later lookup may read it."""


class GenerationNotFoundError(GenerationPendingError):
    """The generation record didn't show up within the lookup's window."""


class GenerationTransientError(GenerationPendingError):
    """The lookup request failed in transport, or with a 5xx."""


class GenerationRateLimitedError(GenerationTransientError):
    """The lookup was rate-limited (429)."""


def may_come_later(reason: str) -> bool:
    """Whether a stored lookup error is a `GenerationPendingError`'s message: a record not found
    in time, a transport error, a 5xx or a 429."""
    return _MAY_COME_LATER.match(reason) is not None


class _Generations(Protocol):
    def get_generation(self, *, id: str) -> GenerationResponse: ...


class _Client(Protocol):
    @property
    def generations(self) -> _Generations: ...


class GenerationLookup:
    """Reads the provider that served a generation; `client`, `sleep` and `clock` are replaced
    in tests."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: _Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = LOOKUP_ATTEMPTS,
        clock: Callable[[], float] = time.monotonic,
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
        self._clock = clock

    def served_by(self, generation_id: str) -> str:
        """The provider name of `generation_id`; retries while the record isn't there yet or the
        lookup is rate-limited. A transport error or 5xx is raised at once, as a
        `GenerationTransientError` the caller may try again later."""
        for attempt in range(self._attempts):
            if attempt:
                self._sleep(LOOKUP_WAIT_SECONDS)
            try:
                name = self._ask(generation_id)
            except GenerationRateLimitedError:
                continue
            if name is not None:
                return name
        raise GenerationNotFoundError(
            f"generation {generation_id} not found after {self._attempts} attempts"
        )

    def served_by_all(
        self, generation_ids: Sequence[str], budget_seconds: float = DEFERRED_BUDGET_SECONDS
    ) -> dict[str, str | GenerationLookupError]:
        """Each id's provider name, or the error that settles it. No request starts once
        `budget_seconds` have passed, so the whole wait is at most the budget plus one request's
        `LOOKUP_TIMEOUT_MS`. A record still missing then is a `GenerationNotFoundError`, or the
        transient error its last request got."""
        deadline = self._clock() + budget_seconds
        settled: dict[str, str | GenerationLookupError] = {}
        waiting: dict[str, GenerationPendingError | None] = dict.fromkeys(generation_ids)
        wait = DEFERRED_FIRST_WAIT_SECONDS
        while True:
            done, waiting = self._round(waiting, deadline)
            settled |= done
            remaining = deadline - self._clock()
            if not waiting or remaining <= 0:
                break
            self._sleep(min(wait, remaining))
            wait = min(wait * DEFERRED_WAIT_GROWTH, DEFERRED_MAX_WAIT_SECONDS)
        late = {
            key: error
            or GenerationNotFoundError(f"generation {key} not found within {budget_seconds:.0f} s")
            for key, error in waiting.items()
        }
        return settled | late

    def _round(
        self, waiting: Mapping[str, GenerationPendingError | None], deadline: float
    ) -> tuple[dict[str, str | GenerationLookupError], dict[str, GenerationPendingError | None]]:
        """One request per waiting record, until the deadline or a 429. Returns what is settled,
        and what still waits with the transient error of its last request (None: not there)."""
        done: dict[str, str | GenerationLookupError] = {}
        still: dict[str, GenerationPendingError | None] = {}
        keys = list(waiting)
        for index, key in enumerate(keys):
            if self._clock() >= deadline:
                return done, still | {later: waiting[later] for later in keys[index:]}
            try:
                name = self._ask(key)
            except GenerationRateLimitedError as error:
                return done, still | {key: error} | {k: waiting[k] for k in keys[index + 1 :]}
            except GenerationPendingError as error:
                still[key] = error
                continue
            except GenerationLookupError as error:
                done[key] = error
                continue
            if name is None:
                still[key] = None
            else:
                done[key] = name
        return done, still

    def _ask(self, generation_id: str) -> str | None:
        """One request: the provider name, or None while the record isn't there yet. A 429 raises
        `GenerationRateLimitedError`, a transport error or 5xx `GenerationTransientError`, any
        other failure `GenerationLookupError`."""
        try:
            response = self._client.generations.get_generation(id=generation_id)
        except OpenRouterError as error:
            if error.status_code == NOT_THERE_YET:
                return None
            reason = f"generation lookup failed: {type(error).__name__} (HTTP {error.status_code})"
            if error.status_code == RATE_LIMITED:
                raise GenerationRateLimitedError(reason) from error
            if error.status_code >= SERVER_ERROR:
                raise GenerationTransientError(reason) from error
            raise GenerationLookupError(reason) from error
        except (NoResponseError, httpx.HTTPError) as error:
            raise GenerationTransientError(
                f"generation lookup failed: {type(error).__name__}"
            ) from error
        name = response.data.provider_name
        if not name:
            raise GenerationLookupError(f"generation {generation_id} names no provider")
        return name
