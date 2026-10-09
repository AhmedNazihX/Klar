"""The state the staged engine carries from node to node, and what each node returns (E1).

Nodes never write the state directly. A node returns one of the outcome models below, and
`aiact.engine.graph` turns it into a state update, so every check can only add its own step.
"""

import operator
from datetime import date
from typing import Annotated, NotRequired, Self, TypedDict

from pydantic import model_validator

from aiact.schemas import (
    DESCRIPTION_QUESTION_IDS,
    PROVIDER_REFUSAL,
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
from aiact.schemas.result import STOPPING_STEPS


class FactsOutcome(ContractModel):
    """What the facts node extracted: the facts and the key-fact questions they raise.

    `needs_description` flags a description too thin to start (E13): what the tool decides or
    who it affects is missing. The run then ends before the checks, and the questions are
    exactly the three `DESCRIPTION_QUESTION_IDS`.
    """

    facts: tuple[Fact, ...] = ()
    follow_up_questions: tuple[FollowUpQuestion, ...] = ()
    needs_description: bool = False

    @model_validator(mode="after")
    def _thin_asks_for_a_description(self) -> Self:
        ids = tuple(question.id for question in self.follow_up_questions)
        if self.needs_description and ids != DESCRIPTION_QUESTION_IDS:
            raise ValueError(f"a thin description asks exactly {list(DESCRIPTION_QUESTION_IDS)}")
        return self


class RoleFinding(ContractModel):
    """What the role_obligations check settled: the role, why it switched, and its duties (E7).

    `also_role` is a role the company keeps next to `role`: a deployer that becomes the provider
    under Art. 25(1) still uses the system, so it keeps its deployer duties; a working assumption
    of provider keeps the base role's duties too. `obligations` covers both roles.
    """

    role: Role
    also_role: Role | None = None
    role_switch_reason: str | None = None
    obligations: tuple[Obligation, ...] = ()


class CheckOutcome(ContractModel):
    """What one check returns: its step, and whether it matched the class that stops the run.

    `matched` is the check's finding (scope: not in scope; prohibited: a prohibited practice).
    Whether the run really ends also depends on the step's status (decision 010): an ambiguous
    or missing-fact match keeps the run going, with the stricter reading as the assumption.

    The other findings belong to one check each, and later checks read them from the state:
    - `high_risk_route` (high_risk): the system is, or is assumed, high-risk on this route.
    - `annex_iii_exempt` (high_risk): the system is listed in Annex III but, or is assumed to be,
      exempted under Art. 6(3); the provider then has the Art. 6(4) duty.
    - `annex_point` (high_risk): the Annex point a high-risk finding (or assumption) rests on,
      e.g. `annex:III:4:a`, or the Annex I legislation, e.g. `annex:I:A:11`; None when the
      system is not high-risk, exempt ones included (their decision still names the point). An
      `annex:I:B:` point is Section B: Art. 2(2) then leaves only Art. 6(1), 60a and 102-112 of
      the Act (the original text: 6(1), 102-109 and 112), so the duties come from the sector law.
      Which law is in Section B depends on the text: the Omnibus moved machinery from A.1 to
      B.21.
    - `transparency_duties` (transparency): every Art. 50 provision that applies, e.g.
      `art:50:1`, including duties that are only assumed or uncertain. The role step lists an
      Art. 50 duty only when it is here, so a duty left out is a duty the result drops.
    - `role` (role_obligations).
    `follow_up_questions` may come from any check: every question it wants asked, which may
    include its step's `missing_fact`; finalize collects them and de-duplicates by id.
    `asked_facts` names the assumed facts of the step's `facts_used` that one of those questions
    already asks the user to confirm (e.g. high-risk's assumed public-authority user for Annex
    III 6 and 7), so finalize adds no second confirm question for them.
    """

    step: StepResult
    matched: bool = False
    high_risk_route: HighRiskRoute | None = None
    annex_iii_exempt: bool = False
    annex_point: str | None = None
    transparency_duties: tuple[str, ...] = ()
    role: RoleFinding | None = None
    follow_up_questions: tuple[FollowUpQuestion, ...] = ()
    asked_facts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _asked_facts_are_the_steps(self) -> Self:
        used = {fact.text for fact in self.step.facts_used}
        if not set(self.asked_facts) <= used:
            raise ValueError("asked_facts must name facts of the step's facts_used")
        return self

    @model_validator(mode="after")
    def _only_stopping_steps_match(self) -> Self:
        if self.matched and self.step.step not in STOPPING_STEPS:
            raise ValueError(f"the {self.step.step.value} check has no class that stops the run")
        return self

    @model_validator(mode="after")
    def _findings_belong_to_their_step(self) -> Self:
        owners = (
            (self.high_risk_route is not None, StepName.HIGH_RISK, "high_risk_route"),
            (self.annex_iii_exempt, StepName.HIGH_RISK, "annex_iii_exempt"),
            (self.annex_point is not None, StepName.HIGH_RISK, "annex_point"),
            (bool(self.transparency_duties), StepName.TRANSPARENCY, "transparency_duties"),
            (self.role is not None, StepName.ROLE_OBLIGATIONS, "role"),
        )
        for is_set, owner, name in owners:
            if is_set and self.step.step is not owner:
                raise ValueError(f"only the {owner.value} check sets {name}")
        if self.annex_iii_exempt and self.high_risk_route is not None:
            raise ValueError("an Art. 6(3)-exempt system is not high-risk")
        if self.annex_point is not None and self.high_risk_route is None:
            raise ValueError("annex_point is set only with the high_risk_route it rests on")
        return self

    @model_validator(mode="after")
    def _refused_step_finds_nothing(self) -> Self:
        """A check the provider refused found nothing, so no class can rest on it (decision
        030)."""
        if self.step.error != PROVIDER_REFUSAL:
            return self
        if (
            self.matched
            or self.high_risk_route is not None
            or self.annex_iii_exempt
            or self.annex_point is not None
            or self.transparency_duties
            or self.role is not None
        ):
            raise ValueError("a refused check has no finding (decision 030)")
        return self


class EngineInput(TypedDict):
    """What a caller passes in to start one classification.

    The answers to follow-up questions are part of `description`: `classify_system` (E10) appends
    them before the facts node (decision 019), so there is no separate answers path.
    `include_held_out` is the gap run's opt-in (V8, decision 012): every corpus lookup, search and
    citation check of the run then sees the held-out examples too. Absent means False, so
    held-out examples stay hidden by default."""

    description: str
    language: Language
    law_version: LawVersion
    as_of: date
    exclude_source_example_ids: tuple[str, ...]
    include_held_out: NotRequired[bool]


class EngineState(EngineInput, total=False):
    """The graph state. `steps` and `matches` only grow, one entry per check that ran; the
    per-check findings are present only when their check set them (see `CheckOutcome`)."""

    facts: tuple[Fact, ...]
    needs_description: bool
    follow_up_questions: Annotated[tuple[FollowUpQuestion, ...], operator.add]
    asked_facts: Annotated[tuple[str, ...], operator.add]
    steps: Annotated[tuple[StepResult, ...], operator.add]
    matches: Annotated[tuple[StepName, ...], operator.add]
    high_risk_route: HighRiskRoute
    annex_iii_exempt: bool
    annex_point: str
    transparency_duties: tuple[str, ...]
    role: RoleFinding
    result: ClassificationResult
