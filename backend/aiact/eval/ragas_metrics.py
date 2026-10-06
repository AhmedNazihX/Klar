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

The three RAGAS metrics run on Gemini 3.1 Flash-Lite (`aiact.llm.ragas_llm`). Until P7's Q&A
exists, the answer comes from `PlainAnswerer`, one retrieval-grounded prompt on the same model;
P7 passes its own `Answerer` to record faithfulness on its answers, and X1a passes another
embedder to compare embedding arms. Unanswerable items have no reference answer, so they are
left out (C8 and X1 calibrate the relevance cut-off on them).

A run writes one `eval_runs` row (benchmark `qa`) and one `eval_case_results` row per item:
`label` is the item, `predicted` the answer and the provisions retrieved (or `{"error": …}`),
`scores` the four metrics plus the runner's `cost_usd`, `tokens` and `is_error`. The run's mean
per metric goes into `config.outcome.means`. A cost cap is checked before each item.
"""

import asyncio
import logging
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import JsonValue
from ragas.llms import InstructorBaseRagasLLM
from ragas.metrics.collections import ContextPrecisionWithReference, ContextRecall, Faithfulness

from aiact.engine.usage import UsageMeter
from aiact.eval.cases import QAItem
from aiact.eval.runner import ERROR_MESSAGE_LIMIT, CaseRecord, RunStatus, RunStore
from aiact.llm.embeddings import OpenRouterEmbeddings
from aiact.llm.ragas_llm import ragas_model, routing_body
from aiact.retrieval.search import QueryEmbedder, SearchHit, SearchResults, search_ai_act
from aiact.settings import Settings, get_settings

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
DEFAULT_MAX_COST_USD = 0.5
"""About the cost of one full run of the 29 answerable items (estimate, not a measurement)."""
ANSWER_MAX_TOKENS = 1024
MODEL_NODE = "ragas_model"
"""The usage-meter node for every call on the RAGAS model (answers and metrics)."""
SEARCH_NODE = "search"

ANSWER_PROMPT = """\
Answer the question about the EU AI Act using only the provisions below. Name the provision ids \
you rely on, such as art:5:1:f. If the provisions don't answer the question, say so instead of \
answering from memory. Answer in {language_name}, in at most 150 words.

Provisions:
{contexts}

Question: {question}"""
LANGUAGE_NAMES = {"en": "English", "de": "German"}

Score = float | bool | None


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
    """`search_ai_act` with the settings' relevance cut-off and Pile B excluded (decision 012)."""

    top_k: int = DEFAULT_TOP_K
    embedder: QueryEmbedder | None = None
    search: Callable[..., SearchResults] = search_ai_act

    def __call__(self, item: QAItem) -> Sequence[SearchHit]:
        results = self.search(
            item.question, item.language, limit=self.top_k, embedder=self.embedder
        )
        return results.hits

    def config(self) -> JsonValue:
        return {
            "search": "search_ai_act",
            "top_k": self.top_k,
            "max_distance": get_settings().search_max_distance,
        }


@dataclass(frozen=True)
class PlainAnswerer:
    """One retrieval-grounded prompt on the RAGAS model: a stand-in for P7's Q&A."""

    client: AsyncOpenAI
    model: str
    provider: str
    name: str = "plain_rag"

    async def answer(self, item: QAItem, contexts: Sequence[str]) -> str:
        prompt = ANSWER_PROMPT.format(
            language_name=LANGUAGE_NAMES[item.language.value],
            contexts="\n\n".join(contexts),
            question=item.question,
        )
        reply = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=ANSWER_MAX_TOKENS,
            extra_body=routing_body(self.provider),
        )
        text = reply.choices[0].message.content if reply.choices else None
        if not text or not text.strip():
            raise ValueError("the answer model returned no text")
        return text.strip()


class RagasScorer:
    """Context precision (with reference), context recall and faithfulness, run together."""

    def __init__(self, llm: InstructorBaseRagasLLM) -> None:
        self._precision = ContextPrecisionWithReference(llm=llm)
        self._recall = ContextRecall(llm=llm)
        self._faithfulness = Faithfulness(llm=llm)

    async def score(
        self, item: QAItem, contexts: Sequence[str], answer: str
    ) -> Mapping[str, float | None]:
        reference = reference_answer(item)
        retrieved = list(contexts)
        precision, recall, faithfulness = await asyncio.gather(
            self._precision.ascore(
                user_input=item.question, reference=reference, retrieved_contexts=retrieved
            ),
            self._recall.ascore(
                user_input=item.question, retrieved_contexts=retrieved, reference=reference
            ),
            self._faithfulness.ascore(
                user_input=item.question, response=answer, retrieved_contexts=retrieved
            ),
        )
        return {
            CONTEXT_PRECISION: finite(precision.value),
            CONTEXT_RECALL: finite(recall.value),
            FAITHFULNESS: finite(faithfulness.value),
        }


@dataclass(frozen=True)
class RagasParts:
    """Everything a run calls, and the model it is judged by (for `eval_runs.config`)."""

    retriever: Retriever
    answerer: Answerer
    scorer: Scorer
    meter: UsageMeter
    model: str
    provider: str
    embedding: JsonValue = None


def build_parts(top_k: int = DEFAULT_TOP_K, settings: Settings | None = None) -> RagasParts:
    """The real run: Flash-Lite on its EU endpoint, the configured embedding arm, one meter.

    Raises `LLMConfigError` when the API key or an `EMBEDDING_*` setting is not set.
    """
    meter = UsageMeter()
    model = ragas_model(lambda cost, tokens: meter.add(MODEL_NODE, cost, tokens), settings=settings)
    embeddings = OpenRouterEmbeddings(settings=settings)
    return RagasParts(
        retriever=SearchRetriever(top_k, meter.embedder(SEARCH_NODE, embeddings)),
        answerer=PlainAnswerer(model.client, model.model, model.provider),
        scorer=RagasScorer(model.llm),
        meter=meter,
        model=model.model,
        provider=model.provider,
        embedding={
            "model": embeddings.model,
            "provider": embeddings.provider,
            "dimensions": embeddings.dimensions,
        },
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
    items_planned: int
    items_scored: int
    items_failed: int
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
    covered = [
        provision
        for provision in required
        if any(provision == hit or provision.startswith(f"{hit}:") for hit in found)
    ]
    return len(covered) / len(required)


def select_items(items: Sequence[QAItem], size: int | None, seed: int) -> tuple[QAItem, ...]:
    """The answerable items in id order, or a seeded random sample of `size` of them."""
    answerable = sorted((item for item in items if item.answerable), key=lambda item: item.id)
    if size is None or size >= len(answerable):
        return tuple(answerable)
    return tuple(sorted(random.Random(seed).sample(answerable, size), key=lambda item: item.id))


def run_ragas(
    items: Sequence[QAItem], parts: RagasParts, store: RunStore, options: RagasOptions
) -> RagasSummary:
    """Score the answerable items one by one and record the run (see the module docstring)."""
    return asyncio.run(
        _run(select_items(items, options.subset, options.seed), parts, store, options)
    )


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
        store.finish_run(run_id, run_outcome(RunStatus.INTERRUPTED, planned, records, parts))
        raise
    outcome = run_outcome(status, planned, records, parts)
    store.finish_run(run_id, outcome)
    usage = parts.meter.usage()
    return RagasSummary(
        run_id=run_id,
        status=status,
        items_planned=len(planned),
        items_scored=sum(1 for record in records if record.scores["is_error"] is False),
        items_failed=sum(1 for record in records if record.scores["is_error"] is True),
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
    predicted: dict[str, JsonValue]
    scores: dict[str, Score]
    try:
        predicted, scores = await _retrieve_answer_score(item, parts)
        is_error = False
    except Exception as exc:
        logger.warning("Q&A item %s failed: %s", item.id, type(exc).__name__)
        predicted = {
            "error": {"type": type(exc).__name__, "message": str(exc)[:ERROR_MESSAGE_LIMIT]}
        }
        scores, is_error = {}, True
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
) -> tuple[dict[str, JsonValue], dict[str, Score]]:
    hits = tuple(await asyncio.to_thread(parts.retriever, item))
    retrieved: list[JsonValue] = [
        {"doc_key": hit.doc_key, "provision_id": hit.provision_id} for hit in hits
    ]
    recall = provision_recall(item.required_provision_ids, hits)
    if not hits:
        # Nothing to answer from or judge: no hit is useful and no claim is supported by one.
        empty: dict[str, Score] = {
            CONTEXT_PRECISION: 0.0,
            CONTEXT_RECALL: 0.0,
            FAITHFULNESS: None,
            PROVISION_RECALL: recall,
        }
        return {"answer": None, "retrieved": retrieved}, empty
    contexts = [context_text(hit) for hit in hits]
    answer = await parts.answerer.answer(item, contexts)
    judged = await parts.scorer.score(item, contexts, answer)
    return {"answer": answer, "retrieved": retrieved}, {**judged, PROVISION_RECALL: recall}


def metric_means(records: Sequence[CaseRecord]) -> dict[str, float | None]:
    """Each metric's mean over the items that have a value for it; None when none has."""
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
    status: RunStatus, planned: Sequence[QAItem], records: Sequence[CaseRecord], parts: RagasParts
) -> dict[str, JsonValue]:
    """`eval_runs.config.outcome`: the status, the item counts and each metric's mean."""
    means: dict[str, JsonValue] = dict(metric_means(records))
    return {
        "status": status.value,
        "finished_at": datetime.now(UTC).isoformat(),
        "items_planned": len(planned),
        "items_scored": sum(1 for record in records if record.scores["is_error"] is False),
        "items_failed": sum(1 for record in records if record.scores["is_error"] is True),
        "is_cost_complete": parts.meter.usage().is_cost_complete,
        "means": means,
    }
