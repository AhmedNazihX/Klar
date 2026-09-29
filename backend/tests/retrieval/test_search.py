"""`search_ai_act` checks that need no database: argument errors, the query-side instruction and the
parent/child rule (the searches themselves are in tests/db/test_search_ai_act.py)."""

from datetime import date
from typing import Any

import pytest

from aiact.retrieval.search import CANDIDATES, prefer_children, search_ai_act


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


def _row(row_id: int, parent_id: int | None) -> dict[str, Any]:
    return {"id": row_id, "parent_id": parent_id}


def test_a_parent_gives_way_to_its_child() -> None:
    rows = [_row(1, None), _row(2, 1), _row(3, 2), _row(4, None), _row(5, 9)]
    assert [row["id"] for row in prefer_children(rows)] == [3, 4, 5]


def test_prefer_children_keeps_the_order() -> None:
    rows = [_row(3, 1), _row(4, None), _row(1, None), _row(2, 1)]
    assert [row["id"] for row in prefer_children(rows)] == [3, 4, 2]
