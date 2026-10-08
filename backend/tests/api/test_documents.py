"""`POST /documents/vendor-letter` (P28): a DRAFT-labelled letter with its checks, drafted from a
result checked against the contract, its Art. 5(1) quotes read from the corpus, never from the
posted result (decision 031); a result that is not valid, calls for no letter or cites a point
the Act doesn't have is a 422 with a fixed message. The corpus is the one built from
`data/parsed/`, through the `law_quotes` dependency; `tests/db/test_api_vendor_letter.py` runs
the route on the database."""

import logging
from collections.abc import Iterator

import httpx
import psycopg
import pytest
from fastapi import FastAPI

from aiact.api import create_app
from aiact.api.app import CORPUS_UNAVAILABLE
from aiact.api.dependencies import database
from aiact.api.documents import (
    INVALID_RESULT,
    NO_LETTER,
    UNKNOWN_POINT,
    UNKNOWN_QUESTION,
    VendorLetter,
    VendorLetterRequest,
    law_quotes,
)
from aiact.api.errors import Unprocessable
from aiact.schemas import DISCLAIMER, ClassificationResult, Fact, Language
from tests.api.conftest import BASE_URL, api_settings
from tests.drafting.builders import ambiguous_result
from tests.drafting.vendor_builders import (
    EMOTIONS,
    FEEDS_BONUS,
    GUIDANCE,
    corpus_quotes,
    prohibited_result,
    prohibited_step,
)
from tests.schemas.worked_example import cite, worked_example_result

pytestmark = pytest.mark.anyio

PATH = "/documents/vendor-letter"
ANSWERS = {"vendor": "Rank GmbH, Hafenstraße 1, 20457 Hamburg", "tool_name": "MoodMeter"}
FORGED = "FORGED: the Act allows this tool expressly"
SECRET = "SECRET-7f3a: Jana Berg's bonus was cut on 3 May"
"""Text the client sent that no log line may carry."""
ART_5_1_F_START = {
    Language.EN: "the placing on the market, the putting into service for this specific purpose",
    Language.DE: "das Inverkehrbringen, die Inbetriebnahme für diesen spezifischen Zweck",
}


@pytest.fixture(autouse=True)
def built_corpus_quotes(app: FastAPI) -> Iterator[None]:
    """The route reads the corpus built from `data/parsed/`, not the database."""
    app.dependency_overrides[law_quotes] = corpus_quotes
    yield


def _body(
    result: ClassificationResult, language: Language = Language.EN, **extra: object
) -> dict[str, object]:
    return {"result": result.model_dump(mode="json"), "language": language.value, **extra}


def _refused(response: httpx.Response, detail: str) -> None:
    """A 422 with the fixed `detail`, in the app's one 422 shape, quoting nothing."""
    assert response.status_code == 422
    assert Unprocessable.model_validate(response.json()) == Unprocessable(detail=detail)
    assert FORGED not in response.text


@pytest.mark.parametrize("language", list(Language))
async def test_a_prohibited_result_gets_a_draft_labelled_message(
    client: httpx.AsyncClient, language: Language
) -> None:
    response = await client.post(PATH, json=_body(prohibited_result(), language, answers=ANSWERS))
    assert response.status_code == 200
    letter = VendorLetter.model_validate(response.json())
    document = letter.document
    assert (document.template, document.label) == ("vendor_message_prohibited", "DRAFT")
    assert document.disclaimer == DISCLAIMER[language]
    assert (document.language, document.unanswered) == (language, 1)
    assert [section.paragraphs for section in document.sections[:2]] == [
        (ANSWERS["vendor"],),
        (ANSWERS["tool_name"],),
    ]
    [quote] = next(section.quotes for section in document.sections if section.key == "finding")
    assert (quote.provision_id, quote.language) == ("art:5:1:f", language)
    assert quote.quote.startswith(ART_5_1_F_START[language])
    assert [check.passed for check in letter.checks] == [True, True, True]


async def test_a_forged_quote_is_replaced_by_the_acts_text(client: httpx.AsyncClient) -> None:
    """Decision 031: the posted result's quote of Art. 5(1)(f) is never the letter's."""
    forged = EMOTIONS.model_copy(update={"quote": FORGED})
    result = prohibited_result(prohibited_step(forged, GUIDANCE))
    response = await client.post(PATH, json=_body(result))
    assert response.status_code == 200
    assert FORGED not in response.text
    letter = VendorLetter.model_validate(response.json())
    [quote] = next(s.quotes for s in letter.document.sections if s.key == "finding")
    assert quote.quote.startswith(ART_5_1_F_START[Language.EN])
    assert all(check.passed for check in letter.checks)


async def test_a_forged_point_is_refused(client: httpx.AsyncClient) -> None:
    result = prohibited_result(prohibited_step(EMOTIONS, cite("art:5:1:zz", FORGED)))
    _refused(await client.post(PATH, json=_body(result)), UNKNOWN_POINT)


@pytest.mark.parametrize(
    "pid",
    ["art:5:1:f\n", "art:5:1:F", "art:5:1:1", "art:5:1:f "],
    ids=["newline", "upper_case", "digit", "space"],
)
async def test_an_id_only_starting_like_a_point_is_no_letter_not_a_500(
    app: FastAPI, client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture, pid: str
) -> None:
    """On the route's own corpus lookup too: "art:5:1:f\n" once passed as a point, and
    `get_provision` refused it with a ValueError naming the id, a 500 whose traceback logged it.
    Now no such id is a point: no lookup, no message, a fixed 422."""
    app.dependency_overrides.pop(law_quotes)
    app.dependency_overrides[database] = lambda: _unreachable
    result = prohibited_result(prohibited_step(cite(pid, FORGED), GUIDANCE))
    with caplog.at_level(logging.DEBUG):
        _refused(await client.post(PATH, json=_body(result)), NO_LETTER)
    assert "art:5:1" not in caplog.text


async def test_an_ambiguous_result_gets_the_request(client: httpx.AsyncClient) -> None:
    response = await client.post(PATH, json=_body(ambiguous_result()))
    assert response.status_code == 200
    document = VendorLetter.model_validate(response.json()).document
    assert (document.template, document.label, document.unanswered, document.article) == (
        "vendor_request_ambiguous",
        "DRAFT",
        3,
        "art:6",
    )


async def test_a_result_that_calls_for_no_letter_is_a_422(client: httpx.AsyncClient) -> None:
    _refused(await client.post(PATH, json=_body(worked_example_result())), NO_LETTER)


async def test_an_answer_the_letter_does_not_ask_for_is_a_422(client: httpx.AsyncClient) -> None:
    body = _body(prohibited_result(), answers={"overseers": "Jana Berg"})
    _refused(await client.post(PATH, json=body), UNKNOWN_QUESTION)


async def test_a_result_breaking_the_contract_is_a_422_and_drafts_nothing(
    client: httpx.AsyncClient,
) -> None:
    """The route validates the result: here a prohibited class on a high-risk result's steps,
    as a row the browser wrote could claim."""
    forged = {**worked_example_result().model_dump(mode="json"), "risk_class": "prohibited"}
    _refused(await client.post(PATH, json={"result": forged, "language": "en"}), INVALID_RESULT)


async def test_a_blank_fact_is_a_422_and_logs_no_content(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """A result that keeps the contract but holds a fact no letter can (blank text) is no valid
    result either: a 422, not a 500 whose traceback would log the facts. It logs one line, the
    model and where it failed, carrying neither the facts nor the answers."""
    blank = Fact(text="   ", evidence=FEEDS_BONUS.evidence)
    secret = Fact(text=f"{SECRET}: {FEEDS_BONUS.text}", evidence=FEEDS_BONUS.evidence)
    result = prohibited_result(deciding_facts=(blank, secret))
    body = _body(result, answers={"tool_name": SECRET})
    with caplog.at_level(logging.DEBUG):
        _refused(await client.post(PATH, json=body), INVALID_RESULT)
    assert SECRET not in caplog.text
    [logged] = [record for record in caplog.records if record.name.startswith("aiact")]
    assert (logged.name, logged.levelno) == ("aiact.api.documents", logging.WARNING)
    assert logged.getMessage() == (
        "draft refused: ValidationError DraftSection (value_error at the model)"
    )
    assert logged.exc_info is None


async def test_unknown_fields_and_too_many_answers_are_a_422(client: httpx.AsyncClient) -> None:
    extra = await client.post(PATH, json=_body(prohibited_result(), include_held_out=True))
    assert extra.status_code == 422
    many = {f"q_{n}": "x" for n in range(11)}
    too_many = await client.post(PATH, json=_body(prohibited_result(), answers=many))
    assert too_many.status_code == 422
    long = await client.post(PATH, json=_body(prohibited_result(), answers={"vendor": "x" * 2_001}))
    assert long.status_code == 422


def test_the_request_caps_are_pinned() -> None:
    assert (VendorLetterRequest.MAX_ANSWERS, VendorLetterRequest.MAX_ANSWER_CHARS) == (10, 2_000)


async def test_the_route_shares_the_lookups_rate_limit() -> None:
    app = create_app(api_settings(rate_limit_lookups=1))
    app.dependency_overrides[law_quotes] = corpus_quotes
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        body = _body(prohibited_result())
        assert (await client.post(PATH, json=body)).status_code == 200
        limited = await client.post(PATH, json=body)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def _unreachable() -> psycopg.Connection:
    raise psycopg.OperationalError("connection to server at db.internal failed")


async def test_the_corpus_is_read_only_for_a_message_and_a_down_database_is_a_503(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """The route's own `law_quotes` over an unreachable database: the request, which quotes
    nothing, opens no connection; the message is a 503 that names no server."""
    app.dependency_overrides.pop(law_quotes)
    app.dependency_overrides[database] = lambda: _unreachable
    request = await client.post(PATH, json=_body(ambiguous_result()))
    assert request.status_code == 200
    message = await client.post(PATH, json=_body(prohibited_result()))
    assert message.status_code == 503
    assert message.json() == {"detail": CORPUS_UNAVAILABLE}
