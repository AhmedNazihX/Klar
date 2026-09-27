"""Database fixtures: one connection to the local Supabase Postgres, one rolled-back transaction
per test.

All worktrees share one local database, so nothing a test writes is ever committed. An unreachable
database skips the tests locally but fails them when the `CI` environment variable is set.
"""

import os
from collections.abc import Iterator

import psycopg
import pytest

from aiact.settings import get_settings

LOCAL_SUPABASE_DB_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
"""The Supabase CLI's default local database, used when DATABASE_URL is unset."""

CONNECT_TIMEOUT_SECONDS = 3


def _database_url() -> str:
    secret = get_settings().database_url
    return secret.get_secret_value() if secret is not None else LOCAL_SUPABASE_DB_URL


@pytest.fixture(scope="session")
def db_connection() -> Iterator[psycopg.Connection]:
    try:
        connection = psycopg.connect(_database_url(), connect_timeout=CONNECT_TIMEOUT_SECONDS)
    except psycopg.OperationalError as exc:
        # The URL may hold a password, so the reason names only the error type.
        reason = f"database not reachable ({type(exc).__name__}); run `supabase start`"
        if os.environ.get("CI"):
            pytest.fail(reason, pytrace=False)
        pytest.skip(reason)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def db(db_connection: psycopg.Connection) -> Iterator[psycopg.Connection]:
    """The shared connection inside a transaction that is rolled back after the test."""
    try:
        yield db_connection
    finally:
        db_connection.rollback()
