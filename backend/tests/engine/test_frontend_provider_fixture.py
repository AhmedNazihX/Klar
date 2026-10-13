"""The frontend's provider-result fixture (P23) still matches the backend.

`frontend/src/test/fixtures/provider.json` holds the provider results the provider layout's
component tests read, one per own case, keyed by case id. Each replays the case's role step exactly
as `test_role_obligations.py::test_b5d_case_replay` recorded it (no model, database or network),
then runs it through the engine's graph and its own `finalize`, with the class the label gives
scripted as the earlier checks would leave it (`role_check_state`: the Annex III route and point,
or the Art. 50(1) duty):
- own-d-01 (English): a recruitment agency that sells a licensed screening tool under its own
  brand, the provider under Art. 25(1)(a), high-risk under Annex III point 4(a);
- own-d-13 (German): a social welfare office that extended a bought mailroom tool to housing
  benefit, the provider under Art. 25(1)(c) and also the deployer, Annex III point 5(a);
- own-d-03 (English): a gym chain's hiring workflow on a general-purpose assistant, the provider
  through the GPAI build route (Art. 3(68)), high-risk under Annex III point 4(a);
- own-d-06 (German): a shop chat built on a third-party large language model, the provider
  through the GPAI build route, limited risk (Art. 50(1)).

The recordings belong to the role node test; re-record them there, never here. When the engine,
the obligations table or a recording changes on purpose, rewrite the fixture with
`AIACT_WRITE_FRONTEND_FIXTURES=1 uv run pytest tests/engine/test_frontend_provider_fixture.py`
and commit it with the change.
"""

import json
import os
from datetime import date
from pathlib import Path

import pytest

from aiact.engine.graph import EngineNodes, build_graph
from aiact.engine.nodes.finalize import finalize
from aiact.engine.nodes.role_obligations import RoleObligationsCheck
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineInput, EngineState
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import case_label, role_check_state
from aiact.schemas import ClassificationResult, RiskClass, Role, StepName, StepResult
from aiact.settings import Settings
from tests.conftest import RECORDINGS_DIR

FIXTURE = (
    Path(__file__).resolve().parents[3] / "frontend" / "src" / "test" / "fixtures" / "provider.json"
)
WRITE_FLAG = "AIACT_WRITE_FRONTEND_FIXTURES"

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
"""The engine model and provider the role replays were recorded with."""
ROLE_AS_OF = date(2026, 9, 29)
"""The role replays' date (`test_role_obligations.ROLE_AS_OF`) for a case without its own."""
ROLE_RECORDINGS = RECORDINGS_DIR / "engine" / "nodes" / "test_role_obligations"

CASES = (
    "own-d-01-own-brand-screening",
    "own-d-13-mailroom-tool-benefits",
    "own-d-03-assistant-repurposed-hiring",
    "own-d-06-shop-chat-on-llm",
)


@pytest.fixture
def vcr_cassette_dir() -> str:
    return str(ROLE_RECORDINGS)


@pytest.fixture
def default_cassette_name(request: pytest.FixtureRequest) -> str:
    return f"test_b5d_case_replay[{request.getfixturevalue('case_id')}]"


@pytest.fixture
def luna_settings(openrouter_settings: Settings, record_mode: str) -> Settings:
    if record_mode != "none":
        pytest.skip("replay only: record the role node test's replays instead")
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


def _own_case(case_id: str) -> BenchmarkCase:
    paths = sorted((CASES_DIR / CaseSet.OWN.value / "d").glob("*.yaml"))
    return next(case for path in paths for case in load_yaml_file(path) if case.id == case_id)


def _class_checks(state: EngineState, point: str | None) -> dict[StepName, CheckOutcome]:
    """The earlier checks as `role_check_state` leaves the state: the high-risk route with the
    label's Annex `point`, or the Art. 50 duties."""
    route = state.get("high_risk_route")
    if route is not None:
        step = StepResult(step=StepName.HIGH_RISK, decision=f"Scripted: high-risk ({point})")
        return {
            StepName.HIGH_RISK: CheckOutcome(step=step, high_risk_route=route, annex_point=point)
        }
    duties = state.get("transparency_duties", ())
    step = StepResult(step=StepName.TRANSPARENCY, decision=f"Scripted: {', '.join(duties)}")
    return {StepName.TRANSPARENCY: CheckOutcome(step=step, transparency_duties=duties)}


def recorded_provider_result(case: BenchmarkCase, settings: Settings) -> ClassificationResult:
    """The case's result from its recorded role step; call it inside the cassette's context."""
    # The role step sees the state it was recorded with; only the scripted check names the point.
    state = role_check_state(case, ROLE_AS_OF)
    role = RoleObligationsCheck(settings)(state)
    point = next(iter(case_label(case).annex_point), None)
    checks = {**_class_checks(state, point), StepName.ROLE_OBLIGATIONS: role}
    graph = build_graph(
        EngineNodes(
            facts=scripted_nodes(Script()).facts,
            checks=scripted_nodes(Script(checks=checks)).checks,
            finalize=finalize,
        )
    )
    given: EngineInput = {
        "description": state["description"],
        "language": state["language"],
        "law_version": state["law_version"],
        "as_of": state["as_of"],
        "exclude_source_example_ids": (),
    }
    result = graph.invoke(given)["result"]
    assert isinstance(result, ClassificationResult)
    return result


@pytest.mark.vcr
@pytest.mark.parametrize("case_id", CASES)
def test_the_frontend_provider_fixture_matches_the_backend(
    case_id: str, luna_settings: Settings
) -> None:
    """Replays `test_b5d_case_replay[<case_id>]` from the role node test's recordings."""
    case = _own_case(case_id)
    result = recorded_provider_result(case, luna_settings)
    assert result.role is Role.PROVIDER
    assert result.risk_class in (RiskClass.HIGH_RISK, RiskClass.LIMITED_RISK)
    stored = json.loads(FIXTURE.read_text()) if FIXTURE.exists() else {}
    expected = result.model_dump(mode="json")
    if os.environ.get(WRITE_FLAG) == "1":
        stored = {**stored, case_id: expected}
        FIXTURE.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n")
    assert stored.get(case_id) == expected, (
        f"{FIXTURE.name} is stale: rewrite it with {WRITE_FLAG}=1"
    )
