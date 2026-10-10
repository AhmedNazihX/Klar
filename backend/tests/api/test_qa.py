"""`POST /qa` (P7): the answer with its citations, law version and notice; a question about a
result answered with the result's citations; the body's bounds and no retrieval option; its own
rate limit; a 503 that quotes nothing when the model or its setup fails."""

import json
import logging
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.messages import AIMessage
from openrouter.errors import NoResponseError

from aiact.api.qa import MAX_QUESTION_CHARS, QuestionRequest, qa_model, qa_search
from aiact.llm.structured import ChatRoute, ProviderRefusalError
from aiact.qa import QaAnswer
from aiact.schemas import DISCLAIMER_DE, DISCLAIMER_EN, Language, LawVersion
from aiact.settings import Settings
from tests.api.conftest import api_settings
from tests.qa.test_answer import ART_3_4, FakeSearch, RecordingChat, model
from tests.schemas.worked_example import worked_example_result

pytestmark = pytest.mark.anyio

QUESTION = "What counts as a deployer?"
SECRET_QUESTION = "Our tool Zorblax-7 screens Jane Doe's application: what counts as a deployer?"


def serve(app: FastAPI, chat: RecordingChat, search: FakeSearch | None = None) -> FakeSearch:
    """The app's model and search replaced by scripted ones."""
    used = search or FakeSearch()
    app.dependency_overrides[qa_model] = lambda: ChatRoute(chat)
    app.dependency_overrides[qa_search] = lambda: used
    return used


async def test_a_question_is_answered_with_its_citations(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    chat = model(answer="A deployer uses an AI system under its own authority.", cited=(1,))
    search = serve(app, chat)
    response = await client.post("/qa", json={"question": f"  {QUESTION} ", "language": "en"})
    assert response.status_code == 200
    answer = QaAnswer.model_validate(response.json())
    assert answer.kind.value == "answered"
    assert answer.answer == "A deployer uses an AI system under its own authority."
    assert [(c.provision_id, c.quote) for c in answer.citations] == [("art:3:4", ART_3_4.text)]
    assert (answer.law_version, answer.disclaimer) == (LawVersion.AMENDED, DISCLAIMER_EN)
    # The question is searched trimmed, under the amended text on today (no date: the default).
    assert search.calls == [(QUESTION, Language.EN, LawVersion.AMENDED, None)]


async def test_a_question_about_a_result_is_answered_with_that_results_citations(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    result = worked_example_result()
    first = result.steps[0].citations[0]
    chat = model(answer="Yes, the people it screens must be told.", cited=(1,))
    search = serve(app, chat)
    body = {
        "question": "Do we have to tell applicants?",
        "language": "en",
        "law_version": "original",
        "result": result.model_dump(mode="json"),
    }
    response = await client.post("/qa", json=body)
    assert response.status_code == 200
    answer = QaAnswer.model_validate(response.json())
    assert answer.citations == (first,)
    assert search.calls == [
        ("Do we have to tell applicants?", Language.EN, LawVersion.AMENDED, result.as_of)
    ]
    assert answer.as_of == result.as_of


async def test_a_german_compliance_question_gets_the_fixed_answer_in_german(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    chat = model()
    search = serve(app, chat)
    body = {"question": "Sind wir konform?", "language": "de"}
    response = await client.post("/qa", json=body)
    assert response.status_code == 200
    answer = QaAnswer.model_validate(response.json())
    assert answer.kind.value == "compliance" and answer.citations == ()
    assert answer.answer.startswith("Das kann ich nicht beantworten.")
    assert answer.disclaimer == DISCLAIMER_DE
    assert search.calls == [] and chat.seen == []


@pytest.mark.parametrize(
    "body",
    [
        {"question": "", "language": "en"},
        {"question": "   ", "language": "en"},
        {"question": "x" * (MAX_QUESTION_CHARS + 1), "language": "en"},
        {"question": QUESTION, "language": "fr"},
        {"question": QUESTION, "language": "en", "law_version": "draft"},
        {"question": QUESTION, "language": "en", "include_held_out": True},
        {"question": QUESTION, "language": "en", "exclude_source_example_ids": ["x"]},
    ],
)
async def test_a_bad_body_is_a_422_before_any_search(
    app: FastAPI, client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    chat = model()
    search = serve(app, chat)
    response = await client.post("/qa", json=body)
    assert response.status_code == 422
    assert "x" * 50 not in response.text
    assert search.calls == [] and chat.seen == []


async def test_a_question_of_the_longest_length_is_taken(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    serve(app, model(answer="An answer.", cited=(1,)))
    body = {"question": "x" * MAX_QUESTION_CHARS, "language": "en"}
    assert (await client.post("/qa", json=body)).status_code == 200


async def test_a_result_that_breaks_the_contract_is_a_422_quoting_none_of_it(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    chat = model()
    search = serve(app, chat)
    broken = {**worked_example_result().model_dump(mode="json"), "disclaimer": ""}
    broken["facts"][0]["text"] = "Secret-Zorblax"
    body = {"question": QUESTION, "language": "en", "result": broken}
    response = await client.post("/qa", json=body)
    assert response.status_code == 422
    assert "Secret-Zorblax" not in response.text
    assert search.calls == [] and chat.seen == []


def test_the_request_has_no_retrieval_option() -> None:
    assert set(QuestionRequest.model_fields) == {"question", "language", "law_version", "result"}


@pytest.mark.parametrize(
    "failure",
    [
        ProviderRefusalError("refused"),
        NoResponseError(f"transport: {SECRET_QUESTION}"),
        ValueError(f"provider error quoting {SECRET_QUESTION}"),
        httpx.ConnectError(f"connect: {SECRET_QUESTION}"),
    ],
)
async def test_a_failed_model_call_is_a_503_that_quotes_and_logs_nothing(
    app: FastAPI,
    client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
    failure: Exception,
) -> None:
    class Failing(RecordingChat):
        def invoke(self, *args: Any, **kwargs: Any) -> AIMessage:  # pyright: ignore[reportIncompatibleMethodOverride]
            raise failure

    serve(app, Failing(messages=iter([])))
    with caplog.at_level(logging.DEBUG):
        response = await client.post("/qa", json={"question": SECRET_QUESTION, "language": "en"})
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Questions can't be answered right now. Please try again later."
    }
    assert "Zorblax" not in caplog.text and "Jane Doe" not in caplog.text
    assert type(failure).__name__ in caplog.text


async def test_a_reply_that_doesnt_fit_is_a_503(app: FastAPI, client: httpx.AsyncClient) -> None:
    chat = RecordingChat(messages=iter([AIMessage(content=json.dumps({"kind": "maybe"}))]))
    serve(app, chat)
    response = await client.post("/qa", json={"question": QUESTION, "language": "en"})
    assert response.status_code == 503


@pytest.mark.parametrize("settings", [api_settings(engine_model=None)])
async def test_an_unconfigured_model_is_a_503_before_any_search(
    app: FastAPI, client: httpx.AsyncClient, settings: Settings
) -> None:
    search = FakeSearch()
    app.dependency_overrides[qa_search] = lambda: search
    response = await client.post("/qa", json={"question": QUESTION, "language": "en"})
    assert response.status_code == 503
    assert search.calls == []


@pytest.mark.parametrize("settings", [api_settings(embedding_model=None)])
async def test_unconfigured_embeddings_are_a_503(
    app: FastAPI, client: httpx.AsyncClient, settings: Settings
) -> None:
    chat = model()
    app.dependency_overrides[qa_model] = lambda: ChatRoute(chat)
    response = await client.post("/qa", json={"question": QUESTION, "language": "en"})
    assert response.status_code == 503
    assert chat.seen == []


@pytest.mark.parametrize("settings", [api_settings(rate_limit_qa=2, rate_limit_lookups=1)])
async def test_a_client_over_its_question_limit_gets_429(
    app: FastAPI, client: httpx.AsyncClient, settings: Settings
) -> None:
    """Questions count in their own bucket: two lookups' worth of limit is not theirs."""
    chats = [model(answer="An answer.", cited=(1,)) for _ in range(2)]
    for chat in chats:
        serve(app, chat)
        response = await client.post("/qa", json={"question": QUESTION, "language": "en"})
        assert response.status_code == 200
    third = model()
    serve(app, third)
    response = await client.post("/qa", json={"question": QUESTION, "language": "en"})
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1
    assert third.seen == []


def test_the_question_limit_defaults_to_twenty_a_minute() -> None:
    assert Settings(_env_file=None).rate_limit_qa == 20  # pyright: ignore[reportCallIssue]
