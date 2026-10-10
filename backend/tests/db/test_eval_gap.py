"""The gap of two stored runs and the corpus's held-out ids, against local Postgres (V8)."""

from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aiact.eval.gap import RunMismatchError, gap_report
from aiact.eval.held_out_hits import held_out_ids
from aiact.eval.isolation import load_contaminated
from aiact.schemas import RiskClass
from tests.eval.outcomes import case, result

pytestmark = pytest.mark.db


def _run(db: psycopg.Connection, exclude_mode: str, benchmark: str = "commission_b") -> UUID:
    config = {
        "model": "openai/gpt-6-luna-20260922",
        "embedding": None,
        "retrieval": None,
        "classifier": "engine",
        "exclude_mode": exclude_mode,
        "subset": None,
        "seed": 0,
        "outcome": {"status": "completed"},
    }
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, %s, %s) returning id",
        ("0" * 40, benchmark, Jsonb(config)),
    ).fetchone()
    assert row is not None
    return row[0]


def _store(db: psycopg.Connection, run_id: UUID, hits: dict[str, bool]) -> None:
    """One case per id, answered right (high_risk) or wrong (minimal_risk)."""
    contaminated = load_contaminated().examples[0].example_id
    for case_id, is_hit in hits.items():
        source = contaminated if case_id == "contaminated" else "hr-ex-100"
        label = case(case_id).model_copy(update={"source_example_id": source})
        predicted = result() if is_hit else result(RiskClass.MINIMAL_RISK)
        db.execute(
            "insert into eval_case_results (run_id, case_id, predicted, label, scores)"
            " values (%s, %s, %s, %s, '{}')",
            (
                run_id,
                case_id,
                Jsonb(predicted.model_dump(mode="json")),
                Jsonb(label.model_dump(mode="json")),
            ),
        )


def test_the_gap_of_two_stored_runs(db: psycopg.Connection) -> None:
    heldout, everything = _run(db, "heldout"), _run(db, "all")
    _store(db, heldout, {"a": True, "b": False, "contaminated": True})
    _store(db, everything, {"a": True, "b": True, "contaminated": True})
    text = gap_report(db, heldout, everything)
    assert "| Every case | 66.7% (2/3) | 100.0% (3/3) | -33.3 pp |" in text
    assert (
        "| Without the contaminated cases (docs/decisions/016-contaminated-pile-b-cases.md) "
        "| 50.0% (1/2) | 100.0% (2/2) | -50.0 pp |"
    ) in text


def test_runs_of_two_sets_are_refused(db: psycopg.Connection) -> None:
    with pytest.raises(RunMismatchError, match="differ in benchmark"):
        gap_report(db, _run(db, "heldout"), _run(db, "all", "own"))


def test_held_out_ids_are_the_corpus_rows_marked_held_out(db: psycopg.Connection) -> None:
    rows = db.execute("select provision_id, is_held_out from provisions").fetchall()
    held_out = {pid for pid, is_held_out in rows if is_held_out}
    retrievable = {pid for pid, is_held_out in rows if not is_held_out}
    if not held_out:
        pytest.skip("the corpus isn't loaded: no held-out rows to read")
    found = held_out_ids(db)
    assert found == held_out
    assert "art:5" in retrievable - found
