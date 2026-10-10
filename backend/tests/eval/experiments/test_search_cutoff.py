"""X1b: the relevance cut-off calibration. The probes come from the committed sets; the
measurements and the run loop are tested with a fake search and an in-memory store."""

import contextlib
from datetime import date

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from aiact.cli import app
from aiact.engine.usage import UsageMeter
from aiact.eval import records
from aiact.eval.cases import CaseSet, load_cases, load_qa_items
from aiact.eval.experiments import search_cutoff
from aiact.eval.experiments.search_cutoff import (
    DISTANCES,
    OFF_TOPIC_PROBES,
    OTHER_LAW_PROBES,
    TOP_K,
    Measurement,
    OnceEmbedder,
    Probe,
    ProbeKind,
    build_probes,
    distributions,
    found_shares,
    is_found,
    mean_recall,
    measure,
    run_calibration,
)
from aiact.eval.runner import RunStatus
from aiact.retrieval.references import exact_references
from aiact.retrieval.search import DEFAULT_LIMIT, SearchHit, SearchResults
from aiact.schemas import Language, LawVersion
from aiact.settings import Settings
from tests.engine.test_usage import FakeEmbeddings
from tests.eval.test_ragas_metrics import hit
from tests.eval.test_runner import MemoryStore

GIT_SHA = "c" * 40
SETTINGS = Settings(_env_file=None, openrouter_api_key=SecretStr("k"),  # pyright: ignore[reportCallIssue]
                    search_max_distance=0.3, search_min_keyword_idf=24.0)  # fmt: skip


def _hit(provision_id: str, similarity: float | None, idf: float | None = None,
         reference_rank: int | None = None) -> SearchHit:  # fmt: skip
    return hit(provision_id).model_copy(
        update={"similarity": similarity, "keyword_idf": idf, "reference_rank": reference_rank}
    )


class FakeSearch:
    """Answers like `search_ai_act` would over three rows: a meaning-arm hit at similarity
    `similarity` on `art:6:3`, a second on `art:6:2` at 0.6, and a keyword-only row of IDF
    `idf`. The cut-off drops meaning-arm rows below `1 - max_distance`."""

    def __init__(self, similarity: float = 0.75, idf: float = 12.0) -> None:
        self.similarity = similarity
        self.idf = idf
        self.calls: list[dict[str, object]] = []

    def __call__(self, query: str, language: Language, **kwargs: object) -> SearchResults:
        self.calls.append({"query": query, "language": language, **kwargs})
        embedder = kwargs["embedder"]
        assert isinstance(embedder, OnceEmbedder)
        embedder.embed_query(query)
        max_distance = kwargs["max_distance"]
        rows = [_hit("art:6:3", self.similarity), _hit("art:6:2", 0.6),
                _hit("art:99", None, self.idf)]  # fmt: skip
        kept = tuple(
            row for row in rows
            if row.similarity is None or max_distance is None
            or row.similarity >= 1 - float(max_distance)  # pyright: ignore[reportArgumentType]
        )  # fmt: skip
        limit = kwargs["limit"]
        assert isinstance(limit, int)
        return SearchResults(
            query=query, language=language, law_version=LawVersion.AMENDED,
            as_of=date(2026, 10, 10), hits=kept[:limit], max_distance=None, found=True,
            disclaimer="Guidance, not legal advice.",
        )  # fmt: skip


def _probe(kind: ProbeKind, targets: tuple[str, ...] = ()) -> Probe:
    return Probe(f"{kind.value}-1", "A probe.", Language.EN, kind, kind.value, targets)


# --- the probes --------------------------------------------------------------------------


def test_the_probes_are_every_qa_item_every_annex_description_and_the_off_topic_strings() -> None:
    qa_items = load_qa_items()
    probes = build_probes(qa_items, load_cases(CaseSet.ANNEX_MATCH))
    counts = {kind: sum(p.kind is kind for p in probes) for kind in ProbeKind}
    assert counts == {
        ProbeKind.ANSWERABLE: 29,
        ProbeKind.DESCRIPTION: 48,
        ProbeKind.UNANSWERABLE: 9,
        ProbeKind.OFF_TOPIC: 20,
    }
    off_topic_groups = [p.group for p in probes if p.kind is ProbeKind.OFF_TOPIC]
    assert (off_topic_groups.count("off_topic"), off_topic_groups.count("other_law_reference")) == (
        14,
        6,
    )
    groups = {p.group for p in probes if p.kind is ProbeKind.UNANSWERABLE}
    assert groups == {
        "unanswerable:other_law",
        "unanswerable:national_law",
        "unanswerable:off_topic",
    }
    answerable = next(p for p in probes if p.id == "qa-en-08-cv-screening")
    assert answerable.targets == ("annex:III:4:a", "art:6:2")
    assert len({p.id for p in probes}) == len(probes)


def test_the_off_topic_probes_are_in_both_languages() -> None:
    languages = [language for _, language, _ in OFF_TOPIC_PROBES]
    assert (languages.count(Language.EN), languages.count(Language.DE)) == (8, 6)


def test_the_other_law_probes_name_article_numbers_but_no_ai_act_reference() -> None:
    languages = [language for _, language, _ in OTHER_LAW_PROBES]
    assert (languages.count(Language.EN), languages.count(Language.DE)) == (3, 3)
    for _, _, text in OTHER_LAW_PROBES:
        assert any(word in text for word in ("Article", "Artikel", "Art.")), text
        assert exact_references(text) == (), text


def test_the_candidates_span_0_20_to_0_40() -> None:
    assert (DISTANCES[0], DISTANCES[-1], len(DISTANCES)) == (0.2, 0.4, 21)


# --- found -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("measurement", "found"),
    [
        (Measurement(0.70, None, is_named=False, found=False), True),
        (Measurement(0.69, None, is_named=False, found=False), False),
        (Measurement(0.69, 24.0, is_named=False, found=False), True),
        (Measurement(0.69, 23.9, is_named=False, found=False), False),
        (Measurement(None, None, is_named=True, found=False), True),
        (Measurement(None, None, is_named=False, found=False), False),
    ],
    ids=["similar enough", "too far", "rare words", "words too common", "named", "nothing"],
)
def test_found_needs_a_close_hit_rare_words_or_a_named_provision(
    measurement: Measurement, found: bool
) -> None:
    assert is_found(measurement, 0.30, 24.0) is found


def test_the_shares_and_the_spread_are_per_group() -> None:
    probes = [
        Probe("a", "q", Language.EN, ProbeKind.ANSWERABLE, "answerable"),
        Probe("b", "q", Language.DE, ProbeKind.ANSWERABLE, "answerable"),
        Probe("u", "q", Language.EN, ProbeKind.UNANSWERABLE, "unanswerable:other_law"),
    ]
    measurements = {
        "a": Measurement(0.80, 10.0, is_named=False, found=True, recall_by_distance={0.3: 1.0}),
        "b": Measurement(0.60, 30.0, is_named=False, found=True, recall_by_distance={0.3: 0.5}),
        "u": Measurement(0.65, None, is_named=False, found=False),
    }
    assert found_shares(probes, measurements, 0.30, 24.0) == {
        "answerable": 1.0,
        "unanswerable:other_law": 0.0,
    }
    assert found_shares(probes, measurements, 0.30, 31.0)["answerable"] == 0.5
    spread = distributions(probes, measurements)
    assert spread["answerable"] == {
        "n": 2,
        "similarity": [0.6, 0.7, 0.8],
        "keyword_idf": [10.0, 20.0, 30.0],
    }
    assert spread["answerable/de"] == {"n": 1, "similarity": [0.6, 0.6, 0.6],
                                       "keyword_idf": [30.0, 30.0, 30.0]}  # fmt: skip
    assert mean_recall(probes, measurements, 0.3) == 0.75
    assert mean_recall(probes, measurements, 0.4) is None


# --- measuring a probe -------------------------------------------------------------------


def test_a_probe_is_searched_uncut_with_every_meaning_row_cut_and_with_the_settings() -> None:
    search = FakeSearch(similarity=0.75, idf=12.0)
    embeddings = FakeEmbeddings()
    embedder = OnceEmbedder(UsageMeter().embedder("search", embeddings))
    measurement = measure(_probe(ProbeKind.UNANSWERABLE), embedder, None, SETTINGS, search=search)  # pyright: ignore[reportArgumentType]

    assert [call["max_distance"] for call in search.calls] == [None, 0.0, 0.3]
    assert {call["limit"] for call in search.calls} == {DEFAULT_LIMIT}
    assert (measurement.best_similarity, measurement.top_keyword_idf) == (0.75, 12.0)
    assert measurement.is_named is False
    assert measurement.found is True  # 0.75 is within the cut-off 0.3
    assert measurement.recall_by_distance == {}
    assert len(embeddings.batches) == 1  # embedded once for all three searches


def test_found_uses_the_runs_keyword_idf_not_the_process_setting() -> None:
    far = FakeSearch(similarity=0.65, idf=30.0)
    embedder = OnceEmbedder(UsageMeter().embedder("search", FakeEmbeddings()))
    probe = _probe(ProbeKind.OFF_TOPIC)
    assert measure(probe, embedder, None, SETTINGS, search=far).found is True  # pyright: ignore[reportArgumentType]
    strict = SETTINGS.model_copy(update={"search_min_keyword_idf": 30.1})
    assert measure(probe, embedder, None, strict, search=far).found is False  # pyright: ignore[reportArgumentType]


def test_an_answerable_probe_is_also_scored_at_every_candidate_distance() -> None:
    search = FakeSearch(similarity=0.75)
    embedder = OnceEmbedder(UsageMeter().embedder("search", FakeEmbeddings()))
    probe = _probe(ProbeKind.ANSWERABLE, ("art:6:3", "art:6:2"))
    measurement = measure(probe, embedder, None, SETTINGS, search=search)  # pyright: ignore[reportArgumentType]
    recall_calls = search.calls[3:]
    assert [call["max_distance"] for call in recall_calls] == list(DISTANCES)
    assert {call["limit"] for call in recall_calls} == {TOP_K}
    # art:6:3 (0.75) stays from 0.25 on, art:6:2 (0.6) from 0.40.
    assert measurement.recall_by_distance[0.2] == 0.0
    assert measurement.recall_by_distance[0.25] == 0.5
    assert measurement.recall_by_distance[0.4] == 1.0


def test_a_named_provision_counts_as_named() -> None:
    class NamedSearch(FakeSearch):
        def __call__(self, query: str, language: Language, **kwargs: object) -> SearchResults:
            results = super().__call__(query, language, **kwargs)
            named = _hit("art:50", None, reference_rank=1)
            return results.model_copy(update={"hits": (named, *results.hits)})

    embedder = OnceEmbedder(UsageMeter().embedder("search", FakeEmbeddings()))
    measurement = measure(_probe(ProbeKind.OFF_TOPIC), embedder, None, SETTINGS,  # pyright: ignore[reportArgumentType]
                          search=NamedSearch(similarity=0.1, idf=1.0))  # fmt: skip
    assert measurement.is_named is True
    assert measurement.found is True


# --- the run -----------------------------------------------------------------------------


def test_a_run_stores_one_row_per_probe_with_what_decides_found() -> None:
    store = MemoryStore()
    probes = [_probe(ProbeKind.ANSWERABLE, ("art:6:3",)),
              Probe("off-1", "Off.", Language.DE, ProbeKind.OFF_TOPIC, "off_topic")]  # fmt: skip
    calibration = run_calibration(probes, FakeEmbeddings(), store, None, SETTINGS,  # pyright: ignore[reportArgumentType]
                                  git_sha=GIT_SHA, search=FakeSearch())  # fmt: skip

    assert calibration.status is RunStatus.COMPLETED
    run = store.runs[calibration.run_id]
    assert (run["git_sha"], run["benchmark"]) == (GIT_SHA, "search_cutoff")
    config = run["config"]
    assert isinstance(config, dict)
    assert config["retrieval"]["max_distance"] == 0.3
    assert config["retrieval"]["min_keyword_idf"] == 24.0
    assert config["embedding"]["model"] == "m"
    _, answerable = store.cases[0]
    assert answerable.case_id == "answerable-1"
    assert answerable.label["kind"] == "answerable"
    assert answerable.scores["best_similarity"] == 0.75
    assert answerable.scores["top_keyword_idf"] == 12.0
    assert answerable.scores["recall_at_0.30"] == 1.0
    _, off = store.cases[1]
    assert off.label == {"kind": "off_topic", "group": "off_topic", "language": "de",
                         "targets": []}  # fmt: skip
    assert not any(key.startswith("recall_at") for key in off.scores)
    outcome = store.outcomes[calibration.run_id]
    assert outcome["status"] == "completed"
    assert (outcome["cases_planned"], outcome["cases_scored"]) == (2, 2)
    assert outcome["found_share_at_settings"] == {"answerable": 1.0, "off_topic": 1.0}
    # Both probes' best hit is at 0.75 and their best keyword row at 12.0 (`FakeSearch`).
    one = {"n": 1, "similarity": [0.75, 0.75, 0.75], "keyword_idf": [12.0, 12.0, 12.0]}
    assert outcome["distributions"] == {
        "answerable": one,
        "answerable/en": one,
        "off_topic": one,
        "off_topic/de": one,
    }
    assert calibration.cost_usd == pytest.approx(0.0002)  # one embedding per probe
    assert [record.cost_usd for _, record in store.cases] == pytest.approx([0.0001, 0.0001])
    assert [record.tokens for _, record in store.cases] == [7, 7]


def test_the_cost_cap_stops_new_probes() -> None:
    store = MemoryStore()
    probes = [_probe(ProbeKind.OFF_TOPIC), _probe(ProbeKind.UNANSWERABLE)]
    calibration = run_calibration(probes, FakeEmbeddings(), store, None, SETTINGS,  # pyright: ignore[reportArgumentType]
                                  git_sha=GIT_SHA, max_cost_usd=0.0001,
                                  search=FakeSearch())  # fmt: skip
    assert calibration.status is RunStatus.COST_CAP_REACHED
    assert len(store.cases) == 1
    assert store.outcomes[calibration.run_id]["status"] == "cost_cap_reached"


def test_an_unknown_cost_stops_the_run() -> None:
    store = MemoryStore()
    probes = [_probe(ProbeKind.OFF_TOPIC), _probe(ProbeKind.UNANSWERABLE)]
    calibration = run_calibration(probes, FakeEmbeddings(is_cost_known=False), store, None,  # pyright: ignore[reportArgumentType]
                                  SETTINGS, git_sha=GIT_SHA, search=FakeSearch())  # fmt: skip
    assert calibration.status is RunStatus.COST_CAP_REACHED
    assert len(store.cases) == 1


def test_an_interrupted_run_is_marked_and_the_error_goes_on() -> None:
    class Failing(FakeSearch):
        def __call__(self, query: str, language: Language, **kwargs: object) -> SearchResults:
            raise RuntimeError("database went away")

    store = MemoryStore()
    with pytest.raises(RuntimeError, match="database went away"):
        run_calibration([_probe(ProbeKind.OFF_TOPIC)], FakeEmbeddings(), store, None, SETTINGS,  # pyright: ignore[reportArgumentType]
                        git_sha=GIT_SHA, search=Failing())  # fmt: skip
    (outcome,) = store.outcomes.values()
    assert outcome["status"] == "interrupted"


# --- the command -------------------------------------------------------------------------


def test_the_command_measures_every_probe_and_prints_the_sweep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    seen: list[int] = []

    def fake_run(probes: list[Probe], *args: object, **kwargs: object):
        seen.append(len(probes))
        return run_calibration(probes[:2], FakeEmbeddings(), store, None, SETTINGS,  # pyright: ignore[reportArgumentType]
                               git_sha=GIT_SHA, search=FakeSearch())  # fmt: skip

    monkeypatch.setattr(records, "connect", contextlib.nullcontext)
    monkeypatch.setattr(records, "PostgresRunStore", lambda connection: store)
    monkeypatch.setattr(search_cutoff, "run_calibration", fake_run)
    monkeypatch.setattr("aiact.cli.OpenRouterEmbeddings", lambda settings: None)
    monkeypatch.setattr("aiact.cli.get_settings", lambda: SETTINGS)
    result = CliRunner().invoke(app, ["evaluate", "search-cutoff"])
    assert result.exit_code == 0, result.output
    assert seen == [106]
    assert "completed, 2/2 probes" in result.stdout
    assert "found share by cut-off" in result.stdout
    # The first two probes are answerable items whose provisions the fake never returns.
    assert "  0.30: {'answerable': 1.0}, recall 0.0" in result.stdout
    assert "found share by keyword IDF (cut-off 0.3)" in result.stdout
