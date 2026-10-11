"""`tests/conftest.py`: the recording scrubber keeps headers and reasoning blobs off disk, and the
test session reaches only the test database, never the hosted project in DATABASE_URL."""

import json
from pathlib import Path

import pytest

from aiact import db
from aiact.settings import BACKEND_DIR, Settings
from tests.conftest import DatabaseForTests, _scrub_response, database_url_for_tests

REPLY = {
    "id": "gen-1",
    "choices": [
        {
            "message": {
                "content": '{"answer": "yes"}',
                "reasoning": "thinking",
                "reasoning_details": [{"type": "reasoning.encrypted", "data": "gAAAA"}],
            }
        }
    ],
    "usage": {"cost": 0.001},
}


def _recorded(body: str | bytes) -> dict[str, object]:
    response = {
        "headers": {"Set-Cookie": ["x"], "Content-Type": ["json"]},
        "body": {"string": body},
    }
    return _scrub_response(response)


def test_reasoning_fields_are_dropped_and_the_rest_is_kept() -> None:
    scrubbed = _recorded(json.dumps(REPLY).encode())
    body = scrubbed["body"]
    assert isinstance(body, dict)
    raw = body["string"]
    assert isinstance(raw, bytes)  # the HTTP client reads the recording back as bytes
    message = json.loads(raw)["choices"][0]["message"]
    assert message == {"content": '{"answer": "yes"}'}
    assert json.loads(raw)["usage"] == {"cost": 0.001}
    assert scrubbed["headers"] == {"Content-Type": ["json"]}


def test_a_text_body_stays_text_and_a_non_json_body_is_untouched() -> None:
    text = _recorded(json.dumps(REPLY))["body"]
    assert isinstance(text, dict)
    assert isinstance(text["string"], str)
    assert "reasoning_details" not in text["string"]
    assert _recorded(b"not json")["body"] == {"string": b"not json"}


HOSTED_LOOKING_URL = (
    "postgresql://postgres.projectref@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
    "?sslmode=require"
)
"""The shape of the hosted project's session pooler URL, without a password."""
OTHER_TEST_DATABASE_URL = (
    "postgresql://postgres:postgres@127.0.0.1:54322/postgres?application_name=aiact-tests"
)

INNER_SESSION_TEST = """
import os

from aiact.settings import get_settings


def test_the_session_sees_only_the_test_database() -> None:
    expected = os.environ["EXPECTED_DATABASE_URL"]
    url = get_settings().database_url
    assert url is not None
    assert (os.environ["DATABASE_URL"], url.get_secret_value()) == (expected, expected)
"""


def test_a_hosted_database_url_never_reaches_a_test_session(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A child pytest session with the conftest hook, started with the hosted URL in
    DATABASE_URL: before any test runs, the settings already point at TEST_DATABASE_URL."""
    monkeypatch.setenv("DATABASE_URL", HOSTED_LOOKING_URL)
    monkeypatch.setenv("TEST_DATABASE_URL", OTHER_TEST_DATABASE_URL)
    monkeypatch.setenv("EXPECTED_DATABASE_URL", OTHER_TEST_DATABASE_URL)
    monkeypatch.setenv("PYTHONPATH", str(BACKEND_DIR))  # `tests` is importable from backend/
    pytester.makeconftest("from tests.conftest import pytest_configure  # noqa: F401\n")
    pytester.makepyfile(INNER_SESSION_TEST)
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)


def test_the_test_database_defaults_to_the_local_supabase_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    url = DatabaseForTests(_env_file=None).test_database_url  # pyright: ignore[reportCallIssue]
    assert url.get_secret_value() == "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def test_a_hosted_url_in_the_env_file_loses_to_the_test_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`backend/.env`'s DATABASE_URL (the hosted project after the switch-over) is overridden in
    this session, for the settings and for `aiact.db.connect()` alike."""
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URL={HOSTED_LOOKING_URL}\n", encoding="utf-8")
    url = Settings(_env_file=env_file).database_url  # pyright: ignore[reportCallIssue]
    assert url is not None
    assert url.get_secret_value() == database_url_for_tests() != HOSTED_LOOKING_URL

    reached: list[str] = []
    monkeypatch.setattr(db.psycopg, "connect", lambda url, **_: reached.append(url))
    db.connect()
    assert reached == [database_url_for_tests()]
