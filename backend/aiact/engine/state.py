"""The state the staged engine carries from node to node, and what each node returns (E1).

Nodes never write the state directly. A node returns one of the outcome models below, and
`aiact.engine.graph` turns it into a state update, so every check can only add its own step.
"""

import operator
from collections.abc import Mapping
from datetime import date
from typing import Annotated, Self, TypedDict

from pydantic import model_validator

from aiact.schemas import (
    ClassificationResult,
    Fact,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    Obligation,
    Role,
    StepName,
    StepResult,
)
from aiact.schemas.base import ContractModel

STOPPING_STEPS: frozenset[StepName] = frozenset({StepName.SCOPE, StepName.PROHIBITED})
"""The checks whose match may end the run early: out_of_scope (Art. 2-3) and prohibited (Art. 5)."""


class FactsOutcome(ContractModel):
    """What the facts node extracted: the facts and the key-fact questions they raise."""

    facts: tuple[Fact, ...] = ()
    follow_up_questions: tuple[FollowUpQuestion, ...] = ()


class RoleFinding(ContractModel):
    """What the role_obligations check settled: the role, why it switched, and its duties (E7)."""

    role: Role
    role_switch_reason: str | None = None
    obligations: tuple[Obligation, ...] = ()


class CheckOutcome(ContractModel):
    """What one check returns: its step, and whether it matched the class that stops the run.

    `matched` is the check's finding (scope: not in scope; prohibited: a prohibited practice).
    Whether the run really ends also depends on the step's status (decision 010): an ambiguous
    or missing-fact match keeps the run going, with the stricter reading as the assumption.

    The other findings belong to one check each, and later checks read them from the state:
    `high_risk_route` (high_risk: the system is, or is assumed, high-risk on this route),
    `transparency_duties` (transparency: the Art. 50 provisions that apply, e.g. `art:50:1`)
    and `role` (role_obligations).
    """

    step: StepResult
    matched: bool = False
    high_risk_route: HighRiskRoute | None = None
    transparency_duties: tuple[str, ...] = ()
    role: RoleFinding | None = None

    @model_validator(mode="after")
    def _only_stopping_steps_match(self) -> Self:
        if self.matched and self.step.step not in STOPPING_STEPS:
            raise ValueError(f"the {self.step.step.value} check has no class that stops the run")
        return self

    @model_validator(mode="after")
    def _findings_belong_to_their_step(self) -> Self:
        owners = (
            (self.high_risk_route is not None, StepName.HIGH_RISK, "high_risk_route"),
            (bool(self.transparency_duties), StepName.TRANSPARENCY, "transparency_duties"),
            (self.role is not None, StepName.ROLE_OBLIGATIONS, "role"),
        )
        for is_set, owner, name in owners:
            if is_set and self.step.step is not owner:
                raise ValueError(f"only the {owner.value} check sets {name}")
        return self


class EngineInput(TypedDict):
    """What a caller passes in to start one classification."""

    description: str
    language: Language
    law_version: LawVersion
    as_of: date
    answers: Mapping[str, str]
    exclude_source_example_ids: tuple[str, ...]


class EngineState(EngineInput, total=False):
    """The graph state. `steps` and `matches` only grow, one entry per check that ran; the
    per-check findings are present only when their check set them (see `CheckOutcome`)."""

    facts: tuple[Fact, ...]
    follow_up_questions: tuple[FollowUpQuestion, ...]
    steps: Annotated[tuple[StepResult, ...], operator.add]
    matches: Annotated[tuple[StepName, ...], operator.add]
    high_risk_route: HighRiskRoute
    transparency_duties: tuple[str, ...]
    role: RoleFinding
    result: ClassificationResult
