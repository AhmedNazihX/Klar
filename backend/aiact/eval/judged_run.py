"""`aiact evaluate judged <run_id>`: judge a stored run's results (V5), apart from the run.

Judging is a pass of its own over the stored rows, so a run is classified once and judged when
the judge is ready (its margin chosen, decision 006), with its own cost cap. A classification
run gets citation support, evidence-tag accuracy and no invented content on each result
(`judged.CLASSIFICATION_CHECKS`); a Q&A run (`aiact evaluate ragas`, benchmark `qa`) gets Q&A
support on each answer, its sources read again from the corpus by the provision ids the run
stored, as of the run's start date (`corpus_source`). A row whose classifier or answer failed has
nothing to judge and is skipped.

Each judged case's tallies are merged into its `eval_case_results.scores`; the judge's settings
into the run's `config.judged`. A row already judged is skipped, so a pass stopped by the cost cap
(checked before each case) goes on where it stopped. Judging again with another judge or margin
than the stored one is refused (`JudgedSettingsError`): one run's tallies come from one judge.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from aiact.eval.cases import BenchmarkCase, QAItem
from aiact.eval.judge import (
    BACKUP_CALL_ESTIMATE_USD,
    JEV_CALL_ESTIMATE_USD,
    PRICED_BACKUP_MODEL,
    JudgeCheck,
)
from aiact.eval.judged import (
    CheckScore,
    JudgedSettings,
    Judges,
    Planned,
    citation_support_items,
    evidence_tag_items,
    invented_content_items,
    is_judged,
    judge_plan,
    parse_settings,
    qa_support_item,
    stored_scores,
)
from aiact.qa.models import AnswerKind
from aiact.retrieval.provisions import AI_ACT_DOC_KEYS, ProvisionNotFoundError, get_provision
from aiact.schemas import ClassificationResult, Language, LawVersion

QA_BENCHMARK = "qa"
"""`ragas_metrics.BENCHMARK`, named here so this module doesn't load RAGAS's."""
ANSWER_KIND_KEY = "answer_kind"
"""`ragas_metrics.ANSWER_KIND`: the stored answer's `AnswerKind` (None for V6's stand-in)."""
FAILED_KEY = "error"
"""A `predicted` object with this key records a failed classifier or answer."""
DEFAULT_MAX_COST_USD = 0.5
DEFAULT_CONCURRENCY = 4
MAX_CONCURRENCY = 16
LAW_VERSIONS: Mapping[str, LawVersion] = MappingProxyType(
    {doc_key: version for version, doc_key in AI_ACT_DOC_KEYS.items()}
)

Plan = Mapping[JudgeCheck, Sequence[Planned]]
SourceReader = Callable[[Mapping[str, object], Language], str | None]
"""A stored hit (`{"doc_key", "provision_id"}`) → its text as the answer was given it, or None
when the corpus no longer has it."""


class JudgedRunNotFoundError(LookupError):
    """No `eval_runs` row has the requested id."""


class JudgedRowError(ValueError):
    """A stored row doesn't hold what judging expects; the message names the case only."""


class JudgedSettingsError(ValueError):
    """The run was judged before with another judge or margin."""


class JudgedStatus(StrEnum):
    COMPLETED = "completed"
    COST_CAP_REACHED = "cost_cap_reached"


@dataclass(frozen=True)
class StoredRow:
    case_id: str
    label: object
    predicted: object
    scores: Mapping[str, object]


@dataclass(frozen=True)
class StoredRun:
    id: UUID
    benchmark: str
    started_at: datetime
    settings: JudgedSettings | None
    rows: tuple[StoredRow, ...]


@dataclass(frozen=True)
class PlannedCase:
    case_id: str
    plan: Plan


@dataclass(frozen=True)
class JudgedOptions:
    max_cost_usd: float = DEFAULT_MAX_COST_USD
    concurrency: int = DEFAULT_CONCURRENCY

    def __post_init__(self) -> None:
        if not 1 <= self.concurrency <= MAX_CONCURRENCY:
            raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
        if self.max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be positive")


@dataclass(frozen=True)
class JudgedSummary:
    status: JudgedStatus
    cases_planned: int
    cases_judged: int
    totals: Mapping[JudgeCheck, CheckScore]

    @property
    def cost_usd(self) -> float:
        return sum(score.cost_usd for score in self.totals.values())

    @property
    def tokens(self) -> int:
        return sum(score.tokens for score in self.totals.values())


# --- planning ------------------------------------------------------------------------------------


def plan_run(run: StoredRun, read_source: SourceReader) -> tuple[PlannedCase, ...]:
    """The rows still to judge, each with its items; rows already judged or with nothing to
    judge (a failed classification or answer, a Q&A item with no answer) are left out."""
    todo = (row for row in run.rows if not is_judged(row.scores))
    planned = (
        PlannedCase(row.case_id, plan)
        for row in todo
        if (plan := plan_row(run.benchmark, row, read_source)) is not None
    )
    return tuple(planned)


def plan_row(benchmark: str, row: StoredRow, read_source: SourceReader) -> Plan | None:
    if _is_failed(row.predicted):
        return None
    try:
        if benchmark == QA_BENCHMARK:
            return _qa_plan(row, read_source)
        return _classification_plan(row)
    except ValidationError as exc:
        # The field paths only: pydantic's message would quote the stored texts.
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise JudgedRowError(
            f"case {row.case_id}: stored row is invalid at {', '.join(fields)}"
        ) from None


def _is_failed(predicted: object) -> bool:
    return isinstance(predicted, Mapping) and FAILED_KEY in predicted


def _classification_plan(row: StoredRow) -> Plan:
    case = BenchmarkCase.model_validate(row.label)
    result = ClassificationResult.model_validate(row.predicted)
    language = case.language
    return {
        JudgeCheck.CITATION_SUPPORT: citation_support_items(result, language),
        JudgeCheck.EVIDENCE_TAG: evidence_tag_items(result, case.description, language),
        JudgeCheck.INVENTED_CONTENT: invented_content_items(result, language),
    }


def _qa_plan(row: StoredRow, read_source: SourceReader) -> Plan | None:
    """None for a row with no answer drawn from the sources: no hit, or one of P7's fixed
    answers (outside the corpus, a compliance question, refused), which claims nothing from
    them. A source the corpus no longer has leaves the item not measured: the answer would be
    judged against part of what it was given."""
    item = QAItem.model_validate(row.label)
    predicted = row.predicted if isinstance(row.predicted, Mapping) else {}
    answer, retrieved = predicted.get("answer"), predicted.get("retrieved")
    kind = predicted.get(ANSWER_KIND_KEY)
    if not isinstance(answer, str) or not isinstance(retrieved, list):
        return None
    if kind is not None and kind != AnswerKind.ANSWERED.value:
        return None
    sources = [read_source(hit, item.language) for hit in retrieved if isinstance(hit, Mapping)]
    texts = [source for source in sources if source]
    is_complete = len(texts) == len(retrieved)
    planned = qa_support_item(item.question, answer, texts, item.language) if is_complete else None
    return {JudgeCheck.QA_SUPPORT: (planned,)}


def item_counts(planned: Sequence[PlannedCase]) -> dict[JudgeCheck, int]:
    """How many items each check would send (items that can't be sent left out)."""
    counts: dict[JudgeCheck, int] = {}
    for case in planned:
        for check, items in case.plan.items():
            sendable = sum(item is not None for item in items)
            counts = counts | {check: counts.get(check, 0) + sendable}
    return counts


def estimate_usd(items: int, backup_model: str) -> float | None:
    """The most judging `items` can cost: Jev on each, and the backup judge on each as if every
    one were unsure. None for a backup model whose prices aren't known."""
    if backup_model != PRICED_BACKUP_MODEL:
        return None
    return items * (JEV_CALL_ESTIMATE_USD + BACKUP_CALL_ESTIMATE_USD)


# --- judging -------------------------------------------------------------------------------------


class JudgedStore(Protocol):
    """Where judged tallies are written; `PostgresJudgedStore` in production."""

    def save_settings(self, run_id: UUID, settings: JudgedSettings) -> None: ...

    def save_case(self, run_id: UUID, case_id: str, scores: Mapping[str, float | int]) -> None: ...


def check_settings(run: StoredRun, settings: JudgedSettings) -> None:
    """Raises `JudgedSettingsError` when the run was judged with another judge or margin."""
    if run.settings is not None and run.settings != settings:
        raise JudgedSettingsError(
            f"run {run.id} was judged with {run.settings.model_dump()}, not "
            f"{settings.model_dump()}: one run's tallies come from one judge"
        )


def judge_run(
    run: StoredRun,
    planned: Sequence[PlannedCase],
    judge: Judges,
    settings: JudgedSettings,
    store: JudgedStore,
    options: JudgedOptions,
) -> JudgedSummary:
    """Judge the planned cases in order, writing each case's tallies as it finishes; no new case
    starts once `options.max_cost_usd` is spent."""
    check_settings(run, settings)
    store.save_settings(run.id, settings)
    totals: dict[JudgeCheck, CheckScore] = {}
    judged = 0
    status = JudgedStatus.COMPLETED
    for case in planned:
        if sum(score.cost_usd for score in totals.values()) >= options.max_cost_usd:
            status = JudgedStatus.COST_CAP_REACHED
            break
        scores = judge_plan(judge, case.plan, options.concurrency)
        store.save_case(run.id, case.case_id, stored_scores(scores))
        totals = {
            check: totals.get(check, CheckScore()) + scores.get(check, CheckScore())
            for check in totals.keys() | scores.keys()
        }
        judged += 1
    return JudgedSummary(status, len(planned), judged, totals)


# --- the database --------------------------------------------------------------------------------


def load_run(conn: psycopg.Connection, run_id: UUID) -> StoredRun:
    head = conn.execute(
        "select benchmark, started_at, config from eval_runs where id = %s", (run_id,)
    ).fetchone()
    if head is None:
        raise JudgedRunNotFoundError(f"no eval run with id {run_id}")
    benchmark, started_at, config = head
    rows = conn.execute(
        "select case_id, label, predicted, scores from eval_case_results "
        "where run_id = %s order by case_id",
        (run_id,),
    ).fetchall()
    return StoredRun(
        id=run_id,
        benchmark=benchmark,
        started_at=started_at,
        settings=parse_settings(config),
        rows=tuple(
            StoredRow(case_id, label, predicted, scores)
            for case_id, label, predicted, scores in rows
        ),
    )


class PostgresJudgedStore:
    """A `JudgedStore` over one psycopg connection; each write is its own short transaction."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def save_settings(self, run_id: UUID, settings: JudgedSettings) -> None:
        with self._connection.transaction():
            self._connection.execute(
                "update eval_runs set config = config || %s where id = %s",
                (Jsonb({"judged": settings.model_dump(mode="json")}), run_id),
            )

    def save_case(self, run_id: UUID, case_id: str, scores: Mapping[str, float | int]) -> None:
        """Merge the tallies into the case's stored scores, keeping the run's own."""
        with self._connection.transaction():
            cursor = self._connection.execute(
                "update eval_case_results set scores = scores || %s"
                " where run_id = %s and case_id = %s",
                (Jsonb(dict(scores)), run_id, case_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"run {run_id} has no stored case {case_id}")


def corpus_source(conn: psycopg.Connection, as_of: date) -> SourceReader:
    """Reads a stored hit's text again from the corpus, in the item's language (English where
    the corpus has no German), as the Q&A run's search returned it: its provision id and
    document, then its heading and text. An AI Act provision is read from the text its document
    holds (`ai-act` the original, `ai-act-consolidated` the amended one on `as_of`)."""

    def read(hit: Mapping[str, object], language: Language) -> str | None:
        provision_id, doc_key = hit.get("provision_id"), hit.get("doc_key")
        if not isinstance(provision_id, str) or not isinstance(doc_key, str):
            return None
        version = LAW_VERSIONS.get(doc_key, LawVersion.AMENDED)
        try:
            provision = get_provision(
                provision_id,
                language,
                version,
                None if version is LawVersion.ORIGINAL else as_of,
                connection=conn,
            )
        except (ProvisionNotFoundError, ValueError):
            return None
        lines = [f"[{provision_id}] {provision.document_title}", provision.heading, provision.text]
        return "\n".join(line for line in lines if line)

    return read
