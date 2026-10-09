"""The reports as files (P25):
- `POST /reports/result`: the report for a lawyer (artboard `ExportPDF`), one result as a two-page
  A4 PDF or a Word file, in English or German;
- `POST /reports/inventory`: the inventory report (artboard `YourData`), every tool with its
  class, status, role and duties.

The posted result is validated against the result contract and nothing more (`valid_result`,
decision 031): it may be a row the browser wrote or an imported file. The report quotes no text
of the Act, so none can be taken from it; its facts and decisions are the user's own run, and
its notice is the report language's own. A result with no class (needs a description, E13) has
nothing to report: a 422. The inventory report takes each tool as the summary its stored result
gives (`InventoryTool`), since a whole inventory of results would not fit the body cap.

A report is a file like a drafted document's export, made the same way (`aiact.api.files`): the
exports' rate limit, the length cap, one of the export workers, the time limit. The routes are
plain `def`, waiting in FastAPI's threadpool for the worker's file. Nothing here logs the result,
a fact, a tool's name or the company, and no error quotes them.
"""

from datetime import date
from typing import Annotated, Any, ClassVar

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import Field, StringConstraints

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
from aiact.report import InventoryTool, inventory_report, report_id, result_report
from aiact.schemas import Language
from aiact.schemas.base import ContractModel

MAX_NAME_CHARS = 200
"""A tool's name and the company's, as the database caps them (`systems.name`,
`inventories.company_name`)."""

INVENTORY_MAX_LINES = 6_000
"""The inventory report's line cap: its tables count each cell as a line, and a hundred tools
of a dozen duties each come to about 4,300 (the drafted documents keep `MAX_FILE_LINES`)."""

RENDERERS: dict[ExportFormat, Renderer] = {"docx": render_docx, "pdf": render_pdf}

NO_CLASS = "This result has no class yet, so there is no report to make. Describe the tool first."
TOO_LONG = "This report is too long to make into a file."
TIMED_OUT = "Making this report took too long. Please try again."

Name = Annotated[str, StringConstraints(min_length=1, max_length=MAX_NAME_CHARS)]


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
    result = valid_result(body.result)
    if result.risk_class is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NO_CLASS)
    paper = result_report(
        result,
        language=body.language,
        prepared_on=prepared_on,
        tool_name=body.tool_name,
        company=body.company,
    )
    stem = f"klar-report-{report_id(result).lower()}"  # [a-z0-9-] only
    refuse_too_long(paper, TOO_LONG)
    return _file(request, context, paper, body.format, stem)


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
    refuse_too_long(paper, TOO_LONG, max_lines=INVENTORY_MAX_LINES)
    return _file(request, context, paper, body.format, "klar-inventory-report")


def _file(
    request: Request, context: ApiContext, paper: Paper, file_format: ExportFormat, stem: str
) -> Response:
    """The paper as a file, made in an export worker within the time limit."""
    with export_worker(request, context) as worker:
        content = rendered(worker, RENDERERS[file_format], paper, TIMED_OUT)
    return attachment(content, file_format, stem)
