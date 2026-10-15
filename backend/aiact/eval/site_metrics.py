"""The site's accuracy figures (P27, decision 024 addendum): `SITE_FILE`, which the landing and
Method pages read, written from stored runs only.

The three Commission figures (risk-class accuracy, false-low-risk rate, citations that exist) come
from one stored held-out run of `commission_b`, recomputed by the run report's own readers
(`report.load_stored_cases`, `report.scored_metrics`), so they equal what `aiact evaluate report`
prints for that run. The head-to-head comes from the stored engine run of the draw
(`head_to_head_report.engine_column`) and the checker's answer sheet, scored by
`head_to_head_report.column_scores`, as `aiact evaluate head-to-head render` scores them. Which
runs are published is the caller's choice (the run ids are arguments), so switching runs is a
rerun, never a code change. Every figure names its run id; nothing here calls a model.

The file holds no Pile B case id and no case text: rates, counts, run ids and dates only.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from uuid import UUID

import psycopg
from pydantic import Field

from aiact.eval.cases import EVAL_DIR, BenchmarkCase, CaseSet
from aiact.eval.head_to_head import Draw
from aiact.eval.head_to_head_report import (
    ColumnClasses,
    EngineColumn,
    checker_classes,
    column_scores,
)
from aiact.eval.head_to_head_sheet import HeadToHeadSheet
from aiact.eval.metrics import Rate
from aiact.eval.report import RunInfo, StoredCase, load_run_info, load_stored_cases, scored_metrics
from aiact.eval.runner import ExcludeMode, RunStatus
from aiact.schemas.base import ContractModel

REPO_ROOT = EVAL_DIR.parent
SITE_FILE = REPO_ROOT / "frontend" / "src" / "content" / "accuracy.json"
REPORT_PATH = "eval/reports/final.md"
"""The final evaluation report the figures are checked against, from the repository root."""
CHECKER_NAME = "EU AI Act Compliance Checker"
"""The Commission's own name for its AI Act Service Desk checker (decision 036): a proper name,
shown as is in both page languages."""


class SiteMetricsError(ValueError):
    """A stored run can't give a published figure; the message names the run, never a case."""


class SiteFigure(ContractModel):
    """One published rate, between 0 and 1, with the stored run it comes from."""

    value: float = Field(ge=0, le=1)
    run_id: UUID


class HeadToHead(ContractModel):
    """The engine and the checker on the same drawn cases."""

    klar: SiteFigure
    checker: SiteFigure
    checker_name: str
    cases: int = Field(gt=0)


class SiteMetrics(ContractModel):
    """`SITE_FILE`: the figures in the shape `frontend/src/lib/accuracy.ts` checks, then the facts
    the pages may show beside them (N, the run date, the run ids, the report, the choice made)."""

    risk_class_accuracy: SiteFigure
    false_low_risk_rate: SiteFigure
    citations_exist: SiteFigure
    head_to_head: HeadToHead
    cases: int
    """The held-out Commission cases the published run scored (N), as its report's "Cases"
    line counts them."""
    run_date: date
    """The day the published Commission run started."""
    run_ids: tuple[UUID, ...]
    report: str
    note: str
    """Which runs are published and why, as the caller states it."""


class CommissionFigures(ContractModel):
    """The Commission figures of one stored run, and the cases its report counts."""

    risk_class_accuracy: SiteFigure
    false_low_risk_rate: SiteFigure
    citations_exist: SiteFigure
    cases: int


def commission_figures(info: RunInfo, cases: Sequence[StoredCase]) -> CommissionFigures:
    """Risk-class accuracy, the false-low-risk rate and citations that exist of one stored
    held-out, completed `commission_b` run, and its case count, as its run report computes them
    (a case whose scoring failed is left out, as there)."""
    _check_commission_run(info)
    metrics = scored_metrics([case for case in cases if not case.is_scoring_error])
    return CommissionFigures(
        risk_class_accuracy=_figure(info.id, "risk-class accuracy", metrics.risk_class_accuracy),
        false_low_risk_rate=_figure(info.id, "false-low-risk rate", metrics.false_low_risk),
        citations_exist=_figure(info.id, "citation existence", metrics.citation_existence),
        cases=metrics.cases,
    )


def _check_commission_run(info: RunInfo) -> None:
    if info.benchmark != CaseSet.COMMISSION_B.value:
        raise SiteMetricsError(
            f"run {info.id} is a run of {info.benchmark}, not of {CaseSet.COMMISSION_B.value}"
        )
    if info.status != RunStatus.COMPLETED.value:
        raise SiteMetricsError(
            f"run {info.id} is {info.status or 'without a status'}, not completed"
        )
    if info.exclude_mode != ExcludeMode.HELDOUT.value:
        raise SiteMetricsError(
            f"run {info.id} has exclude mode {info.exclude_mode}, not {ExcludeMode.HELDOUT.value} "
            "(the reported number)"
        )


def _figure(run_id: UUID, name: str, rate: Rate) -> SiteFigure:
    """The rate as a published figure; a rate with nothing counted can't be published."""
    if rate.value is None:
        raise SiteMetricsError(f"run {run_id} counted no case for its {name}")
    return SiteFigure(value=rate.value, run_id=run_id)


def head_to_head_figures(
    engine: EngineColumn, sheet: HeadToHeadSheet, draw: Draw, cases: Mapping[str, BenchmarkCase]
) -> HeadToHead:
    """The engine column (a stored run of the draw) and the checker's, scored over the drawn
    cases as the head-to-head report scores them. Both name the engine run: the checker has no
    stored run, and its column is reported beside that run's."""
    drawn = [cases[case.case_id] for case in draw.cases]
    run_id = engine.run.id
    return HeadToHead(
        klar=_column(run_id, "engine column", drawn, engine.classes),
        checker=_column(run_id, "checker column", drawn, checker_classes(sheet)),
        checker_name=CHECKER_NAME,
        cases=len(drawn),
    )


def _column(
    run_id: UUID, name: str, drawn: Sequence[BenchmarkCase], classes: ColumnClasses
) -> SiteFigure:
    return _figure(run_id, name, column_scores(drawn, classes).risk_class_accuracy)


def site_metrics(
    conn: psycopg.Connection, commission_run: UUID, head_to_head: HeadToHead, note: str
) -> SiteMetrics:
    """The site file's content: the Commission figures of stored run `commission_run`, beside
    the head-to-head figures."""
    info = load_run_info(conn, commission_run)
    commission = commission_figures(info, load_stored_cases(conn, commission_run))
    return SiteMetrics(
        risk_class_accuracy=commission.risk_class_accuracy,
        false_low_risk_rate=commission.false_low_risk_rate,
        citations_exist=commission.citations_exist,
        head_to_head=head_to_head,
        cases=commission.cases,
        run_date=info.started_at.date(),
        run_ids=(info.id, head_to_head.klar.run_id),
        report=REPORT_PATH,
        note=note,
    )


def write_site_file(metrics: SiteMetrics, path: Path = SITE_FILE) -> None:
    path.write_text(metrics.model_dump_json(indent=2) + "\n", encoding="utf-8")
