"""`POST /documents/vendor-letter` (P28): a DRAFT-labelled letter with its checks, drafted from
a result the backend validated; a result that is not valid, or calls for no letter, is a 422."""

import httpx
import pytest

from aiact.api import create_app
from aiact.api.documents import (
    INVALID_RESULT,
    NO_LETTER,
    UNKNOWN_QUESTION,
    VendorLetter,
    VendorLetterRequest,
)
from aiact.schemas import DISCLAIMER, ClassificationResult, Language
from tests.api.conftest import BASE_URL, api_settings
from tests.drafting.builders import ambiguous_result
from tests.drafting.vendor_builders import prohibited_result
from tests.schemas.worked_example import worked_example_result

pytestmark = pytest.mark.anyio

PATH = "/documents/vendor-letter"
ANSWERS = {"vendor": "Rank GmbH, Hafenstraße 1, 20457 Hamburg", "tool_name": "MoodMeter"}


def _body(
    result: ClassificationResult, language: Language = Language.EN, **extra: object
) -> dict[str, object]:
    return {"result": result.model_dump(mode="json"), "language": language.value, **extra}


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
    assert [check.passed for check in letter.checks] == [True, True, True]


async def test_an_ambiguous_result_gets_the_request(client: httpx.AsyncClient) -> None:
    response = await client.post(PATH, json=_body(ambiguous_result()))
    assert response.status_code == 200
    document = VendorLetter.model_validate(response.json()).document
    assert (document.template, document.label, document.unanswered) == (
        "vendor_request_ambiguous",
        "DRAFT",
        3,
    )


async def test_a_result_that_calls_for_no_letter_is_a_422(client: httpx.AsyncClient) -> None:
    response = await client.post(PATH, json=_body(worked_example_result()))
    assert response.status_code == 422
    assert response.json() == {"detail": NO_LETTER}


async def test_an_answer_the_letter_does_not_ask_for_is_a_422(client: httpx.AsyncClient) -> None:
    body = _body(prohibited_result(), answers={"overseers": "Jana Berg"})
    response = await client.post(PATH, json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": UNKNOWN_QUESTION}


async def test_a_result_breaking_the_contract_is_a_422_and_drafts_nothing(
    client: httpx.AsyncClient,
) -> None:
    """The backend validates the result: here a prohibited class on a high-risk result's steps,
    as a row the browser wrote could claim."""
    forged = {**worked_example_result().model_dump(mode="json"), "risk_class": "prohibited"}
    response = await client.post(PATH, json={"result": forged, "language": "en"})
    assert response.status_code == 422
    assert response.json() == {"detail": INVALID_RESULT}


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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        body = _body(prohibited_result())
        assert (await client.post(PATH, json=body)).status_code == 200
        limited = await client.post(PATH, json=body)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
