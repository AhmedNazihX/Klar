"""The rate limit (aiact/api/rate_limit.py): the fixed window on a fake clock, and through the API,
a 429 with `Retry-After` once a client's classifications or lookups are used up."""

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from aiact.api.rate_limit import WINDOW_SECONDS, RateLimiter
from aiact.engine.scripted import Script, scripted_nodes
from aiact.settings import Settings
from tests.api.conftest import use_nodes

BODY = {"description": "A chatbot that answers customer questions.", "language": "en"}
OBLIGATIONS = "/obligations?role=deployer&risk_class=high_risk"


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_a_key_gets_its_limit_per_window_then_waits_for_the_next() -> None:
    clock = FakeClock(100.0)
    limiter = RateLimiter(2, clock=clock)
    assert limiter.acquire("a") is None  # a's window starts at 100 s
    clock.now = 110.0
    assert limiter.acquire("a") is None
    assert limiter.acquire("a") == 50  # it ends at 160 s
    assert limiter.acquire("b") is None  # each key counts on its own
    clock.now = 100.0 + WINDOW_SECONDS
    assert limiter.acquire("a") is None
    assert limiter.acquire("a") is None
    assert limiter.acquire("a") == WINDOW_SECONDS


def test_retry_after_is_at_least_one_second() -> None:
    clock = FakeClock()
    limiter = RateLimiter(1, clock=clock)
    limiter.acquire("a")
    clock.now = WINDOW_SECONDS - 0.2
    assert limiter.acquire("a") == 1


def test_ended_windows_are_swept() -> None:
    clock = FakeClock()
    limiter = RateLimiter(1, clock=clock)
    for key in ("a", "b", "c"):
        limiter.acquire(key)
    clock.now = 2 * WINDOW_SECONDS
    limiter.acquire("d")
    assert set(limiter._windows) == {"d"}  # pyright: ignore[reportPrivateUsage]


def test_a_limit_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one"):
        RateLimiter(0)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        openrouter_api_key=SecretStr("k"),
        rate_limit_classify=2,
        rate_limit_lookups=3,
    )


@pytest.mark.anyio
async def test_a_client_over_its_classification_limit_gets_429(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    use_nodes(app, scripted_nodes(Script()))
    statuses = [(await client.post("/classify", json=BODY)).status_code for _ in range(3)]
    assert statuses == [200, 200, 429]
    refused = await client.post("/classify", json=BODY)
    assert refused.status_code == 429
    assert 1 <= int(refused.headers["retry-after"]) <= WINDOW_SECONDS
    assert "try again" in refused.json()["detail"]
    # Lookups have their own budget.
    assert (await client.get(OBLIGATIONS)).status_code == 200


@pytest.mark.anyio
async def test_a_client_over_its_lookup_limit_gets_429(client: httpx.AsyncClient) -> None:
    statuses = [(await client.get(OBLIGATIONS)).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]


@pytest.mark.anyio
async def test_another_client_keeps_its_own_budget(app: FastAPI, client: httpx.AsyncClient) -> None:
    for _ in range(3):
        await client.get(OBLIGATIONS)
    other = httpx.ASGITransport(app=app, client=("192.0.2.7", 1234))
    async with httpx.AsyncClient(transport=other, base_url="http://testserver") as second:
        assert (await second.get(OBLIGATIONS)).status_code == 200
