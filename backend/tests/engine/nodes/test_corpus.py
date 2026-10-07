"""The checks' corpus reader and the short connection each step reads it over (E15): a given
library is read as it is, with no connection and no embedder built; the live corpus is built
over a fresh connection per use, closed before the use returns, and embeds with the run's
embedder, or with one built from the check's settings."""

from datetime import date

import psycopg
import pytest
from pydantic import SecretStr

from aiact.engine.nodes import corpus as corpus_module
from aiact.engine.nodes.common import Lookup
from aiact.engine.nodes.corpus import CorpusReader, CorpusReading
from aiact.llm import LLMConfigError
from aiact.retrieval.search import QueryEmbedder
from aiact.schemas import Language, LawVersion
from aiact.settings import Settings

LOOKUP = Lookup(Language.DE, LawVersion.AMENDED, date(2026, 10, 6), ("hr-ex-001",))


class Embedder:
    model = "qwen/qwen3-embedding-8b"
    dimensions = 2

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeConnection:
    """Open from `connect()` until its `with` block ends."""

    def __init__(self) -> None:
        self.is_open = True

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        self.is_open = False


def settings(**values: object) -> Settings:
    configured: dict[str, object] = {
        "openrouter_api_key": SecretStr("k"),
        "embedding_model": "qwen/qwen3-embedding-8b",
        "embedding_provider": "nebius",
        **values,
    }
    return Settings(_env_file=None, **configured)  # pyright: ignore[reportCallIssue]


def live(connection: psycopg.Connection, embedder: QueryEmbedder) -> tuple[object, object]:
    return connection, embedder


def test_a_given_library_is_read_without_a_connection_or_an_embedder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_connect() -> None:
        raise AssertionError("a given library needs no connection")

    monkeypatch.setattr(corpus_module, "connect", no_connect)
    library = object()
    # No embedding settings: a given library builds no embedder.
    reading = CorpusReading(library, live, settings=settings(embedding_model=None))
    assert reading(lambda used: used) is library


def test_the_live_corpus_is_read_over_a_connection_closed_after_each_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[FakeConnection] = []

    def fake_connect() -> FakeConnection:
        opened.append(FakeConnection())
        return opened[-1]

    monkeypatch.setattr(corpus_module, "connect", fake_connect)
    embedder = Embedder()
    reading = CorpusReading(None, live, embedder=embedder)
    for _ in range(2):
        connection, used = reading(lambda library: library)
        assert isinstance(connection, FakeConnection) and connection.is_open is False
        assert used is embedder
    assert len(opened) == 2
    assert not any(connection.is_open for connection in opened)


def test_without_an_embedder_the_live_corpus_builds_one_from_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[Settings | None] = []

    class Embeddings(Embedder):
        def __init__(self, settings: Settings | None = None) -> None:
            built.append(settings)

    monkeypatch.setattr(corpus_module, "connect", FakeConnection)
    monkeypatch.setattr(corpus_module, "OpenRouterEmbeddings", Embeddings)
    configured = settings()
    reading = CorpusReading(None, live, settings=configured)
    reading(lambda library: library)
    reading(lambda library: library)
    assert built == [configured]  # once, when the check is built


def test_without_a_library_or_an_embedder_the_embedding_settings_are_needed() -> None:
    with pytest.raises(LLMConfigError):
        CorpusReading(None, live, settings=settings(embedding_provider=None))


def test_a_search_passes_the_runs_lookup_and_no_cut_off(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class NoHits:
        hits = ()

    def search(*args: object, **kwargs: object) -> NoHits:
        seen.append((args, kwargs))
        return NoHits()

    monkeypatch.setattr(corpus_module, "search_ai_act", search)
    connection = FakeConnection()
    embedder = Embedder()
    reader = CorpusReader(connection, embedder)  # type: ignore[arg-type]
    assert (
        reader.passages("q", LOOKUP, language=Language.EN, limit=4, doc_types={"guideline"}) == ()
    )
    [(args, kwargs)] = seen
    assert args == ("q", Language.EN, LawVersion.AMENDED, date(2026, 10, 6))
    assert kwargs == {
        "doc_keys": None,
        "doc_types": {"guideline"},
        "exclude_source_example_ids": ("hr-ex-001",),
        "include_held_out": False,
        "max_distance": None,
        "limit": 4,
        "embedder": embedder,
        "connection": connection,
    }
