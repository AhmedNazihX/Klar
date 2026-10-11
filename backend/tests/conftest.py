"""Record/replay for model calls (pytest-recording over vcrpy), the network block, and a lock
timeout on every Postgres connection the tests open.

A test marked `@pytest.mark.vcr` replays the HTTP exchanges saved in
`tests/recordings/<module path under tests/>/<test name>.yaml`, for example
`recordings/llm/test_chat/test_chat_roundtrip.yaml`. The default record mode is `none`, so a
request with no recording fails instead of reaching the network. To record, run the test
once with a real key: `uv run pytest tests/llm/test_chat.py --record-mode=once`.

Every other test runs with the network blocked (`--block-network` in pyproject, local hosts
allowed for the database): a call that forgets the `vcr` marker fails instead of making a
paid request. Tests marked `@pytest.mark.live` are the one exception and may connect anywhere.

Recordings keep only the `content-type` header on both sides, so the API key, attribution
headers and provider cookies never land on disk.
"""

import json
from collections.abc import Callable
from pathlib import Path

import psycopg
import pytest
from pydantic import SecretStr
from vcr.request import Request

from aiact.settings import Settings, get_settings

pytest_plugins = ["pytester"]

TESTS_DIR = Path(__file__).parent
RECORDINGS_DIR = TESTS_DIR / "recordings"
KEPT_HEADERS = frozenset({"content-type"})
REPLAY_API_KEY = "replay-without-a-key"
"""Stands in for the key in replay mode; recordings are matched without headers."""
REFUSAL_ROUTE: dict[str, object] = {
    "refusal_model": "google/gemini-3.1-flash-lite",
    "refusal_provider": "google-vertex/eu",
}
"""Decision 033's second model for refused requests, as `backend/.env` sets it when recording."""

ANY_HOST = [".*"]
"""`allowed_hosts` regexes for live tests. The block sees IP addresses, not host names."""

LOCK_TIMEOUT = "15s"
"""The longest a test's Postgres session waits for a lock. All worktrees share one database, so
without it a test could wait forever on a row another worktree's run holds (story F9)."""
SET_LOCK_TIMEOUT = f"set lock_timeout = '{LOCK_TIMEOUT}'"


ConnectFunction = Callable[..., psycopg.Connection]


def _connect_with_lock_timeout(
    connect: ConnectFunction,
) -> "classmethod[psycopg.Connection, ..., psycopg.Connection]":
    """`psycopg.Connection.connect`, followed by a session-level SET of the lock timeout. The SET
    is committed on a non-autocommit connection, so a later rollback can't undo it."""

    def connect_with_lock_timeout(
        cls: type[psycopg.Connection], *args: object, **kwargs: object
    ) -> psycopg.Connection:
        connection = connect(cls, *args, **kwargs)
        connection.execute(SET_LOCK_TIMEOUT)
        if not connection.autocommit:
            connection.commit()
        return connection

    return classmethod(connect_with_lock_timeout)


def pytest_configure() -> None:
    """Give every Postgres connection the tests open a lock timeout: the fixtures', the ones a
    test opens itself and `aiact.db.connect()`'s. A lock wait then fails with 55P03 instead of
    hanging the run. It is a SET after connecting rather than PGOPTIONS, because the hosted
    project's session pooler drops startup options (story F11); the SET works on the pooler, a
    direct connection, the local stack and CI's database alike."""
    original = psycopg.Connection.__dict__["connect"].__func__
    psycopg.Connection.connect = _connect_with_lock_timeout(original)  # pyright: ignore[reportAttributeAccessIssue]
    psycopg.connect = psycopg.Connection.connect  # the module-level alias is bound at import


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Let `live` tests through the network block; everything else stays blocked."""
    for item in items:
        if item.get_closest_marker("live") is not None:
            item.add_marker(pytest.mark.block_network(allowed_hosts=ANY_HOST))


def _scrub_request(request: Request) -> Request:
    request.headers = {k: v for k, v in request.headers.items() if k.lower() in KEPT_HEADERS}
    return request


REASONING_KEYS = frozenset({"reasoning_details", "encrypted_content", "reasoning"})
"""Response fields that carry the model's (often encrypted) reasoning: not needed to replay, and
long base64 runs can look like keys to a secret scanner."""


def strip_reasoning(value: object) -> object:
    """`value` with every `REASONING_KEYS` field removed, at any depth of a JSON value."""
    if isinstance(value, dict):
        return {k: strip_reasoning(v) for k, v in value.items() if k not in REASONING_KEYS}
    if isinstance(value, list):
        return [strip_reasoning(item) for item in value]
    return value


def _scrub_body(body: object) -> object:
    """A JSON response body without its reasoning fields, as the same type (vcrpy keeps bytes
    and the HTTP client expects them back); any other body as it is."""
    raw = body.get("string") if isinstance(body, dict) else None
    if not isinstance(body, dict) or not isinstance(raw, str | bytes):
        return body
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body
    scrubbed = json.dumps(strip_reasoning(data), ensure_ascii=False)
    return {**body, "string": scrubbed.encode() if isinstance(raw, bytes) else scrubbed}


def _scrub_response(response: dict[str, object]) -> dict[str, object]:
    headers = response.get("headers")
    kept = (
        {k: v for k, v in headers.items() if k.lower() in KEPT_HEADERS}
        if isinstance(headers, dict)
        else {}
    )
    return {**response, "headers": kept, "body": _scrub_body(response.get("body"))}


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, object]:
    return {
        "before_record_request": _scrub_request,
        "before_record_response": _scrub_response,
        "decode_compressed_response": True,
        "match_on": ["method", "scheme", "host", "path", "query", "body"],
    }


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    """One folder per test module, keyed by its path under tests/ so names can't collide."""
    return str(RECORDINGS_DIR / request.path.relative_to(TESTS_DIR).with_suffix(""))


@pytest.fixture
def openrouter_settings(record_mode: str) -> Settings:
    """Real settings while recording; a placeholder key, the refusal route and no `.env` while
    replaying."""
    if record_mode != "none":
        return get_settings()
    return Settings(_env_file=None, openrouter_api_key=SecretStr(REPLAY_API_KEY), **REFUSAL_ROUTE)  # pyright: ignore[reportCallIssue]
