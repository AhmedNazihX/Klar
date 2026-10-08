"""X1a: the embedding comparison. Scoring and the run loop are tested with a fake search; the
command with an in-memory store."""

import contextlib
from collections.abc import Sequence
from datetime import date

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from aiact.cli import app
from aiact.engine.usage import MeteredEmbedder
from aiact.eval import ragas_metrics, records
from aiact.eval.cases import CaseSet, load_cases, load_qa_items
from aiact.eval.experiments import embeddings as experiment
from aiact.eval.experiments.embeddings import (
    ARMS,
    BEST_SIMILARITY,
    CONTEXT_PRECISION,
    CONTEXT_RECALL,
    RECIPROCAL_RANK,
    SEARCH_DEPTH,
    ExperimentOptions,
    ExperimentSet,
    Query,
    annex_queries,
    build_embeddings,
    context_precision,
    context_recall,
    is_relevant,
    qa_queries,
    query_scores,
    run_arm,
)
from aiact.eval.runner import RunStatus
from aiact.llm.embeddings import EmbeddingError
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import Language, LawVersion
from aiact.settings import Settings
from tests.engine.test_usage import FakeEmbeddings
from tests.eval.test_ragas_metrics import hit, item
from tests.eval.test_runner import InterruptingStore, MemoryStore

GIT_SHA = "b" * 40
ANNEX_CASES = load_cases(CaseSet.ANNEX_MATCH)


def _settings() -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"))  # pyright: ignore[reportCallIssue]


def annex_query(*points: str, language: Language = Language.EN) -> Query:
    return Query(
        id=f"annex-match-{language.value}-{'-'.join(points)}",
        text="A made-up description.",
        language=language,
        targets=points,
        is_any_target=True,
        is_strict=True,
        doc_types=frozenset({"law"}),
        label={},
    )


def qa_query(*provisions: str) -> Query:
    return Query(
        id="qa-en-01-test",
        text="A made-up question?",
        language=Language.EN,
        targets=provisions,
        is_any_target=False,
        is_strict=False,
        doc_types=None,
        label={},
    )


def similar(provision_id: str, similarity: float | None) -> SearchHit:
    return hit(provision_id).model_copy(update={"similarity": similarity})


# --- the arms ----------------------------------------------------------------------------


def test_the_three_arms_are_qwen3_at_1536_and_1024_and_openai_3_large_at_1536() -> None:
    assert {
        name: (arm.corpus.model, arm.corpus.provider, arm.dims, arm.is_instruction_aware)
        for name, arm in ARMS.items()
    } == {
        "qwen3-1536": ("qwen/qwen3-embedding-8b", "nebius", 1536, True),
        "qwen3-1024": ("qwen/qwen3-embedding-8b", "nebius", 1024, True),
        "openai3l-1536": ("openai/text-embedding-3-large", "azure", 1536, False),
    }


def test_a_qwen3_arm_takes_the_instruction_and_the_openai_arm_none() -> None:
    qwen = build_embeddings(ARMS["qwen3-1024"], settings=_settings())
    assert (qwen.model, qwen.provider, qwen.dimensions) == (
        "qwen/qwen3-embedding-8b",
        "nebius",
        1024,
    )
    assert qwen.query_text("q").startswith("Instruct: Given a description of an AI system")
    chosen = build_embeddings(
        ARMS["qwen3-1536"], instruction="Find the point", settings=_settings()
    )
    assert chosen.query_text("q") == "Instruct: Find the point\nQuery:q"
    openai = build_embeddings(ARMS["openai3l-1536"], instruction="ignored", settings=_settings())
    assert (openai.model, openai.provider) == ("openai/text-embedding-3-large", "azure")
    assert openai.query_text("q") == "q"


# --- the queries -------------------------------------------------------------------------


def test_annex_cases_become_strict_law_only_any_point_queries() -> None:
    queries = annex_queries(ANNEX_CASES)
    assert len(queries) == 48
    assert [query.id for query in queries] == sorted(case.id for case in ANNEX_CASES)
    assert all(query.doc_types == frozenset({"law"}) for query in queries)
    assert all(query.is_strict and query.is_any_target for query in queries)
    multi = [query for query in queries if len(query.targets) > 1]
    assert len(multi) == 9  # the 8 tagged multi_point, and item 30 (7(a) or 7(b), X0b)
    assert {query.language for query in queries} == {Language.EN, Language.DE}


def test_an_annex_case_without_a_point_is_refused() -> None:
    case = ANNEX_CASES[0]
    assert not isinstance(case.label, str)
    pointless = case.model_copy(update={"label": case.label.model_copy(update={"annex_point": ()})})
    with pytest.raises(ValueError, match="has no annex_point"):
        annex_queries((pointless,))


def test_only_answerable_qa_items_become_whole_corpus_queries() -> None:
    items = load_qa_items()
    queries = qa_queries(items)
    answerable = [qa for qa in items if qa.answerable]
    assert [query.id for query in queries] == sorted(qa.id for qa in answerable)
    assert len(queries) < len(items)
    assert all(query.doc_types is None and not query.is_strict for query in queries)
    assert all(query.targets for query in queries)


# --- relevance and the metrics -------------------------------------------------------------


def test_a_point_or_a_provision_under_it_is_relevant() -> None:
    assert is_relevant("annex:III:1:a", ("annex:III:1:a",), is_strict=True)
    assert is_relevant("annex:III:5:b:i", ("annex:III:5:b",), is_strict=True)


def test_an_ancestor_counts_only_when_not_strict() -> None:
    assert not is_relevant("annex:III:1", ("annex:III:1:a",), is_strict=True)
    assert not is_relevant("annex:III", ("annex:III:1:a",), is_strict=True)
    assert is_relevant("art:5:1", ("art:5:1:f",), is_strict=False)


def test_a_shared_prefix_isnt_relevant() -> None:
    assert not is_relevant("annex:III:1:b", ("annex:III:1:a",), is_strict=False)
    assert not is_relevant("art:5:11", ("art:5:1",), is_strict=False)


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        ((True, False, False), 1.0),
        ((False, True, False), 0.5),
        ((False, False, False), 0.0),
        # RAGAS average precision: (1/1 + 2/3) / 2
        ((True, False, True), (1.0 + 2 / 3) / 2),
        ((), 0.0),
    ],
)
def test_context_precision_is_ragas_average_precision(
    verdicts: tuple[bool, ...], expected: float
) -> None:
    assert context_precision(verdicts) == pytest.approx(expected)


def test_any_accepted_point_is_full_recall() -> None:
    query = annex_query("annex:III:7:a", "annex:III:7:b")
    assert context_recall(query, ["art:6:2", "annex:III:7:b"]) == 1.0
    assert context_recall(query, ["annex:III:7", "annex:III:7:c"]) == 0.0


def test_qa_recall_is_the_share_of_required_provisions_covered() -> None:
    query = qa_query("art:5:1:f", "art:113:a", "art:99:3")
    assert context_recall(query, ["art:5:1", "art:113:a"]) == pytest.approx(2 / 3)


def test_query_scores_judge_the_top_k_and_rank_the_first_relevant_in_the_whole_depth() -> None:
    query = annex_query("annex:III:4:a")
    hits = [similar("art:6:2", 0.71), similar("art:26:1", None), similar("annex:III:4:b", 0.64)]
    hits += [similar("annex:III:4:a", 0.62)]
    scores = query_scores(query, hits, top_k=3)
    assert scores == {
        CONTEXT_PRECISION: 0.0,
        CONTEXT_RECALL: 0.0,
        RECIPROCAL_RANK: 0.25,
        BEST_SIMILARITY: 0.71,
    }
    assert query_scores(query, hits, top_k=4)[CONTEXT_RECALL] == 1.0


def test_no_meaning_hit_has_no_best_similarity() -> None:
    scores = query_scores(annex_query("annex:III:2"), [similar("annex:III:2", None)], top_k=5)
    assert scores[BEST_SIMILARITY] is None
    assert scores[CONTEXT_PRECISION] == scores[RECIPROCAL_RANK] == 1.0


def test_options_bound_top_k_and_the_cap() -> None:
    with pytest.raises(ValueError, match="top_k"):
        ExperimentOptions(GIT_SHA, top_k=SEARCH_DEPTH + 1)
    with pytest.raises(ValueError, match="max_cost_usd"):
        ExperimentOptions(GIT_SHA, max_cost_usd=0)


# --- the run -----------------------------------------------------------------------------


class FakeSearch:
    """Embeds the query through the metered embedder (so it is counted), then answers from
    `hits_by_text`; a text listed in `failing` raises as a failed embedding request would."""

    def __init__(
        self, hits: Sequence[SearchHit] = (), failing: frozenset[str] = frozenset()
    ) -> None:
        self.hits = tuple(hits)
        self.failing = failing
        self.calls: list[dict[str, object]] = []

    def __call__(self, query: str, language: Language, **kwargs: object) -> SearchResults:
        self.calls.append({"query": query, "language": language, **kwargs})
        if query in self.failing:
            raise EmbeddingError("embeddings request failed: OpenRouterError (HTTP 502)")
        embedder = kwargs["embedder"]
        assert isinstance(embedder, MeteredEmbedder)
        embedder.embed_query(query)
        return SearchResults(
            query=query,
            language=language,
            law_version=LawVersion.AMENDED,
            as_of=date(2026, 10, 8),
            hits=self.hits,
            max_distance=None,
            found=True,
            disclaimer="Guidance, not legal advice.",
        )


def _run(
    queries: Sequence[Query], search: FakeSearch, store: MemoryStore, **options: object
) -> experiment.ArmSummary:
    return run_arm(
        "qwen3-1024",
        ExperimentSet.ANNEX_MATCH,
        queries,
        FakeEmbeddings(),
        store,
        ExperimentOptions(GIT_SHA, **options),  # pyright: ignore[reportArgumentType]
        search=search,
    )


def test_a_run_searches_each_query_without_a_cut_off_and_stores_its_scores() -> None:
    store = MemoryStore()
    search = FakeSearch([similar("annex:III:1:a", 0.7), similar("art:6:2", 0.6)])
    de = annex_query("annex:III:1:a", language=Language.DE)
    summary = _run((annex_query("annex:III:1:a"), de), search, store)

    assert [call["max_distance"] for call in search.calls] == [None, None]
    assert [call["limit"] for call in search.calls] == [SEARCH_DEPTH, SEARCH_DEPTH]
    assert [call["doc_types"] for call in search.calls] == [frozenset({"law"})] * 2
    assert [call["language"] for call in search.calls] == [Language.EN, Language.DE]
    run = store.runs[summary.run_id]
    assert run["benchmark"] == "embedding_annex_match"
    config = run["config"]
    assert isinstance(config, dict)
    assert config["arm"] == "qwen3-1024"
    assert config["model"] is None
    assert config["retrieval"]["max_distance"] is None
    _, record = store.cases[0]
    assert record.predicted == {"retrieved": ["annex:III:1:a", "art:6:2"]}
    assert record.scores[CONTEXT_PRECISION] == 1.0
    assert record.scores["cost_usd"] == pytest.approx(0.0001)
    assert record.scores["tokens"] == 7
    outcome = store.outcomes[summary.run_id]
    assert outcome["status"] == "completed"
    means, by_language = outcome["means"], outcome["means_by_language"]
    assert isinstance(means, dict) and isinstance(by_language, dict)
    assert means[CONTEXT_RECALL] == 1.0
    german = by_language["de"]
    assert isinstance(german, dict)
    assert german[BEST_SIMILARITY] == pytest.approx(0.7)
    assert summary.cost_usd == pytest.approx(0.0002)
    assert (summary.cases_scored, summary.cases_failed) == (2, 0)


def test_a_failed_query_embedding_is_an_error_row_and_the_run_goes_on() -> None:
    store = MemoryStore()
    failing = Query(**{**annex_query("annex:III:2").__dict__, "id": "x", "text": "broken"})
    search = FakeSearch([similar("annex:III:2", 0.6)], failing=frozenset({"broken"}))
    summary = _run((failing, annex_query("annex:III:2")), search, store)
    (_, first), (_, second) = store.cases
    assert first.scores["is_error"] is True
    assert "HTTP 502" in str(first.predicted["error"])
    assert CONTEXT_RECALL not in first.scores
    assert second.scores[CONTEXT_RECALL] == 1.0
    assert (summary.cases_scored, summary.cases_failed) == (1, 1)
    assert summary.means[CONTEXT_RECALL] == 1.0


def test_the_cost_cap_stops_new_queries() -> None:
    store = MemoryStore()
    queries = tuple(annex_query("annex:III:2") for _ in range(4))
    summary = _run(queries, FakeSearch(), store, max_cost_usd=0.0002)
    assert summary.status is RunStatus.COST_CAP_REACHED
    assert len(store.cases) == 2


def test_an_interrupted_run_is_marked_and_the_interruption_goes_on() -> None:
    store = InterruptingStore()
    with pytest.raises(KeyboardInterrupt):
        _run((annex_query("annex:III:2"), annex_query("annex:III:2")), FakeSearch(), store)
    (outcome,) = store.outcomes.values()
    assert outcome["status"] == RunStatus.INTERRUPTED.value
    assert outcome["cases_planned"] == 2


# --- the commands ------------------------------------------------------------------------


def test_the_command_runs_every_arm_on_both_sets(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryStore()
    runs: list[tuple[str, ExperimentSet, int]] = []

    def fake_run_arm(
        arm_name: str,
        chosen: ExperimentSet,
        queries: Sequence[Query],
        *args: object,
        **kwargs: object,
    ) -> experiment.ArmSummary:
        runs.append((arm_name, chosen, len(queries)))
        return experiment.ArmSummary(
            store.start_run(GIT_SHA, chosen.benchmark, {}), arm_name, chosen,
            RunStatus.COMPLETED, len(queries), len(queries), 0, 0.0, 0, {CONTEXT_RECALL: 0.5},
        )  # fmt: skip

    monkeypatch.setattr(records, "connect", contextlib.nullcontext)
    monkeypatch.setattr(records, "PostgresRunStore", lambda connection: store)
    monkeypatch.setattr(experiment, "require_embedded", lambda connection, name: None)
    monkeypatch.setattr(experiment, "build_embeddings", lambda arm, instruction: None)
    monkeypatch.setattr(experiment, "run_arm", fake_run_arm)
    result = CliRunner().invoke(app, ["evaluate", "embeddings"])
    assert result.exit_code == 0, result.output
    answerable = sum(qa.answerable for qa in load_qa_items())
    assert runs == [
        (name, chosen, 48 if chosen is ExperimentSet.ANNEX_MATCH else answerable)
        for name in ARMS
        for chosen in ExperimentSet
    ]
    assert "qwen3-1024 annex_match: run" in result.stdout
    assert "context_recall 0.500" in result.stdout


def test_the_command_refuses_an_arm_without_corpus_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoRows:
        def execute(self, statement: str, params: object) -> "NoRows":
            return self

        def fetchone(self) -> tuple[int]:
            return (0,)

    monkeypatch.setattr(records, "connect", lambda: contextlib.nullcontext(NoRows()))
    result = CliRunner().invoke(app, ["evaluate", "embeddings", "--arm", "openai3l-1536"])
    assert result.exit_code == 2
    assert "aiact corpus embed --model openai3l --dims 1536" in result.stderr


def test_the_command_refuses_an_unknown_arm() -> None:
    result = CliRunner().invoke(app, ["evaluate", "embeddings", "--arm", "bert"])
    assert result.exit_code == 2
    assert "unknown --arm bert" in result.stderr


def test_ragas_with_an_arm_searches_with_that_arms_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[object] = []

    def fake_build_parts(top_k: int, **kwargs: object) -> object:
        seen.append(kwargs["embeddings"])
        raise records.DatabaseNotConfiguredError("stop here")

    monkeypatch.setattr(ragas_metrics, "build_parts", fake_build_parts)
    monkeypatch.setattr(experiment, "build_embeddings", lambda arm: arm)
    result = CliRunner().invoke(app, ["evaluate", "ragas", "--arm", "openai3l-1536"])
    assert result.exit_code == 2
    assert seen == [ARMS["openai3l-1536"]]


def test_build_parts_searches_and_records_the_arm_it_is_given() -> None:
    arm = build_embeddings(ARMS["openai3l-1536"], settings=_settings())
    parts = ragas_metrics.build_parts(settings=_settings(), embeddings=arm)
    assert parts.embedding == {
        "model": "openai/text-embedding-3-large",
        "provider": "azure",
        "dimensions": 1536,
        "query_instruction": None,
    }
    retriever = parts.retriever
    assert isinstance(retriever, ragas_metrics.SearchRetriever)
    assert retriever.embedder is not None and retriever.embedder.model == arm.model
    assert item(1).answerable
