"""The structured result of classifying one AI system.

The cross-field rules below can't be expressed in JSON Schema; decision 010 covers them.
"""

from collections.abc import Iterable
from datetime import date
from typing import Self

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import LawVersion, RiskClass, Role, Status
from aiact.schemas.evidence import Fact
from aiact.schemas.obligations import Obligation
from aiact.schemas.questions import FollowUpQuestion
from aiact.schemas.steps import PROVIDER_REFUSAL, STEP_ORDER, StepName, StepResult

SCOPE_ONLY = STEP_ORDER[: STEP_ORDER.index(StepName.SCOPE) + 1]
UP_TO_ART_5 = STEP_ORDER[: STEP_ORDER.index(StepName.PROHIBITED) + 1]


def can_end_run(step: StepResult) -> bool:
    """Whether a stopping step may end the run: it is decided, or only failed verification (E9).

    An ambiguous step or a real missing fact means the stricter reading runs on (decision 010).
    """
    if step.status is Status.DECIDED:
        return True
    return (
        step.status is Status.NEEDS_MORE_INFORMATION
        and step.error is not None
        and step.missing_fact is None
    )


def derived_status(steps: Iterable[StepResult]) -> Status:
    """The result status the steps imply: ambiguous beats missing information beats decided."""
    statuses = {step.status for step in steps}
    for status in (Status.LEGALLY_AMBIGUOUS, Status.NEEDS_MORE_INFORMATION):
        if status in statuses:
            return status
    return Status.DECIDED


def refused_steps(steps: Iterable[StepResult]) -> tuple[StepName, ...]:
    """The checks the model provider refused to assess (decision 029), in the steps' order."""
    return tuple(step.step for step in steps if step.error == PROVIDER_REFUSAL)


class ClassificationResult(ContractModel):
    """The engine's answer. When `status` is uncertain, `risk_class` is the stricter reading,
    kept as the labelled working assumption."""

    facts: tuple[Fact, ...] = Field(description="Facts extracted from the description.")
    steps: tuple[StepResult, ...] = Field(min_length=1, description="In the Act's check order.")
    risk_class: RiskClass
    status: Status = Field(description="Derived from the steps; see `derived_status`.")
    role: Role | None = Field(
        default=None, description="Set exactly when the role_obligations step ran."
    )
    also_role: Role | None = Field(
        default=None,
        description="A role the company keeps next to `role`, whose duties are listed too: a "
        'deployer that becomes the provider still uses the system (shown as "You also use it").',
    )
    role_switch_reason: str | None = Field(
        default=None, description="Why the Art. 25 switch to provider applies, when it does."
    )
    annex_point: str | None = Field(default=None, description="For example `annex:III:4:a`.")
    transparency_duties: tuple[str, ...] = Field(
        default=(), description="Art. 50 provisions that apply, for example `art:50:1`."
    )
    deciding_facts: tuple[Fact, ...] = ()
    obligations: tuple[Obligation, ...] = ()
    law_version: LawVersion
    as_of: date
    disclaimer: str = Field(min_length=1)
    legal_review: str | None = Field(
        default=None,
        description="The recommendation to have the result reviewed by a lawyer, in the result's "
        "language: set for high-risk, prohibited and legally ambiguous results (INIT > Ethical "
        "considerations).",
    )
    not_assessed: tuple[StepName, ...] = Field(
        default=(),
        description="The checks the model provider refused to assess (decision 029), in check "
        "order; each needs a person's review, and its stricter reading is assumed.",
    )
    follow_up_questions: tuple[FollowUpQuestion, ...] = ()

    def _step(self, name: StepName) -> StepResult | None:
        return next((step for step in self.steps if step.step is name), None)

    def _ends_at(self, name: StepName) -> bool:
        step = self._step(name)
        return step is not None and can_end_run(step)

    def _expected_steps(self) -> tuple[StepName, ...]:
        if self.risk_class is RiskClass.OUT_OF_SCOPE:
            return SCOPE_ONLY
        if self.risk_class is RiskClass.PROHIBITED and self._ends_at(StepName.PROHIBITED):
            return UP_TO_ART_5
        return STEP_ORDER

    @model_validator(mode="after")
    def _no_check_skipped(self) -> Self:
        names = tuple(step.step for step in self.steps)
        if names != STEP_ORDER[: len(names)]:
            raise ValueError("steps must follow the check order, each once, with none skipped")
        if self.risk_class is RiskClass.OUT_OF_SCOPE and not self._ends_at(StepName.SCOPE):
            raise ValueError("an out_of_scope result needs a decided scope step")
        if names != self._expected_steps():
            raise ValueError(
                f"a {self.risk_class.value} result needs the steps {list(self._expected_steps())}"
            )
        return self

    @model_validator(mode="after")
    def _status_matches_steps(self) -> Self:
        expected = derived_status(self.steps)
        if self.status is not expected:
            raise ValueError(f"the steps imply status {expected.value}, not {self.status.value}")
        return self

    @model_validator(mode="after")
    def _role_iff_role_step(self) -> Self:
        has_role_step = self._step(StepName.ROLE_OBLIGATIONS) is not None
        if has_role_step != (self.role is not None):
            raise ValueError("role is set exactly when the role_obligations step is present")
        if self.role is None and (self.role_switch_reason or self.also_role):
            raise ValueError("role_switch_reason and also_role need a role")
        if self.also_role is not None and self.also_role is self.role:
            raise ValueError("also_role must differ from role")
        return self

    @model_validator(mode="after")
    def _not_assessed_names_the_refused_steps(self) -> Self:
        refused = refused_steps(self.steps)
        if self.not_assessed != refused:
            raise ValueError(
                f"not_assessed must name exactly the refused steps: {[s.value for s in refused]}"
            )
        return self

    @model_validator(mode="after")
    def _class_specific_fields(self) -> Self:
        if self.risk_class is RiskClass.LIMITED_RISK and not self.transparency_duties:
            raise ValueError("a limited_risk result must list its transparency_duties")
        if self.risk_class is RiskClass.OUT_OF_SCOPE and (
            self.obligations or self.annex_point or self.transparency_duties
        ):
            raise ValueError(
                "an out_of_scope result has no obligations, annex_point or transparency_duties"
            )
        return self

    @model_validator(mode="after")
    def _follow_ups_cover_missing_facts(self) -> Self:
        by_id = {question.id: question for question in self.follow_up_questions}
        if len(by_id) != len(self.follow_up_questions):
            raise ValueError("follow_up_questions ids must be unique")
        for step in self.steps:
            missing = step.missing_fact
            if missing is None:
                continue
            listed = by_id.get(missing.id)
            if listed is None or listed.text != missing.text:
                raise ValueError(
                    f"missing_fact {missing.id!r} of step {step.step.value} must appear "
                    "with the same text in follow_up_questions"
                )
        return self
