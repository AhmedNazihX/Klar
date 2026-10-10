"""V6: RAGAS metrics on the Q&A set. The run loop is tested with fakes; one recorded test runs
the real answer and the three RAGAS metrics on Gemini 3.1 Flash-Lite."""

import asyncio
import contextlib
import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

import pytest
from pydantic import JsonValue
from ragas.metrics.result import MetricResult
from typer.testing import CliRunner

from aiact.cli import app
from aiact.engine.usage import UsageMeter
from aiact.eval import ragas_metrics, records
from aiact.eval.cases import QAItem, load_qa_items
from aiact.eval.ragas_metrics import (
    ANSWER_MAX_TOKENS,
    BENCHMARK,
    CONTEXT_PRECISION,
    CONTEXT_RECALL,
    FAITHFULNESS,
    METRICS,
    MODEL_NODE,
    PROVISION_RECALL,
    ItemAnswer,
    PlainAnswerer,
    RagasOptions,
    RagasParts,
    RagasScorer,
    Retrieved,
    SearchRetriever,
    context_text,
    finite,
    provision_recall,
    run_ragas,
    select_items,
)
from aiact.eval.runner import RunStatus
from aiact.llm.ragas_llm import ragas_chat_model, ragas_model
from aiact.retrieval.search import FROM_SETTINGS, SearchHit, SearchResults
from aiact.schemas import DocumentStatus, Language, LawVersion
from aiact.settings import Settings
from tests.eval.test_runner import InterruptingStore, MemoryStore

GIT_SHA = "a" * 40


def hit(pid: str, *, text: str = "", is_law: bool = True, heading: str | None = None) -> SearchHit:
    return SearchHit(
        provision_id=pid,
        doc_key="aiact" if is_law else "guide-prohibited",
        document_title="AI Act" if is_law else "Guidelines",
        doc_type="law" if is_law else "guideline",
        law_version=LawVersion.AMENDED if is_law else None,
        status=DocumentStatus.CONSOLIDATED if is_law else DocumentStatus.FINAL,
        language=Language.EN,
        heading=heading,
        text=text or f"Text of {pid}.",
        valid_from=date(2024, 8, 1),
        valid_to=None,
        score=0.03,
        vector_rank=1,
        keyword_rank=None,
        similarity=0.6,
        keyword_idf=None,
    )


def item(number: int, *, provisions: tuple[str, ...] = ("art:5:1:f",)) -> QAItem:
    return QAItem(
        id=f"qa-en-{number:02d}-test",
        language=Language.EN,
        question=f"Made-up question {number}?",
        required_provision_ids=provisions,
        reference_answer=f"Made-up reference answer {number}.",
    )


UNANSWERABLE = QAItem(
    id="qa-none-en-01-test", language=Language.EN, question="Football results?", answerable=False
)


@dataclass
class FakeRetriever:
    hits: tuple[SearchHit, ...] = (hit("art:5:1"), hit("art:50:1"))
    found: bool = True
    seen: list[str] = field(default_factory=list)

    def __call__(self, item: QAItem) -> Retrieved:
        self.seen.append(item.id)
        return Retrieved(self.hits, self.found)

    def config(self) -> JsonValue:
        return {"search": "fake"}


@dataclass
class FakeAnswerer:
    """Answers with a fixed text and charges `cost` to the meter, as a real model call would."""

    meter: UsageMeter
    cost: float = 0.01
    failing_ids: frozenset[str] = frozenset()
    name: str = "fake"
    calls: list[str] = field(default_factory=list)

    async def answer(self, item: QAItem, contexts: Sequence[str], *, found: bool) -> ItemAnswer:
        self.calls.append(item.id)
        self.meter.add(MODEL_NODE, self.cost, 100)
        if item.id in self.failing_ids:
            raise RuntimeError("provider error")
        return ItemAnswer(f"Answer to {item.id}", "answered" if found else "outside_corpus")


@dataclass
class FakeScorer:
    values: Mapping[str, float | None] = field(
        default_factory=lambda: {CONTEXT_PRECISION: 1.0, CONTEXT_RECALL: 0.5, FAITHFULNESS: None}
    )

    async def score(
        self, item: QAItem, contexts: Sequence[str], answer: str
    ) -> Mapping[str, float | None]:
        return self.values


def parts(
    meter: UsageMeter | None = None,
    retriever: FakeRetriever | None = None,
    answerer: FakeAnswerer | None = None,
) -> RagasParts:
    meter = meter or (answerer.meter if answerer else UsageMeter())
    return RagasParts(
        retriever=retriever or FakeRetriever(),
        answerer=answerer or FakeAnswerer(meter),
        scorer=FakeScorer(),
        meter=meter,
        model="google/gemini-3.1-flash-lite",
        provider="google-vertex/eu",
        embedding={"model": "qwen/qwen3-embedding-8b", "dimensions": 1536},
        answer_model={"model": "openai/gpt-6-luna-20260922", "provider": "azure/eu"},
    )


# --- provision recall --------------------------------------------------------------------


def test_a_hit_covers_its_own_provision_and_those_under_it() -> None:
    required = ("art:5:1:f", "art:50:2", "annex:III:4:a")
    hits = (hit("art:5:1"), hit("art:50:2"), hit("annex:III:5"))
    assert provision_recall(required, hits) == pytest.approx(2 / 3)


def test_a_child_hit_doesnt_cover_its_parent() -> None:
    assert provision_recall(("art:5:1",), (hit("art:5:1:f"),)) == 0.0


def test_a_shared_prefix_isnt_an_ancestor() -> None:
    assert provision_recall(("art:50:1",), (hit("art:5"),)) == 0.0


def test_guidance_hits_never_count_for_provision_recall() -> None:
    assert provision_recall(("art:5:1:f",), (hit("art:5:1:f", is_law=False),)) == 0.0


# --- small helpers -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.75, 0.75), (1, 1.0), (math.nan, None), (math.inf, None), (True, None), ("0.5", None)],
)
def test_only_finite_numbers_are_stored(value: object, expected: float | None) -> None:
    assert finite(value) == expected


def test_a_context_names_its_provision_and_document_before_the_text() -> None:
    text = context_text(hit("art:5:1:f", text="Emotion recognition…", heading="Prohibited"))
    assert text == "[art:5:1:f] AI Act\nProhibited\nEmotion recognition…"


def test_only_answerable_items_are_planned_in_id_order() -> None:
    planned = select_items((item(3), UNANSWERABLE, item(1), item(2)), None, 0)
    assert [i.id for i in planned] == ["qa-en-01-test", "qa-en-02-test", "qa-en-03-test"]


def test_a_subset_is_a_seeded_sample_in_id_order() -> None:
    items = tuple(item(n) for n in range(1, 11))
    first = select_items(items, 4, seed=7)
    assert first == select_items(items, 4, seed=7)
    assert len(first) == 4
    assert [i.id for i in first] == sorted(i.id for i in first)


def test_options_reject_a_cap_that_isnt_positive() -> None:
    with pytest.raises(ValueError, match="max_cost_usd"):
        RagasOptions(GIT_SHA, max_cost_usd=0)


def test_the_search_retriever_searches_the_question_in_its_language() -> None:
    calls: list[tuple[object, ...]] = []
    hits = (hit("art:5:1:f"),)

    def search(
        query: str, language: Language, *, limit: int, embedder: object, max_distance: object
    ) -> SearchResults:
        calls.append((query, language, limit, max_distance))
        return SearchResults(
            query=query,
            language=language,
            law_version=LawVersion.AMENDED,
            as_of=date(2026, 10, 6),
            hits=hits,
            max_distance=None,
            found=True,
            disclaimer="Guidance, not legal advice.",
        )

    retriever = SearchRetriever(top_k=3, search=search)
    question = item(1).model_copy(update={"language": Language.DE})
    assert retriever(question) == Retrieved(hits, True)
    assert calls == [(question.question, Language.DE, 3, FROM_SETTINGS)]
    config = retriever.config()
    assert isinstance(config, dict)
    assert (config["search"], config["top_k"]) == ("search_ai_act", 3)
    # Another embedding arm (X1a) searches without the cut-off calibrated for the default one.
    SearchRetriever(top_k=3, search=search, is_cut_off=False)(question)
    assert calls[-1] == (question.question, Language.DE, 3, None)


# --- the run -----------------------------------------------------------------------------


def test_a_run_stores_every_items_scores_and_the_means() -> None:
    store = MemoryStore()
    summary = run_ragas(
        (item(1), item(2, provisions=("art:6:1",)), UNANSWERABLE),
        parts(),
        store,
        RagasOptions(GIT_SHA),
    )
    run = store.runs[summary.run_id]
    assert run["benchmark"] == BENCHMARK == "qa"
    config = run["config"]
    assert isinstance(config, dict)
    assert config["model"] == "google/gemini-3.1-flash-lite"
    assert config["retrieval"] == {"search": "fake"}
    assert config["answerer"] == "fake"
    assert config["answer_model"] == {"model": "openai/gpt-6-luna-20260922", "provider": "azure/eu"}
    assert config["metrics"] == list(METRICS)

    stored = [record for _, record in store.cases]
    assert [r.case_id for r in stored] == ["qa-en-01-test", "qa-en-02-test"]
    first = stored[0]
    assert first.scores == {
        CONTEXT_PRECISION: 1.0,
        CONTEXT_RECALL: 0.5,
        FAITHFULNESS: None,
        PROVISION_RECALL: 1.0,
        "cost_usd": pytest.approx(0.01),
        "tokens": 100,
        "is_error": False,
    }
    assert first.predicted == {
        "answer": "Answer to qa-en-01-test",
        "answer_kind": "answered",
        "retrieved": [
            {"doc_key": "aiact", "provision_id": "art:5:1"},
            {"doc_key": "aiact", "provision_id": "art:50:1"},
        ],
    }
    assert first.label["reference_answer"] == "Made-up reference answer 1."
    assert stored[1].scores[PROVISION_RECALL] == 0.0

    outcome = store.outcomes[summary.run_id]
    assert outcome["status"] == RunStatus.COMPLETED.value
    assert (outcome["cases_planned"], outcome["cases_scored"], outcome["cases_failed"]) == (2, 2, 0)
    assert outcome["cost_usd"] == pytest.approx(0.02)
    assert outcome["means"] == {
        CONTEXT_PRECISION: 1.0,
        CONTEXT_RECALL: 0.5,
        FAITHFULNESS: None,
        PROVISION_RECALL: 0.5,
    }
    assert summary.means == outcome["means"]
    assert summary.cost_usd == pytest.approx(0.02)
    assert store.stored_cost() == pytest.approx(0.02)


def test_a_failed_model_call_keeps_the_retrieval_its_cost_and_the_run_goes_on() -> None:
    meter = UsageMeter()
    answerer = FakeAnswerer(meter, failing_ids=frozenset({"qa-en-01-test"}))
    store = MemoryStore()
    summary = run_ragas(
        (item(1), item(2, provisions=("art:6:1",))),
        parts(answerer=answerer),
        store,
        RagasOptions(GIT_SHA),
    )
    failed, scored = (record for _, record in store.cases)
    assert failed.predicted == {
        "error": {"type": "RuntimeError", "message": "provider error"},
        "answer_kind": "error",
        "retrieved": [
            {"doc_key": "aiact", "provision_id": "art:5:1"},
            {"doc_key": "aiact", "provision_id": "art:50:1"},
        ],
    }
    assert failed.scores == {
        PROVISION_RECALL: 1.0,
        "cost_usd": pytest.approx(0.01),
        "tokens": 100,
        "is_error": True,
    }
    assert scored.scores["is_error"] is False
    assert (summary.cases_scored, summary.cases_failed) == (1, 1)
    # The means cover the items scored without error only.
    assert summary.means[PROVISION_RECALL] == 0.0


def test_a_failed_retrieval_is_an_error_row_without_scores() -> None:
    class BrokenRetriever(FakeRetriever):
        def __call__(self, item: QAItem) -> Retrieved:
            raise ConnectionError("database went away")

    store = MemoryStore()
    run_ragas((item(1),), parts(retriever=BrokenRetriever()), store, RagasOptions(GIT_SHA))
    (_, record), *_ = store.cases
    assert record.predicted == {
        "error": {"type": "ConnectionError", "message": "database went away"},
        "answer_kind": "error",
    }
    assert record.scores == {"cost_usd": 0.0, "tokens": 0, "is_error": True}


def test_no_hits_scores_zero_without_calling_the_model() -> None:
    meter = UsageMeter()
    answerer = FakeAnswerer(meter)
    store = MemoryStore()
    run_ragas(
        (item(1),),
        parts(retriever=FakeRetriever(hits=()), answerer=answerer),
        store,
        RagasOptions(GIT_SHA),
    )
    (_, record), *_ = store.cases
    assert answerer.calls == []
    assert record.predicted == {"answer": None, "answer_kind": None, "retrieved": []}
    assert record.scores[CONTEXT_PRECISION] == 0.0
    assert record.scores[CONTEXT_RECALL] == 0.0
    assert record.scores[FAITHFULNESS] is None
    assert record.scores[PROVISION_RECALL] == 0.0


def test_the_cost_cap_stops_new_items() -> None:
    meter = UsageMeter()
    store = MemoryStore()
    summary = run_ragas(
        tuple(item(n) for n in range(1, 6)),
        parts(answerer=FakeAnswerer(meter, cost=0.02)),
        store,
        RagasOptions(GIT_SHA, max_cost_usd=0.03),
    )
    assert summary.status is RunStatus.COST_CAP_REACHED
    assert len(store.cases) == 2
    assert store.outcomes[summary.run_id]["status"] == RunStatus.COST_CAP_REACHED.value


def test_an_interrupted_run_is_marked_and_the_interruption_goes_on() -> None:
    store = InterruptingStore()
    with pytest.raises(KeyboardInterrupt):
        run_ragas((item(1), item(2)), parts(), store, RagasOptions(GIT_SHA))
    (outcome,) = store.outcomes.values()
    assert outcome["status"] == RunStatus.INTERRUPTED.value
    assert outcome["cases_planned"] == 2
    # The item written before the interruption cost 0.01; the outcome holds the run's whole spend.
    assert outcome["cost_usd"] == pytest.approx(0.01)


def test_a_run_closes_its_parts_and_a_second_run_on_new_parts_works() -> None:
    closed: list[str] = []

    def closing_parts(name: str) -> RagasParts:
        async def aclose() -> None:
            closed.append(name)

        return dataclasses.replace(parts(), aclose=aclose)

    store = MemoryStore()
    first = run_ragas((item(1),), closing_parts("first"), store, RagasOptions(GIT_SHA))
    second = run_ragas((item(2),), closing_parts("second"), store, RagasOptions(GIT_SHA))
    assert closed == ["first", "second"]
    assert (first.status, second.status) == (RunStatus.COMPLETED, RunStatus.COMPLETED)
    assert len(store.cases) == 2


def test_parts_are_closed_when_a_run_is_interrupted() -> None:
    closed: list[bool] = []

    async def aclose() -> None:
        closed.append(True)

    with pytest.raises(KeyboardInterrupt):
        run_ragas(
            (item(1), item(2)),
            dataclasses.replace(parts(), aclose=aclose),
            InterruptingStore(),
            RagasOptions(GIT_SHA),
        )
    assert closed == [True]


# --- the RAGAS scorer --------------------------------------------------------------------


@dataclass
class StubMetric:
    """A RAGAS metric that returns a fixed value and keeps the arguments it was called with."""

    value: float
    calls: list[dict[str, object]] = field(default_factory=list)

    async def ascore(self, **arguments: object) -> MetricResult:
        self.calls.append(arguments)
        return MetricResult(value=self.value)


def test_the_scorer_maps_each_metric_to_its_own_key() -> None:
    precision, recall, faithfulness = StubMetric(0.25), StubMetric(0.75), StubMetric(0.5)
    scorer = RagasScorer(precision, recall, faithfulness)  # pyright: ignore[reportArgumentType]
    scores = asyncio.run(scorer.score(item(1), ["ctx a", "ctx b"], "the answer"))
    assert scores == {CONTEXT_PRECISION: 0.25, CONTEXT_RECALL: 0.75, FAITHFULNESS: 0.5}
    reference = "Made-up reference answer 1."
    question = "Made-up question 1?"
    contexts = ["ctx a", "ctx b"]
    assert precision.calls == [
        {"user_input": question, "reference": reference, "retrieved_contexts": contexts}
    ]
    assert recall.calls == [
        {"user_input": question, "retrieved_contexts": contexts, "reference": reference}
    ]
    assert faithfulness.calls == [
        {"user_input": question, "response": "the answer", "retrieved_contexts": contexts}
    ]


def test_a_nan_metric_is_stored_as_none() -> None:
    scorer = RagasScorer(StubMetric(1.0), StubMetric(math.nan), StubMetric(0.5))  # pyright: ignore[reportArgumentType]
    scores = asyncio.run(scorer.score(item(1), ["ctx"], "answer"))
    assert scores[CONTEXT_RECALL] is None


# --- the real model, recorded ------------------------------------------------------------

ART_5_1_F = (
    "The following AI practices shall be prohibited: (f) the placing on the market, the putting "
    "into service for this specific purpose, or the use of AI systems to infer emotions of a "
    "natural person in the areas of workplace and education institutions, except where the use "
    "of the AI system is intended to be put in place or into the market for medical or safety "
    "reasons;"
)
ART_50_1 = (
    "Providers shall ensure that AI systems intended to interact directly with natural persons "
    "are designed and developed in such a way that the natural persons concerned are informed "
    "that they are interacting with an AI system."
)
RECORDED_ITEM = QAItem(
    id="qa-en-99-recorded",
    language=Language.EN,
    question="May an employer use AI to read how stressed staff are from their faces at work?",
    required_provision_ids=("art:5:1:f",),
    reference_answer=(
        "No. Art. 5(1)(f) prohibits AI systems that infer the emotions of people at the "
        "workplace, unless they are used for medical or safety reasons."
    ),
)


@pytest.mark.vcr
def test_flash_lite_answers_and_judges_one_item(openrouter_settings: Settings) -> None:
    meter = UsageMeter()
    model = ragas_model(
        lambda cost, tokens: meter.add(MODEL_NODE, cost, tokens), settings=openrouter_settings
    )
    recorded_parts = RagasParts(
        retriever=FakeRetriever(
            hits=(hit("art:5:1:f", text=ART_5_1_F), hit("art:50:1", text=ART_50_1))
        ),
        answerer=PlainAnswerer(
            ragas_chat_model(max_tokens=ANSWER_MAX_TOKENS, settings=openrouter_settings), meter
        ),
        scorer=RagasScorer.from_llm(model.llm),
        meter=meter,
        model=model.model,
        provider=model.provider,
        aclose=model.aclose,
    )
    store = MemoryStore()
    summary = run_ragas((RECORDED_ITEM,), recorded_parts, store, RagasOptions(GIT_SHA))

    (_, record), *_ = store.cases
    assert record.scores["is_error"] is False, record.predicted
    answer = record.predicted["answer"]
    assert isinstance(answer, str)
    assert "5" in answer
    # The relevant provision is ranked first, it supports the reference, and the answer rests
    # on the provisions given.
    assert record.scores[CONTEXT_PRECISION] == pytest.approx(1.0)
    assert record.scores[CONTEXT_RECALL] == pytest.approx(1.0)
    faithfulness = record.scores[FAITHFULNESS]
    assert isinstance(faithfulness, float) and faithfulness >= 0.5
    assert record.scores[PROVISION_RECALL] == 1.0
    usage = meter.usage()
    assert usage.is_cost_complete
    assert usage.by_node[MODEL_NODE].calls >= 5  # the answer, then RAGAS's judging calls
    assert summary.cost_usd == pytest.approx(usage.cost_usd) and usage.cost_usd > 0
    assert summary.status is RunStatus.COMPLETED


# --- the command -------------------------------------------------------------------------


def test_the_command_runs_the_qa_set_and_prints_the_means(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryStore()
    monkeypatch.setattr(ragas_metrics, "build_parts", lambda top_k, **_: parts())
    monkeypatch.setattr(records, "connect", contextlib.nullcontext)
    monkeypatch.setattr(records, "PostgresRunStore", lambda connection: store)
    result = CliRunner().invoke(app, ["evaluate", "ragas", "--subset", "2"])
    assert result.exit_code == 0, result.output
    assert "completed, 2/2 items (0 failed)" in result.stdout
    assert "provision_recall " in result.stdout
    (outcome,) = store.outcomes.values()
    assert outcome["cases_planned"] == 2


def test_the_command_runs_every_answerable_item_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryStore()
    monkeypatch.setattr(ragas_metrics, "build_parts", lambda top_k, **_: parts())
    monkeypatch.setattr(records, "connect", contextlib.nullcontext)
    monkeypatch.setattr(records, "PostgresRunStore", lambda connection: store)
    result = CliRunner().invoke(app, ["evaluate", "ragas"])
    assert result.exit_code == 0, result.output
    answerable = [qa for qa in load_qa_items() if qa.answerable]
    (outcome,) = store.outcomes.values()
    assert outcome["cases_planned"] == len(answerable) > 0
    assert {record.case_id for _, record in store.cases} == {qa.id for qa in answerable}


def test_the_command_without_ragas_installed_says_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ragas_metrics, "find_spec", lambda name: None if name == "ragas" else object()
    )
    result = CliRunner().invoke(app, ["evaluate", "ragas"])
    assert result.exit_code == 2
    assert "uv sync" in result.stderr


def test_the_command_without_an_api_key_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    unconfigured = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr(ragas_metrics, "get_settings", lambda: unconfigured)
    result = CliRunner().invoke(app, ["evaluate", "ragas", "--answerer", "plain_rag"])
    assert result.exit_code == 2
    assert "OPENROUTER_API_KEY" in result.stderr
