"""The staged engine as a LangGraph StateGraph, in the Act's fixed check order (E1).

facts → scope → prohibited → high_risk → transparency → role_obligations → finalize.

The edges are fixed here and the nodes can't change them: a node only returns its outcome.
The only branches are after facts, scope and prohibited, and each goes either to the next node
or to finalize, so no path skips a check. After facts, a description too thin to start (E13,
decision 010 addendum) goes straight to finalize: no check runs, and no class is given.
A stopping check ends the run only when it matched and its step may end the run
(`can_end_run`, decision 010); otherwise the run goes on with the stricter reading as the
working assumption.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Protocol

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from aiact.engine.state import (
    STOPPING_STEPS,
    CheckOutcome,
    EngineInput,
    EngineState,
    FactsOutcome,
)
from aiact.schemas import STEP_ORDER, ClassificationResult, StepName
from aiact.schemas.result import can_end_run

FACTS = "facts"
FINALIZE = "finalize"
NODE_ORDER: tuple[str, ...] = (FACTS, *STEP_ORDER, FINALIZE)
"""Every node of the graph, in the order a full run visits them."""

FactsNode = Callable[[EngineState], FactsOutcome]
CheckNode = Callable[[EngineState], CheckOutcome]
FinalizeNode = Callable[[EngineState], ClassificationResult]
EngineGraph = CompiledStateGraph[EngineState, None, EngineInput, EngineState]
StateUpdate = dict[str, object]


class GraphNode(Protocol):
    """A node as LangGraph calls it: the state in (by the name `state`), an update out."""

    def __call__(self, state: EngineState) -> StateUpdate: ...


class NodeContractError(RuntimeError):
    """A node returned something its place in the graph doesn't allow."""


@dataclass(frozen=True)
class EngineNodes:
    """The node functions the graph runs: one per check, plus facts and finalize."""

    facts: FactsNode
    checks: Mapping[StepName, CheckNode]
    finalize: FinalizeNode

    def __post_init__(self) -> None:
        if set(self.checks) != set(STEP_ORDER):
            raise ValueError(f"EngineNodes needs exactly one node per check: {list(STEP_ORDER)}")


def run_ends_after(state: EngineState, name: StepName) -> bool:
    """Whether the run ends after check `name`: it matched, and its step may end the run."""
    steps = state.get("steps", ())
    if not steps or steps[-1].step is not name:
        raise NodeContractError(f"routing after {name.value}, but its step is not the last one")
    return name in state.get("matches", ()) and can_end_run(steps[-1])


def _facts_node(node: FactsNode) -> GraphNode:
    def run(state: EngineState) -> StateUpdate:
        outcome = node(state)
        return {
            "facts": outcome.facts,
            "follow_up_questions": outcome.follow_up_questions,
            "needs_description": outcome.needs_description,
        }

    return run


def _check_node(name: StepName, node: CheckNode) -> GraphNode:
    def run(state: EngineState) -> StateUpdate:
        outcome = node(state)
        if outcome.step.step is not name:
            raise NodeContractError(
                f"the {name.value} node returned a step for {outcome.step.step.value}"
            )
        return {
            "steps": (outcome.step,),
            "matches": (name,) if outcome.matched else (),
            **_findings(outcome),
        }

    return run


def _findings(outcome: CheckOutcome) -> StateUpdate:
    """The findings a check set, as state keys; unset findings leave the state alone."""
    findings: StateUpdate = {}
    if outcome.high_risk_route is not None:
        findings["high_risk_route"] = outcome.high_risk_route
    if outcome.annex_iii_exempt:
        findings["annex_iii_exempt"] = True
    if outcome.annex_point is not None:
        findings["annex_point"] = outcome.annex_point
    if outcome.transparency_duties:
        findings["transparency_duties"] = outcome.transparency_duties
    if outcome.role is not None:
        findings["role"] = outcome.role
    if outcome.follow_up_questions:
        findings["follow_up_questions"] = outcome.follow_up_questions
    if outcome.asked_facts:
        findings["asked_facts"] = outcome.asked_facts
    return findings


def _finalize_node(node: FinalizeNode) -> GraphNode:
    def run(state: EngineState) -> StateUpdate:
        return {"result": node(state)}

    return run


def _route_after_facts(state: EngineState) -> str:
    return FINALIZE if state.get("needs_description", False) else STEP_ORDER[0].value


def _route_after(name: StepName, next_check: StepName) -> Callable[[EngineState], str]:
    def route(state: EngineState) -> str:
        return FINALIZE if run_ends_after(state, name) else next_check

    return route


def build_graph(nodes: EngineNodes) -> EngineGraph:
    """Compile the staged engine over `nodes`. The order and the branches are fixed here."""
    builder = StateGraph(EngineState, input_schema=EngineInput)
    builder.add_node(FACTS, _facts_node(nodes.facts))
    for name in STEP_ORDER:
        builder.add_node(name.value, _check_node(name, nodes.checks[name]))
    builder.add_node(FINALIZE, _finalize_node(nodes.finalize))

    builder.add_edge(START, FACTS)
    builder.add_conditional_edges(FACTS, _route_after_facts, [STEP_ORDER[0].value, FINALIZE])
    for name, next_check in pairwise(STEP_ORDER):
        if name in STOPPING_STEPS:
            route = _route_after(name, next_check)
            builder.add_conditional_edges(name, route, [next_check.value, FINALIZE])
        else:
            builder.add_edge(name, next_check)
    builder.add_edge(STEP_ORDER[-1], FINALIZE)
    builder.add_edge(FINALIZE, END)
    return builder.compile()
