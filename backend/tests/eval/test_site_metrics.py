"""The site's accuracy figures (P27): the committed `frontend/src/content/accuracy.json` against
`eval/reports/final.md`, figure by figure and run id by run id (decision 024 addendum), and the
head-to-head scoring and the command's errors without a database. The DB-backed tests are in
`tests/db/test_site_metrics.py`."""

import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import records
from aiact.eval.cases import EVAL_DIR
from aiact.eval.head_to_head_report import EngineColumn
from aiact.eval.report import RunInfo
from aiact.eval.site_metrics import (
    REPORT_PATH,
    SITE_FILE,
    HeadToHead,
    SiteFigure,
    SiteMetrics,
    SiteMetricsError,
    head_to_head_figures,
)
from aiact.schemas import RiskClass
from tests.eval.test_head_to_head_report import DRAW, DRAWN, FILLED, sheet, write_sheet_files

FINAL_REPORT = EVAL_DIR.parent / REPORT_PATH
HEADLINE_ROWS = {
    "risk_class_accuracy": "Risk-class accuracy, Commission Pile B held out",
    "false_low_risk_rate": "False-low-risk rate, Commission Pile B",
    "citations_exist": "Citations that exist (at run time), Commission Pile B",
}
UUID_TEXT = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _published() -> SiteMetrics:
    return SiteMetrics.model_validate_json(SITE_FILE.read_text(encoding="utf-8"))


def _final() -> str:
    return FINAL_REPORT.read_text(encoding="utf-8")


def _headline() -> tuple[str, str]:
    """The final report's "Headline figures" section: its table, and the text below it."""
    section = _final().split("## Headline figures", 1)[1].split("\n## ", 1)[0]
    table = "\n".join(line for line in section.splitlines() if line.startswith("| "))
    prose = " ".join(line for line in section.splitlines() if not line.startswith("| "))
    return table, re.sub(r"\s+", " ", prose)


def _rows(table: str) -> dict[str, list[str]]:
    return {
        cells[0]: cells[1:]
        for line in table.splitlines()
        if (cells := [cell.strip() for cell in line.strip("|").split("|")])
    }


def _published_column(rows: dict[str, list[str]], run_id: UUID) -> int:
    """The headline column whose accuracy cell names the published run."""
    cells = rows[HEADLINE_ROWS["risk_class_accuracy"]]
    columns = [n for n, cell in enumerate(cells) if f"`{run_id}`" in cell]
    assert len(columns) == 1, f"run {run_id} is in {len(columns)} headline columns"
    return columns[0]


def _percent(cell: str) -> str:
    match = re.match(r"(\d+\.\d)%", cell)
    assert match is not None, cell
    return match.group(1)


def _page_percent(value: float) -> str:
    """The figure as the pages show it (one decimal place), in the report's format."""
    return f"{value * 100:.1f}"


# --- the committed file against the final report (the DoD test) --------------------------------


def test_each_commission_figure_equals_the_final_report_for_its_run() -> None:
    published = _published()
    rows = _rows(_headline()[0])
    column = _published_column(rows, published.risk_class_accuracy.run_id)
    for field, row in HEADLINE_ROWS.items():
        figure: SiteFigure = getattr(published, field)
        assert figure.run_id == published.risk_class_accuracy.run_id
        assert _page_percent(figure.value) == _percent(rows[row][column]), field


def test_the_head_to_head_equals_the_final_report() -> None:
    head_to_head = _published().head_to_head
    prose = _headline()[1]
    run = re.search(rf"re-rendered from run `({UUID_TEXT})`", prose)
    scores = re.search(
        r"Commission checker (\d+\.\d)% \(\d+/(\d+)\), engine (\d+\.\d)% \(\d+/(\d+)\) "
        r"risk-class accuracy over the same (\d+) drawn cases",
        prose,
    )
    assert run is not None and scores is not None
    checker, checker_cases, engine, engine_cases, drawn = scores.groups()
    assert head_to_head.klar.run_id == head_to_head.checker.run_id == UUID(run.group(1))
    assert _page_percent(head_to_head.klar.value) == engine
    assert _page_percent(head_to_head.checker.value) == checker
    assert head_to_head.cases == int(drawn) == int(checker_cases) == int(engine_cases)
    assert "AI Act Service Desk" in prose


def test_the_run_date_and_case_count_are_the_published_runs() -> None:
    published = _published()
    run_id = published.risk_class_accuracy.run_id
    date = re.search(r"Run date: (\d{4}-\d{2}-\d{2})", _headline()[1])
    assert date is not None and published.run_date.isoformat() == date.group(1)
    run_report = _final().split(f"#### Run {run_id}\n", 1)[1].split("\n#### ", 1)[0]
    cases = re.search(r"^- Cases: (\d+) ", run_report, re.MULTILINE)
    assert cases is not None and published.cases == int(cases.group(1))


def test_the_file_names_every_run_it_quotes_and_the_report() -> None:
    published = _published()
    quoted = (published.risk_class_accuracy.run_id, published.head_to_head.klar.run_id)
    assert published.run_ids == quoted
    assert all(f"`{run_id}`" in _final() for run_id in quoted)
    assert published.report == "eval/reports/final.md" and FINAL_REPORT.is_file()
    assert published.note


def test_the_file_holds_no_case_id() -> None:
    text = SITE_FILE.read_text(encoding="utf-8")
    assert re.search(r"\b(cb|own|aai|acad)-[a-z0-9]", text) is None


def test_the_site_file_is_next_to_the_frontend_schema() -> None:
    schema = SITE_FILE.parents[1] / "lib" / "accuracy.ts"
    assert EVAL_DIR.parent / "frontend/src/content/accuracy.json" == SITE_FILE
    assert "@/content/accuracy.json" in schema.read_text(encoding="utf-8")


# --- the head-to-head figures --------------------------------------------------------------------

ENGINE_RUN = UUID("00000000-0000-4000-8000-0000000000e1")


def _engine(classes: dict[str, RiskClass | None]) -> EngineColumn:
    info = RunInfo(
        id=ENGINE_RUN,
        benchmark="head_to_head",
        git_sha="a" * 40,
        started_at=datetime(2026, 10, 15, 8, tzinfo=UTC),
        model=None,
    )
    return EngineColumn(run=info, classes=classes)


def test_both_columns_are_scored_over_the_drawn_cases_and_name_the_engine_run() -> None:
    # The engine answers high-risk everywhere and gets the drawn high-risk cases right; the
    # checker answered two cases, one right and one with no class (a miss).
    engine = _engine({case.case_id: RiskClass.HIGH_RISK for case in DRAW.cases})
    high = sum(case.risk_class is RiskClass.HIGH_RISK for case in DRAW.cases)
    figures = head_to_head_figures(engine, FILLED, DRAW, DRAWN)
    assert figures == HeadToHead(
        klar=SiteFigure(value=high / 25, run_id=ENGINE_RUN),
        checker=SiteFigure(value=0.5, run_id=ENGINE_RUN),
        checker_name="EU AI Act Compliance Checker",
        cases=25,
    )


def test_a_checker_column_with_no_answer_is_refused() -> None:
    engine = _engine({case.case_id: RiskClass.HIGH_RISK for case in DRAW.cases})
    with pytest.raises(SiteMetricsError, match="counted no case for its checker column"):
        head_to_head_figures(engine, sheet(), DRAW, DRAWN)


# --- the command without a database --------------------------------------------------------------

SECRET_URL = "postgresql://postgres:hunter2@db.example:5432/postgres"
RUN_ID = "00000000-0000-4000-8000-000000000002"


def test_a_database_error_is_reported_without_the_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def connect() -> object:
        raise psycopg.OperationalError(f"could not connect to {SECRET_URL}")

    monkeypatch.setattr("aiact.eval.head_to_head_report.current_cases", lambda draw: DRAWN)
    monkeypatch.setattr(records, "connect", connect)
    output = tmp_path / "accuracy.json"
    result = CliRunner().invoke(
        app,
        [
            *("evaluate", "site-metrics", *write_sheet_files(tmp_path)[:4]),
            *("--commission-run", RUN_ID, "--head-to-head-run", RUN_ID, "--note", "n"),
            *("--output", str(output)),
        ],
    )
    assert result.exit_code == 1
    assert "Error: database error (OperationalError); check DATABASE_URL" in result.stderr
    assert "hunter2" not in result.output
    assert not output.exists()
