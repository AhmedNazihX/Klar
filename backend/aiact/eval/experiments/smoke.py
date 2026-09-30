"""The engine model smoke test: GPT-6 Luna against Gemini 3.1 Flash-Lite on the staged nodes (X2;
INIT > Engine safety net; decision 023).

Each model runs the merged engine nodes on the approved own cases, one probe per node and case:
- facts (E2) on every case below, for broken outputs only (facts have no label to score);
- scope (E3) on the B5b cases (`own/b`), scored against the label's scope outcome;
- high_risk (E5) on INIT's worked example and the B5e cases (`own/e`), scored on class, route,
  Annex point and status;
- role_obligations (E7) on the B5d cases (`own/d`) whose label names a role, given the class the
  label settles (the role-only replay the user chose on 2026-09-29), scored on the role.

Every probe sees the same state as its node's replay test (no facts, no answers, no exclusions),
so a model's accuracy here can be checked against the committed Luna recordings. The node code,
prompts and retrieval are the engine's own; only the model and its pinned endpoint change.

A probe's outcome is one of three:
- **broken**: the model answered, but the answer doesn't fit the node's schema or the result
  contract (the node's `*OutputError`, or a `ValidationError` from the contract). Cross-field rules
  aren't in the JSON Schema, so contract failures count as broken (decision 010 addendum). A reply
  cut off by the output cap is broken too (E5: Luna's reasoning ran out at 3000 tokens). The nodes
  make no tool calls: retrieval is code, and structured output is the model's only interface.
- **failed**: no answer came back (network, provider or database error). Not the model's fault, so
  it counts as neither broken nor wrong, but too many of them make the comparison inconclusive.
- **answered**: scored against the label (facts: not scored).

Each model's run is stored as one `eval_runs` row (`config.experiment` = `x2_engine_smoke`) with
one `eval_case_results` row per probe (`case_id` = `<node>:<case id>`), and the verdict is computed
from those stored rows, so decision 004 quotes numbers by run id. The fixed rule (decision 023):
Luna is dropped if more than 10% of its answers are broken, or if its accuracy is 10 or more
percentage points below Gemini's on the same probes.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

import psycopg
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult
from pydantic import JsonValue, ValidationError

from aiact.engine.nodes import facts, high_risk, role_obligations, scope
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseLabel, CaseSet, load_yaml_file
from aiact.eval.runner import CaseRecord, RunStore, Score, label_record
from aiact.llm import LLMConfigError, engine_chat_model
from aiact.llm.structured import describe_validation_error
from aiact.schemas import HighRiskRoute, Language, LawVersion, RiskClass, Role, Status, StepName
from aiact.settings import Settings

logger = logging.getLogger(__name__)

EXPERIMENT = "x2_engine_smoke"
"""`eval_runs.config.experiment` of every smoke run; the compare step refuses other runs."""
BENCHMARK = CaseSet.OWN.value

BROKEN_SHARE_LIMIT = (1, 10)
"""Luna is dropped when more than 1 in 10 of its answers are broken (decision 023)."""
ACCURACY_GAP_LIMIT = (10, 100)
"""Luna is dropped when its accuracy is 10 or more points (of 100) below Gemini's (decision 023)."""
FAILED_SHARE_LIMIT = (1, 10)
"""More than 1 in 10 probes without an answer, for either model, makes the verdict inconclusive."""

DEFAULT_MAX_COST_USD = 0.5
"""The spending cap per model; the dry-run estimate for both models together is about $0.37."""
DEFAULT_CONCURRENCY = 4
ERROR_MESSAGE_LIMIT = 300
AS_OF = date(2026, 9, 30)
"""The date the probes ask about, as in the high-risk and scope replays."""


class NodeName(StrEnum):
    """The engine nodes the smoke test runs."""

    FACTS = "facts"
    SCOPE = "scope"
    HIGH_RISK = "high_risk"
    ROLE = "role_obligations"


CASE_FOLDERS: Mapping[NodeName, str] = {
    NodeName.SCOPE: "b",
    NodeName.ROLE: "d",
    NodeName.HIGH_RISK: "e",
}
"""The own-case folder (`eval/cases/own/<folder>`) each check is probed on."""

MAX_OUTPUT_TOKENS: Mapping[NodeName, int] = {
    NodeName.FACTS: facts.MAX_OUTPUT_TOKENS,
    NodeName.SCOPE: scope.MAX_OUTPUT_TOKENS,
    NodeName.HIGH_RISK: high_risk.MAX_OUTPUT_TOKENS,
    NodeName.ROLE: role_obligations.MAX_OUTPUT_TOKENS,
}


@dataclass(frozen=True)
class ModelArm:
    """One model under test: its OpenRouter slug, its pinned EU ZDR endpoint and its prices in USD
    per million tokens on that endpoint (decision 005)."""

    name: str
    model: str
    provider: str
    input_usd_per_m: float
    output_usd_per_m: float


LUNA = ModelArm("luna", "openai/gpt-6-luna-20260922", "azure/eu", 0.11, 0.55)
GEMINI = ModelArm("gemini", "google/gemini-3.1-flash-lite", "google-vertex/eu", 0.275, 1.65)
ARMS: Mapping[str, ModelArm] = {arm.name: arm for arm in (LUNA, GEMINI)}


@dataclass(frozen=True)
class NodeTokens:
    prompt: int
    completion: int


TYPICAL_TOKENS: Mapping[NodeName, NodeTokens] = {
    NodeName.FACTS: NodeTokens(prompt=1582, completion=1800),
    NodeName.SCOPE: NodeTokens(prompt=4096, completion=1523),
    NodeName.HIGH_RISK: NodeTokens(prompt=7972, completion=1017),
    NodeName.ROLE: NodeTokens(prompt=1658, completion=1107),
}
"""Mean tokens of one call, from the committed Luna recordings of each node's replay tests (47
calls, $0.049 in total). Completion tokens include Luna's reasoning, so for Gemini, which doesn't
reason, the estimate is an upper bound."""


# --- The probes ---------------------------------------------------------------------------------

WORKED_EXAMPLE = BenchmarkCase(
    id="init-worked-example",
    set_name=CaseSet.OWN,
    language=Language.EN,
    description=(
        "We're a 40-person logistics company. We use a tool that reads incoming job applications, "
        "scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't "
        "change it."
    ),
    label=CaseLabel(
        risk_class=RiskClass.HIGH_RISK, role=Role.DEPLOYER, annex_point="annex:III:4:a"
    ),
    label_citation=("annex:III:4:a", "art:6:3"),
    notes="INIT > Worked example (not a benchmark case): ranking is profiling, so no Art. 6(3).",
)
"""INIT's worked example, which E5's replays include; probed on high_risk and facts."""


@dataclass(frozen=True)
class Probe:
    """One node run on one case."""

    node: NodeName
    case: BenchmarkCase

    @property
    def probe_id(self) -> str:
        return f"{self.node.value}:{self.case.id}"


def case_label(case: BenchmarkCase) -> CaseLabel:
    if not isinstance(case.label, CaseLabel):
        raise ValueError(f"case {case.id} has no engine-vocabulary label")
    return case.label


def _folder_cases(folder: str, cases_dir: Path) -> tuple[BenchmarkCase, ...]:
    set_dir = cases_dir / CaseSet.OWN.value / folder
    paths = sorted(set_dir.rglob("*.yaml")) if set_dir.is_dir() else []
    return tuple(case for path in paths for case in load_yaml_file(path))


def _runs_role_check(case: BenchmarkCase) -> bool:
    """As in the B5d replay: the role check doesn't run out of scope, and needs a labelled role."""
    label = case_label(case)
    return label.risk_class is not RiskClass.OUT_OF_SCOPE and label.role is not None


def plan_probes(cases_dir: Path = CASES_DIR) -> tuple[Probe, ...]:
    """Every probe, checks first (scope, high_risk, role), then facts on each case they use."""
    checks = (
        *(Probe(NodeName.SCOPE, c) for c in _folder_cases(CASE_FOLDERS[NodeName.SCOPE], cases_dir)),
        Probe(NodeName.HIGH_RISK, WORKED_EXAMPLE),
        *(
            Probe(NodeName.HIGH_RISK, c)
            for c in _folder_cases(CASE_FOLDERS[NodeName.HIGH_RISK], cases_dir)
        ),
        *(
            Probe(NodeName.ROLE, c)
            for c in _folder_cases(CASE_FOLDERS[NodeName.ROLE], cases_dir)
            if _runs_role_check(c)
        ),
    )
    cases = {probe.case.id: probe.case for probe in checks}
    return (*checks, *(Probe(NodeName.FACTS, case) for case in cases.values()))


def probe_state(probe: Probe) -> EngineState:
    """The state the node sees, as in its replay test. The role check also gets the class the
    label settles, as the earlier checks would have left it."""
    case = probe.case
    state: EngineState = {
        "description": case.description,
        "language": case.language,
        "law_version": LawVersion.AMENDED,
        "as_of": AS_OF,
        "answers": {},
        "exclude_source_example_ids": (),
        "facts": (),
        "steps": (),
    }
    if probe.node is not NodeName.ROLE:
        return state
    label = case_label(case)
    is_prohibited = label.risk_class is RiskClass.PROHIBITED
    settled: EngineState = {**state, "matches": (StepName.PROHIBITED,) if is_prohibited else ()}
    if label.risk_class is RiskClass.HIGH_RISK:
        is_annex_i = (label.annex_point or "").startswith("annex:I:")
        route = HighRiskRoute.ANNEX_I if is_annex_i else HighRiskRoute.ANNEX_III
        return {**settled, "high_risk_route": route}
    if label.risk_class is RiskClass.LIMITED_RISK:
        return {**settled, "transparency_duties": ("art:50:1",)}
    return settled


# --- Scoring against the label ------------------------------------------------------------------


def _tag(case: BenchmarkCase, name: str) -> list[str]:
    prefix = f"{name}:"
    return [tag.removeprefix(prefix) for tag in case.tags if tag.startswith(prefix)]


def _cited(outcome: CheckOutcome) -> list[str]:
    return [citation.provision_id for citation in outcome.step.citations]


def scope_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    """Out of scope exactly when the label is, with its status; an out-of-scope finding cites the
    provision the label rests on first (the B5b replay's rule)."""
    label = case_label(case)
    is_out = label.risk_class is RiskClass.OUT_OF_SCOPE
    if outcome.matched is not is_out or outcome.step.status is not label.status:
        return False
    return not is_out or case.label_citation[0] in _cited(outcome)


def high_risk_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    """The label's class, route, Annex point and status, and the tags' missing fact and Art. 2(2)
    note (the B5e replay's rule). The route is Annex III when the label's point is in Annex III or
    a tag says the case is on both routes, else Annex I."""
    label = case_label(case)
    step = outcome.step
    if label.risk_class is not RiskClass.HIGH_RISK:
        return (
            outcome.high_risk_route is None
            and not outcome.annex_iii_exempt
            and outcome.annex_point is None
            and step.status is label.status
        )
    is_annex_iii = (label.annex_point or "").startswith("annex:III:")
    also_iii = "annex_iii" in _tag(case, "also_route")
    expected = HighRiskRoute.ANNEX_III if is_annex_iii or also_iii else HighRiskRoute.ANNEX_I
    points = {*_tag(case, "annex_i_point"), *([label.annex_point] if label.annex_point else [])}
    asked = step.missing_fact.id if step.missing_fact else None
    section_b_decided = "b" in _tag(case, "annex_i_section") and label.status is Status.DECIDED
    names_art_2_2 = "2(2)" in step.decision or "Art. 2 Abs. 2" in step.decision
    return (
        outcome.high_risk_route is expected
        and not outcome.annex_iii_exempt
        and outcome.annex_point in points
        and step.status is label.status
        and all(asked == fact for fact in _tag(case, "missing_fact"))
        and (names_art_2_2 or not section_b_decided)
    )


def role_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    """The label's role, and its status when the label is legally ambiguous (the B5d replay's
    rule)."""
    label = case_label(case)
    if outcome.role is None or outcome.role.role is not label.role:
        return False
    return label.status is not Status.LEGALLY_AMBIGUOUS or outcome.step.status is label.status


MATCHERS: Mapping[NodeName, Callable[[CheckOutcome, BenchmarkCase], bool]] = {
    NodeName.SCOPE: scope_matches,
    NodeName.HIGH_RISK: high_risk_matches,
    NodeName.ROLE: role_matches,
}


def is_correct(probe: Probe, outcome: FactsOutcome | CheckOutcome) -> bool | None:
    """Whether a check's outcome matches the label; None for facts, which have no label."""
    if probe.node is NodeName.FACTS:
        return None
    if not isinstance(outcome, CheckOutcome):
        raise TypeError(f"the {probe.node.value} node returned {type(outcome).__name__}")
    return MATCHERS[probe.node](outcome, probe.case)


# --- Running one probe --------------------------------------------------------------------------


class UsageTracker(BaseCallbackHandler):
    """Adds up the cost (OpenRouter's `usage.cost`) and tokens of the calls of one probe."""

    def __init__(self) -> None:
        self.cost_usd = 0.0
        self.tokens = 0

    def add(self, cost_usd: float, tokens: int) -> None:
        self.cost_usd += cost_usd
        self.tokens += tokens

    def on_llm_end(self, response: LLMResult, **kwargs: object) -> None:
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                if not isinstance(message, AIMessage):
                    continue
                cost = message.response_metadata.get("cost")
                usage = message.usage_metadata
                self.add(
                    float(cost) if isinstance(cost, int | float) else 0.0,
                    usage["total_tokens"] if usage else 0,
                )


NodeRunner = Callable[[EngineState], FactsOutcome | CheckOutcome]
NodeFactory = Callable[[NodeName, Settings, UsageTracker], NodeRunner]


def arm_settings(settings: Settings, arm: ModelArm) -> Settings:
    """`settings` with the engine model and its endpoint set to the arm's."""
    return settings.model_copy(update={"engine_model": arm.model, "engine_provider": arm.provider})


def engine_node(node: NodeName, settings: Settings, tracker: UsageTracker) -> NodeRunner:
    """The engine's own node, on the settings' engine model (pinned, fallbacks off, decision 005),
    with `tracker` counting its calls. Scope and high_risk read the corpus from DATABASE_URL."""
    chat = engine_chat_model(max_tokens=MAX_OUTPUT_TOKENS[node], settings=settings)
    tracked = chat.model_copy(update={"callbacks": [tracker]})
    if node is NodeName.FACTS:
        return facts.FactExtractor(settings, chat=tracked)
    if node is NodeName.SCOPE:
        return scope.ScopeCheck(settings, chat=tracked)
    if node is NodeName.HIGH_RISK:
        return high_risk.HighRiskCheck(settings, chat=tracked)
    return role_obligations.RoleObligationsCheck(settings, chat=tracked)


BROKEN_OUTPUT_ERRORS: tuple[type[Exception], ...] = (
    facts.FactsOutputError,
    scope.ScopeOutputError,
    high_risk.HighRiskOutputError,
    role_obligations.RoleOutputError,
    ValidationError,
)
"""An answer that doesn't fit the node's schema, or a result the contract rejects."""


class ProbeKind(StrEnum):
    ANSWERED = "answered"
    BROKEN = "broken"
    FAILED = "failed"


def _error(exc: Exception) -> dict[str, JsonValue]:
    """The error's type and message, without the input values a `ValidationError` would quote."""
    text = describe_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
    return {"type": type(exc).__name__, "message": text[:ERROR_MESSAGE_LIMIT]}


def _record(
    probe: Probe,
    kind: ProbeKind,
    predicted: dict[str, JsonValue],
    correct: bool | None,
    tracker: UsageTracker,
) -> CaseRecord:
    scores: dict[str, Score] = {
        "broken": kind is ProbeKind.BROKEN,
        "failed": kind is ProbeKind.FAILED,
        "correct": correct,
        "is_error": kind is not ProbeKind.ANSWERED,
        "cost_usd": tracker.cost_usd,
        "tokens": tracker.tokens,
    }
    return CaseRecord(
        probe.probe_id,
        predicted,
        label_record(probe.case),
        scores,
        None,
        tracker.cost_usd,
        tracker.tokens,
    )


def run_probe(probe: Probe, settings: Settings, factory: NodeFactory = engine_node) -> CaseRecord:
    """Run one probe and turn its outcome into a row. A missing setting (`LLMConfigError`) is
    raised, since every other probe would fail the same way."""
    tracker = UsageTracker()
    try:
        outcome = factory(probe.node, settings, tracker)(probe_state(probe))
    except LLMConfigError:
        raise
    except BROKEN_OUTPUT_ERRORS as exc:
        correct = None if probe.node is NodeName.FACTS else False
        return _record(probe, ProbeKind.BROKEN, {"error": _error(exc)}, correct, tracker)
    except Exception as exc:
        logger.warning("probe %s got no answer: %s", probe.probe_id, type(exc).__name__)
        return _record(probe, ProbeKind.FAILED, {"error": _error(exc)}, None, tracker)
    answer = outcome.model_dump(mode="json")
    return _record(probe, ProbeKind.ANSWERED, answer, is_correct(probe, outcome), tracker)


# --- Running one model --------------------------------------------------------------------------


class RunStatus(StrEnum):
    COMPLETED = "completed"
    COST_CAP_REACHED = "cost_cap_reached"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class ArmRun:
    """What one model's run recorded."""

    arm: ModelArm
    run_id: UUID
    status: RunStatus
    probes_planned: int
    probes_recorded: int
    cost_usd: float
    tokens: int


def run_config(
    arm: ModelArm,
    settings: Settings,
    probes: Sequence[Probe],
    max_cost_usd: float,
    is_git_dirty: bool,
) -> dict[str, JsonValue]:
    """`eval_runs.config`: the model and endpoint, and what the probes cover."""
    return {
        "model": arm.model,
        "provider": arm.provider,
        "embedding": settings.embedding_model,
        "retrieval": "engine nodes: get_provision and search_ai_act (E3, E5)",
        "classifier": "smoke",
        "experiment": EXPERIMENT,
        "arm": arm.name,
        "nodes": [node.value for node in NodeName if any(p.node is node for p in probes)],
        "probes": len(probes),
        "max_cost_usd": max_cost_usd,
        "git_dirty": is_git_dirty,
        "outcome": {"status": "running"},
    }


def _batches(probes: Sequence[Probe], size: int) -> list[Sequence[Probe]]:
    return [probes[start : start + size] for start in range(0, len(probes), size)]


def run_arm(
    arm: ModelArm,
    probes: Sequence[Probe],
    store: RunStore,
    settings: Settings,
    git_state: tuple[str, bool],
    *,
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
    concurrency: int = DEFAULT_CONCURRENCY,
    factory: NodeFactory = engine_node,
) -> ArmRun:
    """Run every probe on `arm` and store one row each. Probes run `concurrency` at a time; no new
    batch starts once `max_cost_usd` is spent, so a run overshoots by at most one batch."""
    git_sha, is_git_dirty = git_state
    model_settings = arm_settings(settings, arm)
    config = run_config(arm, settings, probes, max_cost_usd, is_git_dirty)
    run_id = store.start_run(git_sha, BENCHMARK, config)
    recorded, cost_usd, tokens = 0, 0.0, 0
    status = RunStatus.COMPLETED
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for batch in _batches(probes, concurrency):
                if cost_usd >= max_cost_usd:
                    status = RunStatus.COST_CAP_REACHED
                    break
                for record in pool.map(lambda p: run_probe(p, model_settings, factory), batch):
                    store.add_case(run_id, record)
                    recorded, cost_usd = recorded + 1, cost_usd + record.cost_usd
                    tokens += record.tokens
    except BaseException:
        store.finish_run(run_id, _outcome(RunStatus.INTERRUPTED, len(probes), recorded))
        raise
    store.finish_run(run_id, _outcome(status, len(probes), recorded))
    return ArmRun(arm, run_id, status, len(probes), recorded, cost_usd, tokens)


def _outcome(status: RunStatus, planned: int, recorded: int) -> dict[str, JsonValue]:
    return {
        "status": status.value,
        "finished_at": datetime.now(UTC).isoformat(),
        "probes_planned": planned,
        "probes_recorded": recorded,
    }


# --- The verdict --------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProbeScore:
    """One stored probe row, as the verdict reads it."""

    probe_id: str
    kind: ProbeKind
    correct: bool | None

    @property
    def node(self) -> NodeName:
        return NodeName(self.probe_id.split(":", 1)[0])


def probe_score(probe_id: str, scores: Mapping[str, JsonValue]) -> ProbeScore:
    """Read a stored row's scores; a row that isn't a smoke probe raises `ValueError`."""
    NodeName(probe_id.split(":", 1)[0])
    broken, failed, correct = scores.get("broken"), scores.get("failed"), scores.get("correct")
    if not isinstance(broken, bool) or not isinstance(failed, bool):
        raise ValueError(f"row {probe_id} has no broken/failed flags; not a smoke probe")
    if correct is not None and not isinstance(correct, bool):
        raise ValueError(f"row {probe_id} has a non-boolean correct score")
    kind = ProbeKind.FAILED if failed else ProbeKind.BROKEN if broken else ProbeKind.ANSWERED
    return ProbeScore(probe_id, kind, correct)


@dataclass(frozen=True)
class ArmSummary:
    """One model's counts over the planned probes; a probe it has no row for counts as failed."""

    name: str
    planned: int
    answered: int
    broken: int
    failed: int
    broken_by_node: Mapping[str, int]

    @property
    def replied(self) -> int:
        """Probes where the model gave an answer, fitting or broken."""
        return self.answered + self.broken


def summarize(name: str, scores: Sequence[ProbeScore], planned: Sequence[str]) -> ArmSummary:
    by_id = {score.probe_id: score for score in scores}
    kinds = [by_id[pid].kind if pid in by_id else ProbeKind.FAILED for pid in planned]
    broken_by_node: dict[str, int] = {}
    for score in scores:
        if score.kind is ProbeKind.BROKEN:
            broken_by_node[score.node.value] = broken_by_node.get(score.node.value, 0) + 1
    return ArmSummary(
        name=name,
        planned=len(planned),
        answered=kinds.count(ProbeKind.ANSWERED),
        broken=kinds.count(ProbeKind.BROKEN),
        failed=kinds.count(ProbeKind.FAILED),
        broken_by_node=broken_by_node,
    )


class Verdict(StrEnum):
    KEEP_LUNA = "keep_luna"
    DROP_LUNA = "drop_luna"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Comparison:
    """Both models' counts, their accuracy on the same scored probes, and the rule's verdict."""

    luna: ArmSummary
    gemini: ArmSummary
    scored: int
    """Labelled probes both models replied to (a broken answer counts as wrong)."""
    luna_correct: int
    gemini_correct: int
    verdict: Verdict
    reasons: tuple[str, ...]

    @property
    def luna_accuracy(self) -> float | None:
        return self.luna_correct / self.scored if self.scored else None

    @property
    def gemini_accuracy(self) -> float | None:
        return self.gemini_correct / self.scored if self.scored else None


def _exceeds(count: int, total: int, limit: tuple[int, int]) -> bool:
    """`count / total > numerator / denominator`, in integers so 10% is exact."""
    numerator, denominator = limit
    return count * denominator > total * numerator


def compare(luna: Sequence[ProbeScore], gemini: Sequence[ProbeScore]) -> Comparison:
    """Apply decision 023's rule to the two runs' stored probes."""
    planned = sorted({score.probe_id for score in (*luna, *gemini)})
    luna_summary = summarize(LUNA.name, luna, planned)
    gemini_summary = summarize(GEMINI.name, gemini, planned)
    luna_by_id = {s.probe_id: s for s in luna if s.kind is not ProbeKind.FAILED}
    gemini_by_id = {s.probe_id: s for s in gemini if s.kind is not ProbeKind.FAILED}
    common = [
        pid
        for pid in planned
        if pid in luna_by_id
        and pid in gemini_by_id
        and luna_by_id[pid].correct is not None
        and gemini_by_id[pid].correct is not None
    ]
    luna_correct = sum(luna_by_id[pid].correct is True for pid in common)
    gemini_correct = sum(gemini_by_id[pid].correct is True for pid in common)
    verdict, reasons = _verdict(
        luna_summary, gemini_summary, len(common), luna_correct, gemini_correct
    )
    return Comparison(
        luna_summary, gemini_summary, len(common), luna_correct, gemini_correct, verdict, reasons
    )


def _verdict(
    luna: ArmSummary, gemini: ArmSummary, scored: int, luna_correct: int, gemini_correct: int
) -> tuple[Verdict, tuple[str, ...]]:
    unusable = [
        f"{arm.name}: {arm.failed} of {arm.planned} probes got no answer"
        for arm in (luna, gemini)
        if arm.replied == 0 or _exceeds(arm.failed, arm.planned, FAILED_SHARE_LIMIT)
    ]
    if unusable or scored == 0:
        return Verdict.INCONCLUSIVE, (
            *unusable,
            *(["no probe scored for both"] if not scored else []),
        )
    reasons: list[str] = []
    if _exceeds(luna.broken, luna.replied, BROKEN_SHARE_LIMIT):
        reasons.append(f"luna: {luna.broken} of {luna.replied} answers broken, more than 10%")
    numerator, denominator = ACCURACY_GAP_LIMIT
    if (gemini_correct - luna_correct) * denominator >= scored * numerator:
        reasons.append(
            f"luna: {luna_correct}/{scored} correct, 10 or more points below gemini's "
            f"{gemini_correct}/{scored}"
        )
    return (Verdict.DROP_LUNA if reasons else Verdict.KEEP_LUNA), tuple(reasons)


# --- Reading stored runs ------------------------------------------------------------------------


class SmokeRunError(LookupError):
    """A run id that isn't a stored smoke run."""


def load_run(connection: psycopg.Connection, run_id: UUID) -> tuple[str, tuple[ProbeScore, ...]]:
    """A stored smoke run's arm name and probe scores."""
    row = connection.execute(
        "select config->>'experiment', config->>'arm' from eval_runs where id = %s", (run_id,)
    ).fetchone()
    if row is None:
        raise SmokeRunError(f"no run {run_id} in eval_runs")
    experiment, arm = row
    if experiment != EXPERIMENT or arm not in ARMS:
        raise SmokeRunError(f"run {run_id} is not an {EXPERIMENT} run")
    rows = connection.execute(
        "select case_id, scores from eval_case_results where run_id = %s order by case_id",
        (run_id,),
    ).fetchall()
    return arm, tuple(probe_score(case_id, scores) for case_id, scores in rows)


# --- The dry run and the printed report ---------------------------------------------------------


def estimate_cost(probes: Sequence[Probe], arm: ModelArm) -> float:
    """What the probes cost on `arm` at cold (uncached) prices, from `TYPICAL_TOKENS`."""
    per_million = 1_000_000
    return sum(
        TYPICAL_TOKENS[probe.node].prompt * arm.input_usd_per_m / per_million
        + TYPICAL_TOKENS[probe.node].completion * arm.output_usd_per_m / per_million
        for probe in probes
    )


def format_plan(probes: Sequence[Probe], arms: Sequence[ModelArm]) -> str:
    """The dry run: probes per node, and the estimated cost per model."""
    counts = {node: sum(p.node is node for p in probes) for node in NodeName}
    cases = len({probe.case.id for probe in probes})
    lines = [f"{len(probes)} probes on {cases} cases (no model call made)"]
    lines += [f"  {node.value}: {count}" for node, count in counts.items()]
    estimates = [(arm, estimate_cost(probes, arm)) for arm in arms]
    lines += [
        f"  {arm.name} ({arm.model} @ {arm.provider}): ~${cost:.3f}" for arm, cost in estimates
    ]
    lines.append(f"  total: ~${sum(cost for _, cost in estimates):.3f} (cold prices, upper bound)")
    return "\n".join(lines)


def _share(count: int, total: int) -> str:
    return f"{count}/{total} ({100 * count / total:.1f}%)" if total else f"{count}/0"


def format_comparison(comparison: Comparison, run_ids: Mapping[str, UUID]) -> str:
    """The comparison as a markdown table, for decision 004."""
    rows = [
        "| Model | Run id | Broken answers | No answer | Accuracy (same probes) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for arm, correct in (
        (comparison.luna, comparison.luna_correct),
        (comparison.gemini, comparison.gemini_correct),
    ):
        by_node = ", ".join(f"{node} {n}" for node, n in sorted(arm.broken_by_node.items()))
        broken = _share(arm.broken, arm.replied) + (f": {by_node}" if by_node else "")
        rows.append(
            f"| {ARMS[arm.name].model} | {run_ids.get(arm.name, '-')} | {broken} | "
            f"{_share(arm.failed, arm.planned)} | {_share(correct, comparison.scored)} |"
        )
    rows.append("")
    rows.append(f"Verdict: {comparison.verdict.value}")
    rows += [f"- {reason}" for reason in comparison.reasons]
    return "\n".join(rows)
