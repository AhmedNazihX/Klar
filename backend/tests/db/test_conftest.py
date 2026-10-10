"""The database fixtures' safety nets: nothing written inside the `db` fixture reaches the shared
database, and no test session waits for a lock longer than the lock timeout."""

import random
import time

import psycopg
import pytest

from aiact.eval.records import PostgresRunStore
from tests.db.conftest import _database_url, rolled_back

pytestmark = pytest.mark.db

GIT_SHA = "fedcba9876543210fedcba9876543210fedcba98"
CONFIG = {"model": None, "embedding": None, "retrieval": None}


def _count(connection: psycopg.Connection) -> int:
    row = connection.execute("select count(*) from eval_runs where git_sha = %s", (GIT_SHA,))
    found = row.fetchone()
    assert found is not None
    return found[0]


def test_a_store_write_that_commits_its_own_transaction_is_rolled_back(
    db_connection: psycopg.Connection,
) -> None:
    # The store wraps each write in `transaction()`, which on an idle connection would COMMIT.
    with rolled_back(db_connection) as connection:
        PostgresRunStore(connection).start_run(GIT_SHA, "own", CONFIG)
        assert _count(connection) == 1
    try:
        assert _count(db_connection) == 0
    finally:
        db_connection.rollback()


LOCK_TIMEOUT_SECONDS = 15
"""tests/conftest.py's LOCK_TIMEOUT, pinned here as a literal."""


def test_every_test_connection_has_the_lock_timeout(db_connection: psycopg.Connection) -> None:
    with psycopg.connect(_database_url()) as own:
        settings = [c.execute("show lock_timeout").fetchone() for c in (db_connection, own)]
    db_connection.rollback()
    assert settings == [(f"{LOCK_TIMEOUT_SECONDS}s",)] * 2


def test_a_held_lock_fails_a_waiting_test_instead_of_hanging(
    db_connection: psycopg.Connection,
) -> None:
    """A lock another session holds and never releases: the waiting statement fails with 55P03
    once the lock timeout has passed, rather than waiting for ever."""
    key = random.getrandbits(62)  # an advisory lock no other test or worktree takes
    with psycopg.connect(_database_url(), autocommit=True) as waiter:
        db_connection.execute("select pg_advisory_xact_lock(%s)", (key,))
        try:
            started = time.monotonic()
            with pytest.raises(psycopg.errors.LockNotAvailable):
                waiter.execute("select pg_advisory_lock(%s)", (key,))
            waited = time.monotonic() - started
        finally:
            db_connection.rollback()
    assert LOCK_TIMEOUT_SECONDS <= waited < LOCK_TIMEOUT_SECONDS + 5
