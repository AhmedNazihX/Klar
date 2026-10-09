"""The reports as files (P25):
- `POST /reports/result`: the report for a lawyer (artboard `ExportPDF`), one result as a two-page
  A4 PDF or a Word file, in English or German;
- `POST /reports/inventory`: the inventory report (artboard `YourData`), every tool with its
  class, status, role and duties;
- `POST /reports/checklist`: the obligations checklist (P24; artboard `Obligations`), every duty of
  every tool with its date and whether the user ticked it off.

The posted result is validated against the result contract and nothing more (`valid_result`,
decision 031): it may be a row the browser wrote or an imported file. Its facts and the steps'
outcomes are the user's own run, written in the report's own sentences; the duties' formal
wording, conditions and labels come from the obligations table, looked up by the result's class,
role, article and law version, never from the posted result (`aiact.report.duties`), and the
notice is the report language's own. A result with no class (needs a description, E13) has
nothing to report: a 422. The inventory report takes each tool as the summary its stored result
gives (`InventoryTool`), since a whole inventory of results would not fit the body cap; the
checklist takes the same summary with each duty's ticked state (`ChecklistTool`).

A report is a file like a drafted document's export, made the same way (`aiact.api.files`): the
exports' rate limit, the length cap, one of the export workers, the time limit, and a 413 when the
renderer finds a table row taller than a page. The routes are plain `def`, waiting in FastAPI's
threadpool for the worker's file. Nothing here logs the result, a fact, a tool's name or the
company, and no error quotes them.
"""

from datetime import date
from typing import Annotated, Any, ClassVar

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import Field

from aiact.api.dependencies import ApiContext, api_context, limit_exports
from aiact.api.documents import ResultJson, valid_result
from aiact.api.errors import UNPROCESSABLE
from aiact.api.files import (
    FILE_ERRORS,
    FILE_RESPONSE,
    ExportFormat,
    Renderer,
    attachment,
    export_worker,
    refuse_too_long,
    rendered,
)
from aiact.export import Paper, render_docx, render_pdf
from aiact.report import (
    ChecklistTool,
    InventoryTool,
    Name,
    NoClassError,
    checklist_report,
    inventory_report,
    result_report,
)
from aiact.schemas import Language
from aiact.schemas.base import ContractModel

INVENTORY_MAX_LINES = 6_000
"""The inventory report's line cap: its tables count each cell as a line, and a hundred tools
of a dozen duties each come to about 4,600 (the drafted documents keep `MAX_FILE_LINES`)."""
INVENTORY_MAX_CHARS = 200_000
"""The inventory report's character cap: a hundred tools of a dozen duties each, with the
table's German labels, come to about 135,000 and render in about two seconds (the drafted
documents keep `MAX_FILE_CHARS`)."""

RENDERERS: dict[ExportFormat, Renderer] = {"docx": render_docx, "pdf": render_pdf}

RESULT_STEM = "klar-report"
"""The report's file name; the browser saves it under its own name for the tool
(`resultReportFileName`), so the server's is only a fallback."""
INVENTORY_STEM = "klar-inventory-report"
CHECKLIST_STEM = "klar-obligations-checklist"

NO_CLASS = "This result has no class yet, so there is no report to make. Describe the tool first."
TOO_LONG = "This report is too long to make into a file."
TIMED_OUT = "Making this report took too long. Please try again."


class ResultReportRequest(ContractModel):
    """One tool's result, and the report wanted."""

    result: ResultJson = Field(
        description="The classification result, as `POST /classify` sent it."
    )
    language: Language = Field(description="The language of the report's wording and notice.")
    format: ExportFormat
    tool_name: Name | None = Field(
        default=None, description='The tool\'s name; null when the user gave none ("Your tool").'
    )
    company: Name | None = Field(
        default=None, description="The company's name from its profile; null without one."
    )


class InventoryReportRequest(ContractModel):
    """Every tool of the user's inventory, summarised, and the report wanted."""

    MAX_TOOLS: ClassVar[int] = 100
    """Far above an SME's inventory; a hundred tools of a dozen duties each fit the file caps
    and render in about a second and a half."""

    tools: tuple[InventoryTool, ...] = Field(max_length=MAX_TOOLS)
    language: Language = Field(description="The language of the report's wording and notice.")
    format: ExportFormat
    company: Name | None = Field(
        default=None, description="The company's name from its profile; null without one."
    )


class ChecklistRequest(ContractModel):
    """Every tool of the user's inventory, summarised with each duty's ticked state, and the
    checklist wanted."""

    tools: tuple[ChecklistTool, ...] = Field(max_length=InventoryReportRequest.MAX_TOOLS)
    language: Language = Field(description="The language of the checklist's wording and notice.")
    format: ExportFormat
    company: Name | None = Field(
        default=None, description="The company's name from its profile; null without one."
    )


def report_date() -> date:
    """The date a report is prepared on: today. Tests override this dependency."""
    return date.today()


router = APIRouter(prefix="/reports", responses=UNPROCESSABLE)

REPORT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_200_OK: FILE_RESPONSE,
    **FILE_ERRORS,
}


@router.post(
    "/result",
    name="export_result_report",
    response_class=Response,
    dependencies=[Depends(limit_exports)],
    responses=REPORT_RESPONSES,
)
def export_result_report(
    request: Request,
    body: ResultReportRequest,
    prepared_on: Annotated[date, Depends(report_date)],
    context: Annotated[ApiContext, Depends(api_context)],
) -> Response:
    """The report for a lawyer: the result, its facts and their sources, the steps and the
    provisions they cite, the duties, the points for legal review and a box for the reviewer to
    sign, as a PDF or Word file. Guidance, not legal advice."""
    try:
        paper = result_report(
            valid_result(body.result),
            language=body.language,
            prepared_on=prepared_on,
            tool_name=body.tool_name,
            company=body.company,
        )
    except NoClassError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NO_CLASS) from None
    refuse_too_long(paper, TOO_LONG)
    return _file(request, context, paper, body.format, RESULT_STEM)


@router.post(
    "/inventory",
    name="export_inventory_report",
    response_class=Response,
    dependencies=[Depends(limit_exports)],
    responses=REPORT_RESPONSES,
)
def export_inventory_report(
    request: Request,
    body: InventoryReportRequest,
    prepared_on: Annotated[date, Depends(report_date)],
    context: Annotated[ApiContext, Depends(api_context)],
) -> Response:
    """The inventory report: every tool with its class, status, role and first duty date, then
    each tool's duties, as a PDF or Word file. Guidance, not legal advice."""
    paper = inventory_report(
        body.tools, language=body.language, prepared_on=prepared_on, company=body.company
    )
    refuse_too_long(paper, TOO_LONG, max_chars=INVENTORY_MAX_CHARS, max_lines=INVENTORY_MAX_LINES)
    return _file(request, context, paper, body.format, INVENTORY_STEM)


@router.post(
    "/checklist",
    name="export_obligations_checklist",
    response_class=Response,
    dependencies=[Depends(limit_exports)],
    responses=REPORT_RESPONSES,
)
def export_obligations_checklist(
    request: Request,
    body: ChecklistRequest,
    prepared_on: Annotated[date, Depends(report_date)],
    context: Annotated[ApiContext, Depends(api_context)],
) -> Response:
    """The obligations checklist: every classified tool with its progress, then each duty with
    whether it is done, its provision and its date, as a PDF or Word file. Klar keeps the list;
    it doesn't check the work. Guidance, not legal advice."""
    paper = checklist_report(
        body.tools, language=body.language, prepared_on=prepared_on, company=body.company
    )
    # The inventory report's caps: a checklist row has one cell more, and still fits them.
    refuse_too_long(paper, TOO_LONG, max_chars=INVENTORY_MAX_CHARS, max_lines=INVENTORY_MAX_LINES)
    return _file(request, context, paper, body.format, CHECKLIST_STEM)


def _file(
    request: Request, context: ApiContext, paper: Paper, file_format: ExportFormat, stem: str
) -> Response:
    """The paper as a file, made in an export worker within the time limit."""
    with export_worker(request, context, TOO_LONG) as worker:
        content = rendered(worker, RENDERERS[file_format], paper, TIMED_OUT)
    return attachment(content, file_format, stem)
