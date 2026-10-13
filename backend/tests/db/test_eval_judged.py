"""Judging a stored run (aiact/eval/judged_run.py, V5) against local Postgres: the tallies pass
the scores check, keep the run's own scores and show in the run report. The judge is a fake."""

from collections.abc import Mapping
from datetime import date
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aiact.eval import judged_run
from aiact.eval.cases import QAItem
from aiact.eval.judge import UNSURE_MARGIN, JudgeItem, Verdict
from aiact.eval.judged import JudgedSettings
from aiact.eval.judged_run import (
    JudgedOptions,
    JudgedSettingsError,
    PostgresJudgedStore,
    corpus_source,
    judge_run,
    load_run,
    plan_run,
)
from aiact.eval.report import run_report
from aiact.schemas import Language
from tests.db.test_eval_report import _insert_worked_example_provisions
from tests.eval.outcomes import case
from tests.schemas.worked_example import DOCUMENT_ID, worked_example_result

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
CONFIG = {"model": "openai/gpt-6-luna", "embedding": None, "retrieval": None}
SETTINGS = JudgedSettings(
    jev_model="typesafe/jev-1.13",
    backup_model="anthropic/claude-haiku-5.5",
    backup_provider="google-vertex/europe",
    margin=UNSURE_MARGIN,
)
RUN_SCORES = {"cost_usd": 0.01, "tokens": 100, "is_error": False, "risk_class_accuracy": True}


class Holding:
    def judge(self, item: JudgeItem) -> Verdict:
        return Verdict(
            holds=True, decided_by="jev", p_yes=0.9, reason=None, cost_usd=0.0001, tokens=10
        )


def _insert_run(db: psycopg.Connection, benchmark: str) -> UUID:
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, %s, %s) returning id",
        (GIT_SHA, benchmark, Jsonb(CONFIG)),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_case(
    db: psycopg.Connection, run_id: UUID, case_id: str, label: object, predicted: object
) -> None:
    db.execute(
        "insert into eval_case_results (run_id, case_id, predicted, label, scores)"
        " values (%s, %s, %s, %s, %s)",
        (run_id, case_id, Jsonb(predicted), Jsonb(label), Jsonb(RUN_SCORES)),
    )


def _scores(db: psycopg.Connection, run_id: UUID, case_id: str) -> Mapping[str, object]:
    row = db.execute(
        "select scores from eval_case_results where run_id = %s and case_id = %s",
        (run_id, case_id),
    ).fetchone()
    assert row is not None
    return row[0]


def _no_source(hit: Mapping[str, object], language: Language) -> str | None:
    raise AssertionError("a classification run reads no source")


def test_a_judged_classification_run_shows_its_scores_in_the_report(
    db: psycopg.Connection,
) -> None:
    run_id = _insert_run(db, "own")
    label = case("a").model_dump(mode="json")
    _insert_case(db, run_id, "a", label, worked_example_result().model_dump(mode="json"))
    assert "not judged yet" in run_report(db, run_id)

    run = load_run(db, run_id)
    planned = plan_run(run, _no_source)
    store = PostgresJudgedStore(db)
    judge_run(run, planned, Holding(), SETTINGS, store, JudgedOptions(concurrency=1))

    scores = _scores(db, run_id, "a")
    assert {key: scores[key] for key in RUN_SCORES} == RUN_SCORES
    assert scores["judged_citation_support_held"] == 5
    assert scores["judged_evidence_tag_judged"] == 3
    assert scores["judged_evidence_tag_cost_usd"] == pytest.approx(0.0003)
    assert load_run(db, run_id).settings == SETTINGS

    report = run_report(db, run_id)
    assert "- Cases judged: 1 of 1" in report
    assert "| Citation support | 100.0% | 5/5 | 0 | 0 | $0.0005 | $0.000100 |" in report
    assert "| Evidence-tag accuracy | 100.0% | 3/3 | 0 | 0 | $0.0003 | $0.000100 |" in report
    assert "checked by code (P8a's `check_nothing_invented`" in report
    assert "not judged: 100.0%, 3/3 documents" in report
    assert plan_run(load_run(db, run_id), _no_source) == ()


def test_the_store_refuses_a_second_judge_for_one_run(db: psycopg.Connection) -> None:
    run_id = _insert_run(db, "own")
    store = PostgresJudgedStore(db)
    store.save_settings(run_id, SETTINGS)
    store.save_settings(run_id, SETTINGS)  # the same judge goes on
    other = SETTINGS.model_copy(update={"margin": 0.05})
    with pytest.raises(JudgedSettingsError, match="one run's tallies come from one judge"):
        store.save_settings(run_id, other)
    assert load_run(db, run_id).settings == SETTINGS
    row = db.execute("select config from eval_runs where id = %s", (run_id,)).fetchone()
    assert row is not None
    assert {key: row[0][key] for key in CONFIG} == CONFIG


def test_an_answers_run_loads_the_questions_its_source_run_asked(db: psycopg.Connection) -> None:
    source_id = _insert_run(db, "own")
    asked = worked_example_result().model_dump(mode="json")
    asked["follow_up_questions"] = [{"id": "human_review"}, {"id": "profiling"}]
    _insert_case(db, source_id, "a", case("a").model_dump(mode="json"), asked)
    run_id = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, %s, %s) returning id",
        (GIT_SHA, "own", Jsonb(CONFIG | {"answers_from": str(source_id)})),
    ).fetchone()
    assert run_id is not None
    run = load_run(db, run_id[0])
    assert run.asked == {"a": ("human_review", "profiling")}
    assert load_run(db, source_id).asked is None


def test_a_judged_qa_run_shows_q_and_a_support_in_its_report(db: psycopg.Connection) -> None:
    run_id = _insert_run(db, judged_run.QA_BENCHMARK)
    item = QAItem(
        id="qa-en-01",
        language=Language.EN,
        question="When do the rules apply?",
        required_provision_ids=("art:113",),
        reference_answer="From 2 August 2026.",
    )
    predicted = {
        "answer": "From 2 August 2026.",
        "answer_kind": "answered",
        "retrieved": [{"doc_key": DOCUMENT_ID, "provision_id": "art:113"}],
    }
    _insert_case(db, run_id, item.id, item.model_dump(mode="json"), predicted)

    run = load_run(db, run_id)
    planned = plan_run(run, lambda hit, language: "[art:113] text")
    judge_run(run, planned, Holding(), SETTINGS, PostgresJudgedStore(db), JudgedOptions())

    report = run_report(db, run_id)
    assert "- Benchmark: `qa`" in report
    assert "| Q&A support | 100.0% | 1/1 | 0 | 0 | $0.0001 | $0.000100 |" in report


def test_the_corpus_source_reads_a_stored_hit_from_the_corpus(db: psycopg.Connection) -> None:
    _insert_worked_example_provisions(db)
    read = corpus_source(db, date.today())
    text = read({"doc_key": DOCUMENT_ID, "provision_id": "art:6:3"}, Language.EN)
    assert text is not None
    assert text.startswith("[art:6:3] ")
    assert read({"doc_key": DOCUMENT_ID, "provision_id": "art:999:9"}, Language.EN) is None
