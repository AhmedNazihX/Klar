"""The eval-records migration (supabase/migrations/*_eval_records.sql) against the local Supabase
Postgres."""

from decimal import Decimal
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.db

EVAL_TABLES = ("eval_runs", "eval_case_results")
GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
CONFIG = {
    "model": "anthropic/claude-sonnet-5",
    "embedding": {"model": "qwen/qwen3-embedding-8b", "dims": 1536},
    "retrieval": {"top_k": 8, "exclude_mode": "heldout"},
    "classifier": "engine",
}
PREDICTED = {"risk_class": "high_risk", "status": "determined", "annex_point": "annex:III:4:a"}
LABEL = {"risk_class": "high_risk", "annex_point": "annex:III:4:a"}
SCORES = {"risk_class_accuracy": True, "citation_support": 0.75, "downgrade": None}


def _insert_run(db: psycopg.Connection, **overrides: object) -> UUID:
    values: dict[str, object] = {
        "git_sha": GIT_SHA,
        "benchmark": "commission_b",
        "config": CONFIG,
    } | overrides
    row = db.execute(
        """
        insert into eval_runs (git_sha, benchmark, config)
        values (%(git_sha)s, %(benchmark)s, %(config)s)
        returning id
        """,
        {**values, "config": Jsonb(values["config"])},
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_result(
    db: psycopg.Connection, run_id: UUID, case_id: str = "cb-017", scores: object = SCORES
) -> None:
    db.execute(
        """
        insert into eval_case_results (run_id, case_id, predicted, label, scores, trace_id)
        values (%s, %s, %s, %s, %s, 'trace-1')
        """,
        (run_id, case_id, Jsonb(PREDICTED), Jsonb(LABEL), Jsonb(scores)),
    )


def test_run_and_case_result_round_trip(db: psycopg.Connection) -> None:
    run_id = _insert_run(db)
    db.execute(
        "update eval_runs set cost_usd = cost_usd + 0.012345, tokens = tokens + 4200 where id = %s",
        (run_id,),
    )
    _insert_result(db, run_id)

    run = db.execute(
        "select git_sha, benchmark, config, started_at is not null, cost_usd, tokens"
        " from eval_runs where id = %s",
        (run_id,),
    ).fetchone()
    assert run == (GIT_SHA, "commission_b", CONFIG, True, Decimal("0.012345"), 4200)

    result = db.execute(
        "select case_id, predicted, label, scores, trace_id from eval_case_results"
        " where run_id = %s",
        (run_id,),
    ).fetchone()
    assert result == ("cb-017", PREDICTED, LABEL, SCORES, "trace-1")


def test_run_ids_are_generated_uuids(db: psycopg.Connection) -> None:
    first, second = _insert_run(db), _insert_run(db)
    assert isinstance(first, UUID)
    assert first != second


def test_deleting_a_run_deletes_its_case_results(db: psycopg.Connection) -> None:
    run_id = _insert_run(db)
    _insert_result(db, run_id)
    db.execute("delete from eval_runs where id = %s", (run_id,))
    row = db.execute(
        "select count(*) from eval_case_results where run_id = %s", (run_id,)
    ).fetchone()
    assert row == (0,)


def test_a_case_is_scored_once_per_run(db: psycopg.Connection) -> None:
    run_id = _insert_run(db)
    _insert_result(db, run_id)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _insert_result(db, run_id)


@pytest.mark.parametrize(
    "overrides",
    [
        {"config": {"model": "m", "embedding": None}},
        {"config": ["model", "embedding", "retrieval"]},
        {"git_sha": "0123abc"},
        {"benchmark": "Commission B"},
    ],
    ids=["config-missing-retrieval", "config-not-object", "short-sha", "bad-benchmark"],
)
def test_run_checks_reject_bad_values(db: psycopg.Connection, overrides: dict[str, object]) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_run(db, **overrides)


def test_config_keys_may_hold_null(db: psycopg.Connection) -> None:
    _insert_run(db, config={"model": "m", "embedding": None, "retrieval": None})


@pytest.mark.parametrize(
    "score",
    ["yes", [1, 2], []],
    ids=["string", "array", "empty-array"],
)
def test_scores_must_map_metrics_to_numbers_booleans_or_null(
    db: psycopg.Connection, score: object
) -> None:
    run_id = _insert_run(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_result(db, run_id, scores={"risk_class_accuracy": score})


def test_eval_tables_have_rls_and_no_data_api_grants(db: psycopg.Connection) -> None:
    for table in EVAL_TABLES:
        row = db.execute(
            """
            select c.relrowsecurity,
                   has_table_privilege('anon', c.oid, 'select,insert,update,delete'),
                   has_table_privilege('authenticated', c.oid, 'select,insert,update,delete')
            from pg_class c where c.oid = %s::regclass
            """,
            (f"public.{table}",),
        ).fetchone()
        assert row == (True, False, False), table
