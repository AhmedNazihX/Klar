"""The API in replay mode, for the end-to-end tests (P13): `python -m tests.e2e.replay_server`.

The real app (`create_app`: every route, its limits and its database lookups) with one change:
classifications run the engine's own nodes on recorded model replies and recorded corpus answers
instead of live ones, the way the API's replay test does (`tests/api/test_classify_replay.py`).
The recordings are E10's worked example and every e2e run recorded so far (`runs.py`), merged
into one cassette and one corpus file for the server's lifetime. vcrpy replays in record mode
`none`, so a request without a recording ends that run in an `error` event and nothing ever
reaches the network: no model is paid for. The process never reads `backend/.env` (`use_only`),
so a developer's machine runs it with the settings CI has, and no key is ever loaded. The engine
runs on the settings the recordings were made with (`tests/engine/replayed_engine.py`).

A run is classified on the recordings' date (`as_of` in `runs.json`): the app sends no date, so
`PinnedRunDate` adds it to each `POST /classify` body that has none, as the API's default
(today) would otherwise ask the recorded corpus slices for a date they don't have.

The lookups, documents and reports read the end-to-end Supabase stack's database
(`frontend/e2e/supabase`, port 54332), and no other.
"""

import argparse
import json
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable, Iterator, MutableMapping, Sequence
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import uvicorn
import vcr
import yaml
from fastapi import FastAPI
from pydantic import SecretStr
from vcr.record_mode import RecordMode

from aiact.api import create_app
from aiact.api.dependencies import node_builder
from aiact.settings import Settings, get_settings
from tests.conftest import REFUSAL_ROUTE, REPLAY_API_KEY
from tests.e2e.runs import Recording, replayed_recordings, run_date
from tests.engine.nodes.corpus_recording import CorpusRecording
from tests.engine.replayed_engine import LiveCorpus, luna_settings, replayed_nodes

logger = logging.getLogger(__name__)

E2E_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54332/postgres"
"""The end-to-end stack's database (`frontend/e2e/supabase/config.toml`, `[db] port`)."""
DEFAULT_PORT = 8766
DEFAULT_ORIGIN = "http://127.0.0.1:4174"
"""The Playwright run's `vite preview` (`frontend/playwright.config.ts`)."""
LOOPBACK = ("127.0.0.1", "localhost")
"""The API's allowed hosts: the e2e frontend calls it on 127.0.0.1."""
MATCH_ON = ("method", "scheme", "host", "path", "query", "body")
"""As the tests' `vcr_config` matches recorded requests (`tests/conftest.py`)."""
GENEROUS_LIMIT = 10_000
"""Every e2e test is a client from 127.0.0.1: the app's per-minute limits would stop a run."""
PARALLEL_SLOTS = 8
"""Classifications and file renders at once, at least one per Playwright worker: the app's 2
export workers answer a third parallel download with "busy". Render workers start on first use."""

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]


# --- The recordings -----------------------------------------------------------------------------


def merged_cassette(recordings: Sequence[Recording], into: Path) -> Path:
    """One vcrpy cassette holding the interactions of every recording, in order."""
    interactions: list[object] = []
    for recording in recordings:
        data = yaml.safe_load(recording.cassette.read_text(encoding="utf-8"))
        interactions.extend(data["interactions"])
    into.write_text(yaml.safe_dump({"interactions": interactions, "version": 1}), encoding="utf-8")
    return into


def merged_corpus(recordings: Sequence[Recording], into: Path) -> Path:
    """One corpus recording with every recording's answers. Each answer is keyed by what was
    asked (query, language, date, law version), so two runs asking the same thing got the same
    answer; a key two recordings answer differently is an error rather than a silent pick."""
    entries: dict[str, object] = {}
    for recording in recordings:
        for key, answer in json.loads(recording.corpus.read_text(encoding="utf-8")).items():
            if entries.setdefault(key, answer) != answer:
                raise ValueError(f"{recording.corpus.name} answers {key} differently")
    into.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return into


@contextmanager
def replayed_model_calls(cassette: Path, ignore_hosts: Sequence[str] = ()) -> Iterator[None]:
    """Every HTTP call the process makes (except to `ignore_hosts`) answered from `cassette`, as
    often as asked; a call it doesn't hold raises (record mode `none`) instead of reaching the
    network."""
    replayer = vcr.VCR(
        record_mode=RecordMode.NONE,
        match_on=MATCH_ON,
        decode_compressed_response=True,
        ignore_hosts=tuple(ignore_hosts),
    )
    with replayer.use_cassette(str(cassette), allow_playback_repeats=True):
        yield


# --- The app ------------------------------------------------------------------------------------


class PinnedRunDate:
    """Adds `"as_of": <date>` to each JSON `POST /classify` body that has no date. A body over
    `max_bytes`, or one that isn't a JSON object, passes as it came, for the app to refuse."""

    def __init__(self, app: AsgiApp, as_of: date, max_bytes: int) -> None:
        self._app = app
        self._as_of = as_of.isoformat()
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/classify":
            await self._app(scope, receive, send)
            return
        body, is_cut = await _read_body(receive, self._max_bytes)
        if is_cut:
            # Over the cap: the part read, then the rest as the client sends it (BodySizeLimit).
            await self._app(scope, _replaying(body, receive, more_body=True), send)
            return
        pinned = self._pinned(body)
        headers = [(k, v) for k, v in scope["headers"] if k.lower() != b"content-length"]
        headers.append((b"content-length", str(len(pinned)).encode()))
        await self._app({**scope, "headers": headers}, _replaying(pinned, receive), send)

    def _pinned(self, body: bytes) -> bytes:
        if len(body) > self._max_bytes:
            return body
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return body
        if not isinstance(data, dict) or "as_of" in data:
            return body
        return json.dumps({**data, "as_of": self._as_of}, ensure_ascii=False).encode()


async def _read_body(receive: Receive, max_bytes: int) -> tuple[bytes, bool]:
    """The request's body, and whether reading stopped past `max_bytes` with more to come."""
    chunks: list[bytes] = []
    size = 0
    more = True
    while more and size <= max_bytes:
        message = await receive()
        chunk = message.get("body", b"")
        chunks.append(chunk)
        size += len(chunk)
        more = message.get("more_body", False)
    return b"".join(chunks), more


def _replaying(body: bytes, receive: Receive, *, more_body: bool = False) -> Receive:
    """A `receive` that gives `body` once (`more_body`: the client has more), then whatever the
    client sends next (the rest of the body, or a disconnect)."""
    given = False

    async def replay() -> Message:
        nonlocal given
        if given:
            return await receive()
        given = True
        return {"type": "http.request", "body": body, "more_body": more_body}

    return replay


def replay_settings(origin: str) -> Settings:
    """The app's settings without `backend/.env`: the replay's placeholder key, the engine as the
    recordings were made (Luna, no tracing), the e2e database, the e2e origin, and limits no test
    run reaches."""
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        openrouter_api_key=SecretStr(REPLAY_API_KEY),
        database_url=SecretStr(E2E_DATABASE_URL),
        cors_origins=(origin,),
        api_allowed_hosts=LOOPBACK,
        rate_limit_classify=GENEROUS_LIMIT,
        rate_limit_lookups=GENEROUS_LIMIT,
        rate_limit_qa=GENEROUS_LIMIT,
        rate_limit_exports=GENEROUS_LIMIT,
        classify_max_concurrent=PARALLEL_SLOTS,
        export_max_concurrent=PARALLEL_SLOTS,
        **REFUSAL_ROUTE,
    )
    return luna_settings(settings)


def replay_api(settings: Settings, corpus: Path) -> FastAPI:
    """The API with its classifications replayed from `corpus` (and the cassette in force): the
    engine's own nodes over the recorded corpus answers, citations checked against the corpus
    built from `data/parsed/` (as in the worked example's replay)."""
    app = create_app(settings)
    nodes = replayed_nodes(CorpusRecording[LiveCorpus](corpus, None))
    app.dependency_overrides[node_builder] = lambda: nodes
    return app


def use_only() -> None:
    """Make the process's own settings (`get_settings()`, which `aiact.db.connect` and a few
    defaults read) the replay's rather than `backend/.env`'s: no `Settings` in this process reads
    the file, and the database and key come from the environment."""
    Settings.model_config["env_file"] = None
    os.environ["DATABASE_URL"] = E2E_DATABASE_URL
    os.environ["OPENROUTER_API_KEY"] = REPLAY_API_KEY
    get_settings.cache_clear()


# --- Entry point --------------------------------------------------------------------------------


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--origin", default=DEFAULT_ORIGIN, help="the e2e frontend's origin")
    return parser.parse_args()


def serve(port: int, origin: str) -> None:
    settings = replay_settings(origin)
    use_only()
    recordings = replayed_recordings()
    logger.info("replaying %s", ", ".join(r.stem.name for r in recordings))
    with tempfile.TemporaryDirectory(prefix="aiact-e2e-") as folder:
        cassette = merged_cassette(recordings, Path(folder) / "cassette.yaml")
        corpus = merged_corpus(recordings, Path(folder) / "corpus.json")
        app = PinnedRunDate(replay_api(settings, corpus), run_date(), settings.api_max_body_bytes)
        with replayed_model_calls(cassette):
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # vcrpy and httpx log every replayed request; the run's own warnings are what matter.
    for noisy in ("vcr", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    arguments = _arguments()
    serve(arguments.port, arguments.origin)
