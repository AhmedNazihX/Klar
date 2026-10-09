"""`POST /reports/result` and `/reports/inventory` (P25): the report for a lawyer made from a
posted result, validated against the contract, and the inventory report, as PDF and Word files
made in the export workers."""

import logging
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from aiact.api import create_app
from aiact.api.dependencies import ApiContext
from aiact.api.reports import (
    INVENTORY_MAX_CHARS,
    INVENTORY_MAX_LINES,
    RENDERERS,
    InventoryReportRequest,
    report_date,
)
from aiact.export.pool import RenderTimeout, RenderWorker
from aiact.report import MAX_NAME_CHARS
from aiact.schemas import DISCLAIMER_EN, ClassificationResult, EvidenceTag, Fact
from tests.api.conftest import BASE_URL, api_settings
from tests.drafting.builders import limited_risk_result
from tests.export.reading import pdf_pages, read_docx
from tests.schemas.builders import needs_description
from tests.schemas.worked_example import worked_example_result

pytestmark = pytest.mark.anyio

PREPARED_ON = date(2026, 10, 1)
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SECRET = "Confidential: the Hamburg pilot of Project Falcon"
"""A name the logs and errors must never show."""


@pytest.fixture(autouse=True)
def fixed_date(app: FastAPI) -> Iterator[None]:
    app.dependency_overrides[report_date] = lambda: PREPARED_ON
    yield


@pytest.fixture
def report_app() -> Iterator[Callable[..., FastAPI]]:
    """Apps with their own limits; their export workers are stopped after the test."""
    apps: list[FastAPI] = []

    def build(**changes: object) -> FastAPI:
        app = create_app(api_settings(**changes))
        app.dependency_overrides[report_date] = lambda: PREPARED_ON
        apps.append(app)
        return app

    yield build
    for app in apps:
        app.state.context.export_slots.close()


def _body(result: ClassificationResult | None = None, **fields: Any) -> dict[str, Any]:
    dumped = (result or worked_example_result()).model_dump(mode="json")
    return {"result": dumped, "language": "en", "format": "pdf", **fields}


def _tool(**fields: Any) -> dict[str, Any]:
    return {
        "name": "Applicant screening",
        "risk_class": "high_risk",
        "status": "decided",
        "role": "deployer",
        "law_version": "amended",
        "as_of": "2026-09-27",
        "duties": [{"label": "Keep the logs", "article": "art:26:6", "applies_from": "2027-12-02"}],
        **fields,
    }


async def test_the_worked_example_is_a_two_page_pdf_of_the_posted_results_class(
    client: httpx.AsyncClient,
) -> None:
    body = _body(tool_name="Applicant screening", company="Nordwerk Logistik GmbH")
    response = await client.post("/reports/result", json=body)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    # A constant name: the browser saves it under its own (`resultReportFileName`).
    assert response.headers["content-disposition"] == 'attachment; filename="klar-report.pdf"'
    first, second = pdf_pages(response.content)
    assert "Nordwerk Logistik GmbH. Prepared on 1 October 2026." in first
    assert "Class Status Role Duties apply from High-risk Decided Deployer" in first
    for page in (first, second):
        assert DISCLAIMER_EN in page


async def test_the_class_follows_the_posted_result(client: httpx.AsyncClient) -> None:
    response = await client.post("/reports/result", json=_body(limited_risk_result("art:50:1")))
    assert response.status_code == 200
    assert "Duties apply from Limited risk Decided" in pdf_pages(response.content)[0]


async def test_a_german_word_report(client: httpx.AsyncClient) -> None:
    response = await client.post("/reports/result", json=_body(language="de", format="docx"))
    assert response.status_code == 200
    assert response.headers["content-type"] == DOCX
    word = read_docx(response.content)
    assert "Pflichten des Betreibers, ab dem 2. Dezember 2027" in word.paragraphs
    assert word.language == "de"


async def test_a_result_with_no_class_is_a_422(client: httpx.AsyncClient) -> None:
    response = await client.post("/reports/result", json=_body(needs_description()))
    assert response.status_code == 422
    assert response.json() == {
        "detail": "This result has no class yet, so there is no report to make. "
        "Describe the tool first."
    }


async def test_a_result_that_breaks_the_contract_is_refused_without_echoing_it(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    forged = {**_body()["result"], "risk_class": "prohibited", "role": SECRET}
    with caplog.at_level(logging.DEBUG):
        response = await client.post(
            "/reports/result", json=_body(result=None) | {"result": forged}
        )
    assert response.status_code == 422
    assert response.json() == {"detail": "The result is not a valid classification result."}
    assert SECRET not in caplog.text


async def test_names_are_capped(client: httpx.AsyncClient) -> None:
    long = await client.post("/reports/result", json=_body(tool_name="x" * 201))
    fits = await client.post("/reports/result", json=_body(tool_name="x" * 200))
    assert (long.status_code, fits.status_code) == (422, 200)


async def test_a_name_never_reaches_the_logs(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        response = await client.post(
            "/reports/result", json=_body(tool_name=SECRET, company=SECRET)
        )
    assert response.status_code == 200
    assert SECRET not in caplog.text


async def test_the_inventory_report(client: httpx.AsyncClient) -> None:
    body = {
        "tools": [_tool(), _tool(name=None, risk_class=None, status=None, role=None, duties=[])],
        "language": "en",
        "format": "pdf",
        "company": "Nordwerk Logistik GmbH",
    }
    response = await client.post("/reports/inventory", json=body)
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="klar-inventory-report.pdf"'
    )
    text = " ".join(pdf_pages(response.content))
    assert "Applicant screening High-risk Decided Deployer 2 December 2027" in text
    assert "Your tool Not classified yet" in text
    # The table's label for the duty, not the posted one.
    assert "Keep the logs it creates for at least six months Art. 26(6) 2 December 2027" in text


async def test_the_inventory_reports_caps(client: httpx.AsyncClient) -> None:
    body: dict[str, Any] = {"language": "en", "format": "docx"}
    too_many = await client.post("/reports/inventory", json={**body, "tools": [_tool()] * 101})
    bad_article = await client.post(
        "/reports/inventory",
        json={
            **body,
            "tools": [
                _tool(duties=[{"label": "x", "article": "26", "applies_from": "2027-12-02"}])
            ],
        },
    )
    too_many_duties = await client.post(
        "/reports/inventory",
        json={**body, "tools": [_tool(duties=_tool()["duties"] * 101)]},
    )
    assert (too_many.status_code, bad_article.status_code, too_many_duties.status_code) == (
        422,
        422,
        422,
    )


@pytest.mark.parametrize(("length", "status_code"), [(1_000, 200), (1_001, 422)])
async def test_a_duty_label_is_capped_at_1000_characters(
    client: httpx.AsyncClient, length: int, status_code: int
) -> None:
    duty = {"label": "x" * length, "article": "art:26:6", "applies_from": "2027-12-02"}
    body = {"tools": [_tool(duties=[duty])], "language": "en", "format": "docx"}
    assert (await client.post("/reports/inventory", json=body)).status_code == status_code


def test_the_report_caps_are_pinned() -> None:
    assert (
        InventoryReportRequest.MAX_TOOLS,
        INVENTORY_MAX_LINES,
        INVENTORY_MAX_CHARS,
        MAX_NAME_CHARS,
    ) == (100, 6_000, 200_000, 200)


async def test_a_hundred_tools_of_a_dozen_duties_each_fit(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(RenderWorker, "run", lambda _worker, _fn, _paper: b"%PDF")
    duty = {
        "label": "Keep the logs it creates for at least six months",
        "article": "art:26:6",
        "applies_from": "2027-12-02",
    }
    tools = [_tool(name=f"Tool {number}", duties=[duty] * 12) for number in range(100)]
    body = {"tools": tools, "language": "de", "format": "pdf"}
    assert (await client.post("/reports/inventory", json=body)).status_code == 200


async def test_a_report_too_long_for_a_file_is_a_413_before_rendering(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    rendered: list[object] = []
    monkeypatch.setattr(
        RenderWorker, "run", lambda _worker, _fn, paper: rendered.append(paper) or b"%"
    )
    # A duty the table lacks keeps its posted label.
    duties = [{"label": "x" * 1_000, "article": "art:99:1", "applies_from": "2027-12-02"}] * 100
    body = {"tools": [_tool(duties=duties)] * 2, "language": "en", "format": "pdf"}
    response = await client.post("/reports/inventory", json=body)
    assert response.status_code == 413
    assert response.json() == {"detail": "This report is too long to make into a file."}
    assert rendered == []


async def test_reports_share_the_exports_rate_limit(report_app: Callable[..., FastAPI]) -> None:
    app = report_app(rate_limit_exports=1)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        first = await client.post("/reports/result", json=_body(format="docx"))
        second = await client.post(
            "/reports/inventory", json={"tools": [], "language": "en", "format": "docx"}
        )
    assert (first.status_code, second.status_code) == (200, 429)


async def test_a_report_with_every_slot_taken_is_a_503_that_gives_back_its_count(
    report_app: Callable[..., FastAPI],
) -> None:
    app = report_app(rate_limit_exports=1, export_max_concurrent=1)
    context: ApiContext = app.state.context
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        taken = context.export_slots.try_acquire()
        assert taken is not None
        busy = await client.post("/reports/result", json=_body(format="docx"))
        context.export_slots.release(taken)
        after = await client.post("/reports/result", json=_body(format="docx"))
    assert (busy.status_code, busy.headers["Retry-After"]) == (503, "5")
    assert after.status_code == 200


async def test_a_report_past_its_time_limit_is_a_504(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timed_out(_worker: RenderWorker, *_args: object) -> bytes:
        raise RenderTimeout

    monkeypatch.setattr(RenderWorker, "run", timed_out)
    response = await client.post("/reports/result", json=_body())
    assert (response.status_code, response.json()) == (
        504,
        {"detail": "Making this report took too long. Please try again."},
    )


@pytest.mark.parametrize("point", ["annex:III", "x", "annex:I:", "annex:III:99:z"])
async def test_an_annex_point_the_report_cant_name_still_makes_a_report(
    client: httpx.AsyncClient, point: str
) -> None:
    result = worked_example_result().model_copy(update={"annex_point": point})
    response = await client.post("/reports/result", json=_body(result))
    assert response.status_code == 200


async def test_a_cell_taller_than_a_page_is_a_413_before_any_worker_is_taken(
    report_app: Callable[..., FastAPI],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """fpdf2 can't break a table cell across pages: such a paper is refused before rendering,
    even with every export slot taken (a 413, not a 503), and no worker runs."""
    runs: list[object] = []
    monkeypatch.setattr(RenderWorker, "run", lambda _worker, *args: runs.append(args) or b"%")
    app = report_app(export_max_concurrent=1)
    context: ApiContext = app.state.context
    tall = Fact(text=f"{SECRET}\n" * 60 + SECRET, evidence=EvidenceTag.ASSUMED)
    worked = worked_example_result()
    result = worked.model_copy(update={"deciding_facts": (tall, *worked.deciding_facts)})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        taken = context.export_slots.try_acquire()
        assert taken is not None
        with caplog.at_level(logging.DEBUG):
            refused = await client.post("/reports/result", json=_body(result))
        context.export_slots.release(taken)
    assert (refused.status_code, refused.json()) == (
        413,
        {"detail": "This report is too long to make into a file."},
    )
    assert runs == []
    assert SECRET not in caplog.text


async def test_a_render_that_fails_is_a_413_that_keeps_its_count(
    report_app: Callable[..., FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed render took a worker and its time: the count stays, so it can't be repeated
    for free."""
    monkeypatch.setitem(RENDERERS, "pdf", int)  # int(paper) raises in the worker process
    app = report_app(rate_limit_exports=1)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        failed = await client.post("/reports/result", json=_body())
        after = await client.post("/reports/result", json=_body(format="docx"))
    assert (failed.status_code, failed.json()) == (
        413,
        {"detail": "This report is too long to make into a file."},
    )
    assert after.status_code == 429


def test_the_report_date_is_today() -> None:
    assert report_date() == date.today()
