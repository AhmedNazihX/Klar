"""The engine model smoke test (X2): the probes it plans, how a probe's outcome becomes a row, a
model's run with a fake node and store, and the dry run. No model is called: nodes are fakes or
built without a call, and the serving provider comes from a stub.

The cases here are made up, not benchmark cases.
"""

import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
import yaml
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from openrouter.errors import NoResponseError, OpenRouterError
from pydantic import JsonValue, SecretStr, ValidationError
from typer.testing import CliRunner

from aiact import cli
from aiact.engine.nodes import facts, high_risk, role_obligations, scope
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.eval import records, runner
from aiact.eval.cases import AppliedAILabel, BenchmarkCase, CaseSet
from aiact.eval.experiments import matchers, smoke
from aiact.eval.experiments.smoke import (
    GEMINI,
    LUNA,
    CallRecord,
    ModelArm,
    NodeName,
    Probe,
    UsageTracker,
)
from aiact.eval.runner import CaseRecord
from aiact.llm import EmbeddingError, LLMConfigError
from aiact.llm.generations import GenerationLookupError, GenerationNotFoundError
from aiact.retrieval.provisions import ProvisionNotFoundError
from aiact.schemas import Language, RiskClass, Role, Status, StepName, StepResult
from aiact.settings import Settings
from tests.eval.experiments.builders import case, role_outcome

GIT_STATE = ("0123456789abcdef0123456789abcdef01234567", False)


def test_the_models_are_pinned_to_their_eu_zdr_endpoints() -> None:
    """Decision 005 and F6's checked slugs; a typo here would compare the wrong endpoint."""
    assert (LUNA.model, LUNA.provider, LUNA.served_by) == (
        "openai/gpt-6-luna-20260922",
        "azure/eu",
        "Azure",
    )
    assert (GEMINI.model, GEMINI.provider, GEMINI.served_by) == (
        "google/gemini-3.1-flash-lite",
        "google-vertex/eu",
        "Google",
    )
    assert dict(smoke.ARMS) == {"luna": LUNA, "gemini": GEMINI}


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


def test_each_probe_gets_its_replay_state() -> None:
    labelled = case("d-1", RiskClass.LIMITED_RISK)
    assert smoke.probe_state(Probe(NodeName.ROLE, labelled)) == matchers.role_check_state(
        labelled, smoke.AS_OF
    )
    for node in (NodeName.FACTS, NodeName.SCOPE, NodeName.HIGH_RISK):
        assert smoke.probe_state(Probe(node, labelled)) == matchers.replay_state(
            labelled, smoke.AS_OF
        )


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
    """A node factory: every node makes one tracked "call" (cost, tokens, a generation id), then
    returns `result` or raises it; `before_call` raises before any call is made. With
    `wait_for_company`, a node waits that long for a second one to start, so a run that would
    allow two at once shows it in `most_in_flight` however fast the threads are."""

    def __init__(
        self,
        result: object,
        cost: float = 0.001,
        tokens: int = 100,
        before_call: Exception | None = None,
        wait_for_company: float | None = None,
        has_generation_id: bool = True,
        finish_reason: str = "stop",
    ) -> None:
        self.result = result
        self.has_generation_id = has_generation_id
        self.finish_reason = finish_reason
        self.wait_for_company = wait_for_company
        self.company = threading.Event()
        self.cost = cost
        self.tokens = tokens
        self.before_call = before_call
        self.seen: list[tuple[NodeName, str | None, str | None]] = []
        self.lock = threading.Lock()
        self.in_flight = 0
        self.most_in_flight = 0

    def __call__(self, node: NodeName, given: Settings, tracker: UsageTracker) -> smoke.NodeRunner:
        self.seen.append((node, given.engine_model, given.engine_provider))

        def run(state: EngineState) -> FactsOutcome | CheckOutcome:
            with self.lock:
                self.in_flight += 1
                self.most_in_flight = max(self.most_in_flight, self.in_flight)
                if self.in_flight > 1:
                    self.company.set()
            if self.wait_for_company is not None:
                self.company.wait(self.wait_for_company)
            try:
                if self.before_call is not None:
                    raise self.before_call
                generation_id = f"gen-{uuid4().hex}" if self.has_generation_id else None
                call = CallRecord(self.cost, self.tokens, generation_id, self.finish_reason)
                tracker.record(call)
                if isinstance(self.result, BaseException):
                    raise self.result
                assert isinstance(self.result, FactsOutcome | CheckOutcome)
                return self.result
            finally:
                with self.lock:
                    self.in_flight -= 1

        return run


def served(name: str) -> smoke.ServedBy:
    return lambda generation_id: name


def probe_on(
    nodes: FakeNodes,
    arm: ModelArm = LUNA,
    probe: Probe | None = None,
    served_by: smoke.ServedBy | None = None,
) -> CaseRecord:
    probe = probe or Probe(NodeName.ROLE, case("d-1", role=Role.DEPLOYER))
    return smoke.run_probe(probe, arm, settings(), served_by or served(arm.served_by), nodes)


def info(record: CaseRecord) -> Mapping[str, JsonValue]:
    smoke_info = record.predicted["smoke"]
    assert isinstance(smoke_info, dict)
    return smoke_info


def test_a_fitting_answer_is_scored_with_its_cost_and_provider() -> None:
    nodes = FakeNodes(role_outcome(Role.DEPLOYER), 0.002, 50)
    record = probe_on(nodes)
    assert record.case_id == "role_obligations:d-1"
    assert record.scores == {
        "broken": False,
        "failed": False,
        "correct": True,
        "served_as_pinned": True,
        "pending_verification": False,
        "is_error": False,
        "cost_usd": 0.002,
        "tokens": 50,
    }
    assert (record.cost_usd, record.tokens) == (0.002, 50)
    role = record.predicted["role"]
    assert isinstance(role, dict) and role["role"] == "deployer"
    assert info(record)["served_by"] == ["Azure"]
    assert info(record)["cost_is_estimated"] is False
    [call] = info(record)["calls"]  # pyright: ignore[reportGeneralTypeIssues]
    assert isinstance(call, dict)
    assert (call["cost_usd"], call["tokens"], call["finish_reason"]) == (0.002, 50, "stop")
    assert info(record)["lookup_skipped"] is None
    assert record.label["id"] == "d-1"
    assert nodes.seen == [(NodeName.ROLE, LUNA.model, LUNA.provider)]


def test_a_wrong_answer_is_answered_but_not_correct() -> None:
    record = probe_on(FakeNodes(role_outcome(Role.PROVIDER)))
    assert record.scores["correct"] is False
    assert record.scores["is_error"] is False


def test_an_answer_from_another_provider_than_the_pinned_one_does_not_count() -> None:
    record = probe_on(
        FakeNodes(role_outcome(Role.DEPLOYER)), GEMINI, served_by=served("Google AI Studio")
    )
    assert record.scores["failed"] is True
    assert record.scores["correct"] is None
    assert record.scores["served_as_pinned"] is False
    assert record.predicted["not_pinned"] == "served by Google AI Studio, not Google"
    assert info(record)["served_by"] == ["Google AI Studio"]


def test_an_unreadable_generation_record_does_not_count() -> None:
    def lookup(generation_id: str) -> str:
        raise GenerationLookupError("generation lookup failed: OpenRouterError (HTTP 401)")

    record = probe_on(FakeNodes(role_outcome(Role.DEPLOYER)), served_by=lookup)
    assert record.scores["failed"] is True
    assert record.scores["served_as_pinned"] is None  # unknown, not a confirmed other provider
    assert record.scores["pending_verification"] is False
    assert record.predicted["not_pinned"] == "generation lookup failed: OpenRouterError (HTTP 401)"


def not_found(generation_id: str) -> str:
    raise GenerationNotFoundError(f"generation {generation_id} not found after 12 attempts")


@pytest.mark.parametrize(
    ("result", "probe", "kind", "correct"),
    [
        (role_outcome(Role.DEPLOYER), None, "answered", True),
        (role_outcome(Role.PROVIDER), None, "answered", False),
        (role_obligations.RoleOutputError("x"), None, "broken", False),
        (facts.FactsOutputError("x"), Probe(NodeName.FACTS, case("e-1")), "broken", None),
    ],
)
def test_a_record_not_found_in_time_leaves_the_probe_pending_with_its_score(
    result: object, probe: Probe | None, kind: str, correct: bool | None
) -> None:
    """X2's paid run: records showed up after the ~18 s window, so the check waits for the end."""
    record = probe_on(FakeNodes(result), probe=probe, served_by=not_found)
    assert record.scores["pending_verification"] is True
    assert record.scores["failed"] is False
    assert record.scores["broken"] is (kind == "broken")
    assert record.scores["correct"] is correct
    assert record.scores["served_as_pinned"] is None
    assert "not_pinned" not in record.predicted
    assert info(record)["pending_generation_ids"] == info(record)["generation_ids"]


def test_a_probe_that_already_got_no_answer_is_never_left_pending() -> None:
    """A provider error in the body after a billed call: no answer, so nothing to wait for."""
    error = ValueError("OpenRouter API returned an error: upstream timeout (code: 504)")
    record = probe_on(FakeNodes(error), served_by=not_found)
    assert record.scores["failed"] is True
    assert record.scores["pending_verification"] is False
    assert str(record.predicted["not_pinned"]).endswith("not found after 12 attempts")


@pytest.mark.parametrize("result", [role_outcome(Role.DEPLOYER), scope.ScopeOutputError("x")])
def test_a_reply_without_a_generation_id_does_not_count(result: object) -> None:
    record = probe_on(FakeNodes(result, has_generation_id=False))
    assert record.scores["failed"] is True
    assert record.scores["broken"] is False
    assert record.scores["served_as_pinned"] is None
    assert record.predicted["not_pinned"] == "the reply carries no generation id"


def test_an_answer_that_misses_the_schema_is_broken_and_wrong() -> None:
    error = scope.ScopeOutputError("scope answer doesn't fit the schema: ai_system: Field required")
    probe = Probe(NodeName.SCOPE, case("b-1", RiskClass.OUT_OF_SCOPE))
    record = probe_on(FakeNodes(error, 0.003), probe=probe)
    assert record.scores == {
        "broken": True,
        "failed": False,
        "correct": False,
        "served_as_pinned": True,
        "pending_verification": False,
        "is_error": True,
        "cost_usd": 0.003,
        "tokens": 100,
    }
    assert record.predicted["error"] == {"type": "ScopeOutputError", "message": str(error)}


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
    record = probe_on(FakeNodes(error), probe=Probe(NodeName.SCOPE, case("b-1")))
    assert record.scores["broken"] is True


@pytest.mark.parametrize("after_reply", [False, True])
def test_an_unknown_provision_is_a_corpus_gap_and_stops_the_run(after_reply: bool) -> None:
    """Neither check lets the model name a provision, so it is never the model's fault."""
    error = ProvisionNotFoundError("no text of art:3:1")
    nodes = FakeNodes(error) if after_reply else FakeNodes(None, before_call=error)
    with pytest.raises(ProvisionNotFoundError):
        probe_on(nodes, probe=Probe(NodeName.SCOPE, case("b-1")))


def test_a_contract_failure_is_broken_and_its_message_quotes_no_input() -> None:
    """Decision 010 addendum: cross-field rules aren't in the JSON Schema."""
    with pytest.raises(ValidationError) as caught:
        StepResult(
            step=StepName.SCOPE, decision="SECRET-DESCRIPTION", status=Status.LEGALLY_AMBIGUOUS
        )
    record = probe_on(FakeNodes(caught.value), probe=Probe(NodeName.SCOPE, case("b-1")))
    assert record.scores["broken"] is True
    assert "SECRET-DESCRIPTION" not in str(record.predicted)


def test_a_broken_facts_answer_has_no_correctness() -> None:
    error = facts.FactsOutputError("facts answer doesn't fit the schema")
    record = probe_on(FakeNodes(error), probe=Probe(NodeName.FACTS, case("e-1")))
    assert record.scores["broken"] is True
    assert record.scores["correct"] is None


def _http_error(status: int) -> OpenRouterError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return OpenRouterError("upstream error", httpx.Response(status, request=request))


@pytest.mark.parametrize(
    "error",
    [
        _http_error(502),
        NoResponseError("no response"),
        httpx.ConnectError("connection refused"),
        psycopg.OperationalError("server closed the connection"),
        EmbeddingError("embeddings request failed: NoResponseError"),
        ValueError("OpenRouter API returned an error: upstream timeout (code: 504)"),
    ],
)
def test_a_transport_provider_or_database_error_failed(error: Exception) -> None:
    record = probe_on(FakeNodes(None, before_call=error))
    assert record.scores["failed"] is True
    assert record.scores["broken"] is False
    assert record.scores["correct"] is None
    assert record.scores["served_as_pinned"] is None
    assert record.predicted["error"] == {"type": type(error).__name__, "message": str(error)}


@pytest.mark.parametrize(
    "error", [RuntimeError("a bug"), KeyError("high_risk_route"), ValueError("bad value")]
)
def test_any_other_error_stops_the_run(error: Exception) -> None:
    with pytest.raises(type(error)):
        probe_on(FakeNodes(None, before_call=error))


def test_a_missing_setting_stops_the_run() -> None:
    def unset(node: NodeName, given: Settings, tracker: UsageTracker) -> smoke.NodeRunner:
        raise LLMConfigError("ENGINE_PROVIDER is not set")

    with pytest.raises(LLMConfigError):
        smoke.run_probe(
            Probe(NodeName.SCOPE, case("b-1")), LUNA, settings(), served("Azure"), unset
        )


def test_a_state_that_cannot_be_built_stops_the_run_before_any_call() -> None:
    appliedai = BenchmarkCase(
        id="ai-1",
        set_name=CaseSet.APPLIEDAI,
        language=Language.EN,
        description="A made-up system.",
        label=AppliedAILabel.HIGH,
    )
    nodes = FakeNodes(role_outcome(Role.DEPLOYER))
    with pytest.raises(ValueError, match="no engine-vocabulary label"):
        probe_on(nodes, probe=Probe(NodeName.ROLE, appliedai))
    assert nodes.seen == []


def test_a_long_error_message_is_cut() -> None:
    record = probe_on(FakeNodes(None, before_call=httpx.ConnectError("x" * 1000)))
    error = record.predicted["error"]
    assert isinstance(error, dict)
    assert error["message"] == "x" * smoke.ERROR_MESSAGE_LIMIT


# --- Usage --------------------------------------------------------------------------------------


def _result(message: AIMessage, generation_id: str = "gen-1") -> LLMResult:
    return LLMResult(
        generations=[[ChatGeneration(message=message)]], llm_output={"id": generation_id}
    )


def test_the_tracker_adds_up_openrouter_cost_tokens_and_generation_ids() -> None:
    tracker = UsageTracker(LUNA, NodeName.ROLE)
    message = AIMessage(
        content="{}",
        response_metadata={"cost": 0.0012},
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
    )
    tracker.on_llm_end(_result(message, "gen-1"))
    tracker.on_llm_end(_result(message, "gen-2"))
    assert (tracker.calls, tracker.cost_usd, tracker.tokens) == (2, 0.0024, 240)
    assert tracker.generation_ids == ["gen-1", "gen-2"]
    assert tracker.is_cost_estimated is False


def test_a_reply_without_a_cost_is_priced_from_its_tokens() -> None:
    tracker = UsageTracker(GEMINI, NodeName.ROLE)
    message = AIMessage(
        content="{}",
        usage_metadata={"input_tokens": 1000, "output_tokens": 200, "total_tokens": 1200},
    )
    tracker.on_llm_end(_result(message))
    assert tracker.cost_usd == pytest.approx((1000 * 0.275 + 200 * 1.65) / 1e6)
    assert tracker.is_cost_estimated is True


@pytest.mark.parametrize(
    "result",
    [
        role_obligations.RoleOutputError("role answer doesn't fit the schema: Invalid JSON: EOF"),
        role_outcome(Role.DEPLOYER),
    ],
)
def test_a_reply_the_provider_broke_off_failed_and_is_not_broken(result: object) -> None:
    """Gemini, 2026-10-01: `finish_reason: "error"`, a cut JSON, $0 billed."""
    looked_up: list[str] = []

    def lookup(generation_id: str) -> str:
        looked_up.append(generation_id)
        return GEMINI.served_by

    nodes = FakeNodes(result, 0.0, 0, finish_reason="error")
    record = probe_on(nodes, GEMINI, served_by=lookup)
    assert record.scores["failed"] is True
    assert record.scores["broken"] is False
    assert record.scores["correct"] is None
    assert record.scores["served_as_pinned"] is None
    assert str(record.predicted["provider_error"]).startswith("a call ended with finish_reason")
    assert "not_pinned" not in record.predicted
    assert looked_up == []  # no ~18 s wait for a record of an unbilled generation
    assert info(record)["lookup_skipped"] == smoke.LOOKUP_SKIPPED
    [call] = info(record)["calls"]  # pyright: ignore[reportGeneralTypeIssues]
    assert isinstance(call, dict) and call["finish_reason"] == "error"
    assert call["cost_usd"] == 0.0


def test_a_provider_error_without_a_generation_id_is_not_looked_up_either() -> None:
    nodes = FakeNodes(role_outcome(Role.DEPLOYER), finish_reason="error", has_generation_id=False)
    record = probe_on(nodes, GEMINI, served_by=served("Google"))
    assert record.scores["failed"] is True
    assert "not_pinned" not in record.predicted
    assert info(record)["lookup_skipped"] == smoke.LOOKUP_SKIPPED


def test_a_reply_cut_off_by_the_output_cap_stays_broken() -> None:
    """Decision 023 addendum part 7: `finish_reason: "length"` is the model's, so it's broken."""
    error = role_obligations.RoleOutputError("role answer doesn't fit the schema: Invalid JSON")
    record = probe_on(FakeNodes(error, finish_reason="length"))
    assert record.scores["broken"] is True
    assert record.scores["failed"] is False
    assert record.scores["correct"] is False
    assert record.scores["served_as_pinned"] is True
    [call] = info(record)["calls"]  # pyright: ignore[reportGeneralTypeIssues]
    assert isinstance(call, dict) and call["finish_reason"] == "length"


def test_the_tracker_keeps_each_calls_finish_reason() -> None:
    tracker = UsageTracker(GEMINI, NodeName.ROLE)
    message = AIMessage(
        content="{",
        response_metadata={"cost": 0.0, "native_finish_reason": "MALFORMED_RESPONSE"},
        usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    )
    generation = ChatGeneration(message=message, generation_info={"finish_reason": "error"})
    tracker.on_llm_end(LLMResult(generations=[[generation]], llm_output={"id": "gen-1"}))
    assert tracker.records == [
        CallRecord(0.0, 0, "gen-1", "error", "MALFORMED_RESPONSE"),
    ]
    assert tracker.has_provider_error


def test_a_reply_without_cost_or_usage_is_charged_its_worst_case() -> None:
    tracker = UsageTracker(GEMINI, NodeName.HIGH_RISK)
    tracker.on_llm_end(_result(AIMessage(content="{}")))
    assert tracker.cost_usd == smoke.worst_case_cost(NodeName.HIGH_RISK, GEMINI)
    assert tracker.cost_usd > 0
    assert (tracker.calls, tracker.tokens, tracker.is_cost_estimated) == (1, 0, True)


@pytest.mark.parametrize(
    ("node", "node_class"),
    [
        (NodeName.FACTS, facts.FactExtractor),
        (NodeName.SCOPE, scope.ScopeCheck),
        (NodeName.HIGH_RISK, high_risk.HighRiskCheck),
        (NodeName.ROLE, role_obligations.RoleObligationsCheck),
    ],
)
def test_each_node_is_the_engines_own_on_the_arms_pinned_model_without_retries(
    node: NodeName, node_class: type
) -> None:
    tracker = UsageTracker(GEMINI, node)
    built = smoke.engine_node(node, smoke.arm_settings(settings(), GEMINI), tracker)
    assert isinstance(built, node_class)
    chat = built._model  # pyright: ignore[reportAttributeAccessIssue, reportFunctionMemberAccess]
    assert chat.model_name == "google/gemini-3.1-flash-lite"
    assert chat.openrouter_provider == {
        "data_collection": "deny",
        "zdr": True,
        "order": ["google-vertex/eu"],
        "allow_fallbacks": False,
    }
    assert chat.max_tokens == smoke.MAX_OUTPUT_TOKENS[node]
    assert chat.max_retries == 0
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
        self.events: list[str] = []

    def start_run(self, git_sha: str, benchmark: str, config: Mapping[str, JsonValue]) -> UUID:
        self.started.append((git_sha, benchmark, config))
        return self.run_id

    def add_case(self, run_id: UUID, record: CaseRecord) -> None:
        if self.fail_on_add:
            raise RuntimeError("database gone")
        self.rows.append(record)
        self.events.append(f"add {record.case_id}")

    def update_case(self, run_id: UUID, record: CaseRecord) -> None:
        [index] = [n for n, row in enumerate(self.rows) if row.case_id == record.case_id]
        self.rows[index] = record
        self.events.append(f"update {record.case_id}")

    def finish_run(self, run_id: UUID, outcome: Mapping[str, JsonValue]) -> None:
        self.finished.append(outcome)
        self.events.append("finish")


PROBES = tuple(Probe(NodeName.ROLE, case(f"d-{n}", role=Role.DEPLOYER)) for n in range(5))
ROLE_WORST = smoke.worst_case_cost(NodeName.ROLE, LUNA)


def run_arm(
    nodes: FakeNodes, store: FakeStore, arm: ModelArm = LUNA, **options: float | int
) -> smoke.ArmRun:
    return smoke.run_arm(
        arm,
        PROBES,
        store,
        settings(),
        GIT_STATE,
        factory=nodes,
        served_by=served(arm.served_by),
        **options,  # pyright: ignore[reportArgumentType]
    )


def test_a_run_stores_one_row_per_probe_on_the_arms_model() -> None:
    store, nodes = FakeStore(), FakeNodes(role_outcome(Role.DEPLOYER), 0.01, 10)
    run = run_arm(nodes, store, concurrency=2)
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
    assert (config["served_by"], config["max_retries"]) == ("Azure", 0)
    assert config["nodes"] == ["role_obligations"]
    assert {"model", "embedding", "retrieval"} <= config.keys()
    [outcome] = store.finished
    assert (outcome["status"], outcome["probes_planned"], outcome["probes_recorded"]) == (
        "completed",
        5,
        5,
    )


def test_no_probe_starts_once_the_spend_reaches_the_cap() -> None:
    store = FakeStore()
    nodes = FakeNodes(role_outcome(Role.DEPLOYER), 0.3, 10)
    run = run_arm(nodes, store, GEMINI, max_cost_usd=0.5, concurrency=1)  # 0.3, 0.6: stop
    assert run.status is smoke.RunStatus.COST_CAP_REACHED
    assert run.probes_recorded == 2
    assert store.finished[0]["status"] == "cost_cap_reached"


def test_the_cap_reserves_each_probe_in_flight_so_concurrency_cannot_widen_the_overshoot() -> None:
    nodes = FakeNodes(role_outcome(Role.DEPLOYER), 0.0, 10, wait_for_company=0.05)
    run = run_arm(nodes, FakeStore(), max_cost_usd=ROLE_WORST * 1.5, concurrency=4)
    assert run.status is smoke.RunStatus.COMPLETED
    assert nodes.most_in_flight == 1
    roomy = FakeNodes(role_outcome(Role.DEPLOYER), 0.0, 10, wait_for_company=5.0)
    run_arm(roomy, FakeStore(), max_cost_usd=ROLE_WORST * 2.5, concurrency=4)
    assert roomy.most_in_flight == 2


def test_a_cap_below_one_probe_starts_none() -> None:
    store = FakeStore()
    run = run_arm(FakeNodes(role_outcome(Role.DEPLOYER)), store, max_cost_usd=ROLE_WORST / 2)
    assert (run.status, run.probes_recorded, store.rows) == (
        smoke.RunStatus.COST_CAP_REACHED,
        0,
        [],
    )


def test_a_run_that_stops_on_an_error_is_marked_interrupted() -> None:
    store = FakeStore(fail_on_add=True)
    with pytest.raises(RuntimeError):
        run_arm(FakeNodes(role_outcome(Role.DEPLOYER)), store)
    assert store.finished[0]["status"] == "interrupted"


def test_a_probe_error_stops_the_run_and_records_the_probes_in_flight() -> None:
    store = FakeStore()
    with pytest.raises(RuntimeError, match="a bug"):
        run_arm(FakeNodes(None, before_call=RuntimeError("a bug")), store, concurrency=1)
    assert store.finished[0]["status"] == "interrupted"


class Verifier:
    """A stand-in for `GenerationLookup.served_by_all`: every id gets `answer`."""

    def __init__(self, answer: str | GenerationLookupError) -> None:
        self.answer = answer
        self.asked: list[list[str]] = []

    def __call__(self, generation_ids: Sequence[str]) -> dict[str, str | GenerationLookupError]:
        self.asked.append(list(generation_ids))
        return {generation_id: self.answer for generation_id in generation_ids}


def run_pending(
    store: FakeStore, verify: smoke.VerifyAll, result: object = None, arm: ModelArm = LUNA
) -> smoke.ArmRun:
    """A run whose every probe's record isn't found in time, so all are checked at the end."""
    return smoke.run_arm(
        arm,
        PROBES,
        store,
        settings(),
        GIT_STATE,
        factory=FakeNodes(result or role_outcome(Role.DEPLOYER)),
        served_by=not_found,
        verify=verify,
        concurrency=1,
    )


def test_pending_probes_are_checked_once_at_the_end_before_the_run_is_finished() -> None:
    store, verify = FakeStore(), Verifier("Azure")
    run = run_pending(store, verify)
    [asked] = verify.asked
    assert len(asked) == len(PROBES)
    assert store.events[-1] == "finish"
    assert store.events[-6:-1] == [f"update {p.probe_id}" for p in PROBES]
    assert (run.checked_late, run.confirmed_late) == (5, 5)
    outcome = store.finished[0]
    assert (outcome["status"], outcome["probes_checked_late"]) == ("completed", 5)
    assert outcome["probes_confirmed_late"] == 5


def test_a_pending_probe_confirmed_on_the_pinned_provider_keeps_its_score() -> None:
    store = FakeStore()
    run_pending(store, Verifier("Azure"), role_outcome(Role.PROVIDER))
    row = store.rows[0]
    assert row.scores["failed"] is False
    assert row.scores["correct"] is False  # the wrong answer it gave, still scored
    assert row.scores["served_as_pinned"] is True
    assert row.scores["pending_verification"] is False
    assert info(row)["served_by"] == ["Azure"]
    assert info(row)["pending_generation_ids"] == []
    deferred = info(row)["deferred_check"]
    assert isinstance(deferred, dict) and deferred["result"] == "confirmed"
    assert "not_pinned" not in row.predicted


def test_a_pending_probe_served_by_another_provider_fails() -> None:
    store = FakeStore()
    run = run_pending(store, Verifier("Google AI Studio"), arm=GEMINI)
    row = store.rows[0]
    assert (row.scores["failed"], row.scores["broken"], row.scores["correct"]) == (
        True,
        False,
        None,
    )
    assert row.scores["served_as_pinned"] is False
    assert row.scores["pending_verification"] is False
    assert row.predicted["not_pinned"] == "served by Google AI Studio, not Google"
    assert run.confirmed_late == 0


def test_a_pending_probe_whose_record_never_shows_up_fails() -> None:
    store = FakeStore()
    late = GenerationNotFoundError("generation gen-1 not found within 300 s")
    run_pending(store, Verifier(late), scope.ScopeOutputError("x"))
    row = store.rows[0]
    assert (row.scores["failed"], row.scores["broken"], row.scores["correct"]) == (
        True,
        False,
        None,
    )
    assert row.scores["served_as_pinned"] is None
    assert row.predicted["not_pinned"] == "generation gen-1 not found within 300 s"
    assert (row.cost_usd, row.scores["cost_usd"]) == (0.001, 0.001)  # billed all the same


def test_no_check_is_made_when_nothing_is_pending() -> None:
    verify = Verifier("Azure")
    store = FakeStore()
    smoke.run_arm(
        LUNA,
        PROBES,
        store,
        settings(),
        GIT_STATE,
        factory=FakeNodes(role_outcome(Role.DEPLOYER)),
        served_by=served("Azure"),
        verify=verify,
    )
    assert verify.asked == []
    assert not any(event.startswith("update") for event in store.events)


def test_a_check_that_breaks_marks_the_run_interrupted() -> None:
    def broken_verify(generation_ids: Sequence[str]) -> dict[str, str | GenerationLookupError]:
        raise KeyboardInterrupt

    store = FakeStore()
    with pytest.raises(KeyboardInterrupt):
        run_pending(store, broken_verify)
    assert store.finished[0]["status"] == "interrupted"


def test_the_worst_case_is_one_call_at_the_full_output_cap() -> None:
    prompt = round(2194 * smoke.PROMPT_MARGIN)
    assert smoke.worst_case_cost(NodeName.ROLE, LUNA) == pytest.approx(
        (prompt * 0.11 + 3000 * 0.55) / 1e6
    )


# --- Dry run ------------------------------------------------------------------------------------


def test_the_estimate_prices_typical_tokens_cold() -> None:
    probes = (
        Probe(NodeName.FACTS, case("e-1")),
        Probe(NodeName.HIGH_RISK, case("e-1")),
        Probe(NodeName.ROLE, case("d-1")),
    )
    expected = (1582 + 7972 + 1958) * 0.11 / 1e6 + (1800 + 1017 + 1452) * 0.55 / 1e6
    assert smoke.estimate_cost(probes, LUNA) == pytest.approx(expected)


def test_the_plan_names_counts_and_both_estimates() -> None:
    text = smoke.format_plan(PROBES, (LUNA, GEMINI))
    assert text.startswith("5 probes on 5 cases (no model call made)")
    assert "  role_obligations: 5" in text
    assert f"luna ({LUNA.model} @ {LUNA.provider}): ~$" in text
    assert "gemini (" in text and "total: ~$" in text


cli_runner = CliRunner()


def test_the_dry_run_makes_no_call_and_prints_the_plan() -> None:
    result = cli_runner.invoke(cli.app, ["evaluate", "smoke", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "(no model call made)" in result.stdout
    assert "luna (" in result.stdout and "gemini (" in result.stdout


def test_the_dry_run_for_one_model_prices_only_it() -> None:
    result = cli_runner.invoke(cli.app, ["evaluate", "smoke", "--dry-run", "--model", "gemini"])
    assert result.exit_code == 0, result.output
    assert "gemini (" in result.stdout and "luna (" not in result.stdout


def test_an_unknown_model_is_refused() -> None:
    result = cli_runner.invoke(cli.app, ["evaluate", "smoke", "--dry-run", "--model", "claude"])
    assert result.exit_code == 2
    assert "unknown model claude" in result.stderr


def test_the_cost_cap_and_concurrency_reach_each_models_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Mapping[str, object]]] = []

    def fake_run_arm(
        arm: ModelArm, probes: Sequence[Probe], *args: object, **kwargs: object
    ) -> smoke.ArmRun:
        calls.append((arm.name, kwargs))
        return smoke.ArmRun(
            arm, uuid4(), smoke.RunStatus.COMPLETED, len(probes), len(probes), 0.1, 10
        )

    @contextmanager
    def fake_connect() -> Iterator[object]:
        yield object()

    monkeypatch.setattr(smoke, "run_arm", fake_run_arm)
    monkeypatch.setattr(records, "connect", fake_connect)
    monkeypatch.setattr(runner, "current_git_state", lambda: GIT_STATE)
    monkeypatch.setattr(cli, "_smoke_comparison", lambda connection, run_ids: "Verdict: keep_luna")
    arguments = ["evaluate", "smoke", "--max-cost-usd", "0.07", "--concurrency", "3"]
    result = cli_runner.invoke(cli.app, arguments)
    assert result.exit_code == 0, result.output
    assert [name for name, _ in calls] == ["luna", "gemini"]
    assert all(kw == {"max_cost_usd": 0.07, "concurrency": 3} for _, kw in calls)
    assert "Verdict: keep_luna" in result.stdout
