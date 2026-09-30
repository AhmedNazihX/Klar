"""The smoke test's runs in the local Supabase Postgres: each model's run is stored, and the verdict
is read back from the stored rows by run id. The nodes are fakes; no model is called.

Everything runs inside the test's rolled-back transaction: the store's writes become savepoints.
"""

from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from pydantic import SecretStr

from aiact.cli import _smoke_comparison  # pyright: ignore[reportPrivateUsage]
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome, RoleFinding
from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.experiments import smoke
from aiact.eval.experiments.smoke import GEMINI, LUNA, NodeName, Probe, UsageTracker, Verdict
from aiact.eval.records import PostgresRunStore
from aiact.schemas import Language, RiskClass, Role, StepName, StepResult
from aiact.settings import Settings

pytestmark = pytest.mark.db

GIT_STATE = ("0123456789abcdef0123456789abcdef01234567", False)
PROBES = tuple(
    Probe(
        NodeName.ROLE,
        BenchmarkCase(
            id=f"fixture-smoke-{number}",
            set_name=CaseSet.OWN,
            language=Language.EN,
            description=f"Made-up description {number}",
            label=CaseLabel(risk_class=RiskClass.MINIMAL_RISK, role=Role.DEPLOYER),
            label_citation=("art:3:4",),
        ),
    )
    for number in range(4)
)
SETTINGS = Settings(_env_file=None, openrouter_api_key=SecretStr("not-a-key"))  # pyright: ignore[reportCallIssue]


def nodes(role: Role) -> smoke.NodeFactory:
    """Every probe answers `role` and costs $0.001."""

    def build(node: NodeName, settings: Settings, tracker: UsageTracker) -> smoke.NodeRunner:
        def run(state: EngineState) -> FactsOutcome | CheckOutcome:
            tracker.add(0.001, 10)
            step = StepResult(step=StepName.ROLE_OBLIGATIONS, decision="A role.")
            return CheckOutcome(step=step, role=RoleFinding(role=role))

        return run

    return build


def run(db: psycopg.Connection, arm: smoke.ModelArm, role: Role) -> smoke.ArmRun:
    store = PostgresRunStore(db)
    return smoke.run_arm(arm, PROBES, store, SETTINGS, GIT_STATE, factory=nodes(role))


def test_both_runs_are_stored_and_the_verdict_comes_from_their_rows(db: psycopg.Connection) -> None:
    luna, gemini = run(db, LUNA, Role.PROVIDER), run(db, GEMINI, Role.DEPLOYER)
    row = db.execute(
        "select benchmark, cost_usd, config -> 'outcome' ->> 'status' from eval_runs where id = %s",
        (luna.run_id,),
    ).fetchone()
    assert row is not None
    assert (row[0], float(row[1]), row[2]) == ("own", pytest.approx(0.004), "completed")

    arm, scores = smoke.load_run(db, luna.run_id)
    assert arm == "luna"
    assert [score.probe_id for score in scores] == sorted(p.probe_id for p in PROBES)

    text = _smoke_comparison(db, {"luna": luna.run_id, "gemini": gemini.run_id})
    assert "Verdict: drop_luna" in text
    assert f"| {LUNA.model} | {luna.run_id} | 0/4 (0.0%) | 0/4 (0.0%) | 0/4 (0.0%) |" in text
    _, gemini_scores = smoke.load_run(db, gemini.run_id)
    assert smoke.compare(scores, gemini_scores).verdict is Verdict.DROP_LUNA


def test_runs_given_as_the_wrong_model_are_refused(db: psycopg.Connection) -> None:
    luna, gemini = run(db, LUNA, Role.DEPLOYER), run(db, GEMINI, Role.DEPLOYER)
    with pytest.raises(smoke.SmokeRunError, match="is the gemini run"):
        _smoke_comparison(db, {"luna": gemini.run_id, "gemini": luna.run_id})


def test_a_run_that_is_not_a_smoke_run_is_refused(db: psycopg.Connection) -> None:
    config = {"model": None, "embedding": None, "retrieval": None, "classifier": "dummy"}
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, 'own', %s) returning id",
        (GIT_STATE[0], Jsonb(config)),
    ).fetchone()
    assert row is not None
    with pytest.raises(smoke.SmokeRunError, match="not an x2_engine_smoke run"):
        smoke.load_run(db, row[0])
    with pytest.raises(smoke.SmokeRunError, match="no run"):
        smoke.load_run(db, uuid4())
