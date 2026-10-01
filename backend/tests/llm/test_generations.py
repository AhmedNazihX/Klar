"""The provider lookup over OpenRouter's generation records (X2), against a fake SDK client."""

import httpx
import pytest
from openrouter.errors import NoResponseError, OpenRouterError
from pydantic import SecretStr

from aiact.llm import LLMConfigError
from aiact.llm.generations import (
    DEFERRED_BUDGET_SECONDS,
    DEFERRED_FIRST_WAIT_SECONDS,
    DEFERRED_MAX_WAIT_SECONDS,
    LOOKUP_TIMEOUT_MS,
    LOOKUP_WAIT_SECONDS,
    GenerationLookup,
    GenerationLookupError,
    GenerationNotFoundError,
    is_not_found,
)
from aiact.llm.routing import NO_RETRIES
from aiact.settings import Settings


def _http_error(status: int) -> OpenRouterError:
    request = httpx.Request("GET", "https://openrouter.ai/api/v1/generation")
    return OpenRouterError("error", httpx.Response(status, request=request))


class _Data:
    def __init__(self, provider_name: str | None) -> None:
        self.provider_name = provider_name


class _Response:
    def __init__(self, provider_name: str | None) -> None:
        self.data = _Data(provider_name)


class FakeGenerations:
    """Answers with each of `replies` in turn: an exception is raised, a name is returned."""

    def __init__(self, *replies: Exception | str | None) -> None:
        self.replies = list(replies)
        self.asked: list[str] = []

    def get_generation(self, *, id: str) -> _Response:
        self.asked.append(id)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return _Response(reply)


class FakeClient:
    def __init__(self, generations: FakeGenerations) -> None:
        self.generations = generations


def lookup(generations: FakeGenerations, attempts: int = 3) -> tuple[GenerationLookup, list[float]]:
    slept: list[float] = []
    client = FakeClient(generations)
    return GenerationLookup(client=client, sleep=slept.append, attempts=attempts), slept  # pyright: ignore[reportArgumentType]


def test_the_provider_name_is_read_once_the_record_exists() -> None:
    generations = FakeGenerations(_http_error(404), _http_error(404), "Azure")
    reader, slept = lookup(generations)
    assert reader.served_by("gen-1") == "Azure"
    assert generations.asked == ["gen-1"] * 3
    assert slept == [LOOKUP_WAIT_SECONDS] * 2


def test_a_rate_limited_lookup_is_tried_again() -> None:
    generations = FakeGenerations(_http_error(429), "Google")
    reader, slept = lookup(generations)
    assert reader.served_by("gen-1") == "Google"
    assert slept == [LOOKUP_WAIT_SECONDS]


def test_the_real_client_never_retries_and_times_out() -> None:
    """The loop above is the only retry: the SDK's default would retry for up to an hour."""
    reader = GenerationLookup(Settings(_env_file=None, openrouter_api_key=SecretStr("k")))  # pyright: ignore[reportCallIssue]
    config = reader._client.sdk_configuration  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]
    assert config.retry_config is NO_RETRIES
    assert NO_RETRIES.strategy == "none"
    assert config.timeout_ms == LOOKUP_TIMEOUT_MS


def test_a_record_that_never_appears_is_an_error() -> None:
    reader, _ = lookup(FakeGenerations(*[_http_error(404)] * 3))
    with pytest.raises(GenerationLookupError, match="not found after 3 attempts"):
        reader.served_by("gen-1")


@pytest.mark.parametrize(
    "error", [_http_error(401), NoResponseError("none"), httpx.ConnectError("refused")]
)
def test_any_other_failure_is_an_error_at_once(error: Exception) -> None:
    generations = FakeGenerations(error, "Azure")
    reader, slept = lookup(generations)
    with pytest.raises(GenerationLookupError, match="generation lookup failed"):
        reader.served_by("gen-1")
    assert slept == []


def test_a_record_without_a_provider_is_an_error() -> None:
    reader, _ = lookup(FakeGenerations(None))
    with pytest.raises(GenerationLookupError, match="names no provider"):
        reader.served_by("gen-1")


def test_a_record_not_found_in_time_is_its_own_error_and_reads_back_as_one() -> None:
    reader, _ = lookup(FakeGenerations(*[_http_error(404)] * 3))
    with pytest.raises(GenerationNotFoundError) as caught:
        reader.served_by("gen-1")
    assert is_not_found(str(caught.value))
    assert is_not_found("generation gen-1 not found within 300 s")
    assert not is_not_found("generation lookup failed: OpenRouterError (HTTP 500)")
    assert not is_not_found("served by Google AI Studio, not Google")


class FakeClock:
    """Time that moves only when the lookup sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class RoundGenerations:
    """`records[id]` lists the replies to that id, one per request; the last one repeats."""

    def __init__(self, records: dict[str, list[Exception | str | None]]) -> None:
        self.records = records
        self.asked: list[str] = []

    def get_generation(self, *, id: str) -> _Response:
        self.asked.append(id)
        replies = self.records[id]
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        if isinstance(reply, Exception):
            raise reply
        return _Response(reply)


def long_lookup(generations: RoundGenerations) -> tuple[GenerationLookup, FakeClock]:
    clock = FakeClock()
    client = FakeClient(generations)  # pyright: ignore[reportArgumentType]
    reader = GenerationLookup(client=client, sleep=clock.sleep, clock=clock)  # pyright: ignore[reportArgumentType]
    return reader, clock


def test_the_long_wait_asks_each_missing_record_once_a_round_until_it_shows_up() -> None:
    late = _http_error(404)
    generations = RoundGenerations(
        {"gen-1": ["Azure"], "gen-2": [late, late, "Azure"], "gen-3": [late, "Google"]}
    )
    reader, clock = long_lookup(generations)
    found = reader.served_by_all(["gen-1", "gen-2", "gen-3", "gen-1"])
    assert found == {"gen-1": "Azure", "gen-2": "Azure", "gen-3": "Google"}
    assert generations.asked == ["gen-1", "gen-2", "gen-3", "gen-2", "gen-3", "gen-2"]
    assert clock.slept == [DEFERRED_FIRST_WAIT_SECONDS, DEFERRED_FIRST_WAIT_SECONDS * 2]


def test_the_long_wait_stops_at_its_budget_with_growing_waits() -> None:
    generations = RoundGenerations({"gen-1": [_http_error(404)]})
    reader, clock = long_lookup(generations)
    [result] = reader.served_by_all(["gen-1"]).values()
    assert isinstance(result, GenerationNotFoundError)
    assert str(result) == "generation gen-1 not found within 300 s"
    assert is_not_found(str(result))
    assert clock.now == DEFERRED_BUDGET_SECONDS
    assert clock.slept[:5] == [5.0, 10.0, 20.0, 40.0, DEFERRED_MAX_WAIT_SECONDS]
    assert max(clock.slept) == DEFERRED_MAX_WAIT_SECONDS


def test_the_long_wait_settles_an_unreadable_record_at_once() -> None:
    generations = RoundGenerations({"gen-1": [_http_error(401)], "gen-2": [None]})
    reader, clock = long_lookup(generations)
    found = reader.served_by_all(["gen-1", "gen-2"])
    assert str(found["gen-1"]) == "generation lookup failed: OpenRouterError (HTTP 401)"
    assert str(found["gen-2"]) == "generation gen-2 names no provider"
    assert clock.slept == []
    assert generations.asked == ["gen-1", "gen-2"]


def test_the_long_wait_with_nothing_to_find_makes_no_request() -> None:
    generations = RoundGenerations({})
    reader, clock = long_lookup(generations)
    assert reader.served_by_all([]) == {}
    assert (generations.asked, clock.slept) == ([], [])


def test_the_real_client_needs_the_api_key() -> None:
    with pytest.raises(LLMConfigError):
        GenerationLookup(Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    GenerationLookup(Settings(_env_file=None, openrouter_api_key=SecretStr("k")))  # pyright: ignore[reportCallIssue]
