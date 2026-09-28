"""The `db` fixture's safety net: nothing written inside it reaches the shared database."""

import psycopg
import pytest

from aiact.eval.records import PostgresRunStore
from tests.db.conftest import rolled_back

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
