"""Database fixtures: one connection to the test database (`TEST_DATABASE_URL`, by default the
Supabase CLI's local one; never the hosted project, see tests/conftest.py), one rolled-back
transaction per test.

All worktrees share one local database, so nothing a test writes is ever committed. An unreachable
database skips the tests locally but fails them when the `CI` environment variable is set.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest

from tests.conftest import database_url_for_tests as _database_url

CONNECT_TIMEOUT_SECONDS = 3


@pytest.fixture(scope="session")
def db_connection() -> Iterator[psycopg.Connection]:
    try:
        connection = psycopg.connect(_database_url(), connect_timeout=CONNECT_TIMEOUT_SECONDS)
    except psycopg.OperationalError as exc:
        # The URL may hold a password, so the reason names only the error type.
        reason = f"database not reachable ({type(exc).__name__}); check DATABASE_URL"
        if os.environ.get("CI"):
            pytest.fail(reason, pytrace=False)
        pytest.skip(reason)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def db(db_connection: psycopg.Connection) -> Iterator[psycopg.Connection]:
    """The shared connection inside a transaction that is always rolled back after the test."""
    with rolled_back(db_connection) as connection:
        yield connection


@contextmanager
def rolled_back(connection: psycopg.Connection) -> Iterator[psycopg.Connection]:
    """Open a `transaction(force_rollback=True)` block before the test's code runs, so every
    `transaction()` that code opens becomes a savepoint: nothing can be committed to the shared
    database, even by code that commits its own writes."""
    connection.rollback()  # start from idle, whatever an earlier test left behind
    with connection.transaction(force_rollback=True):
        yield connection
