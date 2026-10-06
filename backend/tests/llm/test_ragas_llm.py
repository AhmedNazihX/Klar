import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr
from ragas._analytics import do_not_track
from ragas.llms.base import InstructorLLM

from aiact.llm import LLMConfigError
from aiact.llm.ragas_llm import (
    DEFAULT_RAGAS_MODEL,
    RAGAS_PROVIDER,
    ragas_model,
    reply_usage,
    routing_body,
    usage_hook,
)
from aiact.settings import Settings


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def test_ragas_telemetry_is_off_once_the_module_is_imported() -> None:
    assert do_not_track() is True


def test_the_route_is_pinned_to_the_eu_endpoint_without_fallbacks() -> None:
    assert routing_body("google-vertex/eu") == {
        "provider": {
            "data_collection": "deny",
            "zdr": True,
            "order": ["google-vertex/eu"],
            "allow_fallbacks": False,
        }
    }


def test_the_model_defaults_to_flash_lite_on_its_eu_endpoint() -> None:
    model = ragas_model(lambda cost, tokens: None, settings=_settings())
    assert (model.model, model.provider) == (DEFAULT_RAGAS_MODEL, RAGAS_PROVIDER)
    assert isinstance(model.llm, InstructorLLM)
    assert model.llm.model_args["extra_body"] == routing_body(RAGAS_PROVIDER)


def test_the_ragas_model_setting_overrides_the_default() -> None:
    model = ragas_model(lambda cost, tokens: None, settings=_settings(ragas_model="vendor/m"))
    assert model.model == "vendor/m"


def test_a_missing_api_key_is_a_config_error() -> None:
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    with pytest.raises(LLMConfigError, match="OPENROUTER_API_KEY"):
        ragas_model(lambda cost, tokens: None, settings=settings)


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
