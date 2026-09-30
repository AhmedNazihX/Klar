"""The engine model smoke test (X2): the probes it plans, the states they get, the scoring against
labels, how a probe's outcome becomes a row, a model's run with a fake node and store, decision
023's rule, and the dry run. No model is called: nodes are fakes or built without a call.

The cases here are made up, not benchmark cases.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from pydantic import JsonValue, SecretStr, ValidationError
from typer.testing import CliRunner

from aiact.cli import app
from aiact.engine.nodes import facts, high_risk, role_obligations, scope
from aiact.engine.nodes.scope import ScopeOutputError
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome, RoleFinding
from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.experiments import smoke
from aiact.eval.experiments.smoke import (
    GEMINI,
    LUNA,
    WORKED_EXAMPLE,
    NodeName,
    Probe,
    ProbeKind,
    ProbeScore,
    UsageTracker,
    Verdict,
)
from aiact.eval.runner import CaseRecord
from aiact.llm import LLMConfigError
from aiact.schemas import (
    Citation,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    OpenQuestion,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import Settings

GIT_STATE = ("0123456789abcdef0123456789abcdef01234567", False)
OPEN = OpenQuestion(question="Does the law settle it?", readings=("Stricter.", "Lenient."))
ASK = FollowUpQuestion(id="third_party_assessment", text="Is a notified body involved?")


def case(
    case_id: str,
    risk_class: RiskClass = RiskClass.HIGH_RISK,
    *,
    status: Status = Status.DECIDED,
    role: Role | None = Role.PROVIDER,
    annex_point: str | None = None,
    citation: tuple[str, ...] = ("art:6:1:a",),
    tags: tuple[str, ...] = (),
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        set_name=CaseSet.OWN,
        language=Language.EN,
        description=f"A made-up system ({case_id}).",
        label=CaseLabel(risk_class=risk_class, status=status, role=role, annex_point=annex_point),
        label_citation=citation,
        notes="Open question and readings." if status is Status.LEGALLY_AMBIGUOUS else None,
        tags=tags,
    )


def step(
    name: StepName,
    status: Status = Status.DECIDED,
    cited: Sequence[str] = (),
    decision: str = "A decision.",
    missing: FollowUpQuestion | None = None,
) -> StepResult:
    citations = tuple(
        Citation(provision_id=pid, document_id="ai-act", language=Language.EN, quote="Text.")
        for pid in cited
    )
    return StepResult(
        step=name,
        decision=decision,
        citations=citations,
        status=status,
        missing_fact=(missing or ASK) if status is Status.NEEDS_MORE_INFORMATION else None,
        open_question=OPEN if status is Status.LEGALLY_AMBIGUOUS else None,
    )


def scope_outcome(
    matched: bool, status: Status = Status.DECIDED, cited: Sequence[str] = ()
) -> CheckOutcome:
    return CheckOutcome(step=step(StepName.SCOPE, status, cited), matched=matched)


def high_risk_outcome(
    route: HighRiskRoute | None,
    point: str | None,
    status: Status = Status.DECIDED,
    decision: str = "A decision.",
    missing: FollowUpQuestion | None = None,
) -> CheckOutcome:
    return CheckOutcome(
        step=step(StepName.HIGH_RISK, status, decision=decision, missing=missing),
        high_risk_route=route,
        annex_point=point,
    )


def role_outcome(role: Role, status: Status = Status.DECIDED) -> CheckOutcome:
    return CheckOutcome(step=step(StepName.ROLE_OBLIGATIONS, status), role=RoleFinding(role=role))


# --- Planning -----------------------------------------------------------------------------------


def write_cases(root: Path, folder: str, cases: Sequence[BenchmarkCase]) -> None:
    target = root / "own" / folder
    target.mkdir(parents=True, exist_ok=True)
    for item in cases:
        dumped = item.model_dump(mode="json", exclude_none=True)
        (target / f"{item.id}.yaml").write_text(yaml.safe_dump(dumped), encoding="utf-8")


@pytest.fixture
def cases_dir(tmp_path: Path) -> Path:
    write_cases(tmp_path, "b", [case("b-1", RiskClass.OUT_OF_SCOPE, citation=("art:2:3",))])
    write_cases(tmp_path, "e", [case("e-1"), case("e-2", RiskClass.MINIMAL_RISK)])
    write_cases(
        tmp_path,
        "d",
        [
            case("d-1", RiskClass.LIMITED_RISK, role=Role.DEPLOYER),
            case("d-2", RiskClass.OUT_OF_SCOPE, citation=("art:2:3",)),
            case("d-3", RiskClass.MINIMAL_RISK, role=None),
        ],
    )
    return tmp_path


def test_each_check_is_probed_on_its_folder_and_facts_on_every_case_used(cases_dir: Path) -> None:
    probes = smoke.plan_probes(cases_dir)
    assert [probe.probe_id for probe in probes] == [
        "scope:b-1",
        "high_risk:init-worked-example",
        "high_risk:e-1",
        "high_risk:e-2",
        "role_obligations:d-1",
        "facts:b-1",
        "facts:init-worked-example",
        "facts:e-1",
        "facts:e-2",
        "facts:d-1",
    ]


def test_a_missing_folder_plans_no_probe_for_it(tmp_path: Path) -> None:
    probes = smoke.plan_probes(tmp_path)
    assert [probe.probe_id for probe in probes] == [
        "high_risk:init-worked-example",
        "facts:init-worked-example",
    ]


def test_the_default_plan_covers_every_approved_own_case() -> None:
    probes = smoke.plan_probes()
    counts = {node: sum(probe.node is node for probe in probes) for node in NodeName}
    checks = counts[NodeName.SCOPE] + counts[NodeName.HIGH_RISK] + counts[NodeName.ROLE]
    assert counts[NodeName.FACTS] == len({probe.case.id for probe in probes})
    assert checks >= 40  # B5b 13 + B5e 14 and the worked example + B5d 13 (decision 023: ~50)


# --- States -------------------------------------------------------------------------------------


def test_a_check_other_than_role_sees_the_replay_state() -> None:
    state = smoke.probe_state(Probe(NodeName.HIGH_RISK, case("e-1")))
    assert state == {
        "description": "A made-up system (e-1).",
        "language": Language.EN,
        "law_version": smoke.LawVersion.AMENDED,
        "as_of": smoke.AS_OF,
        "answers": {},
        "exclude_source_example_ids": (),
        "facts": (),
        "steps": (),
    }


@pytest.mark.parametrize(
    ("risk_class", "annex_point", "expected"),
    [
        (RiskClass.HIGH_RISK, "annex:III:4:a", {"high_risk_route": HighRiskRoute.ANNEX_III}),
        (RiskClass.HIGH_RISK, "annex:I:11", {"high_risk_route": HighRiskRoute.ANNEX_I}),
        (RiskClass.HIGH_RISK, None, {"high_risk_route": HighRiskRoute.ANNEX_III}),
        (RiskClass.LIMITED_RISK, None, {"transparency_duties": ("art:50:1",)}),
        (RiskClass.PROHIBITED, None, {}),
        (RiskClass.MINIMAL_RISK, None, {}),
    ],
)
def test_the_role_check_gets_the_class_the_label_settles(
    risk_class: RiskClass, annex_point: str | None, expected: dict[str, object]
) -> None:
    labelled = case("d-1", risk_class, annex_point=annex_point)
    state = smoke.probe_state(Probe(NodeName.ROLE, labelled))
    plain = smoke.probe_state(Probe(NodeName.SCOPE, labelled))
    matches = (StepName.PROHIBITED,) if risk_class is RiskClass.PROHIBITED else ()
    assert state == {**plain, "matches": matches, **expected}


# --- Scoring ------------------------------------------------------------------------------------


def test_scope_matches_out_of_scope_with_the_label_citation_first() -> None:
    labelled = case("b-1", RiskClass.OUT_OF_SCOPE, citation=("art:2:3", "art:3:1"))
    assert smoke.scope_matches(scope_outcome(True, cited=("art:3:1", "art:2:3")), labelled)
    assert not smoke.scope_matches(scope_outcome(True, cited=("art:3:1",)), labelled)
    assert not smoke.scope_matches(scope_outcome(False, cited=("art:2:3",)), labelled)


def test_scope_matches_in_scope_on_the_status() -> None:
    labelled = case("b-2", RiskClass.MINIMAL_RISK, status=Status.LEGALLY_AMBIGUOUS)
    assert smoke.scope_matches(scope_outcome(False, Status.LEGALLY_AMBIGUOUS), labelled)
    assert not smoke.scope_matches(scope_outcome(False), labelled)


def test_high_risk_matches_the_annex_i_point_from_the_tags() -> None:
    labelled = case("e-1", tags=("annex_i_point:annex:I:A:11",))
    assert smoke.high_risk_matches(
        high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:A:11"), labelled
    )
    assert not smoke.high_risk_matches(
        high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:I:A:11"), labelled
    )
    assert not smoke.high_risk_matches(
        high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:A:12"), labelled
    )


def test_high_risk_matches_the_worked_example_on_annex_iii() -> None:
    right = high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:III:4:a")
    assert smoke.high_risk_matches(right, WORKED_EXAMPLE)
    wrong = high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:III:4:a")
    assert not smoke.high_risk_matches(wrong, WORKED_EXAMPLE)


def test_high_risk_on_both_routes_expects_annex_iii() -> None:
    labelled = case("e-14", tags=("annex_i_point:annex:I:A:11", "also_route:annex_iii"))
    outcome = high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:I:A:11")
    assert smoke.high_risk_matches(outcome, labelled)


def test_high_risk_asks_the_tagged_missing_fact() -> None:
    labelled = case(
        "e-7",
        status=Status.NEEDS_MORE_INFORMATION,
        tags=("annex_i_point:annex:I:B:21", "missing_fact:third_party_assessment"),
    )
    asked = high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:B:21", Status.NEEDS_MORE_INFORMATION)
    assert smoke.high_risk_matches(asked, labelled)
    other = FollowUpQuestion(id="intended_purpose", text="What is it for?")
    wrong = high_risk_outcome(
        HighRiskRoute.ANNEX_I, "annex:I:B:21", Status.NEEDS_MORE_INFORMATION, missing=other
    )
    assert not smoke.high_risk_matches(wrong, labelled)


def test_a_decided_section_b_case_names_art_2_2() -> None:
    labelled = case("e-5", tags=("annex_i_point:annex:I:B:18", "annex_i_section:b"))
    named = "High-risk. Under Art. 2(2) only Art. 6(1) applies."
    assert smoke.high_risk_matches(
        high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:B:18", decision=named), labelled
    )
    assert not smoke.high_risk_matches(
        high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:B:18"), labelled
    )


def test_a_not_high_risk_label_expects_no_route_and_its_status() -> None:
    labelled = case("e-2", RiskClass.MINIMAL_RISK)
    assert smoke.high_risk_matches(high_risk_outcome(None, None), labelled)
    assert not smoke.high_risk_matches(
        high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:A:4"), labelled
    )
    exempt = CheckOutcome(step=step(StepName.HIGH_RISK), annex_iii_exempt=True)
    assert not smoke.high_risk_matches(exempt, labelled)


def test_role_matches_the_role_and_an_ambiguous_status() -> None:
    assert smoke.role_matches(role_outcome(Role.DEPLOYER), case("d-1", role=Role.DEPLOYER))
    assert not smoke.role_matches(role_outcome(Role.PROVIDER), case("d-1", role=Role.DEPLOYER))
    ambiguous = case("d-2", status=Status.LEGALLY_AMBIGUOUS)
    assert smoke.role_matches(role_outcome(Role.PROVIDER, Status.LEGALLY_AMBIGUOUS), ambiguous)
    assert not smoke.role_matches(role_outcome(Role.PROVIDER), ambiguous)


def test_a_role_outcome_without_a_role_does_not_match() -> None:
    assert not smoke.role_matches(CheckOutcome(step=step(StepName.ROLE_OBLIGATIONS)), case("d-1"))


def test_facts_are_not_scored() -> None:
    assert smoke.is_correct(Probe(NodeName.FACTS, case("e-1")), FactsOutcome()) is None


def test_a_check_that_returns_facts_is_a_contract_error() -> None:
    with pytest.raises(TypeError):
        smoke.is_correct(Probe(NodeName.SCOPE, case("b-1")), FactsOutcome())


# --- One probe ----------------------------------------------------------------------------------


def settings() -> Settings:
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        openrouter_api_key=SecretStr("not-a-key"),
        embedding_model="qwen/qwen3-embedding-8b",
        embedding_provider="nebius",
    )


class FakeNodes:
    """A node factory: every node returns `result` (or raises it), after `cost` is spent."""

    def __init__(self, result: object, cost: float = 0.001, tokens: int = 100) -> None:
        self.result = result
        self.cost = cost
        self.tokens = tokens
        self.seen: list[tuple[NodeName, str | None, str | None]] = []

    def __call__(self, node: NodeName, given: Settings, tracker: UsageTracker) -> smoke.NodeRunner:
        self.seen.append((node, given.engine_model, given.engine_provider))

        def run(state: EngineState) -> FactsOutcome | CheckOutcome:
            tracker.add(self.cost, self.tokens)
            if isinstance(self.result, BaseException):
                raise self.result
            assert isinstance(self.result, FactsOutcome | CheckOutcome)
            return self.result

        return run


def scores_of(record: CaseRecord) -> Mapping[str, object]:
    return record.scores


def test_a_fitting_answer_is_scored_and_its_cost_kept() -> None:
    probe = Probe(NodeName.ROLE, case("d-1", role=Role.DEPLOYER))
    record = smoke.run_probe(probe, settings(), FakeNodes(role_outcome(Role.DEPLOYER), 0.002, 50))
    assert record.case_id == "role_obligations:d-1"
    assert scores_of(record) == {
        "broken": False,
        "failed": False,
        "correct": True,
        "is_error": False,
        "cost_usd": 0.002,
        "tokens": 50,
    }
    assert (record.cost_usd, record.tokens) == (0.002, 50)
    assert record.predicted["role"] == {
        "role": "deployer",
        "also_role": None,
        "role_switch_reason": None,
        "obligations": [],
    }
    assert record.label["id"] == "d-1"


def test_a_wrong_answer_is_answered_but_not_correct() -> None:
    probe = Probe(NodeName.ROLE, case("d-1", role=Role.DEPLOYER))
    record = smoke.run_probe(probe, settings(), FakeNodes(role_outcome(Role.PROVIDER)))
    assert scores_of(record)["correct"] is False
    assert scores_of(record)["is_error"] is False


def test_an_answer_that_misses_the_schema_is_broken_and_wrong() -> None:
    probe = Probe(NodeName.SCOPE, case("b-1", RiskClass.OUT_OF_SCOPE))
    error = ScopeOutputError("scope answer doesn't fit the schema: ai_system: Field required")
    record = smoke.run_probe(probe, settings(), FakeNodes(error, 0.003))
    assert scores_of(record) == {
        "broken": True,
        "failed": False,
        "correct": False,
        "is_error": True,
        "cost_usd": 0.003,
        "tokens": 100,
    }
    assert record.predicted == {"error": {"type": "ScopeOutputError", "message": str(error)}}


@pytest.mark.parametrize(
    "error",
    [
        facts.FactsOutputError("x"),
        high_risk.HighRiskOutputError("x"),
        role_obligations.RoleOutputError("x"),
        scope.ScopeOutputError("x"),
    ],
)
def test_every_nodes_output_error_is_broken(error: Exception) -> None:
    record = smoke.run_probe(Probe(NodeName.HIGH_RISK, case("e-1")), settings(), FakeNodes(error))
    assert scores_of(record)["broken"] is True


def test_a_contract_failure_is_broken_and_its_message_quotes_no_input() -> None:
    """Decision 010 addendum: cross-field rules aren't in the JSON Schema."""
    with pytest.raises(ValidationError) as caught:
        StepResult(
            step=StepName.SCOPE, decision="SECRET-DESCRIPTION", status=Status.LEGALLY_AMBIGUOUS
        )
    record = smoke.run_probe(
        Probe(NodeName.SCOPE, case("b-1")), settings(), FakeNodes(caught.value)
    )
    assert scores_of(record)["broken"] is True
    assert "SECRET-DESCRIPTION" not in str(record.predicted)


def test_a_broken_facts_answer_has_no_correctness() -> None:
    error = facts.FactsOutputError("facts answer doesn't fit the schema")
    record = smoke.run_probe(Probe(NodeName.FACTS, case("e-1")), settings(), FakeNodes(error))
    assert scores_of(record)["broken"] is True
    assert scores_of(record)["correct"] is None


def test_a_call_that_returns_nothing_failed_and_is_not_scored() -> None:
    error = ValueError("OpenRouter API returned an error: upstream timeout (code: 504)")
    record = smoke.run_probe(Probe(NodeName.SCOPE, case("b-1")), settings(), FakeNodes(error))
    assert scores_of(record)["failed"] is True
    assert scores_of(record)["broken"] is False
    assert scores_of(record)["correct"] is None
    assert record.predicted == {"error": {"type": "ValueError", "message": str(error)}}


def test_a_long_error_message_is_cut() -> None:
    record = smoke.run_probe(
        Probe(NodeName.SCOPE, case("b-1")), settings(), FakeNodes(RuntimeError("x" * 1000))
    )
    error = record.predicted["error"]
    assert isinstance(error, dict)
    assert error["message"] == "x" * smoke.ERROR_MESSAGE_LIMIT


def test_a_missing_setting_stops_the_run() -> None:
    with pytest.raises(LLMConfigError):
        smoke.run_probe(
            Probe(NodeName.SCOPE, case("b-1")), settings(), FakeNodes(LLMConfigError("unset"))
        )


def test_the_tracker_adds_up_openrouter_cost_and_tokens() -> None:
    tracker = UsageTracker()
    message = AIMessage(
        content="{}",
        response_metadata={"cost": 0.0012},
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
    )
    no_cost = AIMessage(content="{}")
    result = LLMResult(
        generations=[[ChatGeneration(message=message)], [ChatGeneration(message=no_cost)]]
    )
    tracker.on_llm_end(result)
    tracker.on_llm_end(result)
    assert (tracker.cost_usd, tracker.tokens) == (0.0024, 240)


@pytest.mark.parametrize(
    ("node", "node_class"),
    [
        (NodeName.FACTS, facts.FactExtractor),
        (NodeName.SCOPE, scope.ScopeCheck),
        (NodeName.HIGH_RISK, high_risk.HighRiskCheck),
        (NodeName.ROLE, role_obligations.RoleObligationsCheck),
    ],
)
def test_each_node_is_the_engines_own_on_the_arms_pinned_model(
    node: NodeName, node_class: type
) -> None:
    tracker = UsageTracker()
    built = smoke.engine_node(node, smoke.arm_settings(settings(), GEMINI), tracker)
    assert isinstance(built, node_class)
    chat = built._model  # pyright: ignore[reportAttributeAccessIssue, reportFunctionMemberAccess]
    assert chat.model_name == GEMINI.model
    assert chat.openrouter_provider == {
        "data_collection": "deny",
        "zdr": True,
        "order": [GEMINI.provider],
        "allow_fallbacks": False,
    }
    assert chat.max_tokens == smoke.MAX_OUTPUT_TOKENS[node]
    assert chat.callbacks == [tracker]


def test_the_high_risk_cap_leaves_room_for_reasoning() -> None:
    """E5: Luna's reasoning ran out at 3000 output tokens; the node needs 6000."""
    assert smoke.MAX_OUTPUT_TOKENS[NodeName.HIGH_RISK] == 6000


# --- One model's run ----------------------------------------------------------------------------


class FakeStore:
    def __init__(self, fail_on_add: bool = False) -> None:
        self.started: list[tuple[str, str, Mapping[str, JsonValue]]] = []
        self.rows: list[CaseRecord] = []
        self.finished: list[Mapping[str, JsonValue]] = []
        self.run_id = uuid4()
        self.fail_on_add = fail_on_add

    def start_run(self, git_sha: str, benchmark: str, config: Mapping[str, JsonValue]) -> UUID:
        self.started.append((git_sha, benchmark, config))
        return self.run_id

    def add_case(self, run_id: UUID, record: CaseRecord) -> None:
        if self.fail_on_add:
            raise RuntimeError("database gone")
        self.rows.append(record)

    def finish_run(self, run_id: UUID, outcome: Mapping[str, JsonValue]) -> None:
        self.finished.append(outcome)


PROBES = tuple(Probe(NodeName.ROLE, case(f"d-{n}", role=Role.DEPLOYER)) for n in range(5))


def test_a_run_stores_one_row_per_probe_on_the_arms_model() -> None:
    store, nodes = FakeStore(), FakeNodes(role_outcome(Role.DEPLOYER), 0.01, 10)
    run = smoke.run_arm(LUNA, PROBES, store, settings(), GIT_STATE, concurrency=2, factory=nodes)
    assert run.status is smoke.RunStatus.COMPLETED
    assert (run.probes_planned, run.probes_recorded, run.tokens) == (5, 5, 50)
    assert run.cost_usd == pytest.approx(0.05)
    assert sorted(row.case_id for row in store.rows) == [p.probe_id for p in PROBES]
    assert {seen[1:] for seen in nodes.seen} == {(LUNA.model, LUNA.provider)}
    [(git_sha, benchmark, config)] = store.started
    assert (git_sha, benchmark) == (GIT_STATE[0], "own")
    assert config["experiment"] == smoke.EXPERIMENT
    assert (config["arm"], config["model"], config["provider"]) == (
        "luna",
        LUNA.model,
        LUNA.provider,
    )
    assert config["nodes"] == ["role_obligations"]
    assert {"model", "embedding", "retrieval"} <= config.keys()
    [outcome] = store.finished
    assert (outcome["status"], outcome["probes_recorded"]) == ("completed", 5)


def test_no_batch_starts_once_the_cap_is_spent() -> None:
    store = FakeStore()
    nodes = FakeNodes(role_outcome(Role.DEPLOYER), 0.3, 10)
    run = smoke.run_arm(
        GEMINI, PROBES, store, settings(), GIT_STATE, max_cost_usd=0.5, concurrency=2, factory=nodes
    )
    assert run.status is smoke.RunStatus.COST_CAP_REACHED
    assert run.probes_recorded == 2
    assert store.finished[0]["status"] == "cost_cap_reached"


def test_a_run_that_stops_on_an_error_is_marked_interrupted() -> None:
    store = FakeStore(fail_on_add=True)
    with pytest.raises(RuntimeError):
        smoke.run_arm(
            LUNA,
            PROBES,
            store,
            settings(),
            GIT_STATE,
            factory=FakeNodes(role_outcome(Role.DEPLOYER)),
        )
    assert store.finished[0]["status"] == "interrupted"


# --- Decision 023's rule ------------------------------------------------------------------------


def scores(
    answered_right: int,
    answered_wrong: int = 0,
    broken: int = 0,
    failed: int = 0,
    facts_ok: int = 0,
) -> list[ProbeScore]:
    """Scope probes numbered in this order: right, wrong, broken, failed; then facts probes."""
    kinds = (
        [(ProbeKind.ANSWERED, True)] * answered_right
        + [(ProbeKind.ANSWERED, False)] * answered_wrong
        + [(ProbeKind.BROKEN, False)] * broken
        + [(ProbeKind.FAILED, None)] * failed
    )
    checks = [ProbeScore(f"scope:c-{n:03}", kind, ok) for n, (kind, ok) in enumerate(kinds)]
    facts_rows = [ProbeScore(f"facts:c-{n:03}", ProbeKind.ANSWERED, None) for n in range(facts_ok)]
    return checks + facts_rows


def test_equal_models_keep_luna() -> None:
    result = smoke.compare(scores(18, 2), scores(18, 2))
    assert result.verdict is Verdict.KEEP_LUNA
    assert (result.scored, result.luna_accuracy, result.gemini_accuracy) == (20, 0.9, 0.9)
    assert result.reasons == ()


def test_exactly_10_percent_broken_keeps_luna_and_one_more_drops_it() -> None:
    kept = smoke.compare(scores(18, broken=2), scores(18, 2))  # 2 of 20 broken: not more than 10%
    assert kept.verdict is Verdict.KEEP_LUNA
    dropped = smoke.compare(scores(17, 1, broken=3), scores(17, 3))  # 3 of 21 answers broken
    assert dropped.verdict is Verdict.DROP_LUNA
    assert dropped.reasons == ("luna: 3 of 21 answers broken, more than 10%",)


def test_broken_facts_count_towards_the_share() -> None:
    extra = ("facts:x-1", "facts:x-2", "facts:x-3")
    luna = [*scores(10, facts_ok=8), *(ProbeScore(pid, ProbeKind.BROKEN, None) for pid in extra)]
    gemini = [
        *scores(10, facts_ok=8),
        *(ProbeScore(pid, ProbeKind.ANSWERED, None) for pid in extra),
    ]
    result = smoke.compare(luna, gemini)
    assert result.luna.broken == 3
    assert result.luna.broken_by_node == {"facts": 3}
    assert result.verdict is Verdict.DROP_LUNA  # 3 of 21 replies


def test_ten_points_below_drops_luna_and_less_keeps_it() -> None:
    at_limit = smoke.compare(scores(8, 2), scores(9, 1))  # 80% against 90%
    assert at_limit.verdict is Verdict.DROP_LUNA
    assert at_limit.reasons == ("luna: 8/10 correct, 10 or more points below gemini's 9/10",)
    below_limit = smoke.compare(scores(9, 12), scores(11, 10))  # 42.9% against 52.4%: 9.5 points
    assert below_limit.verdict is Verdict.KEEP_LUNA


def test_a_broken_answer_counts_as_wrong_in_the_accuracy() -> None:
    result = smoke.compare(scores(9, broken=1), scores(10))
    assert (result.luna_correct, result.gemini_correct, result.scored) == (9, 10, 10)
    assert result.verdict is Verdict.DROP_LUNA


def test_accuracy_uses_only_probes_both_models_replied_to() -> None:
    luna = scores(8, 1, failed=1)  # c-009 failed for luna
    gemini = scores(9, 1)  # c-009 is wrong for gemini
    result = smoke.compare(luna, gemini)
    assert result.scored == 9
    assert (result.luna_correct, result.gemini_correct) == (8, 9)


def test_many_unanswered_probes_make_it_inconclusive() -> None:
    result = smoke.compare(scores(15, failed=5), scores(20))
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.reasons == ("luna: 5 of 20 probes got no answer",)


def test_a_probe_one_run_lacks_counts_as_unanswered() -> None:
    result = smoke.compare(scores(8), scores(10))  # luna's run stopped after 8 probes
    assert (result.luna.failed, result.luna.planned) == (2, 10)
    assert result.verdict is Verdict.INCONCLUSIVE


def test_no_probe_scored_for_both_is_inconclusive() -> None:
    result = smoke.compare(scores(0, facts_ok=3), scores(0, facts_ok=3))
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.reasons == ("no probe scored for both",)


def test_a_stored_row_is_read_back_by_its_flags() -> None:
    row = {"broken": True, "failed": False, "correct": False, "is_error": True, "cost_usd": 0.1}
    assert smoke.probe_score("high_risk:e-1", row) == ProbeScore(
        "high_risk:e-1", ProbeKind.BROKEN, False
    )
    assert smoke.probe_score(
        "facts:e-1", {"broken": False, "failed": True, "correct": None}
    ).kind is (ProbeKind.FAILED)


@pytest.mark.parametrize(
    ("probe_id", "row"),
    [
        ("scope:b-1", {"cost_usd": 0.1, "is_error": False}),
        ("scope:b-1", {"broken": False, "failed": False, "correct": 1}),
        ("baseline:b-1", {"broken": False, "failed": False, "correct": True}),
    ],
)
def test_a_row_that_is_not_a_smoke_probe_is_refused(
    probe_id: str, row: Mapping[str, JsonValue]
) -> None:
    with pytest.raises(ValueError):
        smoke.probe_score(probe_id, row)


# --- Dry run and report -------------------------------------------------------------------------


def test_the_estimate_prices_typical_tokens_cold() -> None:
    probes = (Probe(NodeName.FACTS, case("e-1")), Probe(NodeName.HIGH_RISK, case("e-1")))
    expected = (1582 + 7972) * 0.11 / 1e6 + (1800 + 1017) * 0.55 / 1e6
    assert smoke.estimate_cost(probes, LUNA) == pytest.approx(expected)


def test_the_plan_names_counts_and_both_estimates() -> None:
    text = smoke.format_plan(PROBES, (LUNA, GEMINI))
    assert text.startswith("5 probes on 5 cases (no model call made)")
    assert "  role_obligations: 5" in text
    assert f"luna ({LUNA.model} @ {LUNA.provider}): ~$" in text
    assert "gemini (" in text and "total: ~$" in text


def test_the_comparison_table_names_the_run_ids_and_the_verdict() -> None:
    luna_id, gemini_id = uuid4(), uuid4()
    comparison = smoke.compare(scores(8, 1, broken=1), scores(9, 1))
    text = smoke.format_comparison(comparison, {"luna": luna_id, "gemini": gemini_id})
    assert (
        f"| {LUNA.model} | {luna_id} | 1/10 (10.0%): scope 1 | 0/10 (0.0%) | 8/10 (80.0%) |" in text
    )
    assert f"| {GEMINI.model} | {gemini_id} | 0/10 (0.0%) | 0/10 (0.0%) | 9/10 (90.0%) |" in text
    assert "Verdict: drop_luna" in text


cli = CliRunner()


def test_the_dry_run_makes_no_call_and_prints_the_plan() -> None:
    result = cli.invoke(app, ["evaluate", "smoke", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "(no model call made)" in result.stdout
    assert "luna (" in result.stdout and "gemini (" in result.stdout


def test_the_dry_run_for_one_model_prices_only_it() -> None:
    result = cli.invoke(app, ["evaluate", "smoke", "--dry-run", "--model", "gemini"])
    assert result.exit_code == 0, result.output
    assert "gemini (" in result.stdout and "luna (" not in result.stdout


def test_an_unknown_model_is_refused() -> None:
    result = cli.invoke(app, ["evaluate", "smoke", "--dry-run", "--model", "claude"])
    assert result.exit_code == 2
    assert "unknown model claude" in result.stderr
