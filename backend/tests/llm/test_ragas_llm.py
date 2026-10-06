import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr
from ragas._analytics import do_not_track
from ragas.llms.base import InstructorLLM

from aiact.llm import LLMConfigError
from aiact.llm.ragas_llm import (
    ragas_chat_model,
    ragas_model,
    reply_usage,
    routing_body,
    usage_hook,
)
from aiact.settings import Settings

EU_ROUTE = {
    "provider": {
        "data_collection": "deny",
        "zdr": True,
        "order": ["google-vertex/eu"],
        "allow_fallbacks": False,
    }
}


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def _no_usage(cost: float | None, tokens: int) -> None:
    return None


def test_building_the_model_switches_ragas_telemetry_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGAS_DO_NOT_TRACK", "false")
    do_not_track.cache_clear()
    ragas_model(_no_usage, settings=_settings())
    assert do_not_track() is True


def test_the_route_is_pinned_to_the_eu_endpoint_without_fallbacks() -> None:
    assert routing_body("google-vertex/eu") == EU_ROUTE


def test_the_model_defaults_to_flash_lite_on_its_eu_endpoint() -> None:
    model = ragas_model(_no_usage, settings=_settings())
    assert (model.model, model.provider) == ("google/gemini-3.1-flash-lite", "google-vertex/eu")
    assert isinstance(model.llm, InstructorLLM)
    assert model.llm.model_args["extra_body"] == EU_ROUTE


def test_the_answer_model_takes_the_same_route() -> None:
    chat = ragas_chat_model(max_tokens=300, settings=_settings())
    assert chat.model_name == "google/gemini-3.1-flash-lite"
    assert chat.openrouter_provider == EU_ROUTE["provider"]
    assert chat.max_tokens == 300


def test_the_settings_override_model_and_provider_together() -> None:
    settings = _settings(ragas_model="vendor/m", ragas_provider="vendor/eu")
    model = ragas_model(_no_usage, settings=settings)
    assert (model.model, model.provider) == ("vendor/m", "vendor/eu")
    assert isinstance(model.llm, InstructorLLM)
    assert model.llm.model_args["extra_body"] == routing_body("vendor/eu")
    chat = ragas_chat_model(max_tokens=300, settings=settings)
    assert chat.model_name == "vendor/m"
    assert chat.openrouter_provider == routing_body("vendor/eu")["provider"]


def test_a_missing_api_key_is_a_config_error() -> None:
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    with pytest.raises(LLMConfigError, match="OPENROUTER_API_KEY"):
        ragas_model(_no_usage, settings=settings)


def test_closing_the_model_closes_its_http_client() -> None:
    model = ragas_model(_no_usage, settings=_settings())
    asyncio.run(model.aclose())
    assert model.client.is_closed()


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"usage": {"cost": 0.0012, "total_tokens": 900}}, (0.0012, 900)),
        ({"usage": {"total_tokens": 40}}, (None, 40)),
        ({"choices": []}, (None, 0)),
        ([1, 2], (None, 0)),
    ],
)
def test_reply_usage_reads_openrouters_usage(
    body: object, expected: tuple[float | None, int]
) -> None:
    assert reply_usage(json.dumps(body).encode()) == expected


def test_reply_usage_of_a_body_that_isnt_json_is_unknown() -> None:
    assert reply_usage(b"<html>") == (None, 0)


def _send_through_hook(status: int, body: dict[str, object]) -> list[tuple[float | None, int]]:
    seen: list[tuple[float | None, int]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    async def send() -> None:
        hook = usage_hook(lambda cost, tokens: seen.append((cost, tokens)))
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond), event_hooks={"response": [hook]}
        ) as client:
            await client.post("https://openrouter.test/api/v1/chat/completions", json={})

    asyncio.run(send())
    return seen


def test_the_hook_reports_every_successful_reply() -> None:
    body: dict[str, object] = {"usage": {"cost": 0.002, "total_tokens": 1500}}
    assert _send_through_hook(200, body) == [(0.002, 1500)]


def test_the_hook_ignores_error_replies() -> None:
    assert _send_through_hook(429, {"error": {"message": "rate limited"}}) == []
