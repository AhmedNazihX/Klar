"""The run report: one stored run's deterministic metrics as a markdown table (INIT > Metrics).

Reports quote numbers only from stored runs, so everything here is read from `eval_runs` and
`eval_case_results` by run id. Each case row holds (V1's runner writes it so):
- `label`: the `BenchmarkCase` the case was scored against, as `model_dump(mode="json")`;
- `predicted`: the `ClassificationResult` as `model_dump(mode="json")`, or `{"error": {...}}`
  when the classifier failed.
The metrics are recomputed from those two columns, so the runner's own per-case scores
(`runner.RUN_SCORE_KEYS`: cost, tokens, error flags) never appear in the metric table. A case
marked `scoring_error` is left out of the metrics and listed by id instead.
Citation existence is the exception: it depends on the corpus at run time, so the report uses the
per-case `citation_existence` score `aiact evaluate run` stored and never re-checks against
today's corpus. A run without stored citation scores shows n/a. The report never prints a
description.
"""

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

import psycopg
from pydantic import ValidationError

from aiact.eval.cases import BenchmarkCase
from aiact.eval.metrics import (
    CITATION_EXISTENCE_KEY,
    Outcome,
    PrecisionRecall,
    Rate,
    RunMetrics,
    summarize,
)
from aiact.eval.runner import SCORING_ERROR_KEY
from aiact.schemas.base import ContractModel
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
    cost_usd: float = 0.0
    tokens: int = 0


class StoredCase(ContractModel):
    """One stored case row, parsed."""

    outcome: Outcome
    is_scoring_error: bool = False
    citation_existence: bool | None = None


def load_run_info(conn: psycopg.Connection, run_id: UUID) -> RunInfo:
    row = conn.execute(
        "select id, benchmark, git_sha, started_at, config ->> 'model', cost_usd, tokens "
        "from eval_runs where id = %s",
        (run_id,),
    ).fetchone()
    if row is None:
        raise RunNotFoundError(f"no eval run with id {run_id}")
    run_id_value, benchmark, git_sha, started_at, model, cost_usd, tokens = row
    return RunInfo(
        id=run_id_value,
        benchmark=benchmark,
        git_sha=git_sha,
        started_at=started_at,
        model=model,
        cost_usd=float(cost_usd),
        tokens=tokens,
    )


def load_stored_cases(conn: psycopg.Connection, run_id: UUID) -> tuple[StoredCase, ...]:
    rows = conn.execute(
        "select case_id, label, predicted, scores from eval_case_results "
        "where run_id = %s order by case_id",
        (run_id,),
    ).fetchall()
    return tuple(stored_case(*row) for row in rows)


def stored_case(
    case_id: str, label: object, predicted: object, scores: object = None
) -> StoredCase:
    """Parse one `eval_case_results` row (its `label`, `predicted` and `scores` columns)."""
    try:
        case = BenchmarkCase.model_validate(label)
        is_failed = isinstance(predicted, Mapping) and FAILED_KEY in predicted
        result = None if is_failed else ClassificationResult.model_validate(predicted)
    except ValidationError as exc:
        # Only the failing fields: pydantic's message would quote the stored values, descriptions
        # included.
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise RunRecordError(
            f"case {case_id}: stored label or prediction is invalid at {', '.join(fields)}"
        ) from exc
    if case.id != case_id:
        raise RunRecordError(f"case {case_id}: stored label belongs to case {case.id}")
    stored = scores if isinstance(scores, Mapping) else {}
    citation_score = stored.get(CITATION_EXISTENCE_KEY)
    return StoredCase(
        outcome=Outcome(case=case, result=result),
        is_scoring_error=stored.get(SCORING_ERROR_KEY) is True,
        citation_existence=citation_score if isinstance(citation_score, bool) else None,
    )


def run_report(conn: psycopg.Connection, run_id: UUID) -> str:
    """The markdown report for one stored run."""
    return build_report(load_run_info(conn, run_id), load_stored_cases(conn, run_id))


def build_report(info: RunInfo, cases: tuple[StoredCase, ...]) -> str:
    scored = [case for case in cases if not case.is_scoring_error]
    scoring_errors = [case.outcome.case.id for case in cases if case.is_scoring_error]
    citations = [case.citation_existence for case in scored if case.citation_existence is not None]
    metrics = summarize([case.outcome for case in scored], None).model_copy(
        update={"citation_existence": Rate(hits=sum(citations), total=len(citations))}
    )
    return render_markdown(info, metrics, scoring_errors)


def render_markdown(
    info: RunInfo, metrics: RunMetrics, scoring_errors: list[str] | None = None
) -> str:
    header = [
        f"## Run {info.id}",
        "",
        f"- Benchmark: `{info.benchmark}`",
        f"- Commit: `{info.git_sha}`",
        f"- Started: {info.started_at.isoformat()}",
        f"- Model: {info.model or 'n/a'}",
        f"- Cost: ${info.cost_usd:.4f}, {info.tokens} tokens",
        f"- Cases: {metrics.cases} ({metrics.failed} failed)",
        "",
        "| Metric | Value | Count |",
        "| --- | ---: | ---: |",
    ]
    lines = [*header, *(_row(name, value) for name, value in _rows(metrics))]
    if scoring_errors:
        lines += ["", f"Scoring failed, left out of the metrics: {', '.join(scoring_errors)}"]
    return "\n".join(lines) + "\n"


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
        ("Basis accuracy (Commission cases)", metrics.basis_accuracy),
        ("Flip variant asked or flagged", metrics.flip_variant_flagged),
        ("Consistency", metrics.consistency),
        ("Citation existence (at run time)", metrics.citation_existence),
        ("appliedAI disagreement review", metrics.appliedai_disagreement_review),
        ("Academic out-of-scope review", metrics.academic_disagreement_review),
    ]


def _precision_recall(name: str, scores: PrecisionRecall) -> list[tuple[str, Rate]]:
    return [(f"{name}: precision", scores.precision), (f"{name}: recall", scores.recall)]


def _row(name: str, value: Rate | int) -> str:
    if isinstance(value, int):
        return f"| {name} | {value} | |"
    shown = "n/a" if value.value is None else f"{value.value:.1%}"
    return f"| {name} | {shown} | {value.hits}/{value.total} |"
