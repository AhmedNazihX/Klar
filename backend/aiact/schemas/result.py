"""The structured result of classifying one AI system."""

from datetime import date
from typing import Self

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import LawVersion, RiskClass, Role, Status
from aiact.schemas.evidence import Fact
from aiact.schemas.obligations import Obligation
from aiact.schemas.steps import STEP_ORDER, StepName, StepResult


class ClassificationResult(ContractModel):
    """The engine's answer. When `status` is uncertain, `risk_class` is the stricter reading,
    kept as the labelled working assumption."""

    facts: tuple[Fact, ...] = Field(description="Facts extracted from the description.")
    steps: tuple[StepResult, ...] = Field(min_length=1, description="In the Act's check order.")
    risk_class: RiskClass
    status: Status
    role: Role
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
    follow_up_questions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _steps_in_order(self) -> Self:
        positions = [STEP_ORDER.index(step.step) for step in self.steps]
        if positions != sorted(set(positions)):
            raise ValueError("steps must follow the check order, each at most once")
        return self

    @model_validator(mode="after")
    def _limited_risk_has_duties(self) -> Self:
        if self.risk_class is RiskClass.LIMITED_RISK and not self.transparency_duties:
            raise ValueError("a limited_risk result must list its transparency_duties")
        return self

    @model_validator(mode="after")
    def _prohibited_stops_at_art_5(self) -> Self:
        if self.risk_class is not RiskClass.PROHIBITED:
            return self
        last_allowed = STEP_ORDER.index(StepName.PROHIBITED)
        if any(STEP_ORDER.index(step.step) > last_allowed for step in self.steps):
            raise ValueError("a prohibited result has no steps after the Art. 5 check")
        return self

    @model_validator(mode="after")
    def _uncertain_status_has_source(self) -> Self:
        if self.status is Status.DECIDED:
            return self
        if not any(step.status is self.status for step in self.steps):
            raise ValueError(
                f"a {self.status.value} result needs a step with that status, "
                "naming its missing_fact or open_question"
            )
        return self
