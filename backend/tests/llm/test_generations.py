"""The provider lookup over OpenRouter's generation records (X2), against a fake SDK client."""

import httpx
import pytest
from openrouter.errors import NoResponseError, OpenRouterError
from pydantic import SecretStr

from aiact.llm import LLMConfigError
from aiact.llm.generations import LOOKUP_WAIT_SECONDS, GenerationLookup, GenerationLookupError
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


def test_the_real_client_needs_the_api_key() -> None:
    with pytest.raises(LLMConfigError):
        GenerationLookup(Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    GenerationLookup(Settings(_env_file=None, openrouter_api_key=SecretStr("k")))  # pyright: ignore[reportCallIssue]
