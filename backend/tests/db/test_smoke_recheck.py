"""The recheck of stored smoke runs (X2) in the local Supabase Postgres: rows stored the way the
first paid run stored them are rechecked against a stub of the long lookup, rescored, audited and
compared. No model is called and no generation record is read.

Everything runs inside the test's rolled-back transaction: the writes become savepoints.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
import yaml
from pydantic import JsonValue
from typer.testing import CliRunner

from aiact import cli
from aiact.engine.nodes import facts
from aiact.eval import records
from aiact.eval.experiments import smoke, smoke_recheck, smoke_verdict
from aiact.eval.experiments.smoke import GEMINI, LUNA, ModelArm, Probe, RunStatus
from aiact.eval.experiments.smoke_recheck import RecheckError, RecheckResult
from aiact.eval.experiments.smoke_verdict import Verdict
from aiact.eval.records import PostgresRunStore
from aiact.eval.runner import CaseRecord
from aiact.llm.generations import GenerationLookupError, GenerationNotFoundError
from aiact.schemas import RiskClass, Role
from tests.eval.experiments.builders import case, role_outcome
from tests.eval.experiments.stored_rows import SETTINGS, first_run_failed, probe_row

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
AT = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
D1 = case("d-1", RiskClass.LIMITED_RISK, role=Role.DEPLOYER)
ROLE_PROBE = "role_obligations:d-1"
TRANSPORT_PROBE = "high_risk:init-worked-example"


@pytest.fixture
def cases_dir(tmp_path: Path) -> Path:
    target = tmp_path / "own" / "d"
    target.mkdir(parents=True)
    dumped = D1.model_dump(mode="json", exclude_none=True)
    (target / f"{D1.id}.yaml").write_text(yaml.safe_dump(dumped), encoding="utf-8")
    return tmp_path


def planned(cases_dir: Path) -> dict[str, Probe]:
    """high_risk:init-worked-example, role_obligations:d-1, facts:init-worked-example, facts:d-1."""
    return {probe.probe_id: probe for probe in smoke.plan_probes(cases_dir)}


def not_found(generation_id: str) -> str:
    raise GenerationNotFoundError(f"generation {generation_id} not found after 12 attempts")


def first_run_rows(probes: Mapping[str, Probe], arm: ModelArm, role: Role) -> list[CaseRecord]:
    """The role probe answered `role`, the worked example's facts broke, the other facts were cut
    off by the output cap: all three failed only by their lookup. The high_risk probe got a
    provider error in the body, its lookup not found either: no answer, never rescored."""
    timeout = ValueError("OpenRouter API returned an error: upstream timeout (code: 504)")
    return [
        first_run_failed(probe_row(probes[ROLE_PROBE], role_outcome(role), arm)),
        first_run_failed(
            probe_row(probes["facts:init-worked-example"], facts.FactsOutputError("x"), arm)
        ),
        first_run_failed(
            probe_row(
                probes["facts:d-1"], facts.FactsOutputError("cut"), arm, finish_reason="length"
            )
        ),
        probe_row(probes[TRANSPORT_PROBE], timeout, arm, served_by=not_found),
    ]


def store_run(db: psycopg.Connection, arm: ModelArm, rows: Sequence[CaseRecord]) -> UUID:
    store = PostgresRunStore(db)
    run_id = store.start_run(GIT_SHA, "own", smoke.run_config(arm, SETTINGS, [], 0.5, False))
    for row in rows:
        store.add_case(run_id, row)
    outcome: dict[str, JsonValue] = {
        "status": RunStatus.COMPLETED.value,
        "probes_planned": len(rows),
        "probes_recorded": len(rows),
    }
    store.finish_run(run_id, outcome)
    return run_id


class Verifier:
    """A stand-in for the long lookup: every id gets `answer`; it counts the ids asked."""

    def __init__(self, answer: str | GenerationLookupError) -> None:
        self.answer = answer
        self.asked: list[str] = []

    def __call__(self, generation_ids: Sequence[str]) -> dict[str, str | GenerationLookupError]:
        self.asked += generation_ids
        return {generation_id: self.answer for generation_id in generation_ids}


def rows_of(db: psycopg.Connection, run_id: UUID) -> dict[str, tuple[dict, dict]]:  # pyright: ignore[reportMissingTypeArgument]
    stored = db.execute(
        "select case_id, predicted, scores from eval_case_results where run_id = %s", (run_id,)
    ).fetchall()
    return {case_id: (predicted, scores) for case_id, predicted, scores in stored}


def run_state(db: psycopg.Connection, run_id: UUID) -> tuple[object, object, float, int]:
    row = db.execute(
        "select config -> 'rechecks', config -> 'outcome' ->> 'status', cost_usd, tokens"
        " from eval_runs where id = %s",
        (run_id,),
    ).fetchone()
    assert row is not None
    return row[0], row[1], float(row[2]), row[3]


def test_confirmed_probes_are_rescored_from_their_stored_replies(
    db: psycopg.Connection, cases_dir: Path
) -> None:
    run_id = store_run(db, LUNA, first_run_rows(planned(cases_dir), LUNA, Role.DEPLOYER))
    before = run_state(db, run_id)
    verify = Verifier("Azure")
    summary = smoke_recheck.recheck_run(db, run_id, verify, cases_dir, AT)
    assert [(p.case_id, p.result) for p in summary.probes] == [
        ("facts:d-1", RecheckResult.CONFIRMED),
        ("facts:init-worked-example", RecheckResult.CONFIRMED),
        (ROLE_PROBE, RecheckResult.CONFIRMED),
    ]
    assert len(verify.asked) == 3  # the transport-error probe is never looked up
    rows = rows_of(db, run_id)
    predicted, scores = rows[ROLE_PROBE]
    assert (scores["failed"], scores["broken"], scores["correct"]) == (False, False, True)
    assert scores["served_as_pinned"] is True
    assert "not_pinned" not in predicted
    assert predicted["smoke"]["recheck"]["by"] == "smoke-recheck"
    assert predicted["smoke"]["recheck"]["at"] == AT.isoformat()
    assert predicted["smoke"]["recheck"]["served_by"] == ["Azure"]
    assert predicted["smoke"]["recheck"]["original_not_pinned"].endswith("after 12 attempts")
    for broken in ("facts:d-1", "facts:init-worked-example"):  # length and schema: still broken
        assert (rows[broken][1]["broken"], rows[broken][1]["failed"]) == (True, False)
        assert rows[broken][1]["correct"] is None
    transport = rows[TRANSPORT_PROBE]
    assert (transport[1]["failed"], transport[1]["served_as_pinned"]) == (True, None)
    assert "recheck" not in transport[0]["smoke"]
    rechecks, status, cost, tokens = run_state(db, run_id)
    assert rechecks == [
        {
            "at": AT.isoformat(),
            "by": "smoke-recheck",
            "probes_rechecked": 3,
            "confirmed": 3,
            "still_failing": 0,
        }
    ]
    assert (status, cost, tokens) == before[1:]  # status and totals untouched


def test_a_wrong_answer_is_rescored_wrong(db: psycopg.Connection, cases_dir: Path) -> None:
    run_id = store_run(db, LUNA, first_run_rows(planned(cases_dir), LUNA, Role.PROVIDER))
    smoke_recheck.recheck_run(db, run_id, Verifier("Azure"), cases_dir, AT)
    scores = rows_of(db, run_id)[ROLE_PROBE][1]
    assert (scores["failed"], scores["broken"], scores["correct"]) == (False, False, False)


def test_another_provider_stays_failed_and_says_so(db: psycopg.Connection, cases_dir: Path) -> None:
    run_id = store_run(db, GEMINI, first_run_rows(planned(cases_dir), GEMINI, Role.DEPLOYER))
    summary = smoke_recheck.recheck_run(db, run_id, Verifier("Google AI Studio"), cases_dir, AT)
    assert {p.result for p in summary.probes} == {RecheckResult.OTHER_PROVIDER}
    predicted, scores = rows_of(db, run_id)[ROLE_PROBE]
    assert (scores["failed"], scores["correct"], scores["served_as_pinned"]) == (True, None, False)
    assert predicted["not_pinned"] == "served by Google AI Studio, not Google"
    assert predicted["smoke"]["recheck"]["served_by"] == ["Google AI Studio"]
    rechecks = run_state(db, run_id)[0]
    assert isinstance(rechecks, list) and rechecks[0]["still_failing"] == 3


def test_a_record_still_missing_leaves_the_row_as_it_was(
    db: psycopg.Connection, cases_dir: Path
) -> None:
    run_id = store_run(db, LUNA, first_run_rows(planned(cases_dir), LUNA, Role.DEPLOYER))
    before = rows_of(db, run_id)
    late = GenerationNotFoundError("generation g not found within 300 s")
    summary = smoke_recheck.recheck_run(db, run_id, Verifier(late), cases_dir, AT)
    assert {p.result for p in summary.probes} == {RecheckResult.STILL_FAILING}
    assert rows_of(db, run_id) == before
    rechecks = run_state(db, run_id)[0]
    assert isinstance(rechecks, list) and rechecks[0]["confirmed"] == 0


def test_running_the_recheck_again_changes_nothing(db: psycopg.Connection, cases_dir: Path) -> None:
    run_id = store_run(db, LUNA, first_run_rows(planned(cases_dir), LUNA, Role.DEPLOYER))
    smoke_recheck.recheck_run(db, run_id, Verifier("Azure"), cases_dir, AT)
    after_first = (rows_of(db, run_id), run_state(db, run_id))
    verify = Verifier("Azure")
    again = smoke_recheck.recheck_run(db, run_id, verify, cases_dir, datetime.now(UTC))
    assert again.probes == ()
    assert verify.asked == []
    assert (rows_of(db, run_id), run_state(db, run_id)) == after_first


def test_a_case_whose_label_changed_since_the_run_is_refused(
    db: psycopg.Connection, cases_dir: Path
) -> None:
    run_id = store_run(db, LUNA, first_run_rows(planned(cases_dir), LUNA, Role.DEPLOYER))
    before = rows_of(db, run_id)
    changed = D1.model_copy(update={"notes": "Edited after the run."})
    dumped = changed.model_dump(mode="json", exclude_none=True)
    (cases_dir / "own" / "d" / f"{D1.id}.yaml").write_text(yaml.safe_dump(dumped), "utf-8")
    verify = Verifier("Azure")
    with pytest.raises(RecheckError, match="changed since the run"):
        smoke_recheck.recheck_run(db, run_id, verify, cases_dir, AT)
    assert verify.asked == []  # refused before any lookup
    assert rows_of(db, run_id) == before


def test_a_run_that_is_not_a_smoke_run_is_refused(db: psycopg.Connection, cases_dir: Path) -> None:
    run_id = PostgresRunStore(db).start_run(
        GIT_SHA, "own", {"model": None, "embedding": None, "retrieval": None}
    )
    with pytest.raises(smoke_verdict.SmokeRunError, match="not an x2_engine_smoke run"):
        smoke_recheck.recheck_run(db, run_id, Verifier("Azure"), cases_dir, AT)


# --- The command --------------------------------------------------------------------------------


class FakeLookup:
    """Stands in for `GenerationLookup` in the command: every record names the arm's provider."""

    def __init__(self, settings: object) -> None:
        pass

    def served_by_all(self, generation_ids: Sequence[str]) -> dict[str, str]:
        return {gid: "Azure" if "luna" in gid else "Google" for gid in generation_ids}


def test_the_command_rechecks_both_runs_and_prints_the_verdict(
    db: psycopg.Connection, cases_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probes = planned(cases_dir)

    def rows(arm: ModelArm) -> list[CaseRecord]:
        stored = first_run_rows(probes, arm, Role.DEPLOYER)
        return [  # generation ids that say which arm they belong to
            _rename_generation(row, arm.name) for row in stored
        ]

    luna, gemini = store_run(db, LUNA, rows(LUNA)), store_run(db, GEMINI, rows(GEMINI))

    @contextmanager
    def connect() -> Iterator[psycopg.Connection]:
        yield db

    monkeypatch.setattr(records, "connect", connect)
    monkeypatch.setattr(cli, "GenerationLookup", FakeLookup)
    monkeypatch.setattr(smoke_recheck, "CASES_DIR", cases_dir)
    before = (rows_of(db, luna), rows_of(db, gemini))

    runner = CliRunner()
    dry = runner.invoke(cli.app, ["evaluate", "smoke-recheck", str(luna), str(gemini), "--dry-run"])
    assert dry.exit_code == 0, dry.output
    assert "luna: run" in dry.stdout and "3 confirmed on Azure" in dry.stdout
    assert "Dry run: nothing was written" in dry.stdout
    assert (rows_of(db, luna), rows_of(db, gemini)) == before

    done = runner.invoke(cli.app, ["evaluate", "smoke-recheck", str(luna), str(gemini)])
    assert done.exit_code == 0, done.output
    assert "gemini: run" in done.stdout and "3 confirmed on Google" in done.stdout
    assert "| Model | Run id |" in done.stdout and "Verdict: " in done.stdout
    assert (rows_of(db, luna), rows_of(db, gemini)) != before
    comparison = smoke_verdict.compare_runs(db, {"luna": luna, "gemini": gemini})
    assert comparison.luna.failed == comparison.gemini.failed == 1  # the transport errors
    assert comparison.verdict is Verdict.INCONCLUSIVE  # 1 of 4 is more than 10%


def _rename_generation(row: CaseRecord, arm: str) -> CaseRecord:
    """`row` with its generation id tagged with the arm's name."""
    info = row.predicted["smoke"]
    assert isinstance(info, dict)
    ids = info["generation_ids"]
    assert isinstance(ids, list)
    renamed: list[JsonValue] = [f"{gid}-{arm}" for gid in ids if isinstance(gid, str)]
    new_info: dict[str, JsonValue] = {**info, "generation_ids": renamed}
    predicted: dict[str, JsonValue] = {**row.predicted, "smoke": new_info}
    return CaseRecord(row.case_id, predicted, row.label, row.scores, None, row.cost_usd, row.tokens)
