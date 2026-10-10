"""RAGAS metrics on the Q&A set: retrieval quality and answer support (V6; INIT > Metrics,
Retrieval and Q&A quality).

For each answerable Q&A item (B7) the question is searched as Q&A would search it
(`search_ai_act`, the top `DEFAULT_TOP_K` hits; held-out examples never retrievable), answered
from those hits alone, and scored:
- `context_precision`: RAGAS context precision against the reference answer: are the hits that
  help ranked above the noise?
- `context_recall`: RAGAS context recall: the share of the reference answer's claims the hits
  support.
- `faithfulness`: RAGAS faithfulness: the share of the answer's claims the hits support.
- `provision_recall`: no model: the share of the item's required provisions found among the
  AI Act hits. A hit covers its own provision and every provision under it, since a parent row's
  text includes its children's (C1).

The three RAGAS metrics run on the RAGAS model (`aiact.llm.ragas_llm`; Gemini 3.1 Flash-Lite by
default). Until P7's Q&A exists, the answer comes from `PlainAnswerer`, one retrieval-grounded
prompt on the same route; P7 passes its own `Answerer` to record faithfulness on its answers,
and X1a passes another embedder to compare embedding arms. Unanswerable items have no reference
answer, so they are left out (C8 and X1 calibrate the relevance cut-off on them).

A run writes one `eval_runs` row (benchmark `qa`) and one `eval_case_results` row per item:
`label` is the item, `predicted` the answer and the provisions retrieved (or `{"error": …}`,
with the retrieved provisions when only a model call failed), `scores` the four metrics plus the
runner's `cost_usd`, `tokens` and `is_error`. The run's outcome holds each metric's mean over the
items scored without error, and what the run spent in all. A cost cap is checked before each item.

Importing this module is cheap: RAGAS and the OpenAI SDK (the `eval` dependency group) load only
when a real run is built (`build_parts`, `RagasScorer.from_llm`).
"""

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.util import find_spec
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from langchain_core.language_models import BaseChatModel
from pydantic import JsonValue

from aiact.engine.usage import UsageMeter
from aiact.eval.cases import QAItem
from aiact.eval.runner import (
    ERROR_MESSAGE_LIMIT,
    CaseRecord,
    RunStatus,
    RunStore,
    finish_after_failure,
    select_subset,
)
from aiact.llm.embeddings import OpenRouterEmbeddings
from aiact.retrieval.search import (
    FROM_SETTINGS,
    QueryEmbedder,
    SearchHit,
    SearchResults,
    search_ai_act,
)
from aiact.settings import Settings, get_settings

if TYPE_CHECKING:
    from ragas.llms import InstructorBaseRagasLLM
    from ragas.metrics.result import MetricResult

logger = logging.getLogger(__name__)

BENCHMARK = "qa"
CONTEXT_PRECISION = "context_precision"
CONTEXT_RECALL = "context_recall"
FAITHFULNESS = "faithfulness"
PROVISION_RECALL = "provision_recall"
METRICS = (CONTEXT_PRECISION, CONTEXT_RECALL, FAITHFULNESS, PROVISION_RECALL)

DEFAULT_TOP_K = 5
"""Hits per question: what a Q&A answer would be grounded on."""
MAX_TOP_K = 20
"""The most hits per question `aiact evaluate ragas` accepts (each one is a judged context)."""
DEFAULT_MAX_COST_USD = 0.5
"""About twice a full run of the 29 answerable items (a 2-item check cost $0.007 per item)."""
ANSWER_MAX_TOKENS = 1024
MODEL_NODE = "ragas_model"
"""The usage-meter node for every call on the RAGAS route (answers and metrics)."""
SEARCH_NODE = "search"
EVAL_GROUP_HINT = (
    "RAGAS is not installed; install the eval dependency group with `uv sync` "
    "(from backend/; a runtime install with --no-default-groups leaves it out)"
)

ANSWER_PROMPT = """\
Answer the question about the EU AI Act using only the provisions below. Name the provision ids \
you rely on, such as art:5:1:f. If the provisions don't answer the question, say so instead of \
answering from memory. Answer in {language_name}, in at most 150 words.

Provisions:
{contexts}

Question: {question}"""
LANGUAGE_NAMES = {"en": "English", "de": "German"}

Score = float | bool | None


class RagasNotInstalledError(RuntimeError):
    """The `eval` dependency group (RAGAS, the OpenAI SDK) is not installed."""


def require_ragas() -> None:
    """Raise `RagasNotInstalledError` unless RAGAS and the OpenAI SDK can be imported."""
    if find_spec("ragas") is None or find_spec("openai") is None:
        raise RagasNotInstalledError(EVAL_GROUP_HINT)


class Retriever(Protocol):
    """Finds the hits a question's answer is grounded on; describes itself for `eval_runs`."""

    def __call__(self, item: QAItem) -> Sequence[SearchHit]: ...

    def config(self) -> JsonValue: ...


class Answerer(Protocol):
    """Answers a question from the retrieved contexts only."""

    @property
    def name(self) -> str:
        """How `eval_runs.config` names it."""
        ...

    async def answer(self, item: QAItem, contexts: Sequence[str]) -> str: ...


class Scorer(Protocol):
    """The model-judged metrics of one answered item."""

    async def score(
        self, item: QAItem, contexts: Sequence[str], answer: str
    ) -> Mapping[str, float | None]: ...


@dataclass(frozen=True)
class SearchRetriever:
    """`search_ai_act` with Pile B excluded (decision 012) and the settings' relevance cut-off,
    or none (`is_cut_off` False) when X1a compares another embedding arm: the setting is
    calibrated for the default arm only."""

    top_k: int = DEFAULT_TOP_K
    embedder: QueryEmbedder | None = None
    search: Callable[..., SearchResults] = search_ai_act
    is_cut_off: bool = True

    def __call__(self, item: QAItem) -> Sequence[SearchHit]:
        results = self.search(
            item.question,
            item.language,
            limit=self.top_k,
            embedder=self.embedder,
            max_distance=FROM_SETTINGS if self.is_cut_off else None,
        )
        return results.hits

    def config(self) -> JsonValue:
        return {
            "search": "search_ai_act",
            "top_k": self.top_k,
            "max_distance": get_settings().search_max_distance if self.is_cut_off else None,
        }


@dataclass(frozen=True)
class PlainAnswerer:
    """One retrieval-grounded prompt on the RAGAS route: a stand-in for P7's Q&A. Every reply's
    cost is counted on `meter`."""

    chat: BaseChatModel
    meter: UsageMeter
    name: str = "plain_rag"

    async def answer(self, item: QAItem, contexts: Sequence[str]) -> str:
        prompt = ANSWER_PROMPT.format(
            language_name=LANGUAGE_NAMES[item.language.value],
            contexts="\n\n".join(contexts),
            question=item.question,
        )
        reply = await self.chat.ainvoke(
            prompt, config={"callbacks": [self.meter.chat_callback(MODEL_NODE)]}
        )
        text = reply.text.strip()
        if not text:
            raise ValueError("the answer model returned no text")
        return text


class PrecisionMetric(Protocol):
    async def ascore(
        self, user_input: str, reference: str, retrieved_contexts: list[str]
    ) -> "MetricResult": ...


class RecallMetric(Protocol):
    async def ascore(
        self, user_input: str, retrieved_contexts: list[str], reference: str
    ) -> "MetricResult": ...


class FaithfulnessMetric(Protocol):
    async def ascore(
        self, user_input: str, response: str, retrieved_contexts: list[str]
    ) -> "MetricResult": ...


@dataclass(frozen=True)
class RagasScorer:
    """Context precision (with reference), context recall and faithfulness, run together."""

    precision: PrecisionMetric
    recall: RecallMetric
    faithfulness: FaithfulnessMetric

    @classmethod
    def from_llm(cls, llm: "InstructorBaseRagasLLM") -> "RagasScorer":
        from ragas.metrics.collections import (
            ContextPrecisionWithReference,
            ContextRecall,
            Faithfulness,
        )

        return cls(
            ContextPrecisionWithReference(llm=llm), ContextRecall(llm=llm), Faithfulness(llm=llm)
        )

    async def score(
        self, item: QAItem, contexts: Sequence[str], answer: str
    ) -> Mapping[str, float | None]:
        reference = reference_answer(item)
        retrieved = list(contexts)
        precision, recall, faithfulness = await asyncio.gather(
            self.precision.ascore(
                user_input=item.question, reference=reference, retrieved_contexts=retrieved
            ),
            self.recall.ascore(
                user_input=item.question, retrieved_contexts=retrieved, reference=reference
            ),
            self.faithfulness.ascore(
                user_input=item.question, response=answer, retrieved_contexts=retrieved
            ),
        )
        return {
            CONTEXT_PRECISION: finite(precision.value),
            CONTEXT_RECALL: finite(recall.value),
            FAITHFULNESS: finite(faithfulness.value),
        }


async def _nothing_to_close() -> None:
    return None


@dataclass(frozen=True)
class RagasParts:
    """Everything a run calls, the model it is judged by (for `eval_runs.config`), and what
    to close when the run ends."""

    retriever: Retriever
    answerer: Answerer
    scorer: Scorer
    meter: UsageMeter
    model: str
    provider: str
    embedding: JsonValue = None
    aclose: Callable[[], Awaitable[None]] = field(default=_nothing_to_close)


def embedding_config(embeddings: OpenRouterEmbeddings) -> dict[str, JsonValue]:
    """`eval_runs.config.embedding`: the arm as it ran."""
    return {
        "model": embeddings.model,
        "provider": embeddings.provider,
        "dimensions": embeddings.dimensions,
        "query_instruction": embeddings.query_instruction or None,
    }


def build_parts(
    top_k: int = DEFAULT_TOP_K,
    settings: Settings | None = None,
    *,
    embeddings: OpenRouterEmbeddings | None = None,
    is_cut_off: bool = True,
) -> RagasParts:
    """The real run: the RAGAS route, the embedding arm, one meter. Without `embeddings` the
    configured arm searches with the `SEARCH_MAX_DISTANCE` cut-off, unless `is_cut_off` is False
    (to compare with a run from before X1b calibrated it, such as V6's c358b1e3); an arm X1a
    passes always searches without one. Build new parts for each run: the run closes the
    model's client when it ends.

    Raises `RagasNotInstalledError` without the `eval` group, and `LLMConfigError` when the API
    key or an `EMBEDDING_*` setting is not set.
    """
    require_ragas()
    # Imported here: it loads RAGAS and the OpenAI SDK, which only the `eval` group installs.
    from aiact.llm.ragas_llm import ragas_chat_model, ragas_model

    settings = settings or get_settings()
    meter = UsageMeter()
    model = ragas_model(
        lambda cost, tokens: meter.add(MODEL_NODE, cost, tokens, settings.ragas_model),
        settings=settings,
    )
    is_default_arm = embeddings is None
    embeddings = embeddings or OpenRouterEmbeddings(settings=settings)
    return RagasParts(
        retriever=SearchRetriever(
            top_k,
            meter.embedder(SEARCH_NODE, embeddings),
            is_cut_off=is_cut_off and is_default_arm,
        ),
        answerer=PlainAnswerer(
            ragas_chat_model(max_tokens=ANSWER_MAX_TOKENS, settings=settings), meter
        ),
        scorer=RagasScorer.from_llm(model.llm),
        meter=meter,
        model=model.model,
        provider=model.provider,
        embedding=embedding_config(embeddings),
        aclose=model.aclose,
    )


@dataclass(frozen=True)
class RagasOptions:
    git_sha: str
    is_git_dirty: bool = False
    subset: int | None = None
    seed: int = 0
    max_cost_usd: float = DEFAULT_MAX_COST_USD

    def __post_init__(self) -> None:
        if self.max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be positive")
        if self.subset is not None and self.subset < 1:
            raise ValueError("subset must be at least 1")


@dataclass(frozen=True)
class RagasSummary:
    run_id: UUID
    status: RunStatus
    cases_planned: int
    cases_scored: int
    cases_failed: int
    cost_usd: float
    tokens: int
    means: Mapping[str, float | None]


def reference_answer(item: QAItem) -> str:
    if item.reference_answer is None:
        raise ValueError(f"Q&A item {item.id} has no reference answer")
    return item.reference_answer


def finite(value: object) -> float | None:
    """A metric value as a float in the stored scores; NaN (RAGAS found nothing to judge) or
    anything that isn't a number is None, since JSON can't hold NaN."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def context_text(hit: SearchHit) -> str:
    """One hit as a context: its provision id and document, then its heading and text."""
    lines = [f"[{hit.provision_id}] {hit.document_title}", hit.heading, hit.text]
    return "\n".join(line for line in lines if line)


def provision_recall(required: Sequence[str], hits: Sequence[SearchHit]) -> float:
    """The share of `required` provision ids that an AI Act hit covers: the hit's own provision
    or an ancestor of it (`art:5:1` covers `art:5:1:f`). Guidance hits never count."""
    found = [hit.provision_id for hit in hits if hit.law_version is not None]
    covered = [provision for provision in required if any(covers(hit, provision) for hit in found)]
    return len(covered) / len(required)


def covers(hit: str, provision: str) -> bool:
    """Whether a hit's row holds `provision`'s text: it is the provision or an ancestor of it
    (`art:5:1` covers `art:5:1:f`; a parent's text includes its children's, C1). A child never
    covers its parent, nor does a shared prefix (`art:5:11` and `art:5:1`)."""
    return provision == hit or provision.startswith(f"{hit}:")


def select_items(items: Sequence[QAItem], size: int | None, seed: int) -> tuple[QAItem, ...]:
    """The answerable items in id order, or a seeded random sample of `size` of them."""
    return select_subset([item for item in items if item.answerable], size, seed)


def run_ragas(
    items: Sequence[QAItem], parts: RagasParts, store: RunStore, options: RagasOptions
) -> RagasSummary:
    """Score the answerable items one by one and record the run (see the module docstring).
    The parts' clients are closed when it ends."""
    planned = select_items(items, options.subset, options.seed)
    return asyncio.run(_run_and_close(planned, parts, store, options))


async def _run_and_close(
    planned: Sequence[QAItem], parts: RagasParts, store: RunStore, options: RagasOptions
) -> RagasSummary:
    try:
        return await _run(planned, parts, store, options)
    finally:
        await parts.aclose()


async def _run(
    planned: Sequence[QAItem], parts: RagasParts, store: RunStore, options: RagasOptions
) -> RagasSummary:
    run_id = store.start_run(options.git_sha, BENCHMARK, run_config(parts, options))
    records: list[CaseRecord] = []
    status = RunStatus.COMPLETED
    try:
        for item in planned:
            if parts.meter.usage().cost_usd >= options.max_cost_usd:
                status = RunStatus.COST_CAP_REACHED
                break
            record = await score_item(item, parts)
            store.add_case(run_id, record)
            records.append(record)
    except BaseException:
        outcome = run_outcome(RunStatus.INTERRUPTED, planned, records, parts.meter)
        finish_after_failure(store, run_id, outcome)
        raise
    store.finish_run(run_id, run_outcome(status, planned, records, parts.meter))
    usage = parts.meter.usage()
    scored = scored_records(records)
    return RagasSummary(
        run_id=run_id,
        status=status,
        cases_planned=len(planned),
        cases_scored=len(scored),
        cases_failed=len(records) - len(scored),
        cost_usd=usage.cost_usd,
        tokens=usage.tokens,
        means=metric_means(records),
    )


def run_config(parts: RagasParts, options: RagasOptions) -> dict[str, JsonValue]:
    """`eval_runs.config`: the judge model, the retrieval and answerer, and the run's options."""
    return {
        "model": parts.model,
        "provider": parts.provider,
        "embedding": parts.embedding,
        "retrieval": parts.retriever.config(),
        "answerer": parts.answerer.name,
        "metrics": list(METRICS),
        "subset": options.subset,
        "seed": options.seed,
        "max_cost_usd": options.max_cost_usd,
        "git_dirty": options.is_git_dirty,
        "outcome": {"status": RunStatus.RUNNING.value},
    }


async def score_item(item: QAItem, parts: RagasParts) -> CaseRecord:
    """Retrieve, answer and score one item. A failure becomes an `is_error` row with what the
    item spent, and the run goes on."""
    before = parts.meter.usage()
    predicted, scores, is_error = await _retrieve_answer_score(item, parts)
    after = parts.meter.usage()
    cost_usd = after.cost_usd - before.cost_usd
    tokens = after.tokens - before.tokens
    run_scores: dict[str, Score] = {"cost_usd": cost_usd, "tokens": tokens, "is_error": is_error}
    return CaseRecord(
        case_id=item.id,
        predicted=predicted,
        label=item.model_dump(mode="json"),
        scores={**scores, **run_scores},
        trace_id=None,
        cost_usd=cost_usd,
        tokens=tokens,
    )


async def _retrieve_answer_score(
    item: QAItem, parts: RagasParts
) -> tuple[dict[str, JsonValue], dict[str, Score], bool]:
    """The row's prediction, metric scores and error flag. Once retrieval worked, its provisions
    and `provision_recall` are kept even when a later model call fails."""
    try:
        hits = tuple(await asyncio.to_thread(parts.retriever, item))
    except Exception as exc:
        return {"error": _error(item, exc)}, {}, True
    retrieved: list[JsonValue] = [
        {"doc_key": hit.doc_key, "provision_id": hit.provision_id} for hit in hits
    ]
    recall: dict[str, Score] = {
        PROVISION_RECALL: provision_recall(item.required_provision_ids, hits)
    }
    if not hits:
        # Nothing to answer from or judge: no hit is useful and no claim is supported by one.
        empty: dict[str, Score] = {CONTEXT_PRECISION: 0.0, CONTEXT_RECALL: 0.0, FAITHFULNESS: None}
        return {"answer": None, "retrieved": retrieved}, {**empty, **recall}, False
    contexts = [context_text(hit) for hit in hits]
    try:
        answer = await parts.answerer.answer(item, contexts)
        judged = await parts.scorer.score(item, contexts, answer)
    except Exception as exc:
        return {"error": _error(item, exc), "retrieved": retrieved}, recall, True
    return {"answer": answer, "retrieved": retrieved}, {**judged, **recall}, False


def _error(item: QAItem, exc: Exception) -> JsonValue:
    logger.warning("Q&A item %s failed: %s", item.id, type(exc).__name__)
    return {"type": type(exc).__name__, "message": str(exc)[:ERROR_MESSAGE_LIMIT]}


def scored_records(records: Sequence[CaseRecord]) -> list[CaseRecord]:
    """The records scored without error."""
    return [record for record in records if record.scores["is_error"] is False]


def metric_means(
    records: Sequence[CaseRecord], metrics: Sequence[str] = METRICS
) -> dict[str, float | None]:
    """Each metric's mean over the items scored without error that have a value for it; None
    when none has."""
    means: dict[str, float | None] = {}
    for metric in metrics:
        values = [
            float(value)
            for record in scored_records(records)
            if isinstance(value := record.scores.get(metric), int | float)
            and not isinstance(value, bool)
        ]
        means[metric] = sum(values) / len(values) if values else None
    return means


def run_outcome(
    status: RunStatus, planned: Sequence[QAItem], records: Sequence[CaseRecord], meter: UsageMeter
) -> dict[str, JsonValue]:
    """`eval_runs.config.outcome`: the status, the case counts, each metric's mean, and what the
    run spent in all (more than the stored rows' sum when an item in flight was interrupted)."""
    usage = meter.usage()
    scored = scored_records(records)
    means: dict[str, JsonValue] = dict(metric_means(records))
    return {
        "status": status.value,
        "finished_at": datetime.now(UTC).isoformat(),
        "cases_planned": len(planned),
        "cases_scored": len(scored),
        "cases_failed": len(records) - len(scored),
        "cost_usd": usage.cost_usd,
        "tokens": usage.tokens,
        "is_cost_complete": usage.is_cost_complete,
        "means": means,
    }
