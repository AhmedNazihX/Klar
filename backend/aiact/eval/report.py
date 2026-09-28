"""The run report: one stored run's deterministic metrics as a markdown table (INIT > Metrics).

Reports quote numbers only from stored runs, so everything here is read from `eval_runs` and
`eval_case_results` by run id. Each case row is expected to hold:
- `label`: the `BenchmarkCase` the case was scored against, as `model_dump(mode="json")`;
- `predicted`: the `ClassificationResult` as `model_dump(mode="json")`, or an object with an
  `error` key when the classifier failed.
Citation existence resolves `(provision_id, language)` against the corpus `provisions` table,
which is only read. The report names case counts, never descriptions.
"""

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

import psycopg
from pydantic import ValidationError

from aiact.eval.cases import BenchmarkCase
from aiact.eval.metrics import Outcome, PrecisionRecall, Rate, RunMetrics, summarize
from aiact.schemas.base import ContractModel
from aiact.schemas.evidence import Citation
from aiact.schemas.result import ClassificationResult

FAILED_KEY = "error"
"""A `predicted` object with this key records a failed classifier call."""


class RunNotFoundError(LookupError):
    """No `eval_runs` row has the requested id."""


class RunRecordError(ValueError):
    """A stored case row doesn't hold what the report expects; the message names the case."""


class RunInfo(ContractModel):
    """The run facts printed above the table."""

    id: UUID
    benchmark: str
    git_sha: str
    started_at: datetime
    model: str | None


def load_run_info(conn: psycopg.Connection, run_id: UUID) -> RunInfo:
    row = conn.execute(
        "select id, benchmark, git_sha, started_at, config ->> 'model' "
        "from eval_runs where id = %s",
        (run_id,),
    ).fetchone()
    if row is None:
        raise RunNotFoundError(f"no eval run with id {run_id}")
    run_id_value, benchmark, git_sha, started_at, model = row
    return RunInfo(
        id=run_id_value, benchmark=benchmark, git_sha=git_sha, started_at=started_at, model=model
    )


def load_outcomes(conn: psycopg.Connection, run_id: UUID) -> tuple[Outcome, ...]:
    rows = conn.execute(
        "select case_id, label, predicted from eval_case_results "
        "where run_id = %s order by case_id",
        (run_id,),
    ).fetchall()
    return tuple(_outcome(case_id, label, predicted) for case_id, label, predicted in rows)


def _outcome(case_id: str, label: object, predicted: object) -> Outcome:
    try:
        case = BenchmarkCase.model_validate(label)
        is_failed = isinstance(predicted, Mapping) and FAILED_KEY in predicted
        result = None if is_failed else ClassificationResult.model_validate(predicted)
    except ValidationError as exc:
        raise RunRecordError(
            f"case {case_id}: stored label or prediction is invalid: {exc}"
        ) from exc
    if case.id != case_id:
        raise RunRecordError(f"case {case_id}: stored label belongs to case {case.id}")
    return Outcome(case=case, result=result)


def load_citation_index(conn: psycopg.Connection) -> frozenset[tuple[str, str]]:
    """Every `(provision_id, language)` in the corpus."""
    rows = conn.execute("select distinct provision_id, language from provisions").fetchall()
    return frozenset((provision_id, language) for provision_id, language in rows)


def run_report(conn: psycopg.Connection, run_id: UUID) -> str:
    """The markdown report for one stored run."""
    info = load_run_info(conn, run_id)
    index = load_citation_index(conn)

    def exists(citation: Citation) -> bool:
        return (citation.provision_id, citation.language.value) in index

    return render_markdown(info, summarize(load_outcomes(conn, run_id), exists))


def render_markdown(info: RunInfo, metrics: RunMetrics) -> str:
    header = [
        f"## Run {info.id}",
        "",
        f"- Benchmark: `{info.benchmark}`",
        f"- Commit: `{info.git_sha}`",
        f"- Started: {info.started_at.isoformat()}",
        f"- Model: {info.model or 'n/a'}",
        f"- Cases: {metrics.cases} ({metrics.failed} failed)",
        "",
        "| Metric | Value | Count |",
        "| --- | ---: | ---: |",
    ]
    return "\n".join([*header, *(_row(name, value) for name, value in _rows(metrics))]) + "\n"


def _rows(metrics: RunMetrics) -> list[tuple[str, Rate | int]]:
    return [
        ("Risk-class accuracy", metrics.risk_class_accuracy),
        ("False-low-risk rate", metrics.false_low_risk),
        ("Annex point accuracy", metrics.annex_point_accuracy),
        ("Role accuracy", metrics.role_accuracy),
        *_precision_recall("Legally ambiguous", metrics.ambiguous),
        ("Ambiguous answered needs-more-information", metrics.needs_info_on_ambiguous),
        *_precision_recall("Needs more information", metrics.needs_more_information),
        ("Downgrade rate (soft wording)", metrics.downgrade),
        ("Consistency", metrics.consistency),
        ("Citation existence", metrics.citation_existence),
        ("appliedAI disagreement review", metrics.appliedai_disagreement_review),
    ]


def _precision_recall(name: str, scores: PrecisionRecall) -> list[tuple[str, Rate]]:
    return [(f"{name}: precision", scores.precision), (f"{name}: recall", scores.recall)]


def _row(name: str, value: Rate | int) -> str:
    if isinstance(value, int):
        return f"| {name} | {value} | |"
    shown = "n/a" if value.value is None else f"{value.value:.1%}"
    return f"| {name} | {shown} | {value.hits}/{value.total} |"
