"""X1a: the embedding comparison. Scoring and the run loop are tested with a fake search; the
commands with an in-memory store."""

import contextlib
from collections.abc import Mapping, Sequence
from datetime import date

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from aiact.cli import app
from aiact.engine.usage import MeteredEmbedder, UsageMeter
from aiact.eval import ragas_metrics, records
from aiact.eval.cases import CaseSet, load_cases, load_qa_items
from aiact.eval.experiments import embeddings as experiment
from aiact.eval.experiments.embeddings import (
    ANNEX_RECALL_LENIENT,
    ARMS,
    BEST_SIMILARITY,
    CONTEXT_PRECISION,
    CONTEXT_RECALL,
    RECIPROCAL_RANK,
    SEARCH_DEPTH,
    ArmNotEmbeddedError,
    ExperimentOptions,
    ExperimentSet,
    Query,
    annex_queries,
    annex_recall_lenient,
    area_of,
    build_embeddings,
    context_precision,
    context_recall,
    is_relevant,
    qa_queries,
    query_scores,
    require_embedded,
    run_arm,
)
from aiact.eval.ragas_metrics import provision_recall
from aiact.eval.runner import RunStatus
from aiact.llm.embeddings import EmbeddingError
from aiact.retrieval.search import DEFAULT_TUNING, SearchHit, SearchResults, SearchTuning
from aiact.schemas import Language, LawVersion
from aiact.settings import Settings
from tests.engine.test_usage import FakeEmbeddings
from tests.eval.test_ragas_metrics import hit
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
        experiment_set=ExperimentSet.ANNEX_MATCH,
        targets=points,
        doc_types=frozenset({"law"}),
        label={},
    )


def qa_query(*provisions: str) -> Query:
    return Query(
        id="qa-en-01-test",
        text="A made-up question?",
        language=Language.EN,
        experiment_set=ExperimentSet.QA,
        targets=provisions,
        doc_types=None,
        label={},
    )


def similar(provision_id: str, similarity: float | None) -> SearchHit:
    return hit(provision_id).model_copy(update={"similarity": similarity})


def hits(*ids: str) -> list[SearchHit]:
    return [hit(provision_id) for provision_id in ids]


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


class CountingConnection:
    """Answers the two counts `require_embedded` asks: current vectors, rows in scope."""

    def __init__(self, current: int, in_scope: int) -> None:
        self.counts = {"current": current, "in_scope": in_scope}
        self.result = 0

    def execute(self, statement: str, params: Mapping[str, object]) -> "CountingConnection":
        self.result = self.counts["current" if "provision_embeddings" in statement else "in_scope"]
        return self

    def fetchone(self) -> tuple[int]:
        return (self.result,)


def test_a_fully_embedded_arm_passes() -> None:
    require_embedded(CountingConnection(9083, 9083), "qwen3-1024")  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("current", [0, 9000])
def test_an_unembedded_or_partly_embedded_arm_is_refused_with_both_counts(current: int) -> None:
    with pytest.raises(ArmNotEmbeddedError) as error:
        require_embedded(CountingConnection(current, 9083), "openai3l-1536")  # pyright: ignore[reportArgumentType]
    assert f"current vectors for {current} of 9083 provision rows" in str(error.value)
    assert "aiact corpus embed --model openai3l --dims 1536" in str(error.value)


# --- the queries -------------------------------------------------------------------------


def test_annex_cases_become_law_only_annex_queries() -> None:
    queries = annex_queries(ANNEX_CASES)
    assert len(queries) == 48
    assert [query.id for query in queries] == sorted(case.id for case in ANNEX_CASES)
    assert all(query.doc_types == frozenset({"law"}) for query in queries)
    assert all(query.experiment_set is ExperimentSet.ANNEX_MATCH for query in queries)
    multi = [query for query in queries if len(query.targets) > 1]
    assert len(multi) == 9  # the 8 tagged multi_point, and item 30 (7(a) or 7(b), X0b)
    annex_i = [q for q in queries if any(p.startswith("annex:I:") for p in q.targets)]
    assert len(annex_i) == 9
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
    assert all(query.doc_types is None for query in queries)
    assert all(query.experiment_set is ExperimentSet.QA for query in queries)
    assert all(query.targets for query in queries)


# --- relevance and the metrics -------------------------------------------------------------


def test_annex_a_point_or_a_provision_under_it_is_relevant() -> None:
    query = annex_query("annex:III:5:b")
    assert is_relevant(query, "annex:III:5:b")
    assert is_relevant(query, "annex:III:5:b:i")


def test_annex_an_ancestor_is_never_relevant() -> None:
    query = annex_query("annex:III:1:a")
    assert not is_relevant(query, "annex:III:1")
    assert not is_relevant(query, "annex:III")


def test_qa_follows_v6_a_provision_or_an_ancestor_never_a_descendant() -> None:
    query = qa_query("art:6:3")
    assert is_relevant(query, "art:6:3")
    assert is_relevant(query, "art:6")
    assert not is_relevant(query, "art:6:3:a")


def test_a_shared_prefix_isnt_relevant() -> None:
    assert not is_relevant(annex_query("annex:III:1:a"), "annex:III:1:b")
    assert not is_relevant(qa_query("art:5:1"), "art:5:11")


def test_qa_recall_is_v6s_provision_recall_by_construction() -> None:
    query = qa_query("art:5:1:f", "art:113:a", "art:6:3")
    found = hits("art:5:1", "art:113:a", "art:6:3:a")
    assert context_recall(query, found) == pytest.approx(2 / 3)
    assert context_recall(query, found) == provision_recall(query.targets, found)


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        ((True, False, False), 1.0),
        ((False, True, False), 0.5),
        ((False, False, False), 0.0),
        # average precision: (1/1 + 2/3) / 2
        ((True, False, True), (1.0 + 2 / 3) / 2),
        ((), 0.0),
    ],
)
def test_context_precision_is_ragas_average_precision(
    verdicts: tuple[bool, ...], expected: float
) -> None:
    assert context_precision(verdicts) == pytest.approx(expected)


def test_any_accepted_point_is_full_annex_recall() -> None:
    query = annex_query("annex:III:7:a", "annex:III:7:b")
    assert context_recall(query, hits("art:6:2", "annex:III:7:b")) == 1.0
    assert context_recall(query, hits("annex:III:7", "annex:III:7:c")) == 0.0


@pytest.mark.parametrize(
    ("point", "area"),
    [
        ("annex:III:4:a", "annex:III:4"),
        ("annex:I:A:1", "annex:I:A"),
        ("annex:I:B:21", "annex:I:B"),
        ("annex:III:2", None),
    ],
)
def test_a_points_area_or_section_never_the_whole_annex(point: str, area: str | None) -> None:
    assert area_of(point) == area


def test_lenient_recall_also_accepts_the_points_area_but_not_the_annex() -> None:
    query = annex_query("annex:III:4:a")
    assert annex_recall_lenient(query, ["art:6:2", "annex:III:4"]) == 1.0
    assert annex_recall_lenient(query, ["annex:III:4:a"]) == 1.0
    assert annex_recall_lenient(query, ["annex:III", "annex:III:5"]) == 0.0
    point_two = annex_query("annex:III:2")
    assert annex_recall_lenient(point_two, ["annex:III"]) == 0.0
    section = annex_query("annex:I:A:5")
    assert annex_recall_lenient(section, ["annex:I:A"]) == 1.0


def test_query_scores_judge_the_top_k_and_rank_the_first_relevant_in_the_whole_depth() -> None:
    query = annex_query("annex:III:4:a")
    found = [similar("art:6:2", 0.71), similar("annex:III:4", None), similar("annex:III:4:b", 0.64)]
    found += [similar("annex:III:4:a", 0.62)]
    scores = query_scores(query, found, top_k=3)
    assert scores == {
        CONTEXT_PRECISION: 0.0,
        CONTEXT_RECALL: 0.0,
        ANNEX_RECALL_LENIENT: 1.0,
        RECIPROCAL_RANK: 0.25,
        BEST_SIMILARITY: 0.71,
    }
    assert query_scores(query, found, top_k=4)[CONTEXT_RECALL] == 1.0


def test_qa_scores_have_no_lenient_annex_recall() -> None:
    scores = query_scores(qa_query("art:50:1"), hits("art:50"), top_k=5)
    assert scores[ANNEX_RECALL_LENIENT] is None
    assert scores[CONTEXT_RECALL] == 1.0


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
    """Embeds the query through the metered embedder (so it is counted), then answers with the
    hits of the query's language; a text listed in `failing` raises as a failed embedding
    request would."""

    def __init__(
        self,
        found: Sequence[SearchHit] | Mapping[Language, Sequence[SearchHit]] = (),
        failing: frozenset[str] = frozenset(),
    ) -> None:
        self.by_language = (
            {language: tuple(found) for language in Language}
            if isinstance(found, Sequence)
            else {language: tuple(found[language]) for language in found}
        )
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
            hits=self.by_language[language],
            max_distance=None,
            found=True,
            disclaimer="Guidance, not legal advice.",
        )


def _run(
    queries: Sequence[Query],
    search: FakeSearch,
    store: MemoryStore,
    *,
    meter: UsageMeter | None = None,
    is_cost_known: bool = True,
    **options: object,
) -> experiment.ArmSummary:
    return run_arm(
        "qwen3-1024",
        ExperimentSet.ANNEX_MATCH,
        queries,
        FakeEmbeddings(is_cost_known=is_cost_known),
        store,
        ExperimentOptions(GIT_SHA, **options),  # pyright: ignore[reportArgumentType]
        meter=meter,
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
    assert outcome["is_cost_complete"] is True
    means = outcome["means"]
    assert isinstance(means, dict)
    assert means[CONTEXT_RECALL] == 1.0
    assert summary.cost_usd == pytest.approx(0.0002)
    assert (summary.cases_scored, summary.cases_failed) == (2, 0)


def test_the_means_are_kept_per_language() -> None:
    store = MemoryStore()
    search = FakeSearch(
        {
            Language.EN: [similar("annex:III:1:a", 0.7)],
            Language.DE: [similar("art:6:2", 0.5), similar("annex:III:1:a", 0.4)],
        }
    )
    de = annex_query("annex:III:1:a", language=Language.DE)
    summary = _run((annex_query("annex:III:1:a"), de), search, store)
    by_language = store.outcomes[summary.run_id]["means_by_language"]
    assert isinstance(by_language, dict)
    english, german = by_language["en"], by_language["de"]
    assert isinstance(english, dict) and isinstance(german, dict)
    assert (english[CONTEXT_PRECISION], german[CONTEXT_PRECISION]) == (1.0, 0.5)
    assert (english[BEST_SIMILARITY], german[BEST_SIMILARITY]) == (0.7, 0.5)


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


def test_the_cap_covers_every_run_sharing_a_meter() -> None:
    meter = UsageMeter()
    queries = tuple(annex_query("annex:III:2") for _ in range(2))
    first = _run(queries, FakeSearch(), MemoryStore(), meter=meter, max_cost_usd=0.0003)
    store = MemoryStore()
    second = _run(queries, FakeSearch(), store, meter=meter, max_cost_usd=0.0003)
    assert first.status is RunStatus.COMPLETED
    assert second.status is RunStatus.COST_CAP_REACHED
    assert len(store.cases) == 1
    assert second.cost_usd == pytest.approx(0.0001)


def test_an_unknown_cost_stops_the_run() -> None:
    store = MemoryStore()
    queries = tuple(annex_query("annex:III:2") for _ in range(3))
    summary = _run(queries, FakeSearch(), store, is_cost_known=False)
    assert summary.status is RunStatus.COST_CAP_REACHED
    assert len(store.cases) == 1
    assert store.outcomes[summary.run_id]["is_cost_complete"] is False


def test_an_interrupted_run_is_marked_and_the_interruption_goes_on() -> None:
    store = InterruptingStore()
    with pytest.raises(KeyboardInterrupt):
        _run((annex_query("annex:III:2"), annex_query("annex:III:2")), FakeSearch(), store)
    (outcome,) = store.outcomes.values()
    assert outcome["status"] == RunStatus.INTERRUPTED.value
    assert outcome["cases_planned"] == 2


# --- the commands ------------------------------------------------------------------------


def _summary(
    store: MemoryStore, arm_name: str, chosen: ExperimentSet, planned: int, status: RunStatus
) -> experiment.ArmSummary:
    return experiment.ArmSummary(
        store.start_run(GIT_SHA, chosen.benchmark, {}), arm_name, chosen,
        status, planned, planned, 0, 0.0, 0, {CONTEXT_RECALL: 0.5},
    )  # fmt: skip


def _patch_command(
    monkeypatch: pytest.MonkeyPatch,
    store: MemoryStore,
    runs: list[tuple[str, ExperimentSet, int, object]],
    status: RunStatus = RunStatus.COMPLETED,
) -> None:
    def fake_run_arm(
        arm_name: str,
        chosen: ExperimentSet,
        queries: Sequence[Query],
        *args: object,
        **kwargs: object,
    ) -> experiment.ArmSummary:
        runs.append((arm_name, chosen, len(queries), kwargs["meter"]))
        return _summary(store, arm_name, chosen, len(queries), status)

    monkeypatch.setattr(records, "connect", contextlib.nullcontext)
    monkeypatch.setattr(records, "PostgresRunStore", lambda connection: store)
    monkeypatch.setattr(experiment, "require_embedded", lambda connection, name: None)
    monkeypatch.setattr(experiment, "build_embeddings", lambda arm, instruction: None)
    monkeypatch.setattr(experiment, "run_arm", fake_run_arm)


def test_the_command_runs_every_arm_on_both_sets_under_one_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    runs: list[tuple[str, ExperimentSet, int, object]] = []
    _patch_command(monkeypatch, store, runs)
    result = CliRunner().invoke(app, ["evaluate", "embeddings"])
    assert result.exit_code == 0, result.output
    answerable = sum(qa.answerable for qa in load_qa_items())
    assert [run[:3] for run in runs] == [
        (name, chosen, 48 if chosen is ExperimentSet.ANNEX_MATCH else answerable)
        for name in ARMS
        for chosen in ExperimentSet
    ]
    meters = {id(run[3]) for run in runs}
    assert len(meters) == 1 and isinstance(runs[0][3], UsageMeter)
    assert "qwen3-1024 annex_match: run" in result.stdout
    assert "context_recall 0.500" in result.stdout


def test_the_command_stops_once_a_run_reaches_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryStore()
    runs: list[tuple[str, ExperimentSet, int, object]] = []
    _patch_command(monkeypatch, store, runs, status=RunStatus.COST_CAP_REACHED)
    result = CliRunner().invoke(app, ["evaluate", "embeddings"])
    assert result.exit_code == 1
    assert len(runs) == 1
    assert "cost cap" in result.stderr


def test_the_command_starts_no_run_when_the_cap_is_already_spent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    runs: list[tuple[str, ExperimentSet, int, object]] = []
    _patch_command(monkeypatch, store, runs)
    checks: list[UsageMeter] = []

    def spent_after_one_run(meter: UsageMeter, max_cost_usd: float) -> bool:
        checks.append(meter)
        return len(checks) > 1

    monkeypatch.setattr(experiment, "is_over_budget", spent_after_one_run)
    result = CliRunner().invoke(app, ["evaluate", "embeddings"])
    assert result.exit_code == 1
    assert len(runs) == 1 and len(store.runs) == 1  # the second run left no eval_runs row
    assert len(checks) == 2 and checks[0] is checks[1]
    assert "cost cap" in result.stderr


def test_the_command_refuses_an_arm_without_all_its_corpus_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = CountingConnection(100, 9083)
    monkeypatch.setattr(records, "connect", lambda: contextlib.nullcontext(connection))
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

    connection = CountingConnection(9083, 9083)
    monkeypatch.setattr(records, "connect", lambda: contextlib.nullcontext(connection))
    monkeypatch.setattr(ragas_metrics, "build_parts", fake_build_parts)
    monkeypatch.setattr(experiment, "build_embeddings", lambda arm: arm)
    result = CliRunner().invoke(app, ["evaluate", "ragas", "--arm", "openai3l-1536"])
    assert result.exit_code == 2
    assert seen == [ARMS["openai3l-1536"]]


def test_ragas_refuses_an_unembedded_arm_before_any_paid_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[object] = []
    connection = CountingConnection(0, 9083)
    monkeypatch.setattr(records, "connect", lambda: contextlib.nullcontext(connection))
    monkeypatch.setattr(ragas_metrics, "build_parts", lambda *a, **k: built.append(k))
    monkeypatch.setattr(ragas_metrics, "run_ragas", lambda *a, **k: built.append(a))
    result = CliRunner().invoke(app, ["evaluate", "ragas", "--arm", "openai3l-1536"])
    assert result.exit_code == 2
    assert "current vectors for 0 of 9083" in result.stderr
    assert built == []


def test_build_parts_searches_the_arm_it_is_given_without_a_cut_off() -> None:
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
    assert retriever.is_cut_off is False
    config = retriever.config()
    assert isinstance(config, dict) and config["max_distance"] is None


def test_build_parts_keeps_the_cut_off_for_the_configured_arm() -> None:
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        openrouter_api_key=SecretStr("k"),
        embedding_model="qwen/qwen3-embedding-8b",
        embedding_provider="nebius",
    )
    retriever = ragas_metrics.build_parts(settings=settings).retriever
    assert isinstance(retriever, ragas_metrics.SearchRetriever)
    assert retriever.is_cut_off is True


# --- X1b: the search tuning ----------------------------------------------------------------


def test_a_run_ranks_with_its_tuning_and_records_it() -> None:
    store = MemoryStore()
    search = FakeSearch([similar("annex:III:1:a", 0.7)])
    tuning = SearchTuning(keyword_weight=0.5, rrf_k=60, skips_annex_containers=False)
    summary = _run((annex_query("annex:III:1:a"),), search, store, tuning=tuning)
    assert search.calls[0]["tuning"] == tuning
    config = store.runs[summary.run_id]["config"]
    assert isinstance(config, dict)
    assert config["retrieval"]["tuning"] == {
        "keyword_weight": 0.5,
        "rrf_k": 60,
        "max_term_share": 0.05,
        "skips_annex_containers": False,
    }


def test_a_run_without_a_tuning_ranks_with_searchs_own() -> None:
    search = FakeSearch([similar("annex:III:1:a", 0.7)])
    _run((annex_query("annex:III:1:a"),), search, MemoryStore())
    assert search.calls[0]["tuning"] == DEFAULT_TUNING


def test_the_command_passes_its_tuning_options_to_every_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    tunings: list[object] = []

    def fake_run_arm(arm_name: str, chosen: ExperimentSet, queries: Sequence[Query],
                     embeddings: object, run_store: object, options: ExperimentOptions,
                     **kwargs: object) -> experiment.ArmSummary:  # fmt: skip
        tunings.append(options.tuning)
        return _summary(store, arm_name, chosen, len(queries), RunStatus.COMPLETED)

    _patch_command(monkeypatch, store, [])
    monkeypatch.setattr(experiment, "run_arm", fake_run_arm)
    args = ["evaluate", "embeddings", "--arm", "qwen3-1536", "--keyword-weight", "0.5",
            "--rrf-k", "60", "--max-term-share", "0.1", "--with-annex-containers"]  # fmt: skip
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    expected = SearchTuning(keyword_weight=0.5, rrf_k=60, max_term_share=0.1,
                            skips_annex_containers=False)  # fmt: skip
    assert tunings == [expected, expected]
    default = CliRunner().invoke(app, ["evaluate", "embeddings", "--arm", "qwen3-1536"])
    assert default.exit_code == 0, default.output
    assert tunings[2:] == [DEFAULT_TUNING, DEFAULT_TUNING]
