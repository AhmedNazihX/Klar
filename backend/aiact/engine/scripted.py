"""Stub nodes that return scripted outcomes instead of calling a model (E1).

They let the graph run end to end before the real nodes exist (E2-E8), and let tests drive
every routing path. The stub finalize assembles a contract-valid `ClassificationResult`, so a
path that skipped or repeated a check would fail `ClassificationResult`'s own validators.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from aiact.engine.graph import CheckNode, EngineNodes, run_ends_after
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.schemas import (
    DISCLAIMER,
    STEP_ORDER,
    ClassificationResult,
    FollowUpQuestion,
    RiskClass,
    Role,
    StepName,
    StepResult,
)
from aiact.schemas.result import derived_status

STOP_CLASS: Mapping[StepName, RiskClass] = {
    StepName.SCOPE: RiskClass.OUT_OF_SCOPE,
    StepName.PROHIBITED: RiskClass.PROHIBITED,
}
"""The class a matched stopping check ends the run with."""


def no_match(name: StepName) -> CheckOutcome:
    """A decided check that found nothing, the default for any check a script leaves out."""
    return CheckOutcome(step=StepResult(step=name, decision=f"Scripted: no {name.value} finding"))


@dataclass(frozen=True)
class Script:
    """The outcomes the stub nodes return, and the class a full run falls through to."""

    facts: FactsOutcome = field(default_factory=FactsOutcome)
    checks: Mapping[StepName, CheckOutcome] = field(default_factory=dict)
    risk_class: RiskClass = RiskClass.MINIMAL_RISK
    role: Role = Role.DEPLOYER
    transparency_duties: tuple[str, ...] = ()

    def outcome(self, name: StepName) -> CheckOutcome:
        return self.checks.get(name) or no_match(name)


def _risk_class(state: EngineState, steps: tuple[StepResult, ...], script: Script) -> RiskClass:
    """A stopping check that ended the run sets the class; an unsettled Art. 5 match keeps
    prohibited as the stricter working assumption (decision 010)."""
    last = steps[-1].step
    if last in STOP_CLASS and run_ends_after(state, last):
        return STOP_CLASS[last]
    if StepName.PROHIBITED in state.get("matches", ()):
        return RiskClass.PROHIBITED
    return script.risk_class


def _follow_ups(state: EngineState) -> tuple[FollowUpQuestion, ...]:
    """The facts node's questions plus every step's missing fact, each id once."""
    missing = (step.missing_fact for step in state.get("steps", ()) if step.missing_fact)
    by_id = {q.id: q for q in (*state.get("follow_up_questions", ()), *missing)}
    return tuple(by_id.values())


def _finalize(state: EngineState, script: Script) -> ClassificationResult:
    steps: tuple[StepResult, ...] = state.get("steps", ())
    risk_class = _risk_class(state, steps, script)
    has_role_step = len(steps) == len(STEP_ORDER)
    return ClassificationResult(
        facts=state.get("facts", ()),
        steps=steps,
        risk_class=risk_class,
        status=derived_status(steps),
        role=script.role if has_role_step else None,
        transparency_duties=()
        if risk_class is RiskClass.OUT_OF_SCOPE
        else script.transparency_duties,
        law_version=state["law_version"],
        as_of=state["as_of"],
        disclaimer=DISCLAIMER[state["language"]],
        follow_up_questions=_follow_ups(state),
    )


def scripted_nodes(script: Script) -> EngineNodes:
    """Engine nodes that ignore their input and return what `script` says."""
    return EngineNodes(
        facts=lambda _state: script.facts,
        checks={name: _check(script, name) for name in STEP_ORDER},
        finalize=lambda state: _finalize(state, script),
    )


def _check(script: Script, name: StepName) -> CheckNode:
    return lambda _state: script.outcome(name)
