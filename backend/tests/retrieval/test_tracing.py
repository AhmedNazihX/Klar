"""The lookups as LangSmith runs (V7): traced only under a current trace, with the provision id or
the search's document filter as metadata once the lookup resolved, never the query, and never a
connection's text. Nothing reaches the network: posts go to a recording session."""

import json
from collections.abc import Callable
from datetime import date
from typing import Any, NotRequired, TypedDict

import pytest
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree, tracing_context

from aiact.engine.tracing import build_client
from aiact.retrieval import provisions, search, tracing
from aiact.retrieval.provisions import ProvisionNotFoundError, get_provision
from aiact.retrieval.search import search_ai_act
from tests.engine.test_tracing import RecordingSession

SECRET = "the night shifts of our Leipzig depot"
CONNECTION_TEXT = "host=db.internal user=aiact_admin"
INVENTED_ID = "art:5:Leipzig_depot_night_shift"
"""An id a model made up from the description's words: it resolves nowhere."""


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
    """Every provision id but `INVENTED_ID` resolves to `ROW`; every search finds nothing."""

    def rows(query: object, params: dict[str, object], connection: object) -> list[object]:
        return [] if params["provision_id"] == INVENTED_ID else [ROW]

    monkeypatch.setattr(provisions, "_rows", rows)
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
    """The fields of a posted run these tests read: its create post, updated by its end post."""

    id: str
    name: str
    parent_run_id: str | None
    extra: dict[str, dict[str, object]]
    error: NotRequired[str | None]


class UrlRecordingSession(RecordingSession):
    """A recording session that also keeps each request's method and URL."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[tuple[str, str, str]] = []

    def request(self, method: str | bytes, url: str | bytes, *args: object, **kwargs: object):  # type: ignore[override]
        response = super().request(method, url, *args, **kwargs)
        self.requests.append((str(method).upper(), str(url), self.sent[-1]))
        return response


def posted_runs(session: UrlRecordingSession) -> dict[str, PostedRun]:
    """Every posted run by id: its create post, with its end post's error and metadata merged."""
    runs: dict[str, PostedRun] = {}
    for method, url, body in session.requests:
        payload: dict[str, Any] = json.loads(body) if body.startswith("{") else {}
        if method == "POST" and "name" in payload:
            runs[payload["id"]] = PostedRun(**payload)  # pyright: ignore[reportArgumentType]
        elif method == "PATCH":
            run = runs[url.rstrip("/").rsplit("/", 1)[-1]]
            run["error"] = payload.get("error")
            run["extra"] = payload.get("extra") or run["extra"]
    return runs


def traced(lookups: Callable[[], None], *, is_metadata_only: bool = True) -> UrlRecordingSession:
    """`lookups` under one traced parent run, posting into a recording session."""
    session = UrlRecordingSession()
    client = build_client(
        "lsv2-test-key",
        is_metadata_only=is_metadata_only,
        api_url="http://127.0.0.1:9",
        session=session,
        auto_batch_tracing=False,
    )

    @traceable(name="prohibited", client=client)
    def step() -> None:
        lookups()

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
    runs = {run["name"]: run for run in posted_runs(traced(_lookups)).values()}
    assert set(runs) == {"prohibited", "get_provision", "search_ai_act"}
    lookup, found = runs["get_provision"], runs["search_ai_act"]
    assert lookup["parent_run_id"] == runs["prohibited"]["id"]
    assert found["parent_run_id"] == runs["prohibited"]["id"]
    assert lookup["extra"]["metadata"][tracing.PROVISION_ID] == "art:5"
    assert found["extra"]["metadata"][tracing.DOC_KEYS] == ["guide-prohibited"]
    assert tracing.DOC_TYPES not in found["extra"]["metadata"]


def test_a_lookup_that_resolves_nowhere_posts_no_provision_id(no_database: None) -> None:
    """The citation validator looks up whatever id a model cited; one made of the description's
    words must not reach the trace."""

    def invented() -> None:
        with pytest.raises(ProvisionNotFoundError):
            get_provision(INVENTED_ID, connection=FakeConnection())  # pyright: ignore[reportArgumentType]

    session = traced(invented)
    [lookup] = [run for run in posted_runs(session).values() if run["name"] == "get_provision"]
    assert lookup.get("error")  # the failed lookup is still a run, marked failed
    assert tracing.PROVISION_ID not in lookup["extra"].get("metadata", {})
    assert not [body for body in session.sent if "Leipzig" in body]


def test_a_metadata_only_trace_posts_neither_the_query_nor_the_connection(
    no_database: None,
) -> None:
    sent = traced(_lookups).sent
    assert sent
    assert not [body for body in sent if SECRET in body or CONNECTION_TEXT in body]


def test_the_connection_is_dropped_from_the_inputs_before_the_client_sees_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In production the client hides every input anyway; the run's own inputs, read inside the
    lookup, show the connection was dropped before that."""
    seen: list[dict[str, Any]] = []

    def rows(query: object, params: object, connection: object) -> list[object]:
        run = get_current_run_tree()
        assert run is not None
        seen.append(dict(run.inputs))
        return [ROW]

    monkeypatch.setattr(provisions, "_rows", rows)
    connection = FakeConnection()
    traced(lambda: get_provision("art:5", connection=connection))  # pyright: ignore[reportArgumentType]
    [inputs] = seen
    assert inputs["provision_id"] == "art:5"
    assert "connection" not in inputs
    assert CONNECTION_TEXT not in repr(inputs)


def test_a_development_trace_posts_the_query_but_never_the_connection(no_database: None) -> None:
    """The check above can fail: in development the query reaches the posts."""
    sent = traced(_lookups, is_metadata_only=False).sent
    assert [body for body in sent if SECRET in body]
    assert not [body for body in sent if CONNECTION_TEXT in body]


HELD_OUT_TEXT = "the confidential worked example text"


def _search_row(row_id: int, provision_id: str) -> dict[str, object]:
    return ROW | {
        "id": row_id, "ancestors": [], "provision_id": provision_id, "text": HELD_OUT_TEXT,
        "score": 0.5, "vector_rank": row_id, "keyword_rank": None, "distance": 0.4,
        "keyword_idf": None, "reference_rank": None,
    }  # fmt: skip


def test_a_search_posts_the_ids_it_returned_but_never_their_text(
    no_database: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V8: the gap run's traces must show which (held-out) rows a search returned."""
    found_rows = [_search_row(1, "guide:x:ex:hr-ex-002"), _search_row(2, "art:5")]
    monkeypatch.setattr(search, "_run", lambda connection, statement, params: found_rows)
    session = traced(_lookups)
    [found] = [run for run in posted_runs(session).values() if run["name"] == "search_ai_act"]
    assert found["extra"]["metadata"][tracing.HIT_IDS] == ["guide:x:ex:hr-ex-002", "art:5"]
    assert not [body for body in session.sent if HELD_OUT_TEXT in body]


def test_a_search_that_found_nothing_posts_no_ids(no_database: None) -> None:
    runs = {run["name"]: run for run in posted_runs(traced(_lookups)).values()}
    assert runs["search_ai_act"]["extra"]["metadata"][tracing.HIT_IDS] == []


def test_search_metadata_holds_the_filters_only() -> None:
    inputs = {"query": SECRET, "doc_keys": frozenset({"b", "a"}), "doc_types": None}
    assert tracing.search_metadata(inputs) == {
        tracing.DOC_KEYS: ["a", "b"],
        tracing.DOC_TYPES: None,
    }
