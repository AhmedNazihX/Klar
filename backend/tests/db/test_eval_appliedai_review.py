"""The appliedAI disagreement review of a run stored in local Postgres (V9)."""

from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aiact.eval.appliedai_review import NotAppliedAIRunError, load_review
from aiact.eval.appliedai_review_report import render_review
from aiact.eval.cases import AppliedAILabel, BenchmarkCase, CaseSet
from aiact.eval.report import run_report
from aiact.schemas import Language, RiskClass
from tests.eval.outcomes import result

pytestmark = pytest.mark.db

FAILED = {"error": {"type": "ClassifierFailedError", "message": "made-up failure"}}


def _run(db: psycopg.Connection, benchmark: str = CaseSet.APPLIEDAI.value) -> UUID:
    config = {
        "model": "openai/gpt-6-luna-20260922",
        "embedding": None,
        "retrieval": None,
        "classifier": "engine",
        "exclude_mode": "heldout",
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


def _store(
    db: psycopg.Connection, run_id: UUID, case_id: str, tags: tuple[str, ...], predicted: object
) -> None:
    label = BenchmarkCase(
        id=case_id,
        set_name=CaseSet.APPLIEDAI,
        language=Language.DE,
        description="Ein erfundenes System.",
        label=AppliedAILabel.HIGH,
        notes="Made-up expert comment.",
        tags=tags,
    )
    db.execute(
        "insert into eval_case_results (run_id, case_id, predicted, label, scores)"
        " values (%s, %s, %s, %s, '{}')",
        (run_id, case_id, Jsonb(predicted), Jsonb(label.model_dump(mode="json"))),
    )


def test_a_stored_run_is_drafted_with_its_run_report_numbers(
    db: psycopg.Connection, tmp_path: Path
) -> None:
    run_id = _run(db)
    high, minimal = result(), result(RiskClass.MINIMAL_RISK)
    _store(db, run_id, "aai-001", ("function:law",), high.model_dump(mode="json"))  # a match
    _store(db, run_id, "aai-002", ("function:law", "annex_i"), minimal.model_dump(mode="json"))
    _store(db, run_id, "aai-003", ("function:purchase",), FAILED)  # failed: a miss
    review = load_review(db, run_id, tmp_path / "appliedai_review.md")
    assert [case.case_id for case in review.disagreements] == ["aai-002", "aai-003"]
    text = render_review(review)
    assert f"- Run id: `{run_id}`" in text.splitlines()
    assert "| Every case | 33.3% (1/3) | 33.3% (1/3) |" in text.splitlines()
    assert "| Risk-class accuracy | 33.3% | 1/3 |" in run_report(db, run_id).splitlines()
    assert "| appliedAI disagreement review | 2 | |" in run_report(db, run_id).splitlines()
    assert "## Annex I disagreements (1)" in text.splitlines()


def test_a_stored_run_of_another_set_is_refused(db: psycopg.Connection, tmp_path: Path) -> None:
    with pytest.raises(NotAppliedAIRunError):
        load_review(db, _run(db, CaseSet.OWN.value), tmp_path / "appliedai_review.md")
