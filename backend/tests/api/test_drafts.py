"""`POST /documents/list`, `/documents/draft` and `/documents/export` (P9): the documents a
result calls for, one of them drafted from the posted result and the user's answers and
checked, and exported as Word and PDF. Any text of the Act a document quotes is its template's
or the corpus's, never the posted result's (decision 031); the corpus is the one built from
`data/parsed/`, through the `law_quotes` dependency.

The end-to-end test fills one skeleton (Annex IV) through the API and exports it."""

import logging
from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from aiact.api import create_app
from aiact.api.dependencies import ApiContext
from aiact.api.documents import INVALID_RESULT, law_quotes
from aiact.api.drafts import MAX_FILE_CHARS, MAX_FILE_LINES
from aiact.drafting import CheckName, CheckResult, SizeClass
from aiact.drafting.documents import checked_draft
from aiact.schemas import DISCLAIMER, ClassificationResult, Fact, Language
from tests.api.conftest import BASE_URL, api_settings
from tests.drafting.builders import WORKERS, WORKERS_ANSWERS, provider_result
from tests.drafting.vendor_builders import (
    EMOTIONS,
    FEEDS_BONUS,
    GUIDANCE,
    corpus_quotes,
    prohibited_result,
    prohibited_step,
)
from tests.export.reading import one_line, pdf_pages, read_docx
from tests.schemas.builders import rebuild
from tests.schemas.worked_example import worked_example_result

pytestmark = pytest.mark.anyio

ANNEX_IV = "annex_iv_technical_documentation"
MESSAGE = "vendor_message_prohibited"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SECRET = "Confidential: the Hamburg pilot of Project Falcon"
"""An answer the logs must never show."""
FORGED = "FORGED: the Act allows this tool expressly"


@pytest.fixture(autouse=True)
def built_corpus_quotes(app: FastAPI) -> Iterator[None]:
    """The routes read the corpus built from `data/parsed/`, not the database."""
    app.dependency_overrides[law_quotes] = corpus_quotes
    yield


def _body(result: ClassificationResult, **fields: Any) -> dict[str, Any]:
    return {"result": result.model_dump(mode="json"), "language": "en", **fields}


def _draft_body(result: ClassificationResult, template: str, **fields: Any) -> dict[str, Any]:
    return _body(result, template=template, **fields)


async def _draft(client: httpx.AsyncClient, template: str, **fields: Any) -> dict[str, Any]:
    response = await client.post(
        "/documents/draft", json=_draft_body(provider_result(), template, **fields)
    )
    assert response.status_code == 200, response.text
    return response.json()


def _all_passed(item: dict[str, Any]) -> bool:
    return all(check["passed"] for check in item["checks"])


# --- End to end: one skeleton filled through the interview and exported ------------------------


async def test_one_skeleton_is_filled_through_the_interview_and_exported(
    client: httpx.AsyncClient,
) -> None:
    listed = await client.post("/documents/list", json=_body(provider_result()))
    assert listed.status_code == 200
    annex = next(d for d in listed.json()["documents"] if d["template"] == ANNEX_IV)
    questions = [question["key"] for question in annex["questions"]]
    before = await _draft(client, ANNEX_IV, size_class="sme")
    assert before["document"]["status"] == "needs_answers"
    assert before["document"]["unanswered"] == len(questions) == 26
    assert _all_passed(before)

    answers = {key: f"our answer about {key.replace('_', ' ')}" for key in questions}
    after = await _draft(client, ANNEX_IV, size_class="sme", answers=answers)
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

    export = _draft_body(provider_result(), ANNEX_IV, size_class="sme", answers=answers)
    pdf = await client.post("/documents/export", json={**export, "format": "pdf"})
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"] == f'attachment; filename="{ANNEX_IV}.pdf"'
    pages = pdf_pages(pdf.content)
    text = " ".join(pages)
    assert all(paragraph in text for paragraph in written)
    assert one_line(document["note"]) in text, "the file holds the draft on screen, its note too"
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


# --- List ---------------------------------------------------------------------------------------


async def test_the_list_names_each_document_its_duty_and_its_interview(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/documents/list", json=_body(worked_example_result(), language="de")
    )
    assert response.status_code == 200
    documents = response.json()["documents"]
    workers = next(d for d in documents if d["template"] == WORKERS)
    assert workers["title"] == "Information der Arbeitnehmervertreter"
    assert workers["article"] == "art:26:7"
    assert workers["questions"][1] == {
        "key": "tool_and_supplier",
        "text": "Wie heißt das Tool, und wer liefert es?",
        "section": "tool",
        "choices": [],
    }


async def test_a_prohibited_result_lists_its_vendor_message(client: httpx.AsyncClient) -> None:
    response = await client.post("/documents/list", json=_body(prohibited_result()))
    assert [d["template"] for d in response.json()["documents"]] == [MESSAGE]


# --- Draft --------------------------------------------------------------------------------------


async def test_the_draft_is_the_drafters_own(client: httpx.AsyncClient) -> None:
    answers = {"cybersecurity": "Tests"}
    drafted = await _draft(client, ANNEX_IV, language="de", size_class="smc", answers=answers)
    expected = checked_draft(
        ANNEX_IV, provider_result(), answers, Language.DE, SizeClass.SMC, corpus_quotes()
    )
    assert drafted == expected.model_dump(mode="json")
    assert drafted["document"]["note"] is not None, "the size class reaches the note"
    assert drafted["document"]["disclaimer"] == DISCLAIMER[Language.DE]


async def test_without_a_profile_no_simplified_form_note(client: httpx.AsyncClient) -> None:
    assert (await _draft(client, ANNEX_IV))["document"]["note"] is None


async def test_the_vendor_message_quotes_the_corpus_never_the_posted_result(
    client: httpx.AsyncClient,
) -> None:
    forged = EMOTIONS.model_copy(update={"quote": FORGED})
    result = prohibited_result(prohibited_step(forged, GUIDANCE))
    drafted = await client.post("/documents/draft", json=_draft_body(result, MESSAGE))
    assert drafted.status_code == 200
    assert FORGED not in drafted.text
    [quote] = [q for s in drafted.json()["document"]["sections"] for q in s["quotes"]]
    assert quote["quote"].startswith("the placing on the market, the putting into service")
    assert _all_passed(drafted.json())
    body = _draft_body(result, MESSAGE, answers={"vendor": "Rank GmbH", "tool_name": "Mood"})
    exported = await client.post("/documents/export", json={**body, "format": "pdf"})
    assert exported.status_code == 200
    text = " ".join(pdf_pages(exported.content))
    assert "the placing on the market, the putting into service" in text
    assert "FORGED" not in text


async def test_a_point_the_corpus_lacks_is_refused(client: httpx.AsyncClient) -> None:
    unknown = EMOTIONS.model_copy(update={"provision_id": "art:5:1:z"})
    result = prohibited_result(prohibited_step(unknown, GUIDANCE))
    response = await client.post("/documents/draft", json=_draft_body(result, MESSAGE))
    assert (response.status_code, response.json()["detail"]) == (
        422,
        "The result cites a point of Art. 5(1) the AI Act's text doesn't have.",
    )


async def test_a_stale_answer_key_is_left_out_logged_by_count_and_never_a_422(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        drafted = await _draft(client, ANNEX_IV, answers={"retired_question": SECRET})
    assert _all_passed(drafted)
    assert SECRET not in str(drafted)
    assert "left out 1 answers" in caplog.text
    assert SECRET not in caplog.text
    assert "retired_question" not in caplog.text


BROKEN_RESULTS = [
    {"note": SECRET},
    {"risk_class": "limited_risk", "transparency_duties": []},
    {"risk_class": SECRET},
]
"""A field the contract doesn't have, a rule of the contract broken, a value it doesn't allow."""


@pytest.mark.parametrize("route", ["list", "draft", "export"])
@pytest.mark.parametrize("changes", BROKEN_RESULTS)
async def test_a_result_that_breaks_the_contract_is_refused_without_echoing_it(
    client: httpx.AsyncClient, route: str, changes: dict[str, object]
) -> None:
    fields = {
        "list": {},
        "draft": {"template": ANNEX_IV},
        "export": {"template": ANNEX_IV, "format": "pdf"},
    }[route]
    body = _body(provider_result(), **fields)
    body["result"] |= changes
    response = await client.post(f"/documents/{route}", json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": INVALID_RESULT}
    assert SECRET not in response.text


def test_the_schema_keeps_one_classification_result() -> None:
    schemas = create_app(api_settings()).openapi()["components"]["schemas"]
    assert "ClassificationResult" in schemas
    assert not [name for name in schemas if name.endswith(("-Input", "-Output"))]


async def test_an_unknown_field_is_refused(client: httpx.AsyncClient) -> None:
    body = _draft_body(provider_result(), ANNEX_IV, include_held_out=True)
    assert (await client.post("/documents/draft", json=body)).status_code == 422


@pytest.mark.parametrize(
    ("answers", "status_code"),
    [
        ({"cybersecurity": "x" * 20_000}, 200),
        ({"cybersecurity": "x" * 20_001}, 422),
        ({"k" * 200: "x"}, 200),
        ({"k" * 201: "x"}, 422),
        ({"": "x"}, 422),
        ({f"q{n}": "x" for n in range(100)}, 200),
        ({f"q{n}": "x" for n in range(101)}, 422),
    ],
)
async def test_answers_are_capped_as_the_database_caps_them(
    client: httpx.AsyncClient, answers: dict[str, str], status_code: int
) -> None:
    body = _draft_body(provider_result(), ANNEX_IV, answers=answers)
    assert (await client.post("/documents/draft", json=body)).status_code == status_code


@pytest.mark.parametrize(("template", "status_code"), [("t" * 200, 404), ("t" * 201, 422)])
async def test_a_template_id_is_capped(
    client: httpx.AsyncClient, template: str, status_code: int
) -> None:
    body = _draft_body(provider_result(), template)
    assert (await client.post("/documents/draft", json=body)).status_code == status_code


async def test_a_template_id_that_is_not_one_is_refused(client: httpx.AsyncClient) -> None:
    body = _draft_body(provider_result(), "Not-A-Template")
    assert (await client.post("/documents/draft", json=body)).status_code == 422


async def test_a_duty_with_several_dates_is_a_422_not_a_crash(client: httpx.AsyncClient) -> None:
    result = worked_example_result()
    workers = next(o for o in result.obligations if o.article == "art:26:7")
    later = workers.model_copy(update={"applies_from": date(2028, 8, 2)})
    several = rebuild(result, obligations=(*result.obligations, later))
    response = await client.post("/documents/draft", json=_draft_body(several, WORKERS))
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "The result lists this document's duty with several dates, so it can't be drafted."
    )


@pytest.mark.parametrize("route", ["draft", "export"])
async def test_a_blank_fact_in_a_vendor_message_is_a_422_that_logs_no_content(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture, route: str
) -> None:
    """A result that keeps the contract but holds a fact no document can (blank text) is refused
    as `/documents/vendor-letter` refuses it: a 422, not a 500 whose traceback would log the
    facts, and one log line carrying neither the facts nor the answers."""
    blank = Fact(text="   ", evidence=FEEDS_BONUS.evidence)
    secret = Fact(text=f"{SECRET}: {FEEDS_BONUS.text}", evidence=FEEDS_BONUS.evidence)
    result = prohibited_result(deciding_facts=(blank, secret))
    body = {**_draft_body(result, MESSAGE, answers={"tool_name": SECRET}), "format": "pdf"}
    if route == "draft":
        del body["format"]
    with caplog.at_level(logging.DEBUG):
        response = await client.post(f"/documents/{route}", json=body)
    assert (response.status_code, response.json()) == (422, {"detail": INVALID_RESULT})
    assert SECRET not in caplog.text
    [logged] = [record for record in caplog.records if record.name.startswith("aiact")]
    assert (logged.name, logged.levelno) == ("aiact.api.documents", logging.WARNING)
    assert logged.getMessage() == (
        "draft refused: ValidationError DraftSection (value_error at the model)"
    )
    assert logged.exc_info is None


# --- Export ------------------------------------------------------------------------------------


async def test_a_notice_is_exported_with_its_answers_as_given(client: httpx.AsyncClient) -> None:
    body = {
        **_draft_body(worked_example_result(), WORKERS, language="de", answers=WORKERS_ANSWERS),
        "format": "docx",
    }
    response = await client.post("/documents/export", json=body)
    assert response.status_code == 200
    paragraphs = read_docx(response.content).paragraphs
    assert "ENTWURF" in paragraphs
    assert all(answer in paragraphs for answer in WORKERS_ANSWERS.values())


async def test_a_document_the_result_does_not_call_for_is_a_404(client: httpx.AsyncClient) -> None:
    for route, extra in (("draft", {}), ("export", {"format": "pdf"})):
        body = {**_draft_body(provider_result(), WORKERS), **extra}
        response = await client.post(f"/documents/{route}", json=body)
        assert (response.status_code, response.json()["detail"]) == (
            404,
            "This result calls for no such document.",
        )


async def test_a_format_other_than_docx_or_pdf_is_refused(client: httpx.AsyncClient) -> None:
    body = {**_draft_body(provider_result(), ANNEX_IV), "format": "html"}
    assert (await client.post("/documents/export", json=body)).status_code == 422


async def test_a_draft_that_fails_a_check_is_never_exported(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    failed = CheckResult(check=CheckName.NOTHING_INVENTED, passed=False, problems=("forged",))
    monkeypatch.setattr("aiact.drafting.documents.run_checks", lambda *_args: (failed,))
    body = {
        **_draft_body(provider_result(), ANNEX_IV, answers={"cybersecurity": SECRET}),
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

TOO_LONG = "This document is too long to make into a file. Please shorten some answers."
QUESTIONS = (
    "intended_purpose",
    "interactions",
    "software_versions",
    "market_forms",
    "hardware",
    "product_component",
    "user_interface",
)
"""Seven of Annex IV's questions, for long answers."""


def test_the_file_caps_are_pinned() -> None:
    assert (MAX_FILE_CHARS, MAX_FILE_LINES) == (120_000, 2_000)


def _long_answers(count: int, answer: str) -> dict[str, str]:
    return dict.fromkeys(QUESTIONS[:count], answer)


@pytest.mark.parametrize(
    ("answers", "status_code"),
    [
        (_long_answers(4, "x" * 20_000), 200),
        (_long_answers(7, "x" * 20_000), 413),
        (_long_answers(4, "a\n" * 400), 200),
        (_long_answers(4, "a\n" * 600), 413),
        (_long_answers(4, "a\r" * 600), 413),
        (_long_answers(4, "a\r\n" * 400), 200),
        (_long_answers(4, "a\r\n" * 600), 413),
    ],
    ids=[
        "80k characters",
        "140k characters",
        "1,600 lines",
        "2,400 lines",
        "2,400 lines by lone carriage returns",
        "1,600 lines by CRLF, each one break",
        "2,400 lines by CRLF",
    ],
)
async def test_a_draft_too_long_for_a_file_is_a_413_before_rendering(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    answers: dict[str, str],
    status_code: int,
) -> None:
    rendered: list[object] = []
    monkeypatch.setattr("aiact.api.drafts.render_pdf", lambda paper: rendered.append(paper) or b"%")
    body = {**_draft_body(provider_result(), ANNEX_IV, answers=answers), "format": "pdf"}
    response = await client.post("/documents/export", json=body)
    assert response.status_code == status_code
    if status_code == 413:
        assert response.json() == {"detail": TOO_LONG}
        assert rendered == []


async def test_exports_have_their_own_rate_limit() -> None:
    app = create_app(api_settings(rate_limit_exports=1, rate_limit_lookups=100))
    app.dependency_overrides[law_quotes] = corpus_quotes
    export = {**_draft_body(provider_result(), ANNEX_IV), "format": "pdf"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        assert (await client.post("/documents/export", json=export)).status_code == 200
        refused = await client.post("/documents/export", json=export)
        drafted = await client.post(
            "/documents/draft", json=_draft_body(provider_result(), ANNEX_IV)
        )
    assert refused.status_code == 429
    assert "Retry-After" in refused.headers
    assert drafted.status_code == 200, "an export doesn't use up the lookups' limit"


async def test_list_and_draft_share_the_lookup_rate_limit() -> None:
    app = create_app(api_settings(rate_limit_lookups=2))
    app.dependency_overrides[law_quotes] = corpus_quotes
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        body = _body(provider_result())
        assert (await client.post("/documents/list", json=body)).status_code == 200
        draft = _draft_body(provider_result(), ANNEX_IV)
        assert (await client.post("/documents/draft", json=draft)).status_code == 200
        refused = await client.post("/documents/list", json=body)
    assert refused.status_code == 429
    assert "Retry-After" in refused.headers


async def test_an_export_with_every_slot_taken_is_a_503_that_gives_back_its_count() -> None:
    app = create_app(api_settings(rate_limit_exports=1, export_max_concurrent=1))
    app.dependency_overrides[law_quotes] = corpus_quotes
    context: ApiContext = app.state.context
    export = {**_draft_body(provider_result(), ANNEX_IV), "format": "docx"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        assert context.export_slots.try_acquire()
        busy = await client.post("/documents/export", json=export)
        context.export_slots.release()
        after = await client.post("/documents/export", json=export)
    assert (busy.status_code, busy.headers["Retry-After"]) == (503, "5")
    assert busy.json()["detail"] == "Klar is busy making other files. Please try again in a moment."
    assert after.status_code == 200, "the refused export didn't use up the client's one export"


async def test_an_export_gives_its_slot_back_when_its_file_is_made() -> None:
    app = create_app(api_settings(rate_limit_exports=10, export_max_concurrent=1))
    app.dependency_overrides[law_quotes] = corpus_quotes
    export = {**_draft_body(provider_result(), ANNEX_IV), "format": "docx"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        first = await client.post("/documents/export", json=export)
        second = await client.post("/documents/export", json=export)
    assert (first.status_code, second.status_code) == (200, 200)


async def test_an_export_gives_its_slot_back_when_its_render_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_paper: object) -> bytes:
        raise RuntimeError("render failed")

    monkeypatch.setattr("aiact.api.drafts.render_pdf", broken)
    app = create_app(api_settings(rate_limit_exports=10, export_max_concurrent=1))
    app.dependency_overrides[law_quotes] = corpus_quotes
    export = _draft_body(provider_result(), ANNEX_IV)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        failed = await client.post("/documents/export", json={**export, "format": "pdf"})
        after = await client.post("/documents/export", json={**export, "format": "docx"})
    assert (failed.status_code, after.status_code) == (500, 200)
