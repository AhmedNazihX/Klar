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

Above the table go the run's settings from `eval_runs.config` (classifier, models, exclude mode,
status, uncommitted changes, subset, appended answers; T1), each shown only when the run recorded
it, so runs stored before a setting existed still load. Own cases are labelled development cases
(decision 018). A run holding contaminated cases (decision 016) gets a second accuracy row
without them, naming them. Below the table come the provider refusals (`refusals`, from each
row's `scores.models`), the failure cases grouped by step (`failures`), the model-written
texts (`texts`) and the judged metrics (`judged`, V5): the tallies `aiact evaluate judged`
stored in each row's scores, never judged again here. A Q&A run (`aiact evaluate ragas`) gets
its settings and its judged metrics only.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

import psycopg
from pydantic import Field, TypeAdapter, ValidationError

from aiact.eval.cases import BenchmarkCase, CaseSet
from aiact.eval.failures import render_failures
from aiact.eval.isolation import ContaminatedList, load_contaminated
from aiact.eval.judge import JudgeCheck
from aiact.eval.judged import (
    CheckScore,
    JudgedRecordError,
    JudgedSettings,
    parse_settings,
    read_stored,
    render_judged,
    run_totals,
)
from aiact.eval.judged_run import QA_BENCHMARK
from aiact.eval.metrics import (
    CITATION_EXISTENCE_KEY,
    Outcome,
    PrecisionRecall,
    Rate,
    RunMetrics,
    summarize,
)
from aiact.eval.refusals import RefusalCase, render_refusals, summarize_refusals
from aiact.eval.runner import MODELS_KEY, SCORING_ERROR_KEY
from aiact.eval.texts import render_texts
from aiact.schemas.base import ContractModel
from aiact.schemas.result import ClassificationResult

FAILED_KEY = "error"
"""A `predicted` object with this key records a failed classifier call."""
SERVED_MODELS = TypeAdapter(dict[str, dict[str, int]])
DEVELOPMENT_CASES = (
    "development cases: the engine's nodes were developed against them, so Commission Pile B "
    "carries the headline (decision 018)"
)
UNCOMMITTED = " (uncommitted changes: this commit may not reproduce the run)"
EXCLUDE_MODES: Mapping[str, str] = {
    "heldout": " (held-out examples kept out of retrieval: the reported number)",
    "all": " (the gap run: held-out examples retrievable, never the reported number; decision 012)",
}
ANSWERS_FROM = (
    "the stored key-fact answers to the questions run `{run}` asked, any other question "
    'answered "don\'t know" (decision 019)'
)


class RunNotFoundError(LookupError):
    """No `eval_runs` row has the requested id."""


class RunRecordError(ValueError):
    """A stored case row doesn't hold what the report expects; the message names the case."""


class RunInfo(ContractModel):
    """The run facts printed above the table; None where the run didn't record one."""

    id: UUID
    benchmark: str
    git_sha: str
    started_at: datetime
    model: str | None
    cost_usd: float = 0.0
    tokens: int = 0
    classifier: str | None = None
    provider: str | None = None
    second_model: str | None = None
    second_provider: str | None = None
    exclude_mode: str | None = None
    subset: int | None = None
    seed: int | None = None
    status: str | None = None
    is_git_dirty: bool | None = None
    answers_from: str | None = None
    judged: JudgedSettings | None = None
    """The judge the run's results were judged with (`aiact evaluate judged`, V5)."""


class StoredCase(ContractModel):
    """One stored case row, parsed."""

    outcome: Outcome
    is_scoring_error: bool = False
    citation_existence: bool | None = None
    models: dict[str, dict[str, int]] = Field(default_factory=dict)
    """Each node's calls by the model that served them (`runner.MODELS_KEY`); empty when the
    classifier didn't report them."""
    judged: dict[JudgeCheck, CheckScore] = Field(default_factory=dict)
    """The judged tallies (V5); empty when the case wasn't judged."""


def load_run_info(conn: psycopg.Connection, run_id: UUID) -> RunInfo:
    row = conn.execute(
        "select id, benchmark, git_sha, started_at, config, cost_usd, tokens "
        "from eval_runs where id = %s",
        (run_id,),
    ).fetchone()
    if row is None:
        raise RunNotFoundError(f"no eval run with id {run_id}")
    run_id_value, benchmark, git_sha, started_at, config, cost_usd, tokens = row
    return run_info(run_id_value, benchmark, git_sha, started_at, config, float(cost_usd), tokens)


def run_info(
    run_id: UUID,
    benchmark: str,
    git_sha: str,
    started_at: datetime,
    config: object,
    cost_usd: float = 0.0,
    tokens: int = 0,
) -> RunInfo:
    """`RunInfo` from an `eval_runs` row; a setting the config lacks, or holds in another shape,
    stays None."""
    settings = config if isinstance(config, Mapping) else {}
    outcome = settings.get("outcome")
    status = outcome.get("status") if isinstance(outcome, Mapping) else None
    dirty = settings.get("git_dirty")
    return RunInfo(
        id=run_id,
        benchmark=benchmark,
        git_sha=git_sha,
        started_at=started_at,
        model=_text(settings, "model"),
        cost_usd=cost_usd,
        tokens=tokens,
        classifier=_text(settings, "classifier"),
        provider=_text(settings, "provider"),
        second_model=_text(settings, "second_model"),
        second_provider=_text(settings, "second_provider"),
        exclude_mode=_text(settings, "exclude_mode"),
        subset=_number(settings, "subset"),
        seed=_number(settings, "seed"),
        status=status if isinstance(status, str) else None,
        is_git_dirty=dirty if isinstance(dirty, bool) else None,
        answers_from=_text(settings, "answers_from"),
        judged=parse_settings(settings),
    )


def _text(settings: Mapping[str, object], key: str) -> str | None:
    value = settings.get(key)
    return value if isinstance(value, str) else None


def _number(settings: Mapping[str, object], key: str) -> int | None:
    value = settings.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


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
        models=_served_models(case_id, stored.get(MODELS_KEY)),
        judged=_judged(case_id, stored),
    )


def _judged(case_id: str, scores: Mapping[str, object]) -> dict[JudgeCheck, CheckScore]:
    """The stored judged tallies; a malformed one is a `RunRecordError` naming the case."""
    try:
        return read_stored(scores)
    except JudgedRecordError as exc:
        raise RunRecordError(f"case {case_id}: {exc}") from exc


def _served_models(case_id: str, value: object) -> dict[str, dict[str, int]]:
    """The stored `models` score; a malformed one is a `RunRecordError` naming the case."""
    if value is None:
        return {}
    try:
        return SERVED_MODELS.validate_python(value)
    except ValidationError as exc:
        raise RunRecordError(f"case {case_id}: stored models are malformed") from exc


def run_report(conn: psycopg.Connection, run_id: UUID) -> str:
    """The markdown report for one stored run; a Q&A run's holds its judged metrics."""
    info = load_run_info(conn, run_id)
    if info.benchmark == QA_BENCHMARK:
        return build_qa_report(info, load_judged_scores(conn, run_id))
    return build_report(info, load_stored_cases(conn, run_id), load_contaminated())


def load_judged_scores(
    conn: psycopg.Connection, run_id: UUID
) -> tuple[dict[JudgeCheck, CheckScore], ...]:
    """Each stored row's judged tallies, whatever the run's rows hold besides."""
    rows = conn.execute(
        "select case_id, scores from eval_case_results where run_id = %s order by case_id",
        (run_id,),
    ).fetchall()
    return tuple(
        _judged(case_id, scores if isinstance(scores, Mapping) else {}) for case_id, scores in rows
    )


def build_qa_report(info: RunInfo, judged: Sequence[Mapping[JudgeCheck, CheckScore]]) -> str:
    """A Q&A run's report: its settings and its judged metrics (Q&A support)."""
    lines = [
        f"## Run {info.id}",
        "",
        *_settings_lines(info),
        f"- Started: {info.started_at.isoformat()}",
        f"- Cost: ${info.cost_usd:.4f}, {info.tokens} tokens",
        f"- Items: {len(judged)}",
        "",
        *_judged_lines(judged, len(judged), info.judged),
    ]
    return "\n".join(lines) + "\n"


def _judged_lines(
    judged: Sequence[Mapping[JudgeCheck, CheckScore]], cases: int, settings: JudgedSettings | None
) -> list[str]:
    tallies = [scores for scores in judged if scores]
    return render_judged(run_totals(tallies), len(tallies), cases, settings)


def build_report(
    info: RunInfo, cases: tuple[StoredCase, ...], contaminated: ContaminatedList | None = None
) -> str:
    scored = [case for case in cases if not case.is_scoring_error]
    scoring_errors = [case.outcome.case.id for case in cases if case.is_scoring_error]
    outcomes = [case.outcome for case in scored]
    lines = render_markdown(info, scored_metrics(scored), scoring_errors).splitlines()
    flagged = contaminated_cases(outcomes, contaminated)
    if flagged and contaminated is not None:
        clean = summarize([o for o in outcomes if o.case.id not in flagged], None)
        lines += _contaminated_lines(flagged, contaminated.decision, clean)
    refusals = summarize_refusals(
        [RefusalCase(outcome=case.outcome, models=case.models) for case in scored],
        info.second_model,
    )
    answered = [case for case in cases if case.outcome.result is not None]
    judged = _judged_lines([case.judged for case in answered], len(answered), info.judged)
    sections = (
        render_refusals(refusals),
        render_failures(outcomes),
        render_texts(outcomes),
        judged,
    )
    for section in sections:
        lines += ["", *section]
    return "\n".join(lines) + "\n"


def scored_metrics(scored: Sequence[StoredCase]) -> RunMetrics:
    """The run's metrics, with citation existence from the scores stored at run time."""
    citations = [case.citation_existence for case in scored if case.citation_existence is not None]
    return summarize([case.outcome for case in scored], None).model_copy(
        update={"citation_existence": Rate(hits=sum(citations), total=len(citations))}
    )


def contaminated_cases(
    outcomes: Sequence[Outcome], contaminated: ContaminatedList | None
) -> dict[str, str]:
    """The run's cases written from a contaminated example (decision 016): id -> example id."""
    if contaminated is None:
        return {}
    examples = {example.example_id for example in contaminated.examples}
    return {
        o.case.id: o.case.source_example_id
        for o in outcomes
        if o.case.source_example_id is not None and o.case.source_example_id in examples
    }


def _contaminated_lines(flagged: Mapping[str, str], decision: str, clean: RunMetrics) -> list[str]:
    named = ", ".join(f"{case_id} (from {example})" for case_id, example in flagged.items())
    return [
        "",
        f"Contaminated cases, flagged by {decision}: {named}",
        "",
        "| Metric | Value | Count |",
        "| --- | ---: | ---: |",
        _row("Risk-class accuracy without the contaminated cases", clean.risk_class_accuracy),
    ]


def render_markdown(
    info: RunInfo, metrics: RunMetrics, scoring_errors: list[str] | None = None
) -> str:
    header = [
        f"## Run {info.id}",
        "",
        *_settings_lines(info),
        f"- Started: {info.started_at.isoformat()}",
        f"- Model: {info.model or 'n/a'}",
        f"- Cost: ${info.cost_usd:.4f}, {info.tokens} tokens",
        f"- Cases: {metrics.cases} ({metrics.failed} failed)",
        "",
        "| Metric | Value | Count |",
        "| --- | ---: | ---: |",
    ]
    is_development = info.benchmark == CaseSet.OWN.value
    lines = [*header, *(_row(name, value) for name, value in _rows(metrics, is_development))]
    if scoring_errors:
        lines += ["", f"Scoring failed, left out of the metrics: {', '.join(scoring_errors)}"]
    return "\n".join(lines) + "\n"


def _settings_lines(info: RunInfo) -> list[str]:
    """The run's recorded settings, one line each; one the run didn't record is left out."""
    benchmark = f"- Benchmark: `{info.benchmark}`"
    if info.benchmark == CaseSet.OWN.value:
        benchmark += f" ({DEVELOPMENT_CASES})"
    lines = [benchmark, f"- Commit: `{info.git_sha}`{UNCOMMITTED if info.is_git_dirty else ''}"]
    if info.status:
        lines.append(f"- Status: {info.status}")
    if info.classifier:
        lines.append(f"- Classifier: `{info.classifier}`{_served_by(info.model, info.provider)}")
        lines.append(f"- Cases run: {_subset(info)}")
    if info.second_model:
        served = _served_by(info.second_model, info.second_provider)
        lines.append(f"- Second model for refused requests (decision 033){served}")
    if info.exclude_mode:
        mode = EXCLUDE_MODES.get(info.exclude_mode, "")
        lines.append(f"- Exclude mode: `{info.exclude_mode}`{mode}")
    if info.answers_from:
        lines.append(f"- Answers: {ANSWERS_FROM.format(run=info.answers_from)}")
    return lines


def _served_by(model: str | None, provider: str | None) -> str:
    if model is None:
        return ""
    return f": `{model}`" + (f" on `{provider}`" if provider else "")


def _subset(info: RunInfo) -> str:
    if info.subset is None:
        return "every case of the set"
    return f"a seeded sample of {info.subset} (seed {info.seed})"


def _rows(metrics: RunMetrics, is_development: bool = False) -> list[tuple[str, Rate | int]]:
    accuracy = "Risk-class accuracy" + (" (development cases)" if is_development else "")
    return [
        (accuracy, metrics.risk_class_accuracy),
        ("Not assessed (provider refused a check, decision 030)", metrics.not_assessed),
        (
            "Risk-class accuracy, not-assessed cases counted as misses",
            metrics.risk_class_accuracy_not_assessed_as_miss,
        ),
        ("False-low-risk rate", metrics.false_low_risk),
        ("Annex point accuracy", metrics.annex_point_accuracy),
        ("Role accuracy", metrics.role_accuracy),
        *_precision_recall("Legally ambiguous", metrics.ambiguous),
        ("Ambiguous answered needs-more-information", metrics.needs_info_on_ambiguous),
        *_precision_recall("Needs more information", metrics.needs_more_information),
        ("Downgrade rate (soft wording)", metrics.downgrade),
        ("Basis accuracy (Commission cases)", metrics.basis_accuracy),
        ("Flip variant asked or flagged", metrics.flip_variant_flagged),
        ("Label citation cited (any of)", metrics.citation_accuracy),
        ("Needs a description: asked (thin cases)", metrics.description_asked),
        ("Needs a description: asked wrongly (other cases)", metrics.description_asked_wrongly),
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
    return f"| {name} | {value.percent} | {value.hits}/{value.total} |"
