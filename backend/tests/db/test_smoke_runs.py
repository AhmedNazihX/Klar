"""The smoke test's runs in the local Supabase Postgres: each model's run is stored, and the verdict
is read back from the stored rows by run id. The nodes are fakes and the serving provider is a
stub; no model is called.

Everything runs inside the test's rolled-back transaction: the store's writes become savepoints.
"""

from collections.abc import Sequence
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from pydantic import JsonValue, SecretStr

from aiact.cli import _smoke_comparison  # pyright: ignore[reportPrivateUsage]
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome, RoleFinding
from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.experiments import smoke, smoke_verdict
from aiact.eval.experiments.smoke import (
    GEMINI,
    LUNA,
    CallRecord,
    NodeName,
    Probe,
    UsageTracker,
)
from aiact.eval.experiments.smoke_verdict import SmokeRunError, Verdict
from aiact.eval.records import PostgresRunStore
from aiact.eval.runner import CaseRecord
from aiact.llm.generations import GenerationLookupError, GenerationNotFoundError
from aiact.schemas import Language, RiskClass, Role, StepName, StepResult
from aiact.settings import Settings

pytestmark = pytest.mark.db

GIT_STATE = ("0123456789abcdef0123456789abcdef01234567", False)


def probes(count: int = 4, prefix: str = "fixture-smoke") -> tuple[Probe, ...]:
    return tuple(
        Probe(
            NodeName.ROLE,
            BenchmarkCase(
                id=f"{prefix}-{number}",
                set_name=CaseSet.OWN,
                language=Language.EN,
                description=f"Made-up description {number}",
                label=CaseLabel(risk_class=RiskClass.MINIMAL_RISK, role=Role.DEPLOYER),
                label_citation=("art:3:4",),
            ),
        )
        for number in range(count)
    )


SETTINGS = Settings(_env_file=None, openrouter_api_key=SecretStr("not-a-key"))  # pyright: ignore[reportCallIssue]


def nodes(role: Role) -> smoke.NodeFactory:
    """Every probe answers `role`, costs $0.001 and has one generation id."""

    def build(node: NodeName, settings: Settings, tracker: UsageTracker) -> smoke.NodeRunner:
        def run(state: EngineState) -> FactsOutcome | CheckOutcome:
            tracker.record(CallRecord(0.001, 10, f"gen-{uuid4().hex}", "stop"))
            step = StepResult(step=StepName.ROLE_OBLIGATIONS, decision="A role.")
            return CheckOutcome(step=step, role=RoleFinding(role=role))

        return run

    return build


def run(
    db: psycopg.Connection,
    arm: smoke.ModelArm,
    role: Role,
    count: int = 4,
    max_cost_usd: float = smoke.DEFAULT_MAX_COST_USD,
    prefix: str = "fixture-smoke",
) -> smoke.ArmRun:
    return smoke.run_arm(
        arm,
        probes(count, prefix),
        PostgresRunStore(db),
        SETTINGS,
        GIT_STATE,
        max_cost_usd=max_cost_usd,
        factory=nodes(role),
        served_by=lambda generation_id: arm.served_by,
    )


def test_both_runs_are_stored_and_the_verdict_comes_from_their_rows(db: psycopg.Connection) -> None:
    luna, gemini = run(db, LUNA, Role.PROVIDER), run(db, GEMINI, Role.DEPLOYER)
    row = db.execute(
        "select benchmark, cost_usd, config -> 'outcome' ->> 'status' from eval_runs where id = %s",
        (luna.run_id,),
    ).fetchone()
    assert row is not None
    assert (row[0], float(row[1]), row[2]) == ("own", pytest.approx(0.004), "completed")
    served = db.execute(
        "select predicted -> 'smoke' -> 'served_by', scores -> 'served_as_pinned'"
        " from eval_case_results where run_id = %s limit 1",
        (luna.run_id,),
    ).fetchone()
    assert served == (["Azure"], True)

    stored = smoke_verdict.load_run(db, luna.run_id)
    assert (stored.arm, stored.probes_planned) == ("luna", 4)
    assert [score.probe_id for score in stored.scores] == sorted(p.probe_id for p in probes())

    text = _smoke_comparison(db, {"luna": luna.run_id, "gemini": gemini.run_id})
    assert "Verdict: drop_luna" in text
    assert f"| {LUNA.model} | {luna.run_id} | 0/4 (0.0%) | 0/4 (0.0%) | 0/4 (0.0%) |" in text
    comparison = smoke_verdict.compare_runs(db, {"luna": luna.run_id, "gemini": gemini.run_id})
    assert comparison.verdict is Verdict.DROP_LUNA


def test_runs_given_as_the_wrong_model_are_refused(db: psycopg.Connection) -> None:
    luna, gemini = run(db, LUNA, Role.DEPLOYER), run(db, GEMINI, Role.DEPLOYER)
    with pytest.raises(SmokeRunError, match="is the gemini run"):
        smoke_verdict.compare_runs(db, {"luna": gemini.run_id, "gemini": luna.run_id})


def test_runs_that_planned_different_probes_are_refused(db: psycopg.Connection) -> None:
    luna, gemini = run(db, LUNA, Role.DEPLOYER, count=4), run(db, GEMINI, Role.DEPLOYER, count=3)
    with pytest.raises(SmokeRunError, match="did not plan the same probes"):
        smoke_verdict.compare_runs(db, {"luna": luna.run_id, "gemini": gemini.run_id})


def test_runs_of_the_same_size_on_other_cases_are_refused(db: psycopg.Connection) -> None:
    luna = run(db, LUNA, Role.DEPLOYER, count=4)
    gemini = run(db, GEMINI, Role.DEPLOYER, count=4, prefix="fixture-other")
    with pytest.raises(SmokeRunError, match="did not plan the same probes"):
        smoke_verdict.compare_runs(db, {"luna": luna.run_id, "gemini": gemini.run_id})


def test_a_run_stopped_by_the_cap_is_refused(db: psycopg.Connection) -> None:
    capped = run(db, LUNA, Role.DEPLOYER, max_cost_usd=smoke.worst_case_cost(NodeName.ROLE, LUNA))
    assert capped.status is smoke.RunStatus.COST_CAP_REACHED
    with pytest.raises(SmokeRunError, match="did not complete \\(status cost_cap_reached\\)"):
        smoke_verdict.load_run(db, capped.run_id)


def test_a_run_with_rows_missing_is_refused(db: psycopg.Connection) -> None:
    luna = run(db, LUNA, Role.DEPLOYER)
    db.execute(
        "delete from eval_case_results where run_id = %s and case_id = %s",
        (luna.run_id, "role_obligations:fixture-smoke-0"),
    )
    with pytest.raises(SmokeRunError, match="planned 4 probes but stored 3"):
        smoke_verdict.load_run(db, luna.run_id)


def _insert_run(db: psycopg.Connection, config: dict[str, JsonValue]) -> UUID:
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, 'own', %s) returning id",
        (GIT_STATE[0], Jsonb({"model": None, "embedding": None, "retrieval": None, **config})),
    ).fetchone()
    assert row is not None
    return row[0]


@pytest.mark.parametrize(
    "config",
    [
        {"classifier": "dummy"},
        {"arm": "luna", "experiment": "other"},
        {"arm": "claude", "experiment": smoke.EXPERIMENT},
    ],
)
def test_a_run_that_is_not_a_smoke_run_is_refused(
    db: psycopg.Connection, config: dict[str, JsonValue]
) -> None:
    run_id = _insert_run(db, config)
    with pytest.raises(SmokeRunError, match="not an x2_engine_smoke run"):
        smoke_verdict.load_run(db, run_id)


def test_a_missing_run_is_refused(db: psycopg.Connection) -> None:
    with pytest.raises(SmokeRunError, match="no run"):
        smoke_verdict.load_run(db, uuid4())


def test_probes_left_pending_are_settled_in_their_rows_before_the_run_is_finished(
    db: psycopg.Connection,
) -> None:
    def not_found(generation_id: str) -> str:
        raise GenerationNotFoundError(f"generation {generation_id} not found after 12 attempts")

    def verify(ids: Sequence[str]) -> dict[str, str | GenerationLookupError]:
        late = GenerationNotFoundError("generation late not found within 300 s")
        return {gid: LUNA.served_by if n else late for n, gid in enumerate(ids)}

    run = smoke.run_arm(
        LUNA,
        probes(),
        PostgresRunStore(db),
        SETTINGS,
        GIT_STATE,
        factory=nodes(Role.DEPLOYER),
        served_by=not_found,
        verify=verify,
        concurrency=1,
    )
    assert (run.checked_late, run.confirmed_late) == (4, 3)
    stored = smoke_verdict.load_run(db, run.run_id)
    assert sorted(score.kind.value for score in stored.scores) == ["answered"] * 3 + ["failed"]
    pending = db.execute(
        "select count(*) from eval_case_results where run_id = %s"
        " and (scores ->> 'pending_verification')::boolean",
        (run.run_id,),
    ).fetchone()
    assert pending == (0,)


def test_updating_a_case_the_run_does_not_have_is_an_error(db: psycopg.Connection) -> None:
    run = smoke.run_arm(
        LUNA,
        probes(1),
        PostgresRunStore(db),
        SETTINGS,
        GIT_STATE,
        factory=nodes(Role.DEPLOYER),
        served_by=lambda generation_id: LUNA.served_by,
    )
    missing = CaseRecord("role_obligations:nowhere", {}, {}, {}, None, 0.0, 0)
    with pytest.raises(LookupError, match="no stored case"):
        PostgresRunStore(db).update_case(run.run_id, missing)
