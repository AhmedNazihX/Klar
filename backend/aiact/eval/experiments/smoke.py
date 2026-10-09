"""The engine model smoke test: GPT-6 Luna against Gemini 3.1 Flash-Lite on the staged nodes (X2;
INIT > Engine safety net; decision 023). This module plans and runs the probes; the verdict over
the stored runs is in `smoke_verdict`.

Each model runs the merged engine nodes on the approved own cases, one probe per node and case:
- facts (E2) on every case below, for broken outputs only (facts have no label to score);
- scope (E3) on the B5b cases (`own/b`);
- high_risk (E5) on INIT's worked example and the B5e cases (`own/e`);
- role_obligations (E7) on the B5d cases (`own/d`) whose label names a role.
X2's plan is these four (`X2_NODES`). X2b (refused requests) adds prohibited (E4) on the B5c
cases (`own/c`) and transparency (E6) on the B5a cases (`own/a`), and narrows a run to some
nodes and cases (`plan_probes(nodes=…, case_ids=…)`).

Every check probe gets its replay test's state and is scored with the same rules
(`matchers`, which the replay tests import too), so a model's accuracy here can be checked against
the committed Luna recordings. The node code, prompts and retrieval are the engine's own; only the
model and its pinned endpoint change, and the model makes no retries, so every billed attempt is
one the probe counts.

A probe's outcome is one of four:
- **broken**: the model answered, but the answer doesn't fit the node's schema or the result
  contract (the node's `*OutputError`, or a `ValidationError` from the contract: cross-field rules
  aren't in the JSON Schema, decision 010 addendum). A reply cut off by the output cap
  (`finish_reason: "length"`) is broken too (E5: Luna's reasoning ran out at 3000 tokens). The
  nodes make no tool calls: retrieval is code, and structured output is the model's only
  interface.
- **failed**: no usable answer came back: a transport, provider or database error, or a reply
  that isn't shown to come from the pinned provider (OpenRouter's generation record, `generations`:
  another provider, no generation id, or a record that can't be read), or a call that ended with
  `finish_reason: "error"` (the provider broke off mid-reply: seen on Gemini on 2026-10-01, a cut
  JSON at $0 cost; decision 023 addendum, part 7), and isn't looked up in the generation records.
  Not counted as broken or wrong, but too many of them make the comparison inconclusive (parts
  4-6). Every probe stores each call's cost, finish reason and native finish reason.
- **refused**: the provider's content filter refused the call with no parseable answer: the
  node returned its refusal outcome (decisions 029, 030). Not scored, and not broken.
- **answered**: scored against the label (facts: not scored).

A generation record that doesn't show up within the lookup's ~18 s window (or whose lookup fails
in transport or with a 5xx) doesn't fail the probe during the run: OpenRouter writes records
later under a real run's load. The probe is stored "pending verification"
(`scores.pending_verification`), with its kind and correctness kept, and once every probe has
run, the pending records are looked up again with a much longer window
(`generations.DEFERRED_BUDGET_SECONDS` for the whole run) before the run is marked finished.
Confirmed on the pinned provider, the probe keeps its score; another provider, or still no
record, and it fails as above (`predicted.smoke.deferred_check` says which). `smoke_recheck` does
the same for runs stored before this check existed.

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
from typing import Protocol
from uuid import UUID

import httpx
import psycopg
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import Generation, LLMResult
from openrouter.errors import NoResponseError, OpenRouterError
from pydantic import JsonValue, ValidationError

from aiact.engine.nodes import facts, high_risk, prohibited, role_obligations, scope, transparency
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import (
    WORKED_EXAMPLE,
    high_risk_matches,
    prohibited_matches,
    replay_state,
    role_check_state,
    role_matches,
    runs_role_check,
    scope_matches,
    transparency_matches,
)
from aiact.eval.experiments.smoke_served import (
    Served,
    ServedBy,
    VerifyAll,
    judge,
    pending_ids,
    settle,
    settle_pending,
)
from aiact.eval.runner import CaseRecord, RunStore, Score, label_record
from aiact.llm import EmbeddingError, engine_chat_model
from aiact.llm.generations import GenerationLookup, GenerationLookupError, GenerationPendingError
from aiact.llm.structured import describe_validation_error
from aiact.schemas import PROVIDER_REFUSAL
from aiact.settings import Settings

logger = logging.getLogger(__name__)

EXPERIMENT = "x2_engine_smoke"
"""`eval_runs.config.experiment` of every smoke run; the verdict refuses other runs."""
BENCHMARK = CaseSet.OWN.value

DEFAULT_MAX_COST_USD = 0.5
"""The spending cap per model. X2's dry-run estimate for both models together was about $0.38;
X2b's smaller runs print their own (`aiact evaluate smoke --dry-run`)."""
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
    PROHIBITED = "prohibited"
    HIGH_RISK = "high_risk"
    TRANSPARENCY = "transparency"
    ROLE = "role_obligations"


X2_NODES = (NodeName.FACTS, NodeName.SCOPE, NodeName.HIGH_RISK, NodeName.ROLE)
"""The nodes X2's plan probes (decision 023), the default."""
CHECK_ORDER = (
    NodeName.SCOPE,
    NodeName.PROHIBITED,
    NodeName.HIGH_RISK,
    NodeName.TRANSPARENCY,
    NodeName.ROLE,
)
"""The checks in the engine's order, as a plan lists them."""

CASE_FOLDERS: Mapping[NodeName, str] = {
    NodeName.SCOPE: "b",
    NodeName.PROHIBITED: "c",
    NodeName.ROLE: "d",
    NodeName.HIGH_RISK: "e",
    NodeName.TRANSPARENCY: "a",
}
"""The own-case folder (`eval/cases/own/<folder>`) each check is probed on."""
THIN_FOLDER = "thin"
"""The own cases too thin to start the checks (E13): only the facts node runs on them."""

MAX_OUTPUT_TOKENS: Mapping[NodeName, int] = {
    NodeName.FACTS: facts.MAX_OUTPUT_TOKENS,
    NodeName.SCOPE: scope.MAX_OUTPUT_TOKENS,
    NodeName.PROHIBITED: prohibited.MAX_OUTPUT_TOKENS,
    NodeName.HIGH_RISK: high_risk.MAX_OUTPUT_TOKENS,
    NodeName.TRANSPARENCY: transparency.MAX_OUTPUT_TOKENS,
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
    NodeName.FACTS: NodeTokens(prompt=2489, completion=2382, max_prompt=2550),
    NodeName.SCOPE: NodeTokens(prompt=4096, completion=1523, max_prompt=4433),
    NodeName.HIGH_RISK: NodeTokens(prompt=7972, completion=1017, max_prompt=8744),
    NodeName.ROLE: NodeTokens(prompt=1958, completion=1452, max_prompt=2194),
    NodeName.PROHIBITED: NodeTokens(prompt=10408, completion=2006, max_prompt=11630),
    NodeName.TRANSPARENCY: NodeTokens(prompt=6614, completion=1403, max_prompt=7707),
}
"""Mean (and largest) tokens of one call, from the committed Luna recordings of each node's
replay tests (X2: 47 calls, $0.052 in total). Completion tokens include Luna's reasoning, so for
Gemini, which doesn't reason, the estimate is an upper bound. The role figures are C7b's
recordings: its high-risk requests carry the Art. 111(2) section, at about 2,170 prompt and up to
2,206 completion tokens of the node's 3,000 cap. The prohibited and transparency figures (X2b)
are the answered calls of the E4 and E6 recordings committed on 2026-10-09: 9 prohibited calls
(the 8 refused ones carry no usage) and 16 transparency calls; the facts figures, of the 78
answered E13 facts recordings (its prompt grew for the thin-description check)."""

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


def _folder_cases(node: NodeName | None, cases_dir: Path) -> tuple[BenchmarkCase, ...]:
    """The cases of `node`'s folder; None is the thin cases' folder."""
    folder = THIN_FOLDER if node is None else CASE_FOLDERS[node]
    set_dir = cases_dir / CaseSet.OWN.value / folder
    paths = sorted(set_dir.rglob("*.yaml")) if set_dir.is_dir() else []
    return tuple(case for path in paths for case in load_yaml_file(path))


def _check_cases(node: NodeName, cases_dir: Path) -> tuple[BenchmarkCase, ...]:
    """The cases `node` is probed on: its folder; high_risk also INIT's worked example, and the
    role check only the cases whose label names a role."""
    cases = _folder_cases(node, cases_dir)
    if node is NodeName.HIGH_RISK:
        return (WORKED_EXAMPLE, *cases)
    if node is NodeName.ROLE:
        return tuple(case for case in cases if runs_role_check(case))
    return cases


def _facts_cases(checks: Sequence[NodeName], cases_dir: Path) -> tuple[BenchmarkCase, ...]:
    """The cases facts runs on: every case the planned checks use, each once. With every check
    planned, or none (facts alone), that is every own case, so the thin ones (`own/thin`, E13)
    join them (X2b: "facts on all own cases"); X2's plan, without prohibited and transparency,
    stays as it was."""
    is_every_case = not checks or set(checks) == set(CHECK_ORDER)
    used = [c for n in (checks or CHECK_ORDER) for c in _check_cases(n, cases_dir)]
    thin = _folder_cases(None, cases_dir) if is_every_case else ()
    return tuple({case.id: case for case in (*used, *thin)}.values())


class UnknownCaseError(ValueError):
    """A case id asked for that no probe of the planned nodes has."""


def plan_probes(
    cases_dir: Path = CASES_DIR,
    *,
    nodes: Sequence[NodeName] = X2_NODES,
    case_ids: Sequence[str] = (),
) -> tuple[Probe, ...]:
    """Every probe of `nodes`: the checks first, in the engine's order, then facts on each case
    they use (`_facts_cases`). With `case_ids`, only those cases' probes; raises
    `UnknownCaseError` for an id no probe of `nodes` has."""
    checks = [node for node in CHECK_ORDER if node in nodes]
    probes = [Probe(n, c) for n in checks for c in _check_cases(n, cases_dir)]
    if NodeName.FACTS in nodes:
        probes += [Probe(NodeName.FACTS, case) for case in _facts_cases(checks, cases_dir)]
    if not case_ids:
        return tuple(probes)
    unknown = sorted(set(case_ids) - {probe.case.id for probe in probes})
    if unknown:
        raise UnknownCaseError(f"no probe of the planned nodes has the case(s) {unknown}")
    return tuple(probe for probe in probes if probe.case.id in case_ids)


def probe_state(probe: Probe) -> EngineState:
    """The state the node sees, as in its replay test."""
    if probe.node is NodeName.ROLE:
        return role_check_state(probe.case, AS_OF)
    return replay_state(probe.case, AS_OF)


MATCHERS: Mapping[NodeName, Callable[[CheckOutcome, BenchmarkCase], bool]] = {
    NodeName.SCOPE: scope_matches,
    NodeName.PROHIBITED: prohibited_matches,
    NodeName.HIGH_RISK: high_risk_matches,
    NodeName.TRANSPARENCY: transparency_matches,
    NodeName.ROLE: role_matches,
}


def is_refused(outcome: FactsOutcome | CheckOutcome) -> bool:
    """Whether the node returned its refusal outcome: the provider's content filter refused the
    call with no parseable answer (decisions 029, 030)."""
    if isinstance(outcome, CheckOutcome):
        return outcome.step.error == PROVIDER_REFUSAL
    return any(q.id == facts.PERSON_REVIEW_ID for q in outcome.follow_up_questions)


def is_correct(probe: Probe, outcome: FactsOutcome | CheckOutcome) -> bool | None:
    """Whether a check's outcome matches the label; None for facts, which have no label."""
    if probe.node is NodeName.FACTS:
        return None
    if not isinstance(outcome, CheckOutcome):
        raise TypeError(f"the {probe.node.value} node returned {type(outcome).__name__}")
    return MATCHERS[probe.node](outcome, probe.case)


def broken_correct(node: NodeName) -> bool | None:
    """A broken answer is wrong; facts, which have no label, stay unscored."""
    return None if node is NodeName.FACTS else False


# --- Running one probe --------------------------------------------------------------------------


@dataclass(frozen=True)
class CallRecord:
    """One model call of a probe: what it was billed, its tokens, its generation id, OpenRouter's
    finish reason and the provider's own (`native_finish_reason`), stored with the probe so a
    failed or broken call can be checked from the row (decision 023 addendum, part 7)."""

    cost_usd: float
    tokens: int
    generation_id: str | None = None
    finish_reason: str | None = None
    native_finish_reason: str | None = None

    @property
    def is_provider_error(self) -> bool:
        return self.finish_reason == PROVIDER_ERROR_FINISH

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "cost_usd": self.cost_usd,
            "tokens": self.tokens,
            "generation_id": self.generation_id,
            "finish_reason": self.finish_reason,
            "native_finish_reason": self.native_finish_reason,
        }


class UsageTracker(BaseCallbackHandler):
    """The calls of one probe. Cost is OpenRouter's `usage.cost`; the arm's token prices when it's
    missing; the node's worst case when the usage is missing too, or the reply isn't a chat
    message."""

    def __init__(self, arm: ModelArm, node: NodeName) -> None:
        self.arm = arm
        self.node = node
        self.records: list[CallRecord] = []
        self.is_cost_estimated = False

    def record(self, call: CallRecord) -> None:
        self.records.append(call)

    @property
    def calls(self) -> int:
        return len(self.records)

    @property
    def cost_usd(self) -> float:
        return sum(call.cost_usd for call in self.records)

    @property
    def tokens(self) -> int:
        return sum(call.tokens for call in self.records)

    @property
    def generation_ids(self) -> list[str]:
        return [call.generation_id for call in self.records if call.generation_id is not None]

    @property
    def has_provider_error(self) -> bool:
        """A call the provider ended with an error instead of a finished reply."""
        return any(call.is_provider_error for call in self.records)

    def on_llm_end(self, response: LLMResult, **kwargs: object) -> None:
        response_id = (response.llm_output or {}).get("id")
        generation_id = response_id if isinstance(response_id, str) else None
        for generations in response.generations:
            for generation in generations:
                self.record(self._call(generation, generation_id))
                generation_id = None  # one completion per call: the id belongs to the first

    def _call(self, generation: Generation, generation_id: str | None) -> CallRecord:
        info = generation.generation_info or {}
        message = getattr(generation, "message", None)
        metadata = message.response_metadata if isinstance(message, AIMessage) else {}
        native = metadata.get("native_finish_reason", info.get("native_finish_reason"))
        finish = info.get("finish_reason", metadata.get("finish_reason"))
        cost, tokens = self._usage(message) if isinstance(message, AIMessage) else self._worst()
        return CallRecord(
            cost_usd=cost,
            tokens=tokens,
            generation_id=generation_id,
            finish_reason=finish if isinstance(finish, str) else None,
            native_finish_reason=native if isinstance(native, str) else None,
        )

    def _worst(self) -> tuple[float, int]:
        self.is_cost_estimated = True
        return worst_case_cost(self.node, self.arm), 0

    def _usage(self, message: AIMessage) -> tuple[float, int]:
        usage = message.usage_metadata
        prompt, completion = (usage["input_tokens"], usage["output_tokens"]) if usage else (0, 0)
        cost = message.response_metadata.get("cost")
        if isinstance(cost, int | float):
            return float(cost), prompt + completion
        if usage is None:
            return self._worst()
        self.is_cost_estimated = True
        return self.arm.price(prompt, completion), prompt + completion


NodeRunner = Callable[[EngineState], FactsOutcome | CheckOutcome]
NodeFactory = Callable[[NodeName, Settings, UsageTracker], NodeRunner]


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
    if node is NodeName.PROHIBITED:
        return prohibited.ProhibitedCheck(settings, chat=chat)
    if node is NodeName.HIGH_RISK:
        return high_risk.HighRiskCheck(settings, chat=chat)
    if node is NodeName.TRANSPARENCY:
        return transparency.TransparencyCheck(settings, chat=chat)
    return role_obligations.RoleObligationsCheck(settings, chat=chat)


BROKEN_OUTPUT_ERRORS: tuple[type[Exception], ...] = (
    facts.FactsOutputError,
    scope.ScopeOutputError,
    prohibited.ProhibitedOutputError,
    high_risk.HighRiskOutputError,
    transparency.TransparencyOutputError,
    role_obligations.RoleOutputError,
    ValidationError,
)
"""An answer that doesn't fit the node's schema, or a result the contract rejects."""
BROKEN_ERROR_TYPES = frozenset(error.__name__ for error in BROKEN_OUTPUT_ERRORS)
"""Their names, as a broken probe stores them in `predicted.error.type`."""

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
    REFUSED = "refused"
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
            return _Ran(ProbeKind.BROKEN, {"error": _error(exc)}, broken_correct(probe.node))
        if not is_no_answer(exc):
            raise
        logger.warning("probe %s got no answer: %s", probe.probe_id, type(exc).__name__)
        return _Ran(ProbeKind.FAILED, {"error": _error(exc)}, None)
    if is_refused(outcome):
        return _Ran(ProbeKind.REFUSED, outcome.model_dump(mode="json"), None)
    return _Ran(ProbeKind.ANSWERED, outcome.model_dump(mode="json"), is_correct(probe, outcome))


NO_GENERATION_ID = "the reply carries no generation id"
LOOKUP_SKIPPED = (
    "not looked up: the provider broke off the reply (finish_reason error), and OpenRouter may "
    "keep no record of an unbilled generation"
)


def _served(tracker: UsageTracker, has_reply: bool, can_defer: bool, served_by: ServedBy) -> Served:
    """Who served the calls. A call the provider broke off is not looked up: the probe already
    got no answer, and waiting for a record that may never come would hold a slot for ~18 s.
    With `can_defer` (the model replied), a record that doesn't show up in time, or a lookup
    that fails in transport or with a 5xx, leaves the probe pending, to be checked again at the
    end of the run."""
    if not tracker.records:
        return Served(not_counted=NO_GENERATION_ID) if has_reply else Served()
    checked = [call for call in tracker.records if not call.is_provider_error]
    skipped = LOOKUP_SKIPPED if len(checked) < tracker.calls else None
    if not checked:
        return Served(lookup_skipped=skipped)
    ids = [call.generation_id for call in checked if call.generation_id is not None]
    if len(ids) < len(checked):
        return Served(not_counted=NO_GENERATION_ID, lookup_skipped=skipped)
    try:
        names = [served_by(generation_id) for generation_id in ids]
    except GenerationPendingError as exc:
        if can_defer:
            return Served(lookup_skipped=skipped, pending=tuple(ids))
        return Served(not_counted=str(exc), lookup_skipped=skipped)
    except GenerationLookupError as exc:
        return Served(not_counted=str(exc), lookup_skipped=skipped)
    return judge(names, tracker.arm.served_by, skipped)


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
    has_reply = ran.kind is not ProbeKind.FAILED
    if tracker.has_provider_error and has_reply:
        error = "a call ended with finish_reason error: the provider broke off the reply"
        ran = _Ran(ProbeKind.FAILED, {**ran.predicted, "provider_error": error}, None)
    can_defer = ran.kind is not ProbeKind.FAILED
    served = _served(tracker, has_reply, can_defer, served_by)
    if served.not_counted is not None:
        ran = _Ran(ProbeKind.FAILED, {**ran.predicted, "not_pinned": served.not_counted}, None)
    smoke_info: dict[str, JsonValue] = {
        "served_by": list(served.providers),
        "generation_ids": list(tracker.generation_ids),
        "pending_generation_ids": list(served.pending),
        "calls": [call.as_json() for call in tracker.records],
        "lookup_skipped": served.lookup_skipped,
        "cost_is_estimated": tracker.is_cost_estimated,
    }
    scores: dict[str, Score] = {
        "broken": ran.kind is ProbeKind.BROKEN,
        "failed": ran.kind is ProbeKind.FAILED,
        "refused": ran.kind is ProbeKind.REFUSED,
        "correct": ran.correct,
        "served_as_pinned": served.as_pinned,
        "pending_verification": bool(served.pending),
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
    checked_late: int = 0
    """Probes left pending during the run and checked again at its end."""
    confirmed_late: int = 0
    """Of those, the ones confirmed on the pinned provider."""


class SmokeStore(RunStore, Protocol):
    """A `RunStore` that can also replace a stored probe's prediction and scores."""

    def update_case(self, run_id: UUID, record: CaseRecord) -> None: ...


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

    def __init__(self, store: SmokeStore, run_id: UUID) -> None:
        self.store = store
        self.run_id = run_id
        self.recorded = 0
        self.cost_usd = 0.0
        self.tokens = 0
        self.pending: list[CaseRecord] = []
        self.confirmed_late = 0

    def record(self, record: CaseRecord) -> None:
        self.store.add_case(self.run_id, record)
        self.recorded += 1
        self.cost_usd += record.cost_usd
        self.tokens += record.tokens
        if record.scores.get("pending_verification") is True:
            self.pending.append(record)


def run_arm(
    arm: ModelArm,
    probes: Sequence[Probe],
    store: SmokeStore,
    settings: Settings,
    git_state: tuple[str, bool],
    *,
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
    concurrency: int = DEFAULT_CONCURRENCY,
    factory: NodeFactory = engine_node,
    served_by: ServedBy | None = None,
    verify: VerifyAll | None = None,
) -> ArmRun:
    """Run every probe on `arm` and store one row each, `concurrency` at a time. A probe starts
    only while what is spent, plus the worst case of every probe in flight and of this one, stays
    within `max_cost_usd`. Then the probes left pending are checked again (`verify`), before the
    run is marked finished. `served_by` and `verify` default to OpenRouter's generation records."""
    git_sha, is_git_dirty = git_state
    lookup = served_by or GenerationLookup(settings).served_by
    config = run_config(arm, settings, probes, max_cost_usd, is_git_dirty)
    tally = _Tally(store, store.start_run(git_sha, BENCHMARK, config))
    try:
        started = _run_all(probes, arm, settings, lookup, factory, tally, max_cost_usd, concurrency)
        _check_pending(
            tally, arm, verify or (lambda ids: GenerationLookup(settings).served_by_all(ids))
        )
    except BaseException:
        store.finish_run(tally.run_id, _outcome(RunStatus.INTERRUPTED, len(probes), tally))
        raise
    status = RunStatus.COMPLETED if started == len(probes) else RunStatus.COST_CAP_REACHED
    store.finish_run(tally.run_id, _outcome(status, len(probes), tally))
    return ArmRun(
        arm,
        tally.run_id,
        status,
        len(probes),
        tally.recorded,
        tally.cost_usd,
        tally.tokens,
        len(tally.pending),
        tally.confirmed_late,
    )


def _check_pending(tally: _Tally, arm: ModelArm, verify: VerifyAll) -> None:
    """Look up the pending probes' records again, all in one long window, and store each one's
    final row: its own score when every call is confirmed on the pinned provider, else failed."""
    if not tally.pending:
        return
    ids = [generation_id for record in tally.pending for generation_id in pending_ids(record)]
    logger.info("checking %d pending probes (%d generations) again", len(tally.pending), len(ids))
    found = verify(ids)
    checked_at = datetime.now(UTC)
    for record in tally.pending:
        served = settle(pending_ids(record), found, arm.served_by)
        tally.store.update_case(tally.run_id, settle_pending(record, served, checked_at))
        tally.confirmed_late += served.as_pinned is True


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
        "probes_checked_late": len(tally.pending),
        "probes_confirmed_late": tally.confirmed_late,
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
