"""The questions a stored run asked, read back for the downgrade rate's second run (decision 019),
against local Postgres."""

from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aiact.eval.answers import AnswerSourceError, asked_questions
from tests.eval.outcomes import case, result

pytestmark = pytest.mark.db


def _run(db: psycopg.Connection, benchmark: str = "soft_pairs") -> UUID:
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, %s, %s) returning id",
        ("0" * 40, benchmark, Jsonb({"model": None, "embedding": None, "retrieval": None})),
    ).fetchone()
    assert row is not None
    return row[0]


def _case(db: psycopg.Connection, run_id: UUID, case_id: str, predicted: object) -> None:
    db.execute(
        "insert into eval_case_results (run_id, case_id, predicted, label, scores)"
        " values (%s, %s, %s, %s, '{}')",
        (run_id, case_id, Jsonb(predicted), Jsonb(case(case_id).model_dump(mode="json"))),
    )


def test_each_cases_questions_come_back_in_order(db: psycopg.Connection) -> None:
    run_id = _run(db)
    answered = result()
    _case(db, run_id, "a", answered.model_dump(mode="json"))
    _case(db, run_id, "b", {"error": {"type": "Timeout", "message": "-"}})
    asked = asked_questions(db, run_id, "soft_pairs")
    assert asked == {
        "a": tuple(question.id for question in answered.follow_up_questions),
        "b": (),
    }
    assert asked["a"]  # the worked example asks questions


def test_a_missing_run_or_another_set_is_refused(db: psycopg.Connection) -> None:
    with pytest.raises(AnswerSourceError, match="no eval run"):
        asked_questions(db, uuid4(), "soft_pairs")
    run_id = _run(db, "own")
    with pytest.raises(AnswerSourceError, match="ran the own set, not soft_pairs"):
        asked_questions(db, run_id, "soft_pairs")
