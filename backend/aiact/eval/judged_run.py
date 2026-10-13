"""`aiact evaluate judged <run_id>`: judge a stored run's results (V5), apart from the run.

Judging is a pass of its own over the stored rows, so a run is classified once and judged when
the judge is ready (its margin chosen, decision 006), with its own cost cap. A classification
run gets citation support and evidence-tag accuracy on each result, the evidence tags judged
against the text the engine read (on an `--answers-from` run, the description with the fixed
answers appended, rebuilt as the runner built it); a Q&A run (`aiact evaluate ragas`, benchmark
`qa`) gets Q&A support on each answer, its sources read again from the corpus by the provision
ids the run stored, as of the run's start date (`corpus_source`). A row whose classifier or
answer failed has nothing to judge and is skipped.

Each judged case's tallies are merged into its `eval_case_results.scores`; the judge's settings
into the run's `config.judged`. A row already judged is skipped, so a pass stopped by the cost
cap (checked before each case) goes on where it stopped. A call that reaches no model stops the
pass without storing that case, which a rerun then judges. Judging again with another judge or
margin than the stored one is refused (`JudgedSettingsError`): one run's tallies come from one
judge.
"""

import logging
import math
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

from aiact.engine import extended_description
from aiact.eval.answers import AnswerSourceError, asked_questions, fixed_answers
from aiact.eval.cases import BenchmarkCase, QAItem
from aiact.eval.judge import (
    BACKUP_INPUT_USD_PER_MTOK,
    BACKUP_OUTPUT_USD_PER_MTOK,
    JEV_USD_PER_MTOK,
    MAX_OUTPUT_TOKENS,
    PRICED_BACKUP_MODEL,
    JudgeCheck,
    JudgeItem,
    backup_messages,
)
from aiact.eval.judged import (
    CheckScore,
    JudgedSettings,
    Judges,
    JudgeUnreachedError,
    Planned,
    citation_support_items,
    evidence_tag_items,
    is_judged,
    judge_plan,
    parse_settings,
    qa_answer,
    qa_support_item,
    stored_scores,
)
from aiact.eval.ragas_metrics import BENCHMARK as QA_BENCHMARK
from aiact.eval.ragas_metrics import source_text
from aiact.eval.runner import is_failed
from aiact.retrieval.provisions import AI_ACT_DOC_KEYS, ProvisionNotFoundError, get_provision
from aiact.schemas import ClassificationResult, Language, LawVersion

logger = logging.getLogger(__name__)

DEFAULT_MAX_COST_USD = 0.10
"""The project's worker cap (`cost_cap_usd`); a full pass asks for more on purpose."""
DEFAULT_CONCURRENCY = 4
MAX_CONCURRENCY = 16
CHARS_PER_TOKEN = 3
"""The estimate's tokens: three characters a token, as `judge.PROMPT_TOKENS_BOUND` counts."""
LAW_VERSIONS: Mapping[str, LawVersion] = MappingProxyType(
    {doc_key: version for version, doc_key in AI_ACT_DOC_KEYS.items()}
)

Plan = Mapping[JudgeCheck, Sequence[Planned]]
SourceReader = Callable[[Mapping[str, object], Language], str | None]
"""A stored hit (`{"doc_key", "provision_id"}`) → its text as the answer was given it, or None
when the corpus no longer has it."""
Asked = Mapping[str, Sequence[str]]
"""The follow-up question ids each case's result asked in an `--answers-from` source run."""


class JudgedRunNotFoundError(LookupError):
    """No `eval_runs` row has the requested id."""


class JudgedRowError(ValueError):
    """A stored row doesn't hold what judging expects; the message names the case only."""


class JudgedSettingsError(ValueError):
    """The run was judged before with another judge or margin."""


class JudgedStatus(StrEnum):
    COMPLETED = "completed"
    COST_CAP_REACHED = "cost_cap_reached"
    UNREACHED = "unreached"
    """The backup judge's call reached no model; the case it was on isn't stored."""


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
    asked: Asked | None = None
    """The source run's questions on an `--answers-from` run; None on a plain run."""


@dataclass(frozen=True)
class PlannedCase:
    case_id: str
    plan: Plan


@dataclass(frozen=True)
class JudgedOptions:
    """The command's options; `aiact evaluate judged` bounds them."""

    max_cost_usd: float = DEFAULT_MAX_COST_USD
    concurrency: int = DEFAULT_CONCURRENCY


@dataclass(frozen=True)
class JudgedSummary:
    status: JudgedStatus
    cases_planned: int
    cases_judged: int
    totals: Mapping[JudgeCheck, CheckScore]
    unstored_cost_usd: float = 0.0
    unstored_tokens: int = 0
    """What the case a call stopped (`UNREACHED`) spent; it isn't in `totals`."""

    @property
    def cost_usd(self) -> float:
        return sum(score.cost_usd for score in self.totals.values()) + self.unstored_cost_usd

    @property
    def tokens(self) -> int:
        return sum(score.tokens for score in self.totals.values()) + self.unstored_tokens


# --- planning ------------------------------------------------------------------------------------


def plan_run(run: StoredRun, read_source: SourceReader) -> tuple[PlannedCase, ...]:
    """The rows still to judge, each with its items; rows already judged or with nothing to
    judge (a failed classification or answer, a Q&A item with no answer) are left out."""
    todo = (row for row in run.rows if not is_judged(row.scores))
    planned = (
        PlannedCase(row.case_id, plan)
        for row in todo
        if (plan := plan_row(run, row, read_source)) is not None
    )
    return tuple(planned)


def plan_row(run: StoredRun, row: StoredRow, read_source: SourceReader) -> Plan | None:
    if is_failed(row.predicted):
        return None
    try:
        if run.benchmark == QA_BENCHMARK:
            return _qa_plan(row, read_source)
        return _classification_plan(row, run.asked)
    except ValidationError as exc:
        # The field paths only: pydantic's message would quote the stored texts.
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise JudgedRowError(
            f"case {row.case_id}: stored row is invalid at {', '.join(fields)}"
        ) from None


def _classification_plan(row: StoredRow, asked: Asked | None) -> Plan:
    case = BenchmarkCase.model_validate(row.label)
    result = ClassificationResult.model_validate(row.predicted)
    language = case.language
    return {
        JudgeCheck.CITATION_SUPPORT: citation_support_items(result, language),
        JudgeCheck.EVIDENCE_TAG: evidence_tag_items(result, engine_text(case, asked), language),
    }


def engine_text(case: BenchmarkCase, asked: Asked | None) -> str:
    """The text the engine read for `case`: its description, with the fixed answers to the
    questions the source run asked appended on an `--answers-from` run (decision 019), as the
    runner and the engine built it."""
    if asked is None:
        return case.description
    if case.id not in asked:
        raise JudgedRowError(f"case {case.id}: the answers' source run has no row for it")
    answers = fixed_answers(case, asked[case.id])
    return extended_description(case.description, answers, case.language)


def _qa_plan(row: StoredRow, read_source: SourceReader) -> Plan | None:
    """None for a row with no answer drawn from the sources (`qa_answer`). A source the corpus
    no longer has leaves the item not measured: the answer would be judged against part of what
    it was given."""
    item = QAItem.model_validate(row.label)
    found = qa_answer(row.predicted)
    if found is None:
        return None
    answer, retrieved = found
    sources = [read_source(hit, item.language) for hit in retrieved if isinstance(hit, Mapping)]
    texts = [source for source in sources if source]
    is_complete = len(texts) == len(retrieved)
    planned = qa_support_item(item.question, answer, texts, item.language) if is_complete else None
    return {JudgeCheck.QA_SUPPORT: (planned,)}


def sendable(planned: Sequence[PlannedCase]) -> list[tuple[JudgeCheck, JudgeItem]]:
    """Every item the plan would send (items that can't be sent left out), with its check."""
    return [
        (check, item)
        for case in planned
        for check, items in case.plan.items()
        for item in items
        if item is not None
    ]


def item_counts(planned: Sequence[PlannedCase]) -> dict[JudgeCheck, int]:
    """How many items each check would send (items that can't be sent left out)."""
    counts = {check: 0 for case in planned for check in case.plan}
    for check, _ in sendable(planned):
        counts = counts | {check: counts[check] + 1}
    return counts


def estimate_usd(planned: Sequence[PlannedCase], backup_model: str) -> float | None:
    """An estimate of the most judging `planned` can cost: each item's prompt sized from its
    texts at `CHARS_PER_TOKEN`, sent to Jev and to the backup judge as if every item were unsure,
    and the backup's longest answer. None for a backup model whose prices aren't known."""
    if backup_model != PRICED_BACKUP_MODEL:
        return None
    return sum(_item_estimate_usd(item) for _, item in sendable(planned))


def _item_estimate_usd(item: JudgeItem) -> float:
    chars = sum(len(message.text) for message in backup_messages(item))
    tokens = math.ceil(chars / CHARS_PER_TOKEN)
    prompt = tokens * (JEV_USD_PER_MTOK + BACKUP_INPUT_USD_PER_MTOK)
    return (prompt + MAX_OUTPUT_TOKENS * BACKUP_OUTPUT_USD_PER_MTOK) / 1_000_000


# --- judging -------------------------------------------------------------------------------------


class JudgedStore(Protocol):
    """Where judged tallies are written; `PostgresJudgedStore` in production."""

    def save_settings(self, run_id: UUID, settings: JudgedSettings) -> None:
        """Raises `JudgedSettingsError` when the run holds another judge's settings."""
        ...

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
    starts once `options.max_cost_usd` is spent. The backup judge's call reaching no model stops
    the pass; the case it was on isn't stored. The store refuses another judge's run
    (`save_settings`)."""
    store.save_settings(run.id, settings)
    totals: dict[JudgeCheck, CheckScore] = {}
    judged = 0
    for case in planned:
        if sum(score.cost_usd for score in totals.values()) >= options.max_cost_usd:
            return JudgedSummary(JudgedStatus.COST_CAP_REACHED, len(planned), judged, totals)
        try:
            scores = judge_plan(judge, case.plan, options.concurrency)
        except JudgeUnreachedError as exc:
            logger.warning("stopped before storing case %s: %s", case.case_id, exc)
            return JudgedSummary(
                JudgedStatus.UNREACHED, len(planned), judged, totals, exc.cost_usd, exc.tokens
            )
        store.save_case(run.id, case.case_id, stored_scores(scores))
        totals = {
            check: totals.get(check, CheckScore()) + scores.get(check, CheckScore())
            for check in totals.keys() | scores.keys()
        }
        judged += 1
    return JudgedSummary(JudgedStatus.COMPLETED, len(planned), judged, totals)


# --- the database --------------------------------------------------------------------------------


def load_run(conn: psycopg.Connection, run_id: UUID) -> StoredRun:
    """The run and its rows; on an `--answers-from` run, also the questions its source run
    asked. Raises `AnswerSourceError` when that source can't give them."""
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
        asked=_source_questions(conn, run_id, benchmark, config),
    )


def _source_questions(
    conn: psycopg.Connection, run_id: UUID, benchmark: str, config: object
) -> Asked | None:
    source = config.get("answers_from") if isinstance(config, Mapping) else None
    if source is None:
        return None
    try:
        source_id = UUID(str(source))
    except ValueError:
        raise AnswerSourceError(f"run {run_id}: config.answers_from is not a run id") from None
    return asked_questions(conn, source_id, benchmark)


class PostgresJudgedStore:
    """A `JudgedStore` over one psycopg connection; each write is its own short transaction."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def save_settings(self, run_id: UUID, settings: JudgedSettings) -> None:
        """Sets the run's judge unless another one is stored: checked in the update itself, so a
        second pass started with another judge at the same time can't mix the tallies."""
        judged = Jsonb(settings.model_dump(mode="json"))
        with self._connection.transaction():
            cursor = self._connection.execute(
                "update eval_runs set config = config || jsonb_build_object('judged', %s::jsonb)"
                " where id = %s and (config -> 'judged' is null or config -> 'judged' = %s::jsonb)",
                (judged, run_id, judged),
            )
            if cursor.rowcount != 1:
                raise JudgedSettingsError(
                    f"run {run_id} is missing or was judged with another judge: one run's "
                    "tallies come from one judge"
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
    the corpus has no German), as the Q&A run's search returned it (`ragas_metrics.source_text`).
    An AI Act provision is read from the text its document holds (`ai-act` the original,
    `ai-act-consolidated` the amended one on `as_of`)."""

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
        return source_text(
            provision_id, provision.document_title, provision.heading, provision.text
        )

    return read
