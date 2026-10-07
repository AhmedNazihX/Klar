"""The lookups as LangSmith runs (V7): traced only under a current trace, with the provision id or
the search's document filter as metadata, never the query, and never a connection's text.
Nothing reaches the network: posts go to a recording session."""

import json
from datetime import date
from typing import TypedDict

import pytest
from langsmith import traceable
from langsmith.run_helpers import tracing_context

from aiact.engine.tracing import build_client
from aiact.retrieval import provisions, search, tracing
from aiact.retrieval.provisions import get_provision
from aiact.retrieval.search import search_ai_act
from tests.engine.test_tracing import RecordingSession

SECRET = "the night shifts of our Leipzig depot"
CONNECTION_TEXT = "host=db.internal user=aiact_admin"


class FakeConnection:
    """A connection whose text names a host and a user, as psycopg's does."""

    def __repr__(self) -> str:
        return f"<psycopg.Connection ({CONNECTION_TEXT})>"


class FakeEmbedder:
    model = "test/fake"
    dimensions = 3

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


ROW = {
    "doc_key": "ai-act-consolidated", "title": "AI Act", "doc_type": "law",
    "status": "consolidated", "law_version": "amended", "language": "en", "heading": "Article 5",
    "text": "Prohibited…",
    "valid_from": date(2024, 8, 1), "valid_to": None,
}  # fmt: skip


@pytest.fixture
def no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provisions, "_rows", lambda query, params, connection: [ROW])
    monkeypatch.setattr(search, "_run", lambda connection, statement, params: [])


def _lookups() -> None:
    connection = FakeConnection()
    get_provision("art:5", connection=connection)  # pyright: ignore[reportArgumentType]
    search_ai_act(
        SECRET,
        doc_keys={"guide-prohibited"},
        max_distance=None,
        embedder=FakeEmbedder(),
        connection=connection,  # pyright: ignore[reportArgumentType]
    )


class PostedRun(TypedDict):
    """The fields of a posted run these tests read."""

    id: str
    name: str
    parent_run_id: str | None
    extra: dict[str, dict[str, object]]


def _posted_runs(session: RecordingSession) -> list[PostedRun]:
    return [json.loads(body) for body in session.sent if body.startswith("{")]


def _traced_lookups(*, is_metadata_only: bool) -> RecordingSession:
    """The lookups under one traced parent run, posting into a recording session."""
    session = RecordingSession()
    client = build_client(
        "lsv2-test-key",
        is_metadata_only=is_metadata_only,
        api_url="http://127.0.0.1:9",
        session=session,
        auto_batch_tracing=False,
    )

    @traceable(name="prohibited", client=client)
    def step() -> None:
        _lookups()

    with tracing_context(enabled=True, client=client):
        step()
    client.flush()
    return session


def test_outside_a_trace_a_lookup_is_not_traced(no_database: None) -> None:
    session = RecordingSession()
    client = build_client(
        "lsv2-test-key",
        is_metadata_only=False,
        api_url="http://127.0.0.1:9",
        session=session,
        auto_batch_tracing=False,
    )
    with tracing_context(enabled=True, client=client):  # as LANGSMITH_TRACING=true would
        _lookups()
    client.flush()
    assert session.sent == []


def test_under_a_trace_each_lookup_is_a_run_with_its_metadata(no_database: None) -> None:
    runs = {run["name"]: run for run in _posted_runs(_traced_lookups(is_metadata_only=True))}
    assert set(runs) == {"prohibited", "get_provision", "search_ai_act"}
    lookup, found = runs["get_provision"], runs["search_ai_act"]
    assert lookup["parent_run_id"] == runs["prohibited"]["id"]
    assert found["parent_run_id"] == runs["prohibited"]["id"]
    assert lookup["extra"]["metadata"][tracing.PROVISION_ID] == "art:5"
    assert found["extra"]["metadata"][tracing.DOC_KEYS] == ["guide-prohibited"]
    assert tracing.DOC_TYPES not in found["extra"]["metadata"]


def test_a_metadata_only_trace_posts_neither_the_query_nor_the_connection(
    no_database: None,
) -> None:
    sent = _traced_lookups(is_metadata_only=True).sent
    assert sent
    assert not [body for body in sent if SECRET in body or CONNECTION_TEXT in body]


def test_a_development_trace_posts_the_query_but_never_the_connection(no_database: None) -> None:
    """The check above can fail: in development the query reaches the posts."""
    sent = _traced_lookups(is_metadata_only=False).sent
    assert [body for body in sent if SECRET in body]
    assert not [body for body in sent if CONNECTION_TEXT in body]


def test_search_metadata_holds_the_filters_only() -> None:
    inputs = {"query": SECRET, "doc_keys": frozenset({"b", "a"}), "doc_types": None}
    assert tracing.search_metadata(inputs) == {
        tracing.DOC_KEYS: ["a", "b"],
        tracing.DOC_TYPES: None,
    }
    assert tracing.provision_metadata({"provision_id": "art:50"}) == {
        tracing.PROVISION_ID: "art:50"
    }
