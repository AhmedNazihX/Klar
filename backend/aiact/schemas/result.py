"""The structured result of classifying one AI system."""

from datetime import date
from typing import Self

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import LawVersion, RiskClass, Role, Status
from aiact.schemas.evidence import Fact
from aiact.schemas.obligations import Obligation
from aiact.schemas.questions import FollowUpQuestion
from aiact.schemas.steps import STEP_ORDER, StepName, StepResult

SCOPE_ONLY = STEP_ORDER[: STEP_ORDER.index(StepName.SCOPE) + 1]
UP_TO_ART_5 = STEP_ORDER[: STEP_ORDER.index(StepName.PROHIBITED) + 1]


class ClassificationResult(ContractModel):
    """The engine's answer. When `status` is uncertain, `risk_class` is the stricter reading,
    kept as the labelled working assumption."""

    facts: tuple[Fact, ...] = Field(description="Facts extracted from the description.")
    steps: tuple[StepResult, ...] = Field(min_length=1, description="In the Act's check order.")
    risk_class: RiskClass
    status: Status
    role: Role | None = Field(
        default=None, description="Set exactly when the role_obligations step ran."
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
    follow_up_questions: tuple[FollowUpQuestion, ...] = ()

    def _step(self, name: StepName) -> StepResult | None:
        return next((step for step in self.steps if step.step is name), None)

    def _stops_at_art_5(self) -> bool:
        """A decided Art. 5 match ends the run; an ambiguous one keeps going (decision 010)."""
        prohibited = self._step(StepName.PROHIBITED)
        return (
            self.risk_class is RiskClass.PROHIBITED
            and prohibited is not None
            and prohibited.status is Status.DECIDED
        )

    def _expected_steps(self) -> tuple[StepName, ...]:
        if self.risk_class is RiskClass.OUT_OF_SCOPE:
            return SCOPE_ONLY
        return UP_TO_ART_5 if self._stops_at_art_5() else STEP_ORDER

    @model_validator(mode="after")
    def _no_check_skipped(self) -> Self:
        names = tuple(step.step for step in self.steps)
        if names != STEP_ORDER[: len(names)]:
            raise ValueError("steps must follow the check order, each once, with none skipped")
        if self._stops_at_art_5() and len(names) > len(UP_TO_ART_5):
            raise ValueError("a decided prohibited result has no steps after the Art. 5 check")
        if names != self._expected_steps():
            raise ValueError(
                f"a {self.risk_class.value} result needs the steps {list(self._expected_steps())}"
            )
        return self

    @model_validator(mode="after")
    def _role_iff_role_step(self) -> Self:
        has_role_step = self._step(StepName.ROLE_OBLIGATIONS) is not None
        if has_role_step != (self.role is not None):
            raise ValueError("role is set exactly when the role_obligations step is present")
        if self.role is None and self.role_switch_reason is not None:
            raise ValueError("role_switch_reason needs a role")
        return self

    @model_validator(mode="after")
    def _limited_risk_has_duties(self) -> Self:
        if self.risk_class is RiskClass.LIMITED_RISK and not self.transparency_duties:
            raise ValueError("a limited_risk result must list its transparency_duties")
        return self

    @model_validator(mode="after")
    def _uncertain_status_has_source(self) -> Self:
        if self.status is Status.DECIDED:
            return self
        if not any(step.status is self.status for step in self.steps):
            raise ValueError(
                f"a {self.status.value} result needs a step with that status, "
                "naming its missing_fact, open_question or error"
            )
        return self

    @model_validator(mode="after")
    def _follow_up_ids_unique(self) -> Self:
        ids = [question.id for question in self.follow_up_questions]
        if len(ids) != len(set(ids)):
            raise ValueError("follow_up_questions ids must be unique")
        return self
