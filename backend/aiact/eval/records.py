"""Writes benchmark runs to `eval_runs` and `eval_case_results` (F5's migration).

Both tables are server-only (RLS on, no Data API grants), so the runner writes them over a direct
Postgres connection. Each write is its own short transaction, so a run that stops half way keeps
the cases it finished. On a connection already inside a transaction (as in the db tests) the
writes become savepoints and the caller decides whether to commit.
"""

from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from pydantic import JsonValue

from aiact.eval.runner import CaseRecord
from aiact.settings import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """DATABASE_URL is not set."""


def connect() -> psycopg.Connection:
    """An autocommit connection to the database in DATABASE_URL."""
    url = get_settings().database_url
    if url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL is not set; see backend/.env.example")
    return psycopg.connect(url.get_secret_value(), autocommit=True)


class PostgresRunStore:
    """A `RunStore` over one psycopg connection, used from a single thread."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self._connection = connection

    def start_run(self, git_sha: str, benchmark: str, config: Mapping[str, JsonValue]) -> UUID:
        with self._connection.transaction():
            row = self._connection.execute(
                "insert into eval_runs (git_sha, benchmark, config) values (%s, %s, %s)"
                " returning id",
                (git_sha, benchmark, Jsonb(dict(config))),
            ).fetchone()
        if row is None:
            raise RuntimeError("insert into eval_runs returned no id")
        return row[0]

    def add_case(self, run_id: UUID, record: CaseRecord) -> None:
        """Insert the case row and add its cost to the run's totals, together."""
        with self._connection.transaction():
            self._connection.execute(
                "insert into eval_case_results"
                " (run_id, case_id, predicted, label, scores, trace_id)"
                " values (%s, %s, %s, %s, %s, %s)",
                (
                    run_id,
                    record.case_id,
                    Jsonb(record.predicted),
                    Jsonb(record.label),
                    Jsonb(record.scores),
                    record.trace_id,
                ),
            )
            self._connection.execute(
                "update eval_runs set cost_usd = cost_usd + %s, tokens = tokens + %s where id = %s",
                (Decimal(str(record.cost_usd)), record.tokens, run_id),
            )

    def finish_run(self, run_id: UUID, outcome: Mapping[str, JsonValue]) -> None:
        """Merge the final status into `config.outcome` (no status column exists yet)."""
        with self._connection.transaction():
            self._connection.execute(
                "update eval_runs set config = config || %s where id = %s",
                (Jsonb({"outcome": dict(outcome)}), run_id),
            )
