"""The staged graph: every routing path with stub nodes, and no path that skips a check (E1)."""

from collections.abc import Iterator
from datetime import date
from itertools import pairwise, product

import pytest
from langgraph.graph import END, START
from pydantic import ValidationError

from aiact.engine.graph import (
    FACTS,
    FINALIZE,
    NODE_ORDER,
    EngineGraph,
    EngineNodes,
    NodeContractError,
    build_graph,
)
from aiact.engine.scripted import Script, no_match, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineInput, EngineState, FactsOutcome
from aiact.schemas import (
    DISCLAIMER_EN,
    STEP_ORDER,
    ClassificationResult,
    EvidenceTag,
    Fact,
    FollowUpQuestion,
    Language,
    LawVersion,
    OpenQuestion,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)

ENGINE_INPUT: EngineInput = {
    "description": "We sell a chatbot that answers customer questions.",
    "language": Language.EN,
    "law_version": LawVersion.AMENDED,
    "as_of": date(2026, 9, 28),
    "answers": {},
    "exclude_source_example_ids": ("commission-example-7",),
}
MISSING = FollowUpQuestion(id="eu_use", text="Is the system used in the EU?")
OPEN = OpenQuestion(
    question="Does the law settle this?", readings=("Stricter reading", "Lenient reading")
)

ENDING_VARIANTS = ("match", "match_unverified")
"""Stopping-check outcomes that end the run (decision 010); the rest let it go on."""
VARIANTS = (
    "no_match",
    "no_match_ambiguous",
    "match",
    "match_unverified",
    "match_ambiguous",
    "match_missing_fact",
)


def outcome(name: StepName, variant: str) -> CheckOutcome:
    """A stopping check's scripted outcome: whether it matched, and the step's status."""
    matched = variant.startswith("match")
    if variant in ("no_match", "match"):
        step = StepResult(step=name, decision=f"Scripted {variant}")
    elif variant == "match_unverified":
        step = StepResult(
            step=name,
            decision="Matched, but a citation failed verification",
            status=Status.NEEDS_MORE_INFORMATION,
            error="citation_unverified",
        )
    elif variant == "match_missing_fact":
        step = StepResult(
            step=name,
            decision="A deciding fact is missing",
            status=Status.NEEDS_MORE_INFORMATION,
            missing_fact=MISSING,
        )
    else:
        step = StepResult(
            step=name,
            decision="The law doesn't settle this",
            status=Status.LEGALLY_AMBIGUOUS,
            open_question=OPEN,
        )
    return CheckOutcome(step=step, matched=matched)


def run(graph: EngineGraph) -> tuple[list[str], ClassificationResult]:
    """Run the graph once; return the nodes in the order they ran, and the result."""
    visited: list[str] = []
    result: ClassificationResult | None = None
    for update in graph.stream(ENGINE_INPUT, stream_mode="updates"):
        for node, change in update.items():
            visited.append(node)
            if node == FINALIZE:
                result = change["result"]
    assert result is not None
    return visited, result


def expected_checks(scope: str, prohibited: str) -> tuple[StepName, ...]:
    if scope in ENDING_VARIANTS:
        return (StepName.SCOPE,)
    if prohibited in ENDING_VARIANTS:
        return (StepName.SCOPE, StepName.PROHIBITED)
    return STEP_ORDER


def expected_class(scope: str, prohibited: str) -> RiskClass:
    if scope in ENDING_VARIANTS:
        return RiskClass.OUT_OF_SCOPE
    if prohibited.startswith("match"):
        return RiskClass.PROHIBITED
    return RiskClass.MINIMAL_RISK


@pytest.mark.parametrize(("scope", "prohibited"), list(product(VARIANTS, VARIANTS)))
def test_every_routing_path(scope: str, prohibited: str) -> None:
    script = Script(
        checks={
            StepName.SCOPE: outcome(StepName.SCOPE, scope),
            StepName.PROHIBITED: outcome(StepName.PROHIBITED, prohibited),
        }
    )
    visited, result = run(build_graph(scripted_nodes(script)))

    checks = expected_checks(scope, prohibited)
    assert visited == [FACTS, *checks, FINALIZE]
    assert tuple(step.step for step in result.steps) == checks
    assert result.risk_class is expected_class(scope, prohibited)
    assert result.role is (Role.DEPLOYER if checks == STEP_ORDER else None)


def test_an_ambiguous_art_5_match_runs_every_check_and_assumes_prohibited() -> None:
    script = Script(checks={StepName.PROHIBITED: outcome(StepName.PROHIBITED, "match_ambiguous")})
    visited, result = run(build_graph(scripted_nodes(script)))

    assert visited == list(NODE_ORDER)
    assert result.risk_class is RiskClass.PROHIBITED
    assert result.status is Status.LEGALLY_AMBIGUOUS


def test_a_full_run_carries_facts_questions_and_the_later_checks_outcome() -> None:
    fact = Fact(text="Answers customer questions", evidence=EvidenceTag.INFERRED)
    missing_high_risk_fact = StepResult(
        step=StepName.HIGH_RISK,
        decision="A deciding fact is missing",
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact=MISSING,
    )
    script = Script(
        facts=FactsOutcome(facts=(fact,), follow_up_questions=(MISSING,)),
        checks={StepName.HIGH_RISK: CheckOutcome(step=missing_high_risk_fact)},
        risk_class=RiskClass.LIMITED_RISK,
        role=Role.PROVIDER,
        transparency_duties=("art:50:1",),
    )
    _, result = run(build_graph(scripted_nodes(script)))

    assert result.facts == (fact,)
    assert result.follow_up_questions == (MISSING,)
    assert result.risk_class is RiskClass.LIMITED_RISK
    assert result.status is Status.NEEDS_MORE_INFORMATION
    assert result.role is Role.PROVIDER
    assert result.law_version is LawVersion.AMENDED
    assert result.as_of == ENGINE_INPUT["as_of"]
    assert result.disclaimer == DISCLAIMER_EN


def graph_edges(graph: EngineGraph) -> set[tuple[str, str]]:
    return {(edge.source, edge.target) for edge in graph.get_graph().edges}


def test_the_graph_has_exactly_the_fixed_order_and_the_two_early_exits() -> None:
    full_chain = [START, *NODE_ORDER, END]
    expected = set(pairwise(full_chain))
    expected |= {(StepName.SCOPE.value, FINALIZE), (StepName.PROHIBITED.value, FINALIZE)}

    assert graph_edges(build_graph(scripted_nodes(Script()))) == expected


def all_paths(edges: set[tuple[str, str]], node: str = START) -> Iterator[tuple[str, ...]]:
    """Every path from `node` to END (the graph has no cycles)."""
    if node == END:
        yield (END,)
        return
    for source, target in sorted(edges):
        if source == node:
            for rest in all_paths(edges, target):
                yield (node, *rest)


def test_no_path_skips_a_check() -> None:
    paths = list(all_paths(graph_edges(build_graph(scripted_nodes(Script())))))
    checks_per_path = sorted(path[2:-2] for path in paths)

    assert all(path[:2] == (START, FACTS) and path[-2:] == (FINALIZE, END) for path in paths)
    assert checks_per_path == sorted(
        [
            (StepName.SCOPE.value,),
            (StepName.SCOPE.value, StepName.PROHIBITED.value),
            tuple(name.value for name in STEP_ORDER),
        ]
    )


def test_a_node_sees_the_input_and_the_earlier_steps() -> None:
    seen: list[EngineState] = []

    def prohibited(state: EngineState) -> CheckOutcome:
        seen.append(state)
        return no_match(StepName.PROHIBITED)

    scripted = scripted_nodes(Script())
    nodes = EngineNodes(
        facts=scripted.facts,
        checks={**scripted.checks, StepName.PROHIBITED: prohibited},
        finalize=scripted.finalize,
    )
    run(build_graph(nodes))

    (state,) = seen
    assert state["exclude_source_example_ids"] == ENGINE_INPUT["exclude_source_example_ids"]
    assert state["description"] == ENGINE_INPUT["description"]
    assert [step.step for step in state.get("steps", ())] == [StepName.SCOPE]


def test_a_node_cannot_return_another_checks_step() -> None:
    scripted = scripted_nodes(Script())
    nodes = EngineNodes(
        facts=scripted.facts,
        checks={**scripted.checks, StepName.PROHIBITED: lambda _state: no_match(StepName.SCOPE)},
        finalize=scripted.finalize,
    )

    with pytest.raises(NodeContractError, match="prohibited node returned a step for scope"):
        run(build_graph(nodes))


@pytest.mark.parametrize("name", [StepName.HIGH_RISK, StepName.TRANSPARENCY])
def test_only_scope_and_prohibited_can_stop_the_run(name: StepName) -> None:
    with pytest.raises(ValidationError, match="no class that stops the run"):
        CheckOutcome(step=no_match(name).step, matched=True)


def test_every_check_needs_a_node() -> None:
    scripted = scripted_nodes(Script())
    checks = {name: node for name, node in scripted.checks.items() if name is not StepName.SCOPE}

    with pytest.raises(ValueError, match="one node per check"):
        EngineNodes(facts=scripted.facts, checks=checks, finalize=scripted.finalize)
