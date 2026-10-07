"""`POST /documents/drafts` and `POST /documents/export` (P9): the documents a result calls for,
drafted from the posted result and the user's answers, checked, and exported as Word and PDF.

The end-to-end test fills one skeleton (Annex IV) through the API and exports it."""

import logging
from datetime import date
from typing import Any

import httpx
import pytest

from aiact.api import create_app
from aiact.api.documents import INVALID_RESULT
from aiact.drafting import CheckName, CheckResult
from aiact.drafting.documents import checked_drafts
from aiact.schemas import DISCLAIMER, ClassificationResult, Language
from tests.api.conftest import BASE_URL, api_settings
from tests.drafting.builders import WORKERS, WORKERS_ANSWERS, provider_result
from tests.export.reading import one_line, pdf_pages, read_docx
from tests.schemas.builders import rebuild
from tests.schemas.worked_example import worked_example_result

pytestmark = pytest.mark.anyio

ANNEX_IV = "annex_iv_technical_documentation"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SECRET = "Confidential: the Hamburg pilot of Project Falcon"
"""An answer the logs must never show."""


def _body(result: ClassificationResult, **fields: Any) -> dict[str, Any]:
    return {"result": result.model_dump(mode="json"), "language": "en", **fields}


async def _drafts(client: httpx.AsyncClient, **fields: Any) -> dict[str, dict[str, Any]]:
    response = await client.post("/documents/drafts", json=_body(provider_result(), **fields))
    assert response.status_code == 200, response.text
    return {item["document"]["template"]: item for item in response.json()["documents"]}


def _all_passed(item: dict[str, Any]) -> bool:
    return all(check["passed"] for check in item["checks"])


# --- End to end: one skeleton filled through the interview and exported ------------------------


async def test_one_skeleton_is_filled_through_the_interview_and_exported(
    client: httpx.AsyncClient,
) -> None:
    before = (await _drafts(client, size_class="sme"))[ANNEX_IV]
    questions = [question["key"] for question in before["questions"]]
    assert before["document"]["status"] == "needs_answers"
    assert before["document"]["unanswered"] == len(questions) == 26
    assert _all_passed(before)

    answers = {key: f"our answer about {key.replace('_', ' ')}" for key in questions}
    after = (await _drafts(client, size_class="sme", answers={ANNEX_IV: answers}))[ANNEX_IV]
    document = after["document"]
    assert (document["status"], document["unanswered"], document["label"]) == (
        "ready_to_review",
        0,
        "DRAFT",
    )
    assert {section["status"] for section in document["sections"]} == {"drafted"}
    written = [
        p for s in document["sections"] if s["provenance"] == "interview" for p in s["paragraphs"]
    ]
    assert written == [f"Our answer about {key.replace('_', ' ')}." for key in questions]
    assert [check["check"] for check in after["checks"]] == [name.value for name in CheckName]
    assert _all_passed(after)

    export = _body(provider_result(), template=ANNEX_IV, size_class="sme", answers=answers)
    pdf = await client.post("/documents/export", json={**export, "format": "pdf"})
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"] == f'attachment; filename="{ANNEX_IV}.pdf"'
    pages = pdf_pages(pdf.content)
    text = " ".join(pages)
    assert all(paragraph in text for paragraph in written)
    assert "To fill in" not in text
    assert all(one_line(f"Draft prepared with Klar. {DISCLAIMER[Language.EN]}") in p for p in pages)

    docx = await client.post("/documents/export", json={**export, "format": "docx"})
    assert docx.status_code == 200, docx.text
    assert docx.headers["content-type"] == DOCX
    assert docx.headers["content-disposition"] == f'attachment; filename="{ANNEX_IV}.docx"'
    paragraphs = read_docx(docx.content).paragraphs
    assert [p for p in paragraphs if p in written] == written
    assert "DRAFT" in paragraphs
    assert not any(p.startswith("To fill in") for p in paragraphs)


# --- Drafts -------------------------------------------------------------------------------------


async def test_the_drafts_are_the_drafters_own(client: httpx.AsyncClient) -> None:
    listed = await _drafts(
        client, language="de", size_class="smc", answers={ANNEX_IV: {"cybersecurity": "Tests"}}
    )
    expected = checked_drafts(
        provider_result(), {ANNEX_IV: {"cybersecurity": "Tests"}}, Language.DE, None
    )
    assert list(listed) == [draft.document.template for draft in expected]
    assert listed[ANNEX_IV]["document"]["note"] is not None, "the size class reaches the note"
    assert listed[ANNEX_IV]["document"]["disclaimer"] == DISCLAIMER[Language.DE]


async def test_without_a_profile_no_simplified_form_note(client: httpx.AsyncClient) -> None:
    assert (await _drafts(client))[ANNEX_IV]["document"]["note"] is None


async def test_a_stale_answer_key_is_left_out_logged_by_count_and_never_a_422(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    answers = {ANNEX_IV: {"retired_question": SECRET}, "retired_template": {"x": SECRET}}
    with caplog.at_level(logging.DEBUG):
        drafts = await _drafts(client, answers=answers)
    assert _all_passed(drafts[ANNEX_IV])
    assert SECRET not in str(drafts)
    assert "left out 1 answers" in caplog.text
    assert SECRET not in caplog.text
    assert "retired_question" not in caplog.text


BROKEN_RESULTS = [
    {"note": SECRET},
    {"risk_class": "limited_risk", "transparency_duties": []},
    {"risk_class": SECRET},
]
"""A field the contract doesn't have, a rule of the contract broken, a value it doesn't allow."""


@pytest.mark.parametrize("route", ["/documents/drafts", "/documents/export"])
@pytest.mark.parametrize("changes", BROKEN_RESULTS)
async def test_a_result_that_breaks_the_contract_is_refused_without_echoing_it(
    client: httpx.AsyncClient, route: str, changes: dict[str, object]
) -> None:
    body = {**_body(provider_result()), "template": ANNEX_IV, "format": "pdf"}
    if route.endswith("drafts"):
        del body["template"], body["format"]
    body["result"] |= changes
    response = await client.post(route, json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": INVALID_RESULT}
    assert SECRET not in response.text


def test_the_schema_keeps_one_classification_result() -> None:
    schemas = create_app(api_settings()).openapi()["components"]["schemas"]
    assert "ClassificationResult" in schemas
    assert not [name for name in schemas if name.endswith(("-Input", "-Output"))]


async def test_an_unknown_field_is_refused(client: httpx.AsyncClient) -> None:
    body = _body(provider_result(), include_held_out=True)
    assert (await client.post("/documents/drafts", json=body)).status_code == 422


@pytest.mark.parametrize(
    ("answers", "status_code"),
    [
        ({ANNEX_IV: {"cybersecurity": "x" * 20_000}}, 200),
        ({ANNEX_IV: {"cybersecurity": "x" * 20_001}}, 422),
        ({ANNEX_IV: {"k" * 200: "x"}}, 200),
        ({ANNEX_IV: {"k" * 201: "x"}}, 422),
        ({ANNEX_IV: {"": "x"}}, 422),
        ({ANNEX_IV: {f"q{n}": "x" for n in range(100)}}, 200),
        ({ANNEX_IV: {f"q{n}": "x" for n in range(101)}}, 422),
        ({f"t{n}": {} for n in range(20)}, 200),
        ({f"t{n}": {} for n in range(21)}, 422),
        ({"Not-A-Template": {}}, 422),
    ],
)
async def test_answers_are_capped_as_the_database_caps_them(
    client: httpx.AsyncClient, answers: dict[str, dict[str, str]], status_code: int
) -> None:
    body = _body(provider_result(), answers=answers)
    assert (await client.post("/documents/drafts", json=body)).status_code == status_code


async def test_a_duty_with_several_dates_is_a_422_not_a_crash(client: httpx.AsyncClient) -> None:
    result = worked_example_result()
    later = result.obligations[1].model_copy(update={"applies_from": date(2028, 8, 2)})
    several = rebuild(result, obligations=(*result.obligations, later))
    response = await client.post("/documents/drafts", json=_body(several))
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "The result lists this document's duty with several dates, so it can't be drafted."
    )


# --- Export ------------------------------------------------------------------------------------


async def test_a_notice_is_exported_with_its_answers_as_given(client: httpx.AsyncClient) -> None:
    body = {
        **_body(worked_example_result(), language="de"),
        "template": WORKERS,
        "answers": WORKERS_ANSWERS,
        "format": "docx",
    }
    response = await client.post("/documents/export", json=body)
    assert response.status_code == 200
    paragraphs = read_docx(response.content).paragraphs
    assert "ENTWURF" in paragraphs
    assert all(answer in paragraphs for answer in WORKERS_ANSWERS.values())


async def test_a_document_the_result_does_not_call_for_is_a_404(client: httpx.AsyncClient) -> None:
    body = {**_body(provider_result()), "template": WORKERS, "format": "pdf"}
    response = await client.post("/documents/export", json=body)
    assert (response.status_code, response.json()["detail"]) == (
        404,
        "This result calls for no such document.",
    )


async def test_a_format_other_than_docx_or_pdf_is_refused(client: httpx.AsyncClient) -> None:
    body = {**_body(provider_result()), "template": ANNEX_IV, "format": "html"}
    assert (await client.post("/documents/export", json=body)).status_code == 422


async def test_a_draft_that_fails_a_check_is_never_exported(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    failed = CheckResult(check=CheckName.NOTHING_INVENTED, passed=False, problems=("forged",))
    monkeypatch.setattr("aiact.drafting.documents.run_checks", lambda *_args: (failed,))
    body = {
        **_body(provider_result()),
        "template": ANNEX_IV,
        "answers": {"cybersecurity": SECRET},
        "format": "pdf",
    }
    with caplog.at_level(logging.DEBUG):
        response = await client.post("/documents/export", json=body)
    assert (response.status_code, response.json()["detail"]) == (
        409,
        "The draft failed its automatic checks, so it can't be exported.",
    )
    assert f"export of {ANNEX_IV} refused: checks failed: ['nothing_invented']" in caplog.text
    assert SECRET not in caplog.text


# --- Limits -------------------------------------------------------------------------------------


async def test_the_document_routes_share_the_lookup_rate_limit() -> None:
    app = create_app(api_settings(rate_limit_lookups=2))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        body = _body(provider_result())
        assert (await client.post("/documents/drafts", json=body)).status_code == 200
        export = {**body, "template": ANNEX_IV, "format": "pdf"}
        assert (await client.post("/documents/export", json=export)).status_code == 200
        refused = await client.post("/documents/drafts", json=body)
    assert refused.status_code == 429
    assert "Retry-After" in refused.headers
