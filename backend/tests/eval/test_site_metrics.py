"""The site's accuracy figures (P27): the committed `frontend/src/content/accuracy.json` against
`eval/reports/final.md`, figure by figure and run id by run id (decision 024 addendum), and the
head-to-head scoring and the command's errors without a database. The DB-backed tests are in
`tests/db/test_site_metrics.py`."""

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import records
from aiact.eval.cases import EVAL_DIR, CaseFileError
from aiact.eval.head_to_head_report import EngineColumn
from aiact.eval.head_to_head_sheet import SheetError
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
from tests.eval.test_head_to_head_report import (
    DRAW,
    DRAWN,
    FILLED,
    HIGH,
    HIGH_HEADING,
    UNSURE_HEADING,
    run,
    sheet,
    write_sheet_files,
)

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


def test_the_run_date_and_n_are_the_published_runs() -> None:
    published = _published()
    date = re.search(r"Run date: (\d{4}-\d{2}-\d{2})", _headline()[1])
    assert date is not None and published.run_date.isoformat() == date.group(1)
    rows = _rows(_headline()[0])
    column = _published_column(rows, published.risk_class_accuracy.run_id)
    # N is the accuracy's denominator: "65.8% (100/152)" gives 152.
    counts = re.search(r"\((\d+)/(\d+)\)", rows[HEADLINE_ROWS["risk_class_accuracy"]][column])
    assert counts is not None and published.scored_cases.count == int(counts.group(2))
    assert published.scored_cases.run_id == published.risk_class_accuracy.run_id


def _run_section(run_id: UUID) -> str:
    """The final report's `aiact evaluate report` output for one run."""
    return _final().split(f"#### Run {run_id}\n", 1)[1].split("\n#### ", 1)[0]


def test_the_own_case_count_is_the_own_runs_in_the_same_full_run() -> None:
    published = _published()
    own = published.own_cases
    section = _run_section(own.run_id)
    assert "- Benchmark: `own`" in section and "- Exclude mode: `heldout`" in section
    cases = re.search(r"^- Cases: (\d+) ", section, re.MULTILINE)
    assert cases is not None and own.count == int(cases.group(1))
    # The per-benchmark table puts the own run in the same full run's column as the Commission one.
    table = _final().split("### Risk-class accuracy, per benchmark", 1)[1].split("\n### ", 1)[0]
    rows = _rows("\n".join(line for line in table.splitlines() if line.startswith("| ")))
    headline = rows["Commission Pile B, held out (headline)"]
    column = next(
        n for n, cell in enumerate(headline) if str(published.risk_class_accuracy.run_id) in cell
    )
    assert f"`{own.run_id}`" in rows["Own cases (development cases)"][column]


def test_the_file_names_every_run_it_quotes_and_the_report() -> None:
    published = _published()
    quoted = (
        published.risk_class_accuracy.run_id,
        published.own_cases.run_id,
        published.head_to_head.klar.run_id,
    )
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


def _engine(classes: Mapping[str, RiskClass | None]) -> EngineColumn:
    info = RunInfo(
        id=ENGINE_RUN,
        benchmark="head_to_head",
        git_sha="a" * 40,
        started_at=datetime(2026, 10, 15, 8, tzinfo=UTC),
        model=None,
    )
    return EngineColumn(run=info, classes=classes)


ALL_HIGH = {case.case_id: RiskClass.HIGH_RISK for case in DRAW.cases}


def test_both_columns_are_scored_over_every_drawn_case_and_name_the_engine_run() -> None:
    # The engine answers high-risk everywhere and gets the drawn high-risk cases right; the
    # checker gets `HIGH` right and can't determine the other 24 (misses).
    answered = sheet(
        run(HIGH, HIGH_HEADING),
        *(run(c.case_id, UNSURE_HEADING) for c in DRAW.cases if c.case_id != HIGH),
    )
    high = sum(case.risk_class is RiskClass.HIGH_RISK for case in DRAW.cases)
    figures = head_to_head_figures(_engine(ALL_HIGH), answered, DRAW, DRAWN)
    assert figures == HeadToHead(
        klar=SiteFigure(value=high / 25, run_id=ENGINE_RUN),
        checker=SiteFigure(value=0.04, run_id=ENGINE_RUN),
        checker_name="EU AI Act Compliance Checker",
        cases=25,
    )


def test_a_checker_column_that_left_drawn_cases_unanswered_is_refused() -> None:
    # FILLED answers 2 of the 25: "the same 25 cases" would not be true.
    with pytest.raises(SiteMetricsError, match="checker column answered 2 of the 25 drawn cases"):
        head_to_head_figures(_engine(ALL_HIGH), FILLED, DRAW, DRAWN)


def test_an_engine_run_that_failed_on_a_drawn_case_is_refused() -> None:
    first = DRAW.cases[0].case_id
    classes = {case_id: risk for case_id, risk in ALL_HIGH.items() if case_id != first}
    engine = EngineColumn(run=_engine(classes).run, classes=classes, failed=1)
    with pytest.raises(SiteMetricsError, match="failed on 1 of the 25 drawn cases"):
        head_to_head_figures(engine, FILLED, DRAW, DRAWN)


def test_a_checker_column_with_no_answer_is_refused() -> None:
    with pytest.raises(SiteMetricsError, match="checker column answered 0 of the 25"):
        head_to_head_figures(_engine(ALL_HIGH), sheet(), DRAW, DRAWN)


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
            *("--own-run", RUN_ID),
            *("--output", str(output)),
        ],
    )
    assert result.exit_code == 1
    assert "Error: database error (OperationalError); check DATABASE_URL" in result.stderr
    assert "hunter2" not in result.output
    assert not output.exists()


def _invoke(tmp_path: Path, *arguments: str) -> tuple[int, str, Path]:
    output = tmp_path / "accuracy.json"
    result = CliRunner().invoke(
        app,
        [
            *("evaluate", "site-metrics", "--commission-run", RUN_ID),
            *("--head-to-head-run", RUN_ID, "--own-run", RUN_ID),
            *("--output", str(output), *arguments),
        ],
    )
    return result.exit_code, result.output, output


def test_a_sheet_error_never_prints_the_case_ids_it_names(tmp_path: Path) -> None:
    # The draw is fine; the sheet names a made-up case and leaves every drawn one out.
    files = write_sheet_files(tmp_path)[:4]
    (tmp_path / "s.yaml").write_text(
        "headings: {}\ncases:\n  - case_id: cb-test-not-drawn\n", encoding="utf-8"
    )
    code, output, path = _invoke(tmp_path, *files, "--note", "n")
    assert code == 1
    assert output.startswith(
        "Error: the draw, the answer sheet (s.yaml) or a case file doesn't fit (SheetError); "
        "run `aiact evaluate head-to-head render`"
    )
    assert "cb-test" not in output
    assert not any(case.case_id in output for case in DRAW.cases)
    assert not path.exists()


def test_a_case_file_error_never_prints_its_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def current_cases(draw: object) -> object:
        raise CaseFileError("cb-test-secret: bad label")

    monkeypatch.setattr("aiact.eval.head_to_head_report.current_cases", current_cases)
    files = write_sheet_files(tmp_path)[:4]
    code, output, path = _invoke(tmp_path, *files, "--note", "n")
    assert code == 1
    assert "(CaseFileError)" in output and "cb-test" not in output
    assert not path.exists()


@pytest.mark.parametrize(
    "note", ["from cb-12 on", "own-3 was", "aai-x", "see acad-7", "CB-Test-1", "Own-2"]
)
def test_a_note_naming_a_case_id_is_refused(tmp_path: Path, note: str) -> None:
    code, output, path = _invoke(tmp_path, *write_sheet_files(tmp_path)[:4], "--note", note)
    assert code == 1
    assert output == "Error: --note names a case id; the site file is public\n"
    assert not path.exists()


@pytest.mark.parametrize(
    "url",
    ["http://example.org/final.md", "javascript:alert(1)", "eval/reports/other.md", "https://"],
)
def test_a_report_url_that_is_neither_https_nor_the_reports_path_is_refused(
    tmp_path: Path, url: str
) -> None:
    files = write_sheet_files(tmp_path)[:4]
    code, output, path = _invoke(tmp_path, *files, "--note", "n", "--report-url", url)
    assert code == 1
    assert output == "Error: --report-url must be an https URL or eval/reports/final.md\n"
    assert not path.exists()


def test_the_count_of_drawn_cases_gone_from_the_case_files_is_printed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # current_cases' own error counts the missing cases and names none (V11), so it is shown.
    def current_cases(draw: object) -> object:
        raise SheetError("24 drawn cases are no longer in eval/cases")

    monkeypatch.setattr("aiact.eval.head_to_head_report.current_cases", current_cases)
    files = write_sheet_files(tmp_path)[:4]
    code, output, path = _invoke(tmp_path, *files, "--note", "n")
    assert code == 1
    assert output == "Error: 24 drawn cases are no longer in eval/cases\n"
    assert not path.exists()
