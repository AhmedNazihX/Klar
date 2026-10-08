"""X1a: compare embedding arms on retrieval (decision 003; INIT > Tech stack > Embeddings).

Three arms, each with its own vectors in `provision_embeddings` (`aiact corpus embed`):
Qwen3-Embedding-8B at 1536 and at 1024 dimensions (with the `EMBEDDING_QUERY_INSTRUCTION` task
text), and OpenAI text-embedding-3-large shortened to 1536 (not instruction-aware: queries go as
they are). Each arm searches both sets the way their callers search:
- **Annex matching** (X0, 48 items): the description, in its language, over the law only
  (`doc_types={"law"}`). A hit is relevant when it is a labelled Annex I or III point or lies
  under one; an ancestor (the area, the section, the whole annex) is not, as it doesn't pin the
  point. Naming any one of an item's accepted points counts, so recall is 1 or 0.
- **Q&A** (B7, the answerable items): the question over the whole corpus, as Q&A searches. A hit
  is relevant when it covers a required provision by V6's rule (`ragas_metrics.covers`: the
  provision itself or an ancestor, whose text includes its children's, C1; never a descendant),
  and recall is V6's `provision_recall` itself.

No search applies a relevance cut-off (`max_distance=None`): the cut-off is calibrated per arm
afterwards (X1b), so it mustn't tilt this comparison.

The metrics take the relevance verdict from the provision ids instead of a judge model, so they
cost nothing but the query embeddings and are exact:
- `context_precision`: the formula of RAGAS's (judged) context precision, the mean of precision@i
  over the ranks i of the relevant hits in the top `top_k` (0 when none is relevant), with id
  verdicts. It rewards relevant hits ranked high (RAGAS's own ID-based precision is plain set
  precision, which ignores the order).
- `context_recall`: ID-based recall with the hierarchy rules above: the share of the item's
  targets the top `top_k` hits cover (Annex: any one point, 1 or 0).
- `annex_recall_lenient` (Annex only): as `context_recall`, but the point's own area or section
  (`annex:III:4` for `annex:III:4:a`, `annex:I:A` for `annex:I:A:1`) also counts, never the whole
  annex. Search keeps the better-ranked of a parent and its children (`distinct_units`), so when
  an area row outranks its point the point is dropped although the area's text contains it; the
  strict recall then scores 0 for every arm alike. This shows how much of the gap that is.
- `reciprocal_rank`: 1 / the rank of the first relevant hit in the top `SEARCH_DEPTH`, else 0.
- `best_similarity`: the top meaning-arm hit's cosine similarity, for the cut-off (X1b) and for
  how compressed an arm's cosines are (B13's isolation limit).

The judged RAGAS metrics on the Q&A set (paid) run through `aiact evaluate ragas --arm …`
(`ragas_metrics.build_parts(embeddings=…)`). Each (arm, set) run writes one `eval_runs` row
(benchmark `embedding_annex_match` or `embedding_qa`) and one `eval_case_results` row per item.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import LiteralString
from uuid import UUID

import psycopg
from pydantic import JsonValue

from aiact.corpus.embed import ARMS as CORPUS_ARMS
from aiact.corpus.embed import EmbeddingArm
from aiact.engine.usage import UsageMeter
from aiact.eval.cases import BenchmarkCase, CaseLabel, QAItem
from aiact.eval.ragas_metrics import (
    covers,
    embedding_config,
    metric_means,
    provision_recall,
    scored_records,
)
from aiact.eval.runner import (
    ERROR_MESSAGE_LIMIT,
    CaseRecord,
    RunStatus,
    RunStore,
    finish_after_failure,
)
from aiact.llm.embeddings import EmbeddingError, OpenRouterEmbeddings
from aiact.retrieval.search import QueryEmbedder, SearchHit, SearchResults, search_ai_act
from aiact.schemas import Language
from aiact.settings import Settings

logger = logging.getLogger(__name__)

CONTEXT_PRECISION = "context_precision"
CONTEXT_RECALL = "context_recall"
ANNEX_RECALL_LENIENT = "annex_recall_lenient"
RECIPROCAL_RANK = "reciprocal_rank"
BEST_SIMILARITY = "best_similarity"
METRICS = (
    CONTEXT_PRECISION,
    CONTEXT_RECALL,
    ANNEX_RECALL_LENIENT,
    RECIPROCAL_RANK,
    BEST_SIMILARITY,
)

DEFAULT_TOP_K = 5
"""Hits judged for precision and recall: what a Q&A answer is grounded on (V6's baseline)."""
SEARCH_DEPTH = 20
"""Hits fetched per query, for the rank of the first relevant one."""
DEFAULT_MAX_COST_USD = 0.05
"""For a whole command: query embeddings only, all three arms on both sets cost under a cent."""
SEARCH_NODE = "search"
LAW_ONLY = frozenset({"law"})
AREA_DEPTH = 3
"""Id parts of an Annex area or section (`annex:III:4`, `annex:I:A`); the whole annex has 2."""


class ExperimentSet(StrEnum):
    ANNEX_MATCH = "annex_match"
    QA = "qa"

    @property
    def benchmark(self) -> str:
        """The `eval_runs.benchmark` name."""
        return f"embedding_{self.value}"


@dataclass(frozen=True)
class Arm:
    """One embedding arm under comparison."""

    corpus: EmbeddingArm
    dims: int
    is_instruction_aware: bool
    """Qwen3 takes the query instruction; OpenAI's model gets the query as it is."""


ARMS: Mapping[str, Arm] = {
    "qwen3-1536": Arm(CORPUS_ARMS["qwen3"], 1536, is_instruction_aware=True),
    "qwen3-1024": Arm(CORPUS_ARMS["qwen3"], 1024, is_instruction_aware=True),
    "openai3l-1536": Arm(CORPUS_ARMS["openai3l"], 1536, is_instruction_aware=False),
}


class ArmNotEmbeddedError(RuntimeError):
    """The corpus has no current vectors, or not all of them, for the arm."""


COUNT_CURRENT: LiteralString = """
    select count(*) from provision_embeddings e
    join provisions p on p.id = e.provision_row_id and p.content_sha256 = e.content_sha256
    where e.model = %(model)s and e.dims = %(dims)s
"""
# The rows `aiact corpus embed` embeds for the arm: those within its input limit, measured on
# the text it sends (`corpus.embed.input_text`: the heading, a newline, the body).
COUNT_IN_SCOPE: LiteralString = """
    select count(*) from provisions p
    where length(case when coalesce(p.heading, '') = '' then p.text
                      else p.heading || E'\\n' || p.text end) <= %(max_chars)s
"""


def require_embedded(connection: psycopg.Connection, arm_name: str) -> None:
    """Raise `ArmNotEmbeddedError` unless every provision row the arm can embed has a current
    vector: a missing one can't be found by meaning and would score the arm as if it were bad."""
    arm = ARMS[arm_name]
    params = {"model": arm.corpus.model, "dims": arm.dims, "max_chars": arm.corpus.max_input_chars}
    current = _count(connection, COUNT_CURRENT, params)
    in_scope = _count(connection, COUNT_IN_SCOPE, params)
    if current == 0 or current < in_scope:  # an empty corpus (as in CI) has nothing to search
        model = next(key for key, value in CORPUS_ARMS.items() if value == arm.corpus)
        raise ArmNotEmbeddedError(
            f"{arm_name} has current vectors for {current} of {in_scope} provision rows; run "
            f"`aiact corpus embed --model {model} --dims {arm.dims}` first (paid)"
        )


def _count(
    connection: psycopg.Connection, statement: LiteralString, params: dict[str, object]
) -> int:
    row = connection.execute(statement, params).fetchone()
    return row[0] if row else 0


def build_embeddings(
    arm: Arm, *, instruction: str | None = None, settings: Settings | None = None
) -> OpenRouterEmbeddings:
    """The arm's client: its model, pinned provider and size; an instruction-aware arm takes
    `instruction` (default: `EMBEDDING_QUERY_INSTRUCTION`), the other none."""
    return OpenRouterEmbeddings(
        model=arm.corpus.model,
        provider=arm.corpus.provider,
        dimensions=arm.dims,
        query_instruction=instruction if arm.is_instruction_aware else "",
        settings=settings,
    )


@dataclass(frozen=True)
class Query:
    """One item to search: its text, where to search, and the provisions that answer it."""

    id: str
    text: str
    language: Language
    experiment_set: ExperimentSet
    targets: tuple[str, ...]
    doc_types: frozenset[str] | None
    label: dict[str, JsonValue]


def annex_queries(cases: Sequence[BenchmarkCase]) -> tuple[Query, ...]:
    """The Annex-matching cases as law-only searches for their labelled points, in id order."""
    queries: list[Query] = []
    for case in sorted(cases, key=lambda case: case.id):
        if not isinstance(case.label, CaseLabel) or not case.label.annex_point:
            raise ValueError(f"Annex-matching case {case.id} has no annex_point")
        queries.append(
            Query(
                id=case.id,
                text=case.description,
                language=case.language,
                experiment_set=ExperimentSet.ANNEX_MATCH,
                targets=case.label.annex_point,
                doc_types=LAW_ONLY,
                label=case.model_dump(mode="json"),
            )
        )
    return tuple(queries)


def qa_queries(items: Sequence[QAItem]) -> tuple[Query, ...]:
    """The answerable Q&A items as whole-corpus searches for their required provisions."""
    return tuple(
        Query(
            id=item.id,
            text=item.question,
            language=item.language,
            experiment_set=ExperimentSet.QA,
            targets=item.required_provision_ids,
            doc_types=None,
            label=item.model_dump(mode="json"),
        )
        for item in sorted(items, key=lambda item: item.id)
        if item.answerable
    )


def is_at_or_under(hit_id: str, point: str) -> bool:
    """Whether a hit is the point or lies under it (`annex:III:5:b:i` under `annex:III:5:b`)."""
    return hit_id == point or hit_id.startswith(f"{point}:")


def is_relevant(query: Query, hit_id: str) -> bool:
    """Annex: the hit is a labelled point or under one. Q&A: it covers a required provision by
    V6's rule (the provision or an ancestor of it)."""
    if query.experiment_set is ExperimentSet.ANNEX_MATCH:
        return any(is_at_or_under(hit_id, point) for point in query.targets)
    return any(covers(hit_id, provision) for provision in query.targets)


def area_of(point: str) -> str | None:
    """The point's own area or section (`annex:III:4` for `annex:III:4:a`), or None when its
    parent is the whole annex (`annex:III:2`)."""
    parent = point.rsplit(":", 1)[0]
    return parent if parent.count(":") >= AREA_DEPTH - 1 else None


def context_precision(verdicts: Sequence[bool]) -> float:
    """RAGAS context precision's formula over ranked verdicts: the mean of precision@i at each
    relevant rank i; 0 when no hit is relevant."""
    relevant = 0
    total = 0.0
    for rank, verdict in enumerate(verdicts, start=1):
        if verdict:
            relevant += 1
            total += relevant / rank
    return total / relevant if relevant else 0.0


def context_recall(query: Query, hits: Sequence[SearchHit]) -> float:
    """Annex: 1 when a hit is (or is under) any accepted point, else 0. Q&A: V6's
    `provision_recall`, the share of the required provisions the hits cover."""
    if query.experiment_set is ExperimentSet.QA:
        return provision_recall(query.targets, hits)
    return 1.0 if any(is_relevant(query, hit.provision_id) for hit in hits) else 0.0


def annex_recall_lenient(query: Query, hit_ids: Sequence[str]) -> float:
    """1 when a hit is an accepted point, under one, or the point's own area or section (never
    the whole annex); else 0."""
    areas = {area for point in query.targets if (area := area_of(point)) is not None}
    found = any(hit in areas or is_relevant(query, hit) for hit in hit_ids)
    return 1.0 if found else 0.0


def reciprocal_rank(verdicts: Sequence[bool]) -> float:
    """1 / the rank of the first relevant hit; 0 when none is."""
    return next((1.0 / rank for rank, verdict in enumerate(verdicts, start=1) if verdict), 0.0)


def query_scores(query: Query, hits: Sequence[SearchHit], top_k: int) -> dict[str, float | None]:
    """The metrics of one query's ranked hits (see the module docstring); the lenient Annex
    recall is None for Q&A."""
    hit_ids = [hit.provision_id for hit in hits]
    verdicts = [is_relevant(query, hit) for hit in hit_ids]
    similarities = [hit.similarity for hit in hits if hit.similarity is not None]
    is_annex = query.experiment_set is ExperimentSet.ANNEX_MATCH
    return {
        CONTEXT_PRECISION: context_precision(verdicts[:top_k]),
        CONTEXT_RECALL: context_recall(query, hits[:top_k]),
        ANNEX_RECALL_LENIENT: annex_recall_lenient(query, hit_ids[:top_k]) if is_annex else None,
        RECIPROCAL_RANK: reciprocal_rank(verdicts),
        BEST_SIMILARITY: max(similarities) if similarities else None,
    }


@dataclass(frozen=True)
class ExperimentOptions:
    git_sha: str
    is_git_dirty: bool = False
    top_k: int = DEFAULT_TOP_K
    max_cost_usd: float = DEFAULT_MAX_COST_USD
    """For every run sharing one meter (a whole `evaluate embeddings` command)."""

    def __post_init__(self) -> None:
        if not 1 <= self.top_k <= SEARCH_DEPTH:
            raise ValueError(f"top_k must be between 1 and {SEARCH_DEPTH}")
        if self.max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be positive")


@dataclass(frozen=True)
class ArmSummary:
    run_id: UUID
    arm: str
    experiment_set: ExperimentSet
    status: RunStatus
    cases_planned: int
    cases_scored: int
    cases_failed: int
    cost_usd: float
    tokens: int
    means: Mapping[str, float | None]


Search = Callable[..., SearchResults]


def is_over_budget(meter: UsageMeter, max_cost_usd: float) -> bool:
    """The cap is reached, or a call came without its cost, so what was spent is unknown."""
    usage = meter.usage()
    return not usage.is_cost_complete or usage.cost_usd >= max_cost_usd


def run_arm(
    arm_name: str,
    experiment_set: ExperimentSet,
    queries: Sequence[Query],
    embeddings: OpenRouterEmbeddings,
    store: RunStore,
    options: ExperimentOptions,
    *,
    meter: UsageMeter | None = None,
    connection: psycopg.Connection | None = None,
    search: Search = search_ai_act,
) -> ArmSummary:
    """Search every query with one arm, score it and record the run. A failed query embedding
    is an `is_error` row and the run goes on. Before each query the cap is checked against
    `meter`, which the caller shares across its runs so the cap covers them all."""
    meter = meter or UsageMeter()
    embedder = meter.embedder(SEARCH_NODE, embeddings)
    config = run_config(arm_name, embeddings, options)
    run_id = store.start_run(options.git_sha, experiment_set.benchmark, config)
    records: list[CaseRecord] = []
    status = RunStatus.COMPLETED
    try:
        for query in queries:
            if is_over_budget(meter, options.max_cost_usd):
                status = RunStatus.COST_CAP_REACHED
                break
            record = _score_query(query, embedder, meter, options.top_k, connection, search)
            store.add_case(run_id, record)
            records.append(record)
    except BaseException:
        outcome = run_outcome(RunStatus.INTERRUPTED, queries, records, meter)
        finish_after_failure(store, run_id, outcome)
        raise
    store.finish_run(run_id, run_outcome(status, queries, records, meter))
    scored = scored_records(records)
    return ArmSummary(
        run_id=run_id,
        arm=arm_name,
        experiment_set=experiment_set,
        status=status,
        cases_planned=len(queries),
        cases_scored=len(scored),
        cases_failed=len(records) - len(scored),
        cost_usd=sum(record.cost_usd for record in records),
        tokens=sum(record.tokens for record in records),
        means=metric_means(records, METRICS),
    )


def run_config(
    arm_name: str, embeddings: OpenRouterEmbeddings, options: ExperimentOptions
) -> dict[str, JsonValue]:
    """`eval_runs.config`: no judge model, the arm, and how it searched."""
    return {
        "model": None,
        "arm": arm_name,
        "embedding": embedding_config(embeddings),
        "retrieval": {
            "search": "search_ai_act",
            "top_k": options.top_k,
            "depth": SEARCH_DEPTH,
            "max_distance": None,
        },
        "metrics": list(METRICS),
        "max_cost_usd": options.max_cost_usd,
        "git_dirty": options.is_git_dirty,
        "outcome": {"status": RunStatus.RUNNING.value},
    }


def _score_query(
    query: Query,
    embedder: QueryEmbedder,
    meter: UsageMeter,
    top_k: int,
    connection: psycopg.Connection | None,
    search: Search,
) -> CaseRecord:
    before = meter.usage()
    try:
        results = search(
            query.text,
            query.language,
            doc_types=query.doc_types,
            max_distance=None,
            limit=SEARCH_DEPTH,
            embedder=embedder,
            connection=connection,
        )
    except EmbeddingError as exc:
        logger.warning("query %s failed: %s", query.id, type(exc).__name__)
        predicted: dict[str, JsonValue] = {
            "error": {"type": type(exc).__name__, "message": str(exc)[:ERROR_MESSAGE_LIMIT]}
        }
        scores: dict[str, float | bool | None] = {"is_error": True}
    else:
        retrieved: list[JsonValue] = [hit.provision_id for hit in results.hits]
        predicted = {"retrieved": retrieved}
        scores = {**query_scores(query, results.hits, top_k), "is_error": False}
    after = meter.usage()
    cost_usd = after.cost_usd - before.cost_usd
    tokens = after.tokens - before.tokens
    return CaseRecord(
        case_id=query.id,
        predicted=predicted,
        label=query.label,
        scores={**scores, "cost_usd": cost_usd, "tokens": tokens},
        trace_id=None,
        cost_usd=cost_usd,
        tokens=tokens,
    )


def run_outcome(
    status: RunStatus, queries: Sequence[Query], records: Sequence[CaseRecord], meter: UsageMeter
) -> dict[str, JsonValue]:
    """`eval_runs.config.outcome`: the status, counts, this run's cost, and the means overall and
    per language (German retrieval is a known weak spot)."""
    scored = scored_records(records)
    languages = {query.id: query.language.value for query in queries}
    by_language: dict[str, JsonValue] = {
        language.value: dict(
            metric_means([r for r in scored if languages[r.case_id] == language.value], METRICS)
        )
        for language in Language
    }
    return {
        "status": status.value,
        "finished_at": datetime.now(UTC).isoformat(),
        "cases_planned": len(queries),
        "cases_scored": len(scored),
        "cases_failed": len(records) - len(scored),
        "cost_usd": sum(record.cost_usd for record in records),
        "tokens": sum(record.tokens for record in records),
        "is_cost_complete": meter.usage().is_cost_complete,
        "means": dict(metric_means(records, METRICS)),
        "means_by_language": by_language,
    }
