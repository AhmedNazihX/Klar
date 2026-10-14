"""The API in replay mode that the end-to-end tests run against (P13): the date it pins, the
recordings it merges, the settings it refuses, and a whole classification through it. No model,
network or database is used."""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import FastAPI
from pydantic import SecretStr

from aiact.engine import ClassifyEvent, ErrorEvent, ResultEvent
from aiact.schemas import RiskClass
from aiact.settings import Settings, get_settings
from tests.api.conftest import BASE_URL, FULL_RUN, TEST_HOST, outline, sse_events
from tests.conftest import REPLAY_API_KEY
from tests.e2e.replay_server import (
    Message,
    PinnedRunDate,
    Receive,
    Scope,
    Send,
    merged_cassette,
    merged_corpus,
    replay_api,
    replay_settings,
    replayed_model_calls,
    use_only,
)
from tests.e2e.runs import (
    RUNS_FILE,
    WORKED_EXAMPLE_RECORDING,
    Recording,
    e2e_runs,
    replayed_recordings,
    run_date,
)
from tests.engine.nodes.known_gaps import raise_if_recording_stale
from tests.engine.replayed_engine import LUNA
from tests.engine.test_classify_worked_example import AS_OF, worked_example_request

ORIGIN = "http://127.0.0.1:4174"
AS_OF_TEXT = "2026-10-06"
MAX_BYTES = 1_024
E2E_DB = "postgresql://postgres:postgres@127.0.0.1:54332/postgres"
HOSTED_DB = "postgresql://postgres@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# --- PinnedRunDate ------------------------------------------------------------------------------


class Echo:
    """An ASGI app that keeps the body and headers it was given."""

    def __init__(self) -> None:
        self.body = b""
        self.headers: dict[bytes, bytes] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.headers = dict(scope["headers"])
        message = await receive()
        self.body = message["body"]
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})


async def _sent(path: str, body: bytes, method: str = "POST") -> Echo:
    echo = Echo()
    app = PinnedRunDate(echo, AS_OF, MAX_BYTES)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        await client.request(method, path, content=body)
    return echo


@pytest.mark.anyio
async def test_a_classification_without_a_date_gets_the_recordings_date() -> None:
    echo = await _sent("/classify", json.dumps({"description": "x", "language": "en"}).encode())
    assert json.loads(echo.body) == {"description": "x", "language": "en", "as_of": AS_OF_TEXT}
    assert echo.headers[b"content-length"] == str(len(echo.body)).encode()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "body", "method"),
    [
        ("/classify", json.dumps({"description": "x", "as_of": "2027-01-01"}).encode(), "POST"),
        ("/classify", b"not json", "POST"),
        ("/classify", b"[1, 2]", "POST"),
        ("/classify", json.dumps({"description": "x" * MAX_BYTES}).encode(), "POST"),
        ("/reports/result", json.dumps({"description": "x"}).encode(), "POST"),
        ("/classify", b"", "GET"),
    ],
    ids=["has-a-date", "not-json", "not-an-object", "too-long", "other-path", "not-a-post"],
)
async def test_every_other_request_passes_unchanged(path: str, body: bytes, method: str) -> None:
    echo = await _sent(path, body, method)
    assert echo.body == body


@pytest.mark.anyio
async def test_a_body_in_chunks_is_read_whole() -> None:
    chunks = [b'{"description": ', b'"x", "language": "en"}']
    given = iter(chunks)

    async def receive() -> Message:
        chunk = next(given)
        return {"type": "http.request", "body": chunk, "more_body": chunk is not chunks[-1]}

    async def send(message: Message) -> None:
        del message

    echo = Echo()
    scope: Scope = {"type": "http", "method": "POST", "path": "/classify", "headers": []}
    await PinnedRunDate(echo, AS_OF, MAX_BYTES)(scope, receive, send)
    assert json.loads(echo.body)["as_of"] == AS_OF_TEXT


@pytest.mark.anyio
async def test_a_body_cut_off_past_the_cap_reaches_the_app_whole_and_unchanged() -> None:
    chunks = [b"x" * (MAX_BYTES + 1), b"tail"]
    given = iter(chunks)

    async def receive() -> Message:
        chunk = next(given)
        return {"type": "http.request", "body": chunk, "more_body": chunk is not chunks[-1]}

    received: list[Message] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, send
        received.append(await receive())
        received.append(await receive())

    async def send(message: Message) -> None:
        del message

    headers = [(b"content-length", str(MAX_BYTES + 5).encode())]
    scope: Scope = {"type": "http", "method": "POST", "path": "/classify", "headers": headers}
    await PinnedRunDate(app, AS_OF, MAX_BYTES)(scope, receive, send)
    assert [message["body"] for message in received] == chunks
    assert [message["more_body"] for message in received] == [True, False]


# --- The recordings -----------------------------------------------------------------------------


def _recording(folder: Path, name: str, bodies: list[str], corpus: dict[str, object]) -> Recording:
    recording = Recording(folder / name)
    cassette = {"interactions": [{"request": {"body": body}} for body in bodies]}
    recording.cassette.write_text(yaml.safe_dump(cassette), encoding="utf-8")
    recording.corpus.write_text(json.dumps(corpus), encoding="utf-8")
    return recording


def test_the_merged_recordings_hold_every_interaction_and_answer(tmp_path: Path) -> None:
    first = _recording(tmp_path, "first", ["a", "b"], {"k1": [1], "shared": [2]})
    second = _recording(tmp_path, "second", ["c"], {"k2": [3], "shared": [2]})
    cassette = merged_cassette([first, second], tmp_path / "cassette.yaml")
    corpus = merged_corpus([first, second], tmp_path / "corpus.json")
    interactions = yaml.safe_load(cassette.read_text(encoding="utf-8"))["interactions"]
    assert [interaction["request"]["body"] for interaction in interactions] == ["a", "b", "c"]
    assert json.loads(corpus.read_text(encoding="utf-8")) == {
        "k1": [1],
        "k2": [3],
        "shared": [2],
    }


def test_two_recordings_answering_one_question_differently_are_refused(tmp_path: Path) -> None:
    first = _recording(tmp_path, "first", ["a"], {"shared": [1]})
    second = _recording(tmp_path, "second", ["b"], {"shared": [2]})
    with pytest.raises(ValueError, match="answers shared differently"):
        merged_corpus([first, second], tmp_path / "corpus.json")


def test_the_worked_example_is_always_replayed_and_unrecorded_runs_are_left_out() -> None:
    recordings = replayed_recordings()
    assert recordings[0] == Recording(WORKED_EXAMPLE_RECORDING)
    assert all(recording.exists for recording in recordings)


def test_the_runs_file_types_the_worked_example_on_its_recording_date() -> None:
    data = json.loads(RUNS_FILE.read_text(encoding="utf-8"))
    assert data["workedExample"] == worked_example_request().description
    assert run_date() == AS_OF == date(2026, 10, 6)
    assert all(run.as_of == AS_OF for run in e2e_runs().values())


# --- The settings -------------------------------------------------------------------------------


def test_the_settings_use_the_replay_key_and_model_and_no_tracing() -> None:
    settings = replay_settings(ORIGIN)
    assert settings.openrouter_api_key == SecretStr(REPLAY_API_KEY)
    assert settings.engine_model == LUNA == "openai/gpt-6-luna-20260922"
    assert settings.engine_provider == "azure/eu"
    assert settings.langsmith_api_key is None
    assert settings.database_url == SecretStr(E2E_DB)
    assert settings.cors_origins == (ORIGIN,)
    assert settings.export_max_concurrent == 8


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`backend/.env` stood in for by a file that names a hosted database and a tracing key; the
    settings, the environment and the settings cache are put back afterwards."""
    file = tmp_path / ".env"
    file.write_text(
        f"DATABASE_URL={HOSTED_DB}\nLANGSMITH_API_KEY=from-the-file\nOPENROUTER_API_KEY=key-from-the-file\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(Settings.model_config, "env_file", file)
    for name in ("DATABASE_URL", "OPENROUTER_API_KEY", "LANGSMITH_API_KEY"):
        # Empty is unset to the settings (`env_ignore_empty`), and is undone afterwards even
        # where the variable didn't exist (a `delenv` of a missing one wouldn't be).
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("env_file")
def test_the_process_settings_never_read_the_env_file() -> None:
    assert get_settings().langsmith_api_key == SecretStr("from-the-file")
    use_only()
    settings = get_settings()
    assert settings.database_url == SecretStr(E2E_DB)
    assert settings.openrouter_api_key == SecretStr(REPLAY_API_KEY)
    assert settings.langsmith_api_key is None


# --- A whole classification ---------------------------------------------------------------------


@pytest.fixture
def replayed(tmp_path: Path) -> Iterator[FastAPI]:
    """The replay API as `serve` builds it, over the merged recordings, its test host allowed."""
    recordings = replayed_recordings()
    settings = replay_settings(ORIGIN).model_copy(update={"api_allowed_hosts": (TEST_HOST,)})
    cassette = merged_cassette(recordings, tmp_path / "cassette.yaml")
    app = replay_api(settings, merged_corpus(recordings, tmp_path / "corpus.json"))
    with replayed_model_calls(cassette, ignore_hosts=[TEST_HOST]):
        yield app
    app.state.context.export_slots.close()


async def _classify(app: FastAPI, body: dict[str, str]) -> list[ClassifyEvent]:
    pinned = PinnedRunDate(app, AS_OF, app.state.context.settings.api_max_body_bytes)
    transport = httpx.ASGITransport(app=pinned)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post("/classify", json=body)
    assert response.status_code == 200
    return sse_events(response.text)


MERGED_STALE = "a merged recording is stale; re-record the run it belongs to"


@pytest.mark.anyio
async def test_the_worked_example_as_the_app_sends_it_replays_to_its_result(
    replayed: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    body = {"description": worked_example_request().description, "language": "en"}
    events = await _classify(replayed, body)
    raise_if_recording_stale(events, caplog.text, MERGED_STALE)
    assert outline(events) == FULL_RUN
    result = events[-1]
    assert isinstance(result, ResultEvent)
    assert result.result.risk_class is RiskClass.HIGH_RISK
    assert result.result.as_of == AS_OF


@pytest.mark.anyio
async def test_a_run_without_a_recording_stops_in_an_error_event(replayed: FastAPI) -> None:
    body = {"description": "A chatbot that answers staff questions.", "language": "en"}
    events = await _classify(replayed, body)
    assert isinstance(events[-1], ErrorEvent)
    assert not any(isinstance(event, ResultEvent) for event in events)
