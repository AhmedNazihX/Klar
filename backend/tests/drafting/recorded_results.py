"""Classification results built from recorded engine replays, for the vendor letters' DoD.

Each replays one check of an own case exactly as its node test recorded it (the model's reply
from the cassette, the corpus answers from `<test>.corpus.json`; no model, database or network),
then runs it through the engine's graph with the other checks scripted and the engine's own
`finalize`, so the result is aggregated as a real run aggregates it:
- prohibited: own-c-08 (German; a call centre's bought software that reads its staff's moods
  from their voices), decided under Art. 5(1)(f), from `test_prohibited`'s B5c replay;
- legally ambiguous: own-e-09 (English; a predictive-maintenance tool for cableways), whose
  Annex I safety-component question the law leaves open, from `test_high_risk`'s replay (E12's
  DoD case), finished by a scripted deployer role step, as a resort that bought it would be.

The recordings belong to those node tests; re-record them there, never here.
"""

from datetime import date
from pathlib import Path
from typing import NoReturn

import pytest

from aiact.engine.graph import EngineNodes, build_graph
from aiact.engine.nodes.finalize import finalize
from aiact.engine.nodes.high_risk import HighRiskCheck
from aiact.engine.nodes.prohibited import ProhibitedCheck
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineInput, RoleFinding
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import replay_state
from aiact.obligations.list import list_obligations
from aiact.schemas import (
    ClassificationResult,
    HighRiskRoute,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import Settings
from tests.conftest import RECORDINGS_DIR
from tests.engine.nodes.corpus_recording import (
    CORPUS_SUFFIX,
    RecordedGuidelineLibrary,
    RecordingPendingError,
    corpus_recording,
)
from tests.engine.nodes.test_high_risk import RecordedHighRiskLibrary

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
"""The engine model and provider the node replays were recorded with."""
AS_OF = date(2026, 9, 30)
"""The node replays' date for a case without its own."""

NODE_RECORDINGS = RECORDINGS_DIR / "engine" / "nodes"
PROHIBITED_CASE = "own-c-08-agent-voice-mood-scores"
PROHIBITED_DIR = NODE_RECORDINGS / "test_prohibited"
PROHIBITED_CASSETTE = f"test_b5c_case_replay[{PROHIBITED_CASE}]"
AMBIGUOUS_CASE = "own-e-09-ropeway-wear-forecast"
AMBIGUOUS_DIR = NODE_RECORDINGS / "test_high_risk"
AMBIGUOUS_CASSETTE = f"test_replay_annex_i_case[{AMBIGUOUS_CASE}]"

RECORD_COMMAND = "the node test's own RECORD_COMMAND (test_prohibited.py, test_high_risk.py)"


def recording_files(cassette_dir: Path, cassette: str) -> tuple[Path, Path]:
    """The cassette and the corpus answers of one node replay."""
    return cassette_dir / f"{cassette}.yaml", cassette_dir / f"{cassette}{CORPUS_SUFFIX}"


def replay_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER})


def own_case(category: str, case_id: str) -> BenchmarkCase:
    """The own case `case_id` from `eval/cases/own/<category>/`."""
    paths = sorted((CASES_DIR / CaseSet.OWN.value / category).glob("*.yaml"))
    return next(case for path in paths for case in load_yaml_file(path) if case.id == case_id)


def _no_live_corpus() -> NoReturn:
    raise AssertionError("this helper only replays")


def _finalized(case: BenchmarkCase, checks: dict[StepName, CheckOutcome]) -> ClassificationResult:
    """The result of a run of the case whose checks return `checks` (the others decide
    nothing), aggregated by the engine's `finalize`."""
    scripted = scripted_nodes(Script(checks=checks))
    graph = build_graph(
        EngineNodes(facts=scripted.facts, checks=scripted.checks, finalize=finalize)
    )
    state = replay_state(case, AS_OF)
    given: EngineInput = {
        "description": state["description"],
        "language": state["language"],
        "law_version": state["law_version"],
        "as_of": state["as_of"],
        "exclude_source_example_ids": state["exclude_source_example_ids"],
    }
    result = graph.invoke(given)["result"]
    assert isinstance(result, ClassificationResult)
    return result


def recorded_prohibited_result(settings: Settings, record_mode: str) -> ClassificationResult:
    """own-c-08 from its recorded Art. 5 check; call it inside the cassette's `vcr` context."""
    case = own_case("c", PROHIBITED_CASE)
    with corpus_recording(
        str(PROHIBITED_DIR), PROHIBITED_CASSETTE, record_mode, RECORD_COMMAND, _no_live_corpus
    ) as recording:
        check = ProhibitedCheck(
            replay_settings(settings), library=RecordedGuidelineLibrary(recording)
        )
        outcome = check(replay_state(case, AS_OF))
    return _finalized(case, {StepName.PROHIBITED: outcome})


def _deployer_step() -> CheckOutcome:
    """A deployer of a high-risk Annex I system, with the committed table's duties."""
    duties = list_obligations(Role.DEPLOYER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_I)
    step = StepResult(
        step=StepName.ROLE_OBLIGATIONS, decision="Scripted: a deployer of the bought tool"
    )
    return CheckOutcome(
        step=step, role=RoleFinding(role=Role.DEPLOYER, obligations=duties.obligations)
    )


AMBIGUOUS_RECORDING_PENDING = pytest.mark.xfail(
    strict=True,
    raises=RecordingPendingError,
    reason="recording pending (orchestrator): E20's re-record of own-e-09 settles its "
    "safety-component question (a known gap in test_high_risk.py, run-to-run variance), so no "
    "recorded result is legally ambiguous; re-record own-e-09 there",
)
"""The tests on the recorded ambiguous result, while own-e-09's recording isn't ambiguous."""


def recorded_ambiguous_result(settings: Settings, record_mode: str) -> ClassificationResult:
    """own-e-09 from its recorded high-risk check; call it inside the cassette's `vcr`
    context. Raises `RecordingPendingError` when the recording isn't legally ambiguous, which
    makes it no source for these tests."""
    case = own_case("e", AMBIGUOUS_CASE)
    with corpus_recording(
        str(AMBIGUOUS_DIR), AMBIGUOUS_CASSETTE, record_mode, RECORD_COMMAND, _no_live_corpus
    ) as recording:
        check = HighRiskCheck(replay_settings(settings), library=RecordedHighRiskLibrary(recording))
        outcome = check(replay_state(case, AS_OF))
    checks = {StepName.HIGH_RISK: outcome, StepName.ROLE_OBLIGATIONS: _deployer_step()}
    result = _finalized(case, checks)
    if result.status is not Status.LEGALLY_AMBIGUOUS:
        raise RecordingPendingError(f"{AMBIGUOUS_CASSETTE} is not legally ambiguous; re-record it")
    return result
