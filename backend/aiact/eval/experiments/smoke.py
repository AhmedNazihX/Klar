"""The engine model smoke test: GPT-6 Luna against Gemini 3.1 Flash-Lite on the staged nodes (X2;
INIT > Engine safety net; decision 023). This module plans and runs the probes; the verdict over
the stored runs is in `smoke_verdict`.

Each model runs the merged engine nodes on the approved own cases, one probe per node and case:
- facts (E2) on every case below, for broken outputs only (facts have no label to score);
- scope (E3) on the B5b cases (`own/b`);
- high_risk (E5) on INIT's worked example and the B5e cases (`own/e`);
- role_obligations (E7) on the B5d cases (`own/d`) whose label names a role.

Every check probe gets its replay test's state and is scored with the same rules
(`matchers`, which the replay tests import too), so a model's accuracy here can be checked against
the committed Luna recordings. The node code, prompts and retrieval are the engine's own; only the
model and its pinned endpoint change, and the model makes no retries, so every billed attempt is
one the probe counts.

A probe's outcome is one of three:
- **broken**: the model answered, but the answer doesn't fit the node's schema or the result
  contract (the node's `*OutputError`, or a `ValidationError` from the contract: cross-field rules
  aren't in the JSON Schema, decision 010 addendum). A reply cut off by the output cap is broken
  too (E5: Luna's reasoning ran out at 3000 tokens). The nodes make no tool calls: retrieval is
  code, and structured output is the model's only interface.
- **failed**: no usable answer came back: a transport, provider or database error, or a reply
  that isn't shown to come from the pinned provider (OpenRouter's generation record, `generations`:
  another provider, no generation id, or a record that can't be read), or a call that ended with
  `finish_reason: "error"` (the provider broke off mid-reply: seen on Gemini on 2026-10-01, a cut
  JSON at $0 cost). Not counted as broken or wrong, but too many of them make the comparison
  inconclusive (decision 023 addendum).
- **answered**: scored against the label (facts: not scored).

Any other error (a missing setting, a bug, a provision the corpus lacks) stops the run. Neither
check lets the model name a provision (scope cites fixed rules, high_risk picks from the retrieved
points), so a missing provision is a corpus gap, never the model's fault.
Each model's run is one `eval_runs` row (`config.experiment` = `x2_engine_smoke`) with one
`eval_case_results` row per probe (`case_id` = `<node>:<case id>`). Cost is OpenRouter's
`usage.cost` per call, or the token-price estimate when it's missing, or the probe's worst case
when the usage is missing too; embedding calls for
retrieval are not counted (a few hundred tokens per search at $0.01/M, the same for both models).
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

import httpx
import psycopg
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult
from openrouter.errors import NoResponseError, OpenRouterError
from pydantic import JsonValue, ValidationError

from aiact.engine.nodes import facts, high_risk, role_obligations, scope
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import (
    WORKED_EXAMPLE,
    high_risk_matches,
    replay_state,
    role_check_state,
    role_matches,
    runs_role_check,
    scope_matches,
)
from aiact.eval.runner import CaseRecord, RunStore, Score, label_record
from aiact.llm import EmbeddingError, engine_chat_model
from aiact.llm.generations import GenerationLookup, GenerationLookupError
from aiact.llm.structured import describe_validation_error
from aiact.settings import Settings

logger = logging.getLogger(__name__)

EXPERIMENT = "x2_engine_smoke"
"""`eval_runs.config.experiment` of every smoke run; the verdict refuses other runs."""
BENCHMARK = CaseSet.OWN.value

DEFAULT_MAX_COST_USD = 0.5
"""The spending cap per model; the dry-run estimate for both models together is about $0.38."""
DEFAULT_CONCURRENCY = 4
ERROR_MESSAGE_LIMIT = 300
AS_OF = date(2026, 9, 30)
"""The date the probes ask about, as in the high-risk and scope replays."""
MODEL_RETRIES = 0
"""No silent retries: a retried call would be billed without the probe seeing it."""
PER_MILLION = 1_000_000


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
    """One model under test: its OpenRouter slug, its pinned EU ZDR endpoint, the provider name
    OpenRouter's generation record gives for that endpoint, and its prices in USD per million
    tokens there (decision 005)."""

    name: str
    model: str
    provider: str
    served_by: str
    input_usd_per_m: float
    output_usd_per_m: float

    def price(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens * self.input_usd_per_m + completion_tokens * self.output_usd_per_m
        ) / PER_MILLION


LUNA = ModelArm("luna", "openai/gpt-6-luna-20260922", "azure/eu", "Azure", 0.11, 0.55)
GEMINI = ModelArm(
    "gemini", "google/gemini-3.1-flash-lite", "google-vertex/eu", "Google", 0.275, 1.65
)
ARMS: Mapping[str, ModelArm] = {arm.name: arm for arm in (LUNA, GEMINI)}


@dataclass(frozen=True)
class NodeTokens:
    prompt: int
    completion: int
    max_prompt: int


TYPICAL_TOKENS: Mapping[NodeName, NodeTokens] = {
    NodeName.FACTS: NodeTokens(prompt=1582, completion=1800, max_prompt=1587),
    NodeName.SCOPE: NodeTokens(prompt=4096, completion=1523, max_prompt=4433),
    NodeName.HIGH_RISK: NodeTokens(prompt=7972, completion=1017, max_prompt=8744),
    NodeName.ROLE: NodeTokens(prompt=1958, completion=1452, max_prompt=2194),
}
"""Mean (and largest) tokens of one call, from the committed Luna recordings of each node's
replay tests (47 calls, $0.052 in total). Completion tokens include Luna's reasoning, so for
Gemini, which doesn't reason, the estimate is an upper bound. The role figures are C7b's
recordings: its high-risk requests carry the Art. 111(2) section, at about 2,170 prompt and up to
2,206 completion tokens of the node's 3,000 cap."""

PROMPT_MARGIN = 1.5
"""The worst-case prompt is the largest recorded one times this (longer descriptions)."""


def estimate_cost(probes: Sequence["Probe"], arm: ModelArm) -> float:
    """What the probes cost on `arm` at cold (uncached) prices, from `TYPICAL_TOKENS`."""
    return sum(
        arm.price(TYPICAL_TOKENS[p.node].prompt, TYPICAL_TOKENS[p.node].completion) for p in probes
    )


def worst_case_cost(node: NodeName, arm: ModelArm) -> float:
    """The most one probe can cost: its node makes one call, with no retries, of at most the
    worst-case prompt and the full output cap."""
    prompt = round(TYPICAL_TOKENS[node].max_prompt * PROMPT_MARGIN)
    return arm.price(prompt, MAX_OUTPUT_TOKENS[node])


# --- The probes ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Probe:
    """One node run on one case."""

    node: NodeName
    case: BenchmarkCase

    @property
    def probe_id(self) -> str:
        return f"{self.node.value}:{self.case.id}"


def _folder_cases(node: NodeName, cases_dir: Path) -> tuple[BenchmarkCase, ...]:
    set_dir = cases_dir / CaseSet.OWN.value / CASE_FOLDERS[node]
    paths = sorted(set_dir.rglob("*.yaml")) if set_dir.is_dir() else []
    return tuple(case for path in paths for case in load_yaml_file(path))


def plan_probes(cases_dir: Path = CASES_DIR) -> tuple[Probe, ...]:
    """Every probe, checks first (scope, high_risk, role), then facts on each case they use."""
    role_cases = (c for c in _folder_cases(NodeName.ROLE, cases_dir) if runs_role_check(c))
    checks = (
        *(Probe(NodeName.SCOPE, c) for c in _folder_cases(NodeName.SCOPE, cases_dir)),
        Probe(NodeName.HIGH_RISK, WORKED_EXAMPLE),
        *(Probe(NodeName.HIGH_RISK, c) for c in _folder_cases(NodeName.HIGH_RISK, cases_dir)),
        *(Probe(NodeName.ROLE, c) for c in role_cases),
    )
    cases = {probe.case.id: probe.case for probe in checks}
    return (*checks, *(Probe(NodeName.FACTS, case) for case in cases.values()))


def probe_state(probe: Probe) -> EngineState:
    """The state the node sees, as in its replay test."""
    if probe.node is NodeName.ROLE:
        return role_check_state(probe.case, AS_OF)
    return replay_state(probe.case, AS_OF)


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
    """The calls of one probe: their cost (OpenRouter's `usage.cost`; the arm's token prices when
    it's missing; the node's worst case when the usage is missing too), tokens and generation
    ids."""

    def __init__(self, arm: ModelArm, node: NodeName) -> None:
        self.arm = arm
        self.node = node
        self.calls = 0
        self.cost_usd = 0.0
        self.tokens = 0
        self.is_cost_estimated = False
        self.generation_ids: list[str] = []
        self.finish_reasons: list[str] = []

    def add(self, cost_usd: float, tokens: int) -> None:
        self.calls += 1
        self.cost_usd += cost_usd
        self.tokens += tokens

    def on_llm_end(self, response: LLMResult, **kwargs: object) -> None:
        generation_id = (response.llm_output or {}).get("id")
        if isinstance(generation_id, str):
            self.generation_ids.append(generation_id)
        for generations in response.generations:
            for generation in generations:
                finish_reason = (generation.generation_info or {}).get("finish_reason")
                if isinstance(finish_reason, str):
                    self.finish_reasons.append(finish_reason)
                message = getattr(generation, "message", None)
                if isinstance(message, AIMessage):
                    self.add(*self._usage(message))

    @property
    def has_provider_error(self) -> bool:
        """A call the provider ended with an error instead of a finished reply."""
        return PROVIDER_ERROR_FINISH in self.finish_reasons

    def _usage(self, message: AIMessage) -> tuple[float, int]:
        usage = message.usage_metadata
        prompt, completion = (usage["input_tokens"], usage["output_tokens"]) if usage else (0, 0)
        cost = message.response_metadata.get("cost")
        if isinstance(cost, int | float):
            return float(cost), prompt + completion
        self.is_cost_estimated = True
        if usage is None:
            return worst_case_cost(self.node, self.arm), 0
        return self.arm.price(prompt, completion), prompt + completion


NodeRunner = Callable[[EngineState], FactsOutcome | CheckOutcome]
NodeFactory = Callable[[NodeName, Settings, UsageTracker], NodeRunner]
ServedBy = Callable[[str], str]
"""Generation id to the name of the provider that served it."""


def arm_settings(settings: Settings, arm: ModelArm) -> Settings:
    """`settings` with the engine model and its endpoint set to the arm's."""
    return settings.model_copy(update={"engine_model": arm.model, "engine_provider": arm.provider})


def engine_node(node: NodeName, settings: Settings, tracker: UsageTracker) -> NodeRunner:
    """The engine's own node on the settings' engine model (pinned, fallbacks off, decision 005),
    without retries and with `tracker` counting its calls. Scope and high_risk read the corpus
    from DATABASE_URL."""
    chat = engine_chat_model(
        max_tokens=MAX_OUTPUT_TOKENS[node], max_retries=MODEL_RETRIES, settings=settings
    ).model_copy(update={"callbacks": [tracker]})
    if node is NodeName.FACTS:
        return facts.FactExtractor(settings, chat=chat)
    if node is NodeName.SCOPE:
        return scope.ScopeCheck(settings, chat=chat)
    if node is NodeName.HIGH_RISK:
        return high_risk.HighRiskCheck(settings, chat=chat)
    return role_obligations.RoleObligationsCheck(settings, chat=chat)


BROKEN_OUTPUT_ERRORS: tuple[type[Exception], ...] = (
    facts.FactsOutputError,
    scope.ScopeOutputError,
    high_risk.HighRiskOutputError,
    role_obligations.RoleOutputError,
    ValidationError,
)
"""An answer that doesn't fit the node's schema, or a result the contract rejects."""

NO_ANSWER_ERRORS: tuple[type[Exception], ...] = (
    OpenRouterError,
    NoResponseError,
    httpx.HTTPError,
    psycopg.Error,
    EmbeddingError,
)
"""Transport, provider and database errors: the call never produced an answer."""
PROVIDER_ERROR_FINISH = "error"
"""OpenRouter's `finish_reason` for a reply the provider broke off; its text is cut, not the
model's answer."""
PROVIDER_ERROR_PREFIXES = ("OpenRouter API returned",)
"""ChatOpenRouter raises a plain `ValueError` with this text for an error in the response body."""


def is_no_answer(exc: Exception) -> bool:
    if isinstance(exc, NO_ANSWER_ERRORS):
        return True
    return isinstance(exc, ValueError) and str(exc).startswith(PROVIDER_ERROR_PREFIXES)


class ProbeKind(StrEnum):
    ANSWERED = "answered"
    BROKEN = "broken"
    FAILED = "failed"


def _error(exc: Exception) -> dict[str, JsonValue]:
    """The error's type and message, without the input values a `ValidationError` would quote."""
    text = describe_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
    return {"type": type(exc).__name__, "message": text[:ERROR_MESSAGE_LIMIT]}


@dataclass(frozen=True)
class _Ran:
    kind: ProbeKind
    predicted: dict[str, JsonValue]
    correct: bool | None


def _run_node(probe: Probe, node: NodeRunner, state: EngineState) -> _Ran:
    try:
        outcome = node(state)
    except Exception as exc:
        if isinstance(exc, BROKEN_OUTPUT_ERRORS):
            correct = None if probe.node is NodeName.FACTS else False
            return _Ran(ProbeKind.BROKEN, {"error": _error(exc)}, correct)
        if not is_no_answer(exc):
            raise
        logger.warning("probe %s got no answer: %s", probe.probe_id, type(exc).__name__)
        return _Ran(ProbeKind.FAILED, {"error": _error(exc)}, None)
    return _Ran(ProbeKind.ANSWERED, outcome.model_dump(mode="json"), is_correct(probe, outcome))


@dataclass(frozen=True)
class _Served:
    """Who served the probe's calls. `as_pinned` is True when every call is shown to come from
    the pinned provider, False when one is shown to come from another, and None when unknown;
    `not_counted` says why a reply can't count."""

    providers: tuple[str, ...] = ()
    as_pinned: bool | None = None
    not_counted: str | None = None


def _served(tracker: UsageTracker, has_reply: bool, served_by: ServedBy) -> _Served:
    if not tracker.generation_ids:
        return _Served(not_counted="the reply carries no generation id") if has_reply else _Served()
    try:
        names = tuple(served_by(generation_id) for generation_id in tracker.generation_ids)
    except GenerationLookupError as exc:
        return _Served(not_counted=str(exc))
    others = sorted({name for name in names if name != tracker.arm.served_by})
    if others:
        reason = f"served by {', '.join(others)}, not {tracker.arm.served_by}"
        return _Served(names, as_pinned=False, not_counted=reason)
    return _Served(names, as_pinned=True)


def run_probe(
    probe: Probe,
    arm: ModelArm,
    settings: Settings,
    served_by: ServedBy,
    factory: NodeFactory = engine_node,
) -> CaseRecord:
    """Run one probe on `arm` and turn its outcome into a row. Errors outside the three outcomes
    (a missing setting, a bug) are raised, since every other probe would hit them too."""
    state = probe_state(probe)
    tracker = UsageTracker(arm, probe.node)
    node = factory(probe.node, arm_settings(settings, arm), tracker)
    ran = _run_node(probe, node, state)
    if tracker.has_provider_error and ran.kind is not ProbeKind.FAILED:
        error = "a call ended with finish_reason error: the provider broke off the reply"
        ran = _Ran(ProbeKind.FAILED, {**ran.predicted, "provider_error": error}, None)
    served = _served(tracker, ran.kind is not ProbeKind.FAILED or tracker.calls > 0, served_by)
    if served.not_counted is not None:
        ran = _Ran(ProbeKind.FAILED, {**ran.predicted, "not_pinned": served.not_counted}, None)
    smoke_info: dict[str, JsonValue] = {
        "served_by": list(served.providers),
        "generation_ids": list(tracker.generation_ids),
        "cost_is_estimated": tracker.is_cost_estimated,
    }
    scores: dict[str, Score] = {
        "broken": ran.kind is ProbeKind.BROKEN,
        "failed": ran.kind is ProbeKind.FAILED,
        "correct": ran.correct,
        "served_as_pinned": served.as_pinned,
        "is_error": ran.kind is not ProbeKind.ANSWERED,
        "cost_usd": tracker.cost_usd,
        "tokens": tracker.tokens,
    }
    return CaseRecord(
        probe.probe_id,
        {**ran.predicted, "smoke": smoke_info},
        label_record(probe.case),
        scores,
        None,
        tracker.cost_usd,
        tracker.tokens,
    )


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
        "served_by": arm.served_by,
        "embedding": settings.embedding_model,
        "retrieval": "engine nodes: get_provision and search_ai_act (E3, E5)",
        "classifier": "smoke",
        "experiment": EXPERIMENT,
        "arm": arm.name,
        "nodes": [node.value for node in NodeName if any(p.node is node for p in probes)],
        "probes": len(probes),
        "max_cost_usd": max_cost_usd,
        "max_retries": MODEL_RETRIES,
        "git_dirty": is_git_dirty,
        "outcome": {"status": "running"},
    }


class _Tally:
    """Spend and rows of one run, kept by the thread that records them."""

    def __init__(self, store: RunStore, run_id: UUID) -> None:
        self.store = store
        self.run_id = run_id
        self.recorded = 0
        self.cost_usd = 0.0
        self.tokens = 0

    def record(self, record: CaseRecord) -> None:
        self.store.add_case(self.run_id, record)
        self.recorded += 1
        self.cost_usd += record.cost_usd
        self.tokens += record.tokens


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
    served_by: ServedBy | None = None,
) -> ArmRun:
    """Run every probe on `arm` and store one row each, `concurrency` at a time. A probe starts
    only while what is spent, plus the worst case of every probe in flight and of this one, stays
    within `max_cost_usd`. `served_by` defaults to OpenRouter's generation records."""
    git_sha, is_git_dirty = git_state
    lookup = served_by or GenerationLookup(settings).served_by
    config = run_config(arm, settings, probes, max_cost_usd, is_git_dirty)
    tally = _Tally(store, store.start_run(git_sha, BENCHMARK, config))
    try:
        started = _run_all(probes, arm, settings, lookup, factory, tally, max_cost_usd, concurrency)
    except BaseException:
        store.finish_run(tally.run_id, _outcome(RunStatus.INTERRUPTED, len(probes), tally))
        raise
    status = RunStatus.COMPLETED if started == len(probes) else RunStatus.COST_CAP_REACHED
    store.finish_run(tally.run_id, _outcome(status, len(probes), tally))
    return ArmRun(
        arm, tally.run_id, status, len(probes), tally.recorded, tally.cost_usd, tally.tokens
    )


def _run_all(
    probes: Sequence[Probe],
    arm: ModelArm,
    settings: Settings,
    served_by: ServedBy,
    factory: NodeFactory,
    tally: _Tally,
    max_cost_usd: float,
    concurrency: int,
) -> int:
    """Run the probes under the cap; returns how many were started. On an error, the probes in
    flight are recorded before it is raised, so the stored spend stays complete."""
    started = 0
    pending: dict[Future[CaseRecord], float] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        try:
            while True:
                while started < len(probes) and len(pending) < concurrency:
                    probe = probes[started]
                    worst = worst_case_cost(probe.node, arm)
                    if tally.cost_usd + sum(pending.values()) + worst > max_cost_usd:
                        break
                    future = pool.submit(run_probe, probe, arm, settings, served_by, factory)
                    pending[future] = worst
                    started += 1
                if not pending:
                    return started
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    del pending[future]
                    tally.record(future.result())
        except BaseException:
            _drain(pending, tally)
            raise


def _drain(pending: Mapping[Future[CaseRecord], float], tally: _Tally) -> None:
    for future in tuple(pending):
        try:
            tally.record(future.result())
        except Exception as exc:
            logger.warning("could not record a probe in flight: %s", type(exc).__name__)


def _outcome(status: RunStatus, planned: int, tally: _Tally) -> dict[str, JsonValue]:
    return {
        "status": status.value,
        "finished_at": datetime.now(UTC).isoformat(),
        "probes_planned": planned,
        "probes_recorded": tally.recorded,
    }


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
