"""X1a: compare embedding arms on retrieval (decision 003; INIT > Tech stack > Embeddings).

Three arms, each with its own vectors in `provision_embeddings` (`aiact corpus embed`):
Qwen3-Embedding-8B at 1536 and at 1024 dimensions (with the `EMBEDDING_QUERY_INSTRUCTION` task
text), and OpenAI text-embedding-3-large shortened to 1536 (not instruction-aware: queries go as
they are). Each arm searches both sets the way their callers search:
- **Annex matching** (X0, 48 items): the description, in its language, over the law only
  (`doc_types={"law"}`). A hit is relevant when it is a labelled Annex point or lies under one;
  an ancestor (the area, the whole annex) is not, as it doesn't pin the point. Naming any one of
  an item's accepted points counts, so recall is 1 or 0.
- **Q&A** (B7, the answerable items): the question over the whole corpus, as Q&A searches. A hit
  is relevant when it is a required provision, under one, or above one (a parent row's text
  includes its children's, C1), as V6's `provision_recall` counts it.

No search applies a relevance cut-off (`max_distance=None`): the cut-off is calibrated per arm
afterwards (X1b), so it mustn't tilt this comparison.

The metrics follow RAGAS's definitions with the relevance verdict taken from the provision ids
instead of a judge model (RAGAS's ID-based context metrics), so they cost nothing but the query
embeddings and are exact:
- `context_precision`: RAGAS context precision, the average of precision@i over the ranks i of
  the relevant hits in the top `top_k` (0 when none is relevant): rewards relevant hits ranked
  high.
- `context_recall`: the share of the item's targets the top `top_k` hits cover (Annex: any one).
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
from uuid import UUID

import psycopg
from pydantic import JsonValue

from aiact.corpus.embed import ARMS as CORPUS_ARMS
from aiact.corpus.embed import EmbeddingArm
from aiact.engine.usage import UsageMeter
from aiact.eval.cases import BenchmarkCase, CaseLabel, QAItem
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
RECIPROCAL_RANK = "reciprocal_rank"
BEST_SIMILARITY = "best_similarity"
METRICS = (CONTEXT_PRECISION, CONTEXT_RECALL, RECIPROCAL_RANK, BEST_SIMILARITY)

DEFAULT_TOP_K = 5
"""Hits judged for precision and recall: what a Q&A answer is grounded on (V6's baseline)."""
SEARCH_DEPTH = 20
"""Hits fetched per query, for the rank of the first relevant one."""
DEFAULT_MAX_COST_USD = 0.05
"""Query embeddings only: a full run of all three arms costs well under a cent."""
SEARCH_NODE = "search"
LAW_ONLY = frozenset({"law"})


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
    """The corpus has no vectors for the arm yet."""


COUNT_ARM = "select count(*) from provision_embeddings where model = %(model)s and dims = %(dims)s"


def require_embedded(connection: psycopg.Connection, arm_name: str) -> None:
    """Raise `ArmNotEmbeddedError` unless the corpus has vectors for the arm: a search would
    otherwise find nothing by meaning and score the arm as if it were bad."""
    arm = ARMS[arm_name]
    row = connection.execute(COUNT_ARM, {"model": arm.corpus.model, "dims": arm.dims}).fetchone()
    if not row or row[0] == 0:
        model = next(key for key, value in CORPUS_ARMS.items() if value == arm.corpus)
        raise ArmNotEmbeddedError(
            f"no corpus vectors for {arm_name}; run `aiact corpus embed --model {model} "
            f"--dims {arm.dims}` first (paid)"
        )


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


def embedding_config(embeddings: OpenRouterEmbeddings) -> dict[str, JsonValue]:
    """`eval_runs.config.embedding`: the arm as it ran."""
    return {
        "model": embeddings.model,
        "provider": embeddings.provider,
        "dimensions": embeddings.dimensions,
        "query_instruction": embeddings.query_instruction or None,
    }


@dataclass(frozen=True)
class Query:
    """One item to search: its text, where to search, and the provisions that answer it."""

    id: str
    text: str
    language: Language
    targets: tuple[str, ...]
    is_any_target: bool
    """True: covering any one target is full recall (Annex points); False: each counts."""
    is_strict: bool
    """True: only a target or a provision under it is relevant, never an ancestor."""
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
                targets=case.label.annex_point,
                is_any_target=True,
                is_strict=True,
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
            targets=item.required_provision_ids,
            is_any_target=False,
            is_strict=False,
            doc_types=None,
            label=item.model_dump(mode="json"),
        )
        for item in sorted(items, key=lambda item: item.id)
        if item.answerable
    )


def is_relevant(hit_id: str, targets: Sequence[str], *, is_strict: bool) -> bool:
    """Whether a hit is one of `targets` or lies under one (`annex:III:1:a:i` under
    `annex:III:1:a`), or, unless strict, lies above one (`art:5:1` above `art:5:1:f`)."""
    return any(
        hit_id == target
        or hit_id.startswith(f"{target}:")
        or (not is_strict and target.startswith(f"{hit_id}:"))
        for target in targets
    )


def context_precision(verdicts: Sequence[bool]) -> float:
    """RAGAS context precision over ranked verdicts: the mean of precision@i at each relevant
    rank i; 0 when no hit is relevant."""
    relevant = 0
    total = 0.0
    for rank, verdict in enumerate(verdicts, start=1):
        if verdict:
            relevant += 1
            total += relevant / rank
    return total / relevant if relevant else 0.0


def context_recall(query: Query, hit_ids: Sequence[str]) -> float:
    """The share of the query's targets the hits cover; for an any-target query, 1 or 0."""
    covered = [
        target
        for target in query.targets
        if any(is_relevant(hit, (target,), is_strict=query.is_strict) for hit in hit_ids)
    ]
    if query.is_any_target:
        return 1.0 if covered else 0.0
    return len(covered) / len(query.targets)


def reciprocal_rank(verdicts: Sequence[bool]) -> float:
    """1 / the rank of the first relevant hit; 0 when none is."""
    return next((1.0 / rank for rank, verdict in enumerate(verdicts, start=1) if verdict), 0.0)


def query_scores(query: Query, hits: Sequence[SearchHit], top_k: int) -> dict[str, float | None]:
    """The four metrics of one query's ranked hits (see the module docstring)."""
    hit_ids = [hit.provision_id for hit in hits]
    verdicts = [is_relevant(hit, query.targets, is_strict=query.is_strict) for hit in hit_ids]
    similarities = [hit.similarity for hit in hits if hit.similarity is not None]
    return {
        CONTEXT_PRECISION: context_precision(verdicts[:top_k]),
        CONTEXT_RECALL: context_recall(query, hit_ids[:top_k]),
        RECIPROCAL_RANK: reciprocal_rank(verdicts),
        BEST_SIMILARITY: max(similarities) if similarities else None,
    }


@dataclass(frozen=True)
class ExperimentOptions:
    git_sha: str
    is_git_dirty: bool = False
    top_k: int = DEFAULT_TOP_K
    max_cost_usd: float = DEFAULT_MAX_COST_USD

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


def run_arm(
    arm_name: str,
    experiment_set: ExperimentSet,
    queries: Sequence[Query],
    embeddings: OpenRouterEmbeddings,
    store: RunStore,
    options: ExperimentOptions,
    *,
    connection: psycopg.Connection | None = None,
    search: Search = search_ai_act,
) -> ArmSummary:
    """Search every query with one arm, score it and record the run. A failed query embedding
    is an `is_error` row and the run goes on; the cost cap is checked before each query."""
    meter = UsageMeter()
    embedder = meter.embedder(SEARCH_NODE, embeddings)
    config = run_config(arm_name, embeddings, options)
    run_id = store.start_run(options.git_sha, experiment_set.benchmark, config)
    records: list[CaseRecord] = []
    status = RunStatus.COMPLETED
    try:
        for query in queries:
            if meter.usage().cost_usd >= options.max_cost_usd:
                status = RunStatus.COST_CAP_REACHED
                break
            record = _score_query(query, embedder, meter, options.top_k, connection, search)
            store.add_case(run_id, record)
            records.append(record)
    except BaseException:
        finish_after_failure(store, run_id, run_outcome(RunStatus.INTERRUPTED, queries, records))
        raise
    outcome = run_outcome(status, queries, records)
    store.finish_run(run_id, outcome)
    usage = meter.usage()
    return ArmSummary(
        run_id=run_id,
        arm=arm_name,
        experiment_set=experiment_set,
        status=status,
        cases_planned=len(queries),
        cases_scored=len(_scored(records)),
        cases_failed=len(records) - len(_scored(records)),
        cost_usd=usage.cost_usd,
        tokens=usage.tokens,
        means=metric_means(_scored(records)),
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


def _scored(records: Sequence[CaseRecord]) -> list[CaseRecord]:
    return [record for record in records if record.scores["is_error"] is False]


def metric_means(records: Sequence[CaseRecord]) -> dict[str, float | None]:
    """Each metric's mean over the records that have a number for it; None when none has."""
    means: dict[str, float | None] = {}
    for metric in METRICS:
        values = [
            float(value)
            for record in records
            if isinstance(value := record.scores.get(metric), int | float)
            and not isinstance(value, bool)
        ]
        means[metric] = sum(values) / len(values) if values else None
    return means


def run_outcome(
    status: RunStatus, queries: Sequence[Query], records: Sequence[CaseRecord]
) -> dict[str, JsonValue]:
    """`eval_runs.config.outcome`: the status, counts, cost, and the means overall and per
    language (German retrieval is a known weak spot)."""
    scored = _scored(records)
    languages = {query.id: query.language.value for query in queries}
    by_language: dict[str, JsonValue] = {
        language.value: dict(
            metric_means([r for r in scored if languages[r.case_id] == language.value])
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
        "means": dict(metric_means(scored)),
        "means_by_language": by_language,
    }
