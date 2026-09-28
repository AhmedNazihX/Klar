"""The benchmark runner: classify a set of cases and record every result (INIT > Evaluation).

`aiact eval run` loads a case set, optionally draws a seeded subset, runs a classifier over it with
a few cases in flight at once, and writes one `eval_runs` row plus one `eval_case_results` row per
case. Reports quote numbers only from these rows, by run id.

The classifier sees the description, the language and the source example ids to keep out of
retrieval; it never sees the label. `--exclude-mode heldout` (the reported number) reads the
committed `eval/split.json`: in split mode every Pile B example is excluded, in leave-one-out mode
the example the case was written from. `--exclude-mode all` excludes nothing, for the gap run
(INIT > Benchmark isolation 4).

A cost cap is checked before each case starts, so a run can overshoot it by at most the cost of
the cases already in flight. Per-case cost, tokens and failures are stored as run-level scores
(`cost_usd`, `tokens`, `is_error`) next to the metric scores, and the run's final status is merged
into `config.outcome`, because the F5 schema has no columns for them yet.
"""

import json
import logging
import random
import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from aiact.eval.cases import (
    APPLIEDAI_FILE,
    CASES_DIR,
    EVAL_DIR,
    AppliedAILabel,
    BenchmarkCase,
    CaseSet,
    load_cases,
    load_jsonl,
)
from aiact.schemas import (
    DISCLAIMER,
    ClassificationResult,
    Language,
    LawVersion,
    RiskClass,
    StepName,
    StepResult,
)
from aiact.settings import BACKEND_DIR

logger = logging.getLogger(__name__)

SPLIT_FILE = EVAL_DIR / "split.json"
DEFAULT_CONCURRENCY = 4
MAX_CONCURRENCY = 16
DEFAULT_MAX_COST_USD = 1.0
"""The default spending cap per run; the whole project has a €50 budget (INIT > Budget rules)."""

RUN_SCORE_KEYS = frozenset({"cost_usd", "tokens", "is_error"})
"""Scores the runner itself writes for every case; a metric scorer may not use these names."""

ERROR_MESSAGE_LIMIT = 300

Score = float | bool | None
Scorer = Callable[[BenchmarkCase, ClassificationResult], Mapping[str, Score]]


class ExcludeMode(StrEnum):
    """What retrieval must leave out: the held-out examples (reported) or nothing (gap run)."""

    HELDOUT = "heldout"
    ALL = "all"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    COST_CAP_REACHED = "cost_cap_reached"
    INTERRUPTED = "interrupted"


class SplitError(ValueError):
    """`eval/split.json` is missing or unusable, or a case contradicts it."""


class ClassifierUnavailableError(RuntimeError):
    """The named classifier can't be built (unknown name, or its story isn't merged yet)."""


@dataclass(frozen=True)
class ClassifierInput:
    """What a classifier may see of a case: never its label."""

    description: str
    language: Language
    exclude_source_example_ids: tuple[str, ...]


@dataclass(frozen=True)
class Classification:
    """A classifier's answer and what it cost."""

    result: ClassificationResult
    cost_usd: float = 0.0
    tokens: int = 0
    trace_id: str | None = None


@dataclass(frozen=True)
class ClassifierInfo:
    """The settings recorded in `eval_runs.config` (F5 requires the three keys; null allowed)."""

    model: str | None
    embedding: JsonValue = None
    retrieval: JsonValue = None


class Classifier(Protocol):
    """Anything that turns a description into a `ClassificationResult`; must be thread-safe."""

    @property
    def info(self) -> ClassifierInfo: ...

    def classify(self, request: ClassifierInput) -> Classification: ...


class DummyClassifier:
    """A free, offline classifier: every system is out of scope. For dry runs and tests."""

    info = ClassifierInfo(model=None)

    def classify(self, request: ClassifierInput) -> Classification:
        scope = StepResult(step=StepName.SCOPE, decision="Dummy classifier: not an AI system")
        result = ClassificationResult(
            facts=(),
            steps=(scope,),
            risk_class=RiskClass.OUT_OF_SCOPE,
            status=scope.status,
            law_version=LawVersion.AMENDED,
            as_of=date(2026, 12, 2),
            disclaimer=DISCLAIMER[request.language],
        )
        return Classification(result=result)


def _engine_classifier() -> Classifier:
    raise ClassifierUnavailableError("the engine classifier is wired in once E10 is merged")


CLASSIFIERS: Mapping[str, Callable[[], Classifier]] = {
    "dummy": DummyClassifier,
    "engine": _engine_classifier,
}
"""Classifier factories by CLI name. V3 adds the `baseline_*` entries."""


def build_classifier(name: str) -> Classifier:
    factory = CLASSIFIERS.get(name)
    if factory is None:
        raise ClassifierUnavailableError(
            f"unknown classifier {name!r}; available: {', '.join(sorted(CLASSIFIERS))}"
        )
    return factory()


class _SplitFile(BaseModel):
    """The part of B3's `eval/split.json` the runner reads."""

    model_config = ConfigDict(frozen=True)

    mode: str
    pile_a: tuple[str, ...]
    pile_b: tuple[str, ...]


@dataclass(frozen=True)
class Split:
    is_loo: bool
    pile_a: frozenset[str]
    pile_b: tuple[str, ...]


def load_split(path: Path | None = None) -> Split:
    """Read the committed split (default `SPLIT_FILE`); a missing or bad file is a `SplitError`."""
    path = path or SPLIT_FILE
    if not path.is_file():
        raise SplitError(
            f"{path} not found: --exclude-mode heldout needs the committed split (story B3); "
            "use --exclude-mode all for a development run"
        )
    try:
        split = _SplitFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError) as exc:
        raise SplitError(f"{path}: not a valid split file: {exc}") from exc
    if split.mode not in {"split", "loo"}:
        raise SplitError(f"{path}: mode must be split or loo, not {split.mode!r}")
    return Split(split.mode == "loo", frozenset(split.pile_a), tuple(sorted(split.pile_b)))


def exclusions_for(case: BenchmarkCase, split: Split | None) -> tuple[str, ...]:
    """The source example ids retrieval must leave out for `case`; no split means none."""
    if split is None:
        return ()
    if not split.is_loo:
        if case.source_example_id in split.pile_a:
            raise SplitError(f"case {case.id} comes from a Pile A example, not a held-out one")
        return split.pile_b
    return (case.source_example_id,) if case.source_example_id else ()


def load_benchmark(case_set: CaseSet, cases_dir: Path = CASES_DIR) -> tuple[BenchmarkCase, ...]:
    """Every case of a set: YAML under `eval/cases/`, or the private appliedAI JSONL."""
    if case_set is CaseSet.APPLIEDAI:
        return load_jsonl(APPLIEDAI_FILE)
    return load_cases(case_set, cases_dir)


def select_subset(
    cases: Sequence[BenchmarkCase], size: int | None, seed: int
) -> tuple[BenchmarkCase, ...]:
    """A seeded random sample of `size` cases in id order, or every case when `size` is None."""
    ordered = sorted(cases, key=lambda case: case.id)
    if size is None or size >= len(ordered):
        return tuple(ordered)
    return tuple(sorted(random.Random(seed).sample(ordered, size), key=lambda case: case.id))


def label_record(case: BenchmarkCase) -> dict[str, JsonValue]:
    """The frozen label as stored in `eval_case_results.label`."""
    if isinstance(case.label, AppliedAILabel):
        return {"appliedai": case.label.value}
    return case.label.model_dump(mode="json")


def no_metric_scores(case: BenchmarkCase, result: ClassificationResult) -> Mapping[str, Score]:
    """The default scorer: metrics come with V2, so only the runner's own scores are written."""
    return {}


@dataclass(frozen=True)
class CaseRecord:
    """One `eval_case_results` row, plus the cost to add to the run's totals."""

    case_id: str
    predicted: dict[str, JsonValue]
    label: dict[str, JsonValue]
    scores: dict[str, Score]
    trace_id: str | None
    cost_usd: float
    tokens: int


class RunStore(Protocol):
    """Where runs are recorded; `aiact.eval.records.PostgresRunStore` in production."""

    def start_run(self, git_sha: str, benchmark: str, config: Mapping[str, JsonValue]) -> UUID: ...

    def add_case(self, run_id: UUID, record: CaseRecord) -> None: ...

    def finish_run(self, run_id: UUID, outcome: Mapping[str, JsonValue]) -> None: ...


@dataclass(frozen=True)
class RunOptions:
    benchmark: CaseSet
    classifier_name: str
    exclude_mode: ExcludeMode
    git_sha: str
    is_git_dirty: bool = False
    subset: int | None = None
    seed: int = 0
    concurrency: int = DEFAULT_CONCURRENCY
    max_cost_usd: float = DEFAULT_MAX_COST_USD

    def __post_init__(self) -> None:
        if not 1 <= self.concurrency <= MAX_CONCURRENCY:
            raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
        if self.max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be positive")
        if self.subset is not None and self.subset < 1:
            raise ValueError("subset must be at least 1")


@dataclass(frozen=True)
class RunSummary:
    run_id: UUID
    status: RunStatus
    cases_planned: int
    cases_scored: int
    cases_failed: int
    cost_usd: float
    tokens: int


def run_config(
    options: RunOptions, info: ClassifierInfo, split: Split | None
) -> dict[str, JsonValue]:
    """`eval_runs.config`: the classifier's settings and the run's own options."""
    return {
        "model": info.model,
        "embedding": info.embedding,
        "retrieval": info.retrieval,
        "classifier": options.classifier_name,
        "exclude_mode": options.exclude_mode.value,
        "split_mode": None if split is None else ("loo" if split.is_loo else "split"),
        "subset": options.subset,
        "seed": options.seed,
        "concurrency": options.concurrency,
        "max_cost_usd": options.max_cost_usd,
        "git_dirty": options.is_git_dirty,
        "outcome": {"status": RunStatus.RUNNING.value},
    }


@dataclass(frozen=True)
class _Planned:
    case: BenchmarkCase
    request: ClassifierInput


def run_benchmark(
    cases: Sequence[BenchmarkCase],
    classifier: Classifier,
    store: RunStore,
    options: RunOptions,
    split: Split | None,
    scorer: Scorer = no_metric_scores,
) -> RunSummary:
    """Classify the (subset of) cases and record each result as it finishes.

    `split` must be given for `ExcludeMode.HELDOUT` and is ignored for `ExcludeMode.ALL`.
    """
    if options.exclude_mode is ExcludeMode.HELDOUT and split is None:
        raise SplitError("--exclude-mode heldout needs eval/split.json")
    active_split = split if options.exclude_mode is ExcludeMode.HELDOUT else None
    planned = [
        _Planned(
            case,
            ClassifierInput(case.description, case.language, exclusions_for(case, active_split)),
        )
        for case in select_subset(cases, options.subset, options.seed)
    ]
    run_id = store.start_run(
        options.git_sha, options.benchmark.value, run_config(options, classifier.info, active_split)
    )
    tally = _Tally()
    status = RunStatus.INTERRUPTED
    try:
        for record in _classify_all(planned, classifier, scorer, options, tally):
            store.add_case(run_id, record)
        status = RunStatus.COST_CAP_REACHED if tally.scored < len(planned) else RunStatus.COMPLETED
    finally:
        store.finish_run(run_id, tally.outcome(status, len(planned)))
    return RunSummary(
        run_id, status, len(planned), tally.scored, tally.failed, tally.cost_usd, tally.tokens
    )


class _Tally:
    """Running totals of one run, owned by the thread that records results."""

    def __init__(self) -> None:
        self.scored = 0
        self.failed = 0
        self.cost_usd = 0.0
        self.tokens = 0

    def add(self, record: CaseRecord) -> None:
        self.scored += 1
        self.failed += int(record.scores["is_error"] is True)
        self.cost_usd += record.cost_usd
        self.tokens += record.tokens

    def outcome(self, status: RunStatus, planned: int) -> dict[str, JsonValue]:
        return {
            "status": status.value,
            "finished_at": datetime.now(UTC).isoformat(),
            "cases_planned": planned,
            "cases_scored": self.scored,
            "cases_failed": self.failed,
        }


def _classify_all(
    planned: Sequence[_Planned],
    classifier: Classifier,
    scorer: Scorer,
    options: RunOptions,
    tally: _Tally,
) -> Iterator[CaseRecord]:
    """Yield records as cases finish, starting a new case only while under the cost cap."""
    queue = iter(planned)
    with ThreadPoolExecutor(max_workers=options.concurrency) as pool:
        pending: set[Future[CaseRecord]] = set()
        while True:
            while len(pending) < options.concurrency and tally.cost_usd < options.max_cost_usd:
                item = next(queue, None)
                if item is None:
                    break
                pending.add(pool.submit(_classify_one, item, classifier, scorer))
            if not pending:
                return
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                record = future.result()
                tally.add(record)
                yield record


def _classify_one(item: _Planned, classifier: Classifier, scorer: Scorer) -> CaseRecord:
    """Classify and score one case; a classifier failure becomes an `is_error` row, not a crash."""
    case = item.case
    try:
        answer = classifier.classify(item.request)
    except Exception as exc:
        logger.warning("case %s failed: %s", case.id, type(exc).__name__)
        error: dict[str, JsonValue] = {
            "type": type(exc).__name__,
            "message": str(exc)[:ERROR_MESSAGE_LIMIT],
        }
        return CaseRecord(
            case.id,
            {"error": error},
            label_record(case),
            {"cost_usd": 0.0, "tokens": 0, "is_error": True},
            None,
            0.0,
            0,
        )
    metric_scores = dict(scorer(case, answer.result))
    clashing = RUN_SCORE_KEYS & metric_scores.keys()
    if clashing:
        raise ValueError(f"scorer used reserved score names: {sorted(clashing)}")
    run_scores: dict[str, Score] = {
        "cost_usd": answer.cost_usd,
        "tokens": answer.tokens,
        "is_error": False,
    }
    return CaseRecord(
        case.id,
        answer.result.model_dump(mode="json"),
        label_record(case),
        metric_scores | run_scores,
        answer.trace_id,
        answer.cost_usd,
        answer.tokens,
    )


def current_git_state(cwd: Path = BACKEND_DIR) -> tuple[str, bool]:
    """The commit the run is made from, and whether the working tree has uncommitted changes."""
    sha = _git(["rev-parse", "HEAD"], cwd).strip()
    is_dirty = bool(_git(["status", "--porcelain"], cwd).strip())
    return sha, is_dirty


def _git(arguments: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
    )
    return completed.stdout
