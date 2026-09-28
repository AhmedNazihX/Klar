import json

import httpx
import pytest
from pydantic import SecretStr

from aiact.llm import ChoiceQuestion, DecisionsClient, DecisionsError
from aiact.settings import Settings, get_settings

JEV = "typesafe/jev-1.13"
STATE = (
    "We are a 40-person staffing agency. We bought a tool that reads applicants' CVs and ranks "
    "them for each vacancy; recruiters only interview the top ten."
)
QUESTIONS = {
    "is_hiring_tool": ChoiceQuestion(
        instructions="Is the described tool used in recruitment?",
        criteria={"yes": "It is used to select or rank job applicants.", "no": "It is not."},
    )
}
USAGE = {"input_tokens": 400, "output_tokens": 60, "cost": 0.00002}


def _settings() -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"))  # pyright: ignore[reportCallIssue]


def _client(
    status: int, body: object, seen: list[dict[str, object]] | None = None
) -> DecisionsClient:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        return httpx.Response(status, json=body)

    http = httpx.Client(transport=httpx.MockTransport(handle))
    return DecisionsClient(JEV, settings=_settings(), http=http)


def _answer(choice: str) -> dict[str, object]:
    return {
        "model": "typesafe/jev-1.13-20260917",
        "answers": {"is_hiring_tool": {"type": "choice", "choice": choice, "confidence": 0.9}},
        "usage": USAGE,
    }


def test_request_sends_the_questions_and_privacy_routing() -> None:
    seen: list[dict[str, object]] = []
    response = _client(200, _answer("yes"), seen).choose(STATE, QUESTIONS)

    assert response.answers["is_hiring_tool"].choice == "yes"
    assert response.usage.tokens == 460
    assert seen[0]["model"] == JEV
    assert seen[0]["provider"] == {"data_collection": "deny", "zdr": True}
    assert seen[0]["questions"] == {
        "is_hiring_tool": {
            "type": "choice",
            "instructions": "Is the described tool used in recruitment?",
            "criteria": {"yes": "It is used to select or rank job applicants.", "no": "It is not."},
        }
    }


def test_http_error_spent_nothing() -> None:
    with pytest.raises(DecisionsError, match="HTTP 400") as caught:
        _client(400, {"error": {"message": "bad"}}).choose(STATE, QUESTIONS)
    assert (caught.value.cost_usd, caught.value.tokens) == (0.0, 0)


def test_choice_outside_the_criteria_keeps_the_cost() -> None:
    with pytest.raises(DecisionsError, match="no valid choice") as caught:
        _client(200, _answer("maybe")).choose(STATE, QUESTIONS)
    assert (caught.value.cost_usd, caught.value.tokens) == (0.00002, 460)


def test_malformed_answers_keep_the_reported_cost() -> None:
    body = {"model": JEV, "answers": {"is_hiring_tool": {"type": "noul"}}, "usage": USAGE}
    with pytest.raises(DecisionsError, match="unexpected decisions response") as caught:
        _client(200, body).choose(STATE, QUESTIONS)
    assert caught.value.cost_usd == 0.00002


def test_body_without_usage_is_an_unpaid_error() -> None:
    with pytest.raises(DecisionsError) as caught:
        _client(200, {"unexpected": True}).choose(STATE, QUESTIONS)
    assert caught.value.cost_usd == 0.0


def _assert_jev_answers(settings: Settings) -> None:
    response = DecisionsClient(JEV, settings=settings).choose(STATE, QUESTIONS)
    assert response.answers["is_hiring_tool"].choice == "yes"
    assert response.usage.cost > 0


@pytest.mark.vcr
def test_jev_roundtrip(openrouter_settings: Settings) -> None:
    _assert_jev_answers(openrouter_settings)


@pytest.mark.live
def test_jev_roundtrip_live() -> None:
    _assert_jev_answers(get_settings())
