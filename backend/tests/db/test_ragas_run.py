"""A RAGAS run (V6) with fake retrieval, answers and judging, stored in the local Supabase Postgres.

Everything runs inside the test's rolled-back transaction: the store's writes become savepoints.
"""

from decimal import Decimal

import psycopg
import pytest

from aiact.eval.ragas_metrics import (
    CONTEXT_PRECISION,
    FAITHFULNESS,
    PROVISION_RECALL,
    RagasOptions,
    run_ragas,
)
from aiact.eval.records import PostgresRunStore
from tests.eval.test_ragas_metrics import UNANSWERABLE, item, parts

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def test_a_ragas_run_stores_its_scores_and_means(db: psycopg.Connection) -> None:
    summary = run_ragas(
        (item(1), item(2, provisions=("art:6:1",)), UNANSWERABLE),
        parts(),
        PostgresRunStore(db),
        RagasOptions(GIT_SHA),
    )

    run = db.execute(
        "select benchmark, config, cost_usd, tokens from eval_runs where id = %s",
        (summary.run_id,),
    ).fetchone()
    assert run is not None
    benchmark, config, cost_usd, tokens = run
    assert (benchmark, cost_usd, tokens) == ("qa", Decimal("0.020000"), 200)
    assert config["model"] == "google/gemini-3.1-flash-lite"
    assert config["outcome"]["status"] == "completed"
    assert config["outcome"]["means"][PROVISION_RECALL] == 0.5
    assert config["outcome"]["means"][FAITHFULNESS] is None

    rows = db.execute(
        "select case_id, scores from eval_case_results where run_id = %s order by case_id",
        (summary.run_id,),
    ).fetchall()
    assert [case_id for case_id, _ in rows] == ["qa-en-01-test", "qa-en-02-test"]
    scores = rows[0][1]
    assert (scores[CONTEXT_PRECISION], scores[FAITHFULNESS], scores["is_error"]) == (
        1.0,
        None,
        False,
    )
