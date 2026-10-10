"""`search_ai_act` checks that need no database: argument errors, the query-side instruction, the
parent/child rule, the statement's vector arm and the relevance signals (the searches themselves
are in tests/db/test_search_ai_act.py)."""

from datetime import date
from typing import Any

import pytest

from aiact.retrieval import search
from aiact.retrieval.search import (
    CANDIDATES,
    distinct_units,
    prepare_search,
    search_ai_act,
)
from aiact.schemas import Language, LawVersion
from aiact.settings import DEFAULT_MIN_KEYWORD_IDF, Settings


class RecordingEmbedder:
    """Stands in for `OpenRouterEmbeddings`; remembers what it was asked to embed."""

    model = "test/fake"
    dimensions = 3

    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [1.0, 0.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("search must embed the query with embed_query")


class NoConnection:
    """Fails the test if a search gets as far as the database."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the database was used ({name})")


def _search(query: str = "credit scoring", **kwargs: Any) -> None:
    search_ai_act(query, embedder=RecordingEmbedder(), connection=NoConnection(), **kwargs)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("query", ["", "   ", "\n"])
def test_an_empty_query_is_rejected(query: str) -> None:
    with pytest.raises(ValueError, match="the search query is empty"):
        _search(query)


@pytest.mark.parametrize("limit", [0, -1, CANDIDATES + 1])
def test_a_limit_outside_the_candidate_pool_is_rejected(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be between 1 and"):
        _search(limit=limit)


def test_an_unknown_doc_type_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"unknown doc types \['faq'\]"):
        _search(doc_types={"law", "faq"})


def test_original_with_as_of_is_rejected() -> None:
    with pytest.raises(ValueError, match="as_of resolves only against the amended text"):
        _search(law_version="original", as_of=date(2026, 9, 29))


@pytest.mark.parametrize(("language", "law_version"), [("fr", None), ("en", "draft")])
def test_unknown_language_or_version_strings_raise(language: str, law_version: str | None) -> None:
    with pytest.raises(ValueError, match="is not a valid"):
        _search(language=language, law_version=law_version)


def test_non_integer_dimensions_are_rejected() -> None:
    embedder = RecordingEmbedder()
    embedder.dimensions = "3; drop table provisions"  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(ValueError, match="embedding dimensions must be a positive integer"):
        search_ai_act("credit", embedder=embedder, connection=NoConnection())  # pyright: ignore[reportArgumentType]


def test_the_query_goes_through_embed_query_as_given() -> None:
    """The task instruction is the embedder's job (`embed_query` adds it, `embed_documents`
    never does); search hands it the raw query once, without adding anything itself."""
    embedder = RecordingEmbedder()
    with pytest.raises(AssertionError, match="the database was used"):
        search_ai_act("tenant screening", embedder=embedder, connection=NoConnection())  # pyright: ignore[reportArgumentType]
    assert embedder.queries == ["tenant screening"]


def _row(row_id: int, *ancestors: int) -> dict[str, Any]:
    return {"id": row_id, "ancestors": list(ancestors)}


def _ids(rows: list[dict[str, Any]]) -> list[int]:
    return [row["id"] for row in rows]


def test_the_better_ranked_of_parent_and_child_wins() -> None:
    parent_first = [_row(1), _row(2, 1), _row(4)]
    child_first = [_row(2, 1), _row(1), _row(4)]
    assert _ids(distinct_units(parent_first, 10)) == [1, 4]
    assert _ids(distinct_units(child_first, 10)) == [2, 4]


def test_the_whole_ancestry_counts_even_without_the_middle_level() -> None:
    """Row 3's chain is 2 -> 1; row 2 isn't a hit, yet 3 and 1 still overlap."""
    assert _ids(distinct_units([_row(1), _row(3, 2, 1), _row(5)], 10)) == [1, 5]
    assert _ids(distinct_units([_row(3, 2, 1), _row(1), _row(5)], 10)) == [3, 5]


def test_a_child_below_the_limit_doesnt_remove_its_parent() -> None:
    rows = [_row(1), _row(4), _row(6), _row(2, 1)]
    assert _ids(distinct_units(rows, 2)) == [1, 4]


def test_the_limit_counts_distinct_units() -> None:
    rows = [_row(1), _row(2, 1), _row(3, 1), _row(4), _row(5)]
    assert _ids(distinct_units(rows, 3)) == [1, 4, 5]


@pytest.mark.parametrize("max_distance", [-0.1, 2.1, float("nan"), float("inf")])
def test_a_max_distance_outside_0_to_2_is_rejected(max_distance: float) -> None:
    with pytest.raises(ValueError, match="max_distance must be between 0 and 2"):
        _search(max_distance=max_distance)


def _vector_arm(max_distance: float | None) -> str:
    """The statement's meaning arm: the nearest rows and their ranking, up to the keyword arm."""
    _, statement = prepare_search(
        "credit scoring", Language.EN, LawVersion.AMENDED, None, None, ("hr-ex-9",), False, 10,
        RecordingEmbedder(), max_distance=max_distance,
    )  # fmt: skip
    text = statement.as_string()
    return text[text.index("vector_hits as materialized") : text.index("query_terms as")]


def test_the_vector_arm_keeps_the_held_out_and_exclude_filters() -> None:
    """B13: CI has no corpus vectors, so this pins the meaning arm's filters on the statement."""
    nearest = _vector_arm(0.3).split("vector_ranked as")[0]
    assert "(%(include_held_out)s or not p.is_held_out)" in nearest
    assert "not (p.source_example_id = any(%(exclude_source_example_ids)s::text[]))" in nearest


def test_both_arms_keep_every_filter_when_doc_keys_is_set() -> None:
    """The doc_keys filter sits inside the SQL of both arms, next to the held-out and exclude
    filters, which it never replaces."""
    params, statement = prepare_search(
        "credit scoring", Language.EN, LawVersion.AMENDED, None, None, ("hr-ex-9",), False, 10,
        RecordingEmbedder(), doc_keys={"guide-definition"},
    )  # fmt: skip
    text = statement.as_string()
    nearest = text[text.index("vector_hits as materialized") : text.index("vector_ranked as")]
    keyword = text[text.index("keyword_ranked as") : text.index("fused as")]
    for arm in (nearest, keyword):
        assert "d.doc_key = any(%(doc_keys)s::text[])" in arm
        assert "(%(include_held_out)s or not p.is_held_out)" in arm
        assert "not (p.source_example_id = any(%(exclude_source_example_ids)s::text[]))" in arm
    assert params["doc_keys"] == ["guide-definition"]
    assert params["include_held_out"] is False


def test_doc_keys_defaults_to_every_document_and_rejects_an_empty_set() -> None:
    params, _ = prepare_search(
        "q", Language.EN, LawVersion.AMENDED, None, None, (), False, 10, RecordingEmbedder()
    )
    assert params["doc_keys"] is None
    with pytest.raises(ValueError, match="doc_keys is empty"):
        _search(doc_keys=set())


def test_the_cut_off_is_in_the_vector_arm_after_the_nearest_rows() -> None:
    nearest, ranked = _vector_arm(0.3).split("vector_ranked as")
    assert "max_distance" not in nearest
    assert "distance <= %(max_distance)s::float8" in ranked


class CapturedRun:
    """Stands in for `search._run`: keeps the parameters and returns the given rows."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.params: dict[str, Any] = {}

    def __call__(self, connection: object, statement: object, params: dict[str, Any]):
        self.params = params
        return self.rows


def _fused_row(row_id: int, distance: float | None, keyword_idf: float | None) -> dict[str, Any]:
    return {
        "id": row_id, "ancestors": [], "score": 0.01, "vector_rank": None if distance is None
        else row_id, "keyword_rank": None if keyword_idf is None else row_id,
        "reference_rank": None, "distance": distance, "keyword_idf": keyword_idf,
        "provision_id": f"art:{row_id}",
        "doc_key": "ai-act-consolidated", "title": "AI Act", "doc_type": "law",
        "law_version": "amended", "status": "consolidated", "language": "en", "heading": None,
        "text": "…", "valid_from": date(2024, 8, 1), "valid_to": None,
    }  # fmt: skip


def _captured_search(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, Any]],
    setting: float | None = None,
    **kwargs: Any,
) -> tuple[search.SearchResults, dict[str, Any]]:
    run = CapturedRun(rows)
    monkeypatch.setattr(search, "_run", run)
    settings = Settings(_env_file=None, search_max_distance=setting)  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr(search, "get_settings", lambda: settings)
    results = search_ai_act("credit", embedder=RecordingEmbedder(), connection=NoConnection(),  # pyright: ignore[reportArgumentType]
                            **kwargs)  # fmt: skip
    return results, run.params


def test_max_distance_defaults_to_the_setting_and_none_turns_it_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    by_default, params = _captured_search(monkeypatch, [], setting=0.3)
    assert (by_default.max_distance, params["max_distance"]) == (0.3, 0.3)
    explicit, params = _captured_search(monkeypatch, [], setting=0.3, max_distance=None)
    assert (explicit.max_distance, params["max_distance"]) == (None, None)
    unset, params = _captured_search(monkeypatch, [])
    assert (unset.max_distance, params["max_distance"]) == (None, None)


def test_hits_carry_the_similarity_and_the_keyword_idf(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_fused_row(1, 0.25, 3.5), _fused_row(2, None, 1.0), _fused_row(3, 0.5, None)]
    hits = _captured_search(monkeypatch, rows)[0].hits
    assert [(h.similarity, h.keyword_idf) for h in hits] == [(0.75, 3.5), (None, 1.0), (0.5, None)]


@pytest.mark.parametrize(
    ("rows", "found"),
    [
        ([], False),
        ([_fused_row(1, 0.4, None)], True),
        ([_fused_row(1, None, DEFAULT_MIN_KEYWORD_IDF)], True),
        ([_fused_row(1, None, DEFAULT_MIN_KEYWORD_IDF - 0.01), _fused_row(2, None, 1.0)], False),
    ],
    ids=["no hits", "a meaning-arm hit", "a strong keyword match", "only weak keyword matches"],
)
def test_found_needs_a_meaning_arm_hit_or_a_strong_keyword_match(
    monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]], found: bool
) -> None:
    assert _captured_search(monkeypatch, rows, setting=0.3)[0].found is found
