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
stored in each row's scores, never judged again here, and P8a's deterministic "no invented
content" check on the documents the results call for (`judged.code_checked_documents`, no model
call). A Q&A run (`aiact evaluate ragas`) gets its settings and its judged metrics only.

A Pile B run's report (`commission_b`, or the head-to-head draw's, V10b) names no case unless the
caller asks for it (`should_name_cases`): the scoring errors, contaminated cases, refusals and
failures are counted only, and a line names the file that holds the full report, under
`eval/reports/pile_b/`, which the Engine lane can't read (`run_reports`, V11). A stored row the
report can't read is named by its position in such a run, never by its case id.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

import psycopg
from pydantic import Field, TypeAdapter, ValidationError

from aiact.eval.cases import BenchmarkCase, CaseSet
from aiact.eval.failures import NAMED_IN_PILE_B_FILE, render_failures
from aiact.eval.head_to_head import HEAD_TO_HEAD_BENCHMARK
from aiact.eval.isolation import ContaminatedList, load_contaminated
from aiact.eval.judge import JudgeCheck
from aiact.eval.judged import (
    CheckScore,
    JudgedRecordError,
    JudgedSettings,
    code_checked_documents,
    parse_settings,
    qa_answer,
    read_stored,
    render_code_check,
    render_judged,
    run_totals,
)
from aiact.eval.label_filter import reports_folder
from aiact.eval.label_filter_report import display_path
from aiact.eval.metrics import (
    CITATION_EXISTENCE_KEY,
    Outcome,
    PrecisionRecall,
    Rate,
    RunMetrics,
    summarize,
)
from aiact.eval.ragas_metrics import BENCHMARK as QA_BENCHMARK
from aiact.eval.refusals import RefusalCase, render_refusals, summarize_refusals
from aiact.eval.runner import MODELS_KEY, SCORING_ERROR_KEY, is_failed
from aiact.eval.texts import render_texts
from aiact.schemas.base import ContractModel
from aiact.schemas.result import ClassificationResult

PILE_B_BENCHMARKS = frozenset({CaseSet.COMMISSION_B.value, HEAD_TO_HEAD_BENCHMARK})
"""The runs holding Pile B cases: `commission_b`, and the head-to-head draw's (V10b)."""
SERVED_MODELS = TypeAdapter(dict[str, dict[str, int]])
DEVELOPMENT_CASES = (
    "development cases: the engine's nodes were developed against them, so Commission Pile B "
    "carries the headline (decision 018)"
)
HEAD_TO_HEAD_MIX = (
    "the head-to-head draw: own development cases and Commission Pile B cases together, so this "
    "accuracy mixes the two; the per-set scores are in `eval/reports/pile_b/head_to_head.md`"
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
PILE_B_POINTER = (
    "- Case ids and expected labels: `{file}` (Pile B's, kept out of this text: the Engine lane "
    "can't read that folder, V11)"
)
PILE_B_INTRO = (
    "\nWritten by `aiact evaluate report {run}`: the full report, with the case ids and expected "
    "labels its printed text leaves out. The Engine lane denies this folder (V11). "
    "Classifications are guidance, not legal advice.\n\n"
)


class RunNotFoundError(LookupError):
    """No `eval_runs` row has the requested id."""


class RunRecordError(ValueError):
    """A stored case row doesn't hold what the report expects; the message names the case, or
    for a Pile B run the row's position."""


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
    """The run's case rows, by case id; a Pile B run's unreadable row is named by position."""
    rows = conn.execute(
        "select r.case_id, r.label, r.predicted, r.scores, e.benchmark"
        " from eval_case_results r join eval_runs e on e.id = r.run_id"
        " where r.run_id = %s order by r.case_id",
        (run_id,),
    ).fetchall()
    return tuple(
        stored_case(
            case_id,
            label,
            predicted,
            scores,
            row=f"row {position}" if benchmark in PILE_B_BENCHMARKS else None,
        )
        for position, (case_id, label, predicted, scores, benchmark) in enumerate(rows, 1)
    )


def stored_case(
    case_id: str, label: object, predicted: object, scores: object = None, row: str | None = None
) -> StoredCase:
    """Parse one `eval_case_results` row (its `label`, `predicted` and `scores` columns). An
    error names `row` when given (a Pile B run's row position), else `case <case_id>`."""
    name = row or f"case {case_id}"
    try:
        case = BenchmarkCase.model_validate(label)
        result = None if is_failed(predicted) else ClassificationResult.model_validate(predicted)
    except ValidationError as exc:
        # Only the failing fields: pydantic's message would quote the stored values, descriptions
        # included.
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise RunRecordError(
            f"{name}: stored label or prediction is invalid at {', '.join(fields)}"
        ) from exc
    if case.id != case_id:
        other = "another case" if row else f"case {case.id}"
        raise RunRecordError(f"{name}: stored label belongs to {other}")
    stored = scores if isinstance(scores, Mapping) else {}
    citation_score = stored.get(CITATION_EXISTENCE_KEY)
    return StoredCase(
        outcome=Outcome(case=case, result=result),
        is_scoring_error=stored.get(SCORING_ERROR_KEY) is True,
        citation_existence=citation_score if isinstance(citation_score, bool) else None,
        models=_served_models(name, stored.get(MODELS_KEY)),
        judged=_judged(name, stored),
    )


def _judged(name: str, scores: Mapping[str, object]) -> dict[JudgeCheck, CheckScore]:
    """The stored judged tallies; a malformed one is a `RunRecordError` naming the row."""
    try:
        return read_stored(scores)
    except JudgedRecordError as exc:
        raise RunRecordError(f"{name}: {exc}") from exc


def _served_models(name: str, value: object) -> dict[str, dict[str, int]]:
    """The stored `models` score; a malformed one is a `RunRecordError` naming the row."""
    if value is None:
        return {}
    try:
        return SERVED_MODELS.validate_python(value)
    except ValidationError as exc:
        raise RunRecordError(f"{name}: stored models are malformed") from exc


@dataclass(frozen=True)
class RunReport:
    """A stored run's report: the text to print, and for a Pile B run the full one (V11)."""

    text: str
    """The report to print and paste. A Pile B run's names no case id and no expected label,
    only the file `pile_b_text` goes to."""
    pile_b_text: str | None = None
    """A Pile B run's full report, every case named with what it shows, for `pile_b_file`."""


def run_reports(conn: psycopg.Connection, run_id: UUID) -> RunReport:
    """The report for one stored run; a Q&A run's holds its judged metrics. A Pile B
    (`commission_b`) run's text names `pile_b_file` instead of its cases, and `pile_b_text` is
    what goes in that file."""
    info = load_run_info(conn, run_id)
    if info.benchmark == QA_BENCHMARK:
        return RunReport(build_qa_report(info, load_qa_tallies(conn, run_id)))
    cases, contaminated = load_stored_cases(conn, run_id), load_contaminated()
    if not is_pile_b(info):
        return RunReport(build_report(info, cases, contaminated))
    named = build_report(info, cases, contaminated, should_name_cases=True)
    pointer = display_path(pile_b_file(info.id))
    return RunReport(
        build_report(info, cases, contaminated, pile_b_pointer=pointer),
        pile_b_heading(info.id) + PILE_B_INTRO.format(run=info.id) + named,
    )


def is_pile_b(info: RunInfo) -> bool:
    return info.benchmark in PILE_B_BENCHMARKS


def pile_b_file(run_id: UUID) -> Path:
    """Where a Pile B run's full report goes: the folder the Engine lane denies."""
    return reports_folder(CaseSet.COMMISSION_B) / f"run-{run_id}.md"


def pile_b_heading(run_id: UUID) -> str:
    """The Pile B file's first line; a file there that doesn't start with it is never
    overwritten."""
    return f"# Pile B run {run_id}: every case named\n"


QaTally = Mapping[JudgeCheck, CheckScore] | None
"""A Q&A row's judged tallies (empty until judged), or None for a row with nothing to judge."""


def load_qa_tallies(conn: psycopg.Connection, run_id: UUID) -> tuple[QaTally, ...]:
    """Each stored Q&A row's judged tallies; None for a row a pass leaves out (`qa_answer`: a
    failed answer, no answer, or a fixed one)."""
    rows = conn.execute(
        "select case_id, predicted, scores from eval_case_results"
        " where run_id = %s order by case_id",
        (run_id,),
    ).fetchall()
    return tuple(
        None
        if qa_answer(predicted) is None
        else _judged(case_id, scores if isinstance(scores, Mapping) else {})
        for case_id, predicted, scores in rows
    )


def build_qa_report(info: RunInfo, rows: Sequence[QaTally]) -> str:
    """A Q&A run's report: its settings and its judged metrics (Q&A support) over the rows a
    pass would judge."""
    judgeable = [tallies for tallies in rows if tallies is not None]
    lines = [
        f"## Run {info.id}",
        "",
        *_settings_lines(info),
        f"- Started: {info.started_at.isoformat()}",
        f"- Cost: ${info.cost_usd:.4f}, {info.tokens} tokens",
        f"- Items: {len(rows)}, {len(judgeable)} with an answer drawn from the sources",
        "",
        *_judged_lines(judgeable, len(judgeable), info.judged),
    ]
    return "\n".join(lines) + "\n"


def _judged_lines(
    judged: Sequence[Mapping[JudgeCheck, CheckScore]], cases: int, settings: JudgedSettings | None
) -> list[str]:
    tallies = [scores for scores in judged if scores]
    return render_judged(run_totals(tallies), len(tallies), cases, settings)


def build_report(
    info: RunInfo,
    cases: tuple[StoredCase, ...],
    contaminated: ContaminatedList | None = None,
    *,
    should_name_cases: bool | None = None,
    pile_b_pointer: str | None = None,
) -> str:
    """The report's markdown. A Pile B run's names no case (no id, no expected label) unless
    `should_name_cases` is True: it counts them, and `pile_b_pointer` names the file that does
    (V11). Another run's names its cases unless `should_name_cases` is False."""
    should_name_cases = _names_cases(info, should_name_cases)
    scored = [case for case in cases if not case.is_scoring_error]
    scoring_errors = [case.outcome.case.id for case in cases if case.is_scoring_error]
    outcomes = [case.outcome for case in scored]
    lines = render_markdown(
        info,
        scored_metrics(scored),
        scoring_errors,
        should_name_cases=should_name_cases,
        pile_b_pointer=pile_b_pointer,
    ).splitlines()
    flagged = contaminated_cases(outcomes, contaminated)
    if flagged and contaminated is not None:
        clean = summarize([o for o in outcomes if o.case.id not in flagged], None)
        named = _named(flagged, should_name_cases)
        lines += _contaminated_lines(named, contaminated.decision, clean)
    refusals = summarize_refusals(
        [RefusalCase(outcome=case.outcome, models=case.models) for case in scored],
        info.second_model,
    )
    answered = [case for case in cases if case.outcome.result is not None]
    judged = _judged_lines([case.judged for case in answered], len(answered), info.judged)
    results = [
        (result, case.outcome.case.language)
        for case in answered
        if (result := case.outcome.result) is not None
    ]
    sections = (
        render_refusals(refusals, should_name_cases=should_name_cases),
        render_failures(outcomes, should_name_cases=should_name_cases),
        render_texts(outcomes),
        judged,
        render_code_check(code_checked_documents(results)),
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


def _names_cases(info: RunInfo, should_name_cases: bool | None) -> bool:
    """Whether a report names its cases: as asked, else every run's but a Pile B run's."""
    return not is_pile_b(info) if should_name_cases is None else should_name_cases


def _named(flagged: Mapping[str, str], should_name_cases: bool) -> str:
    """The contaminated cases, each with its example; their count alone for a Pile B text."""
    if not should_name_cases:
        return f"{len(flagged)} {NAMED_IN_PILE_B_FILE}"
    return ", ".join(f"{case_id} (from {example})" for case_id, example in flagged.items())


def _contaminated_lines(named: str, decision: str, clean: RunMetrics) -> list[str]:
    return [
        "",
        f"Contaminated cases, flagged by {decision}: {named}",
        "",
        "| Metric | Value | Count |",
        "| --- | ---: | ---: |",
        _row("Risk-class accuracy without the contaminated cases", clean.risk_class_accuracy),
    ]


def render_markdown(
    info: RunInfo,
    metrics: RunMetrics,
    scoring_errors: list[str] | None = None,
    *,
    should_name_cases: bool | None = None,
    pile_b_pointer: str | None = None,
) -> str:
    """The header and the metric table. Unnamed (by default for a Pile B run, as in
    `build_report`), the scoring errors are counted only; `pile_b_pointer` adds a line naming
    the Pile B file."""
    should_name_cases = _names_cases(info, should_name_cases)
    header = [
        f"## Run {info.id}",
        "",
        *run_lines(info),
        f"- Cases: {metrics.cases} ({metrics.failed} failed)",
        *([PILE_B_POINTER.format(file=pile_b_pointer)] if pile_b_pointer is not None else []),
        "",
        "| Metric | Value | Count |",
        "| --- | ---: | ---: |",
    ]
    is_development = info.benchmark == CaseSet.OWN.value
    lines = [*header, *(_row(name, value) for name, value in _rows(metrics, is_development))]
    if scoring_errors:
        named = (
            ", ".join(scoring_errors)
            if should_name_cases
            else f"{len(scoring_errors)} {NAMED_IN_PILE_B_FILE}"
        )
        lines += ["", f"Scoring failed, left out of the metrics: {named}"]
    return "\n".join(lines) + "\n"


def run_lines(info: RunInfo) -> list[str]:
    """A run's settings, start, model and cost, one line each, as a report's header shows them."""
    return [
        *_settings_lines(info),
        f"- Started: {info.started_at.isoformat()}",
        f"- Model: {info.model or 'n/a'}",
        f"- Cost: ${info.cost_usd:.4f}, {info.tokens} tokens",
    ]


def _settings_lines(info: RunInfo) -> list[str]:
    """The run's recorded settings, one line each; one the run didn't record is left out."""
    benchmark = f"- Benchmark: `{info.benchmark}`"
    if info.benchmark == CaseSet.OWN.value:
        benchmark += f" ({DEVELOPMENT_CASES})"
    if info.benchmark == HEAD_TO_HEAD_BENCHMARK:
        benchmark += f" ({HEAD_TO_HEAD_MIX})"
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
