"""Made-up cases and check outcomes for the smoke test's tests; never benchmark cases."""

from collections.abc import Sequence

from aiact.engine.state import CheckOutcome, RoleFinding
from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.schemas import (
    Citation,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from tests.schemas.builders import open_question

OPEN = open_question("Does the law settle it?", "Stricter.", "Lenient.")
ASK = FollowUpQuestion(id="third_party_assessment", text="Is a notified body involved?")


def case(
    case_id: str,
    risk_class: RiskClass = RiskClass.HIGH_RISK,
    *,
    status: Status = Status.DECIDED,
    role: Role | None = Role.PROVIDER,
    annex_point: tuple[str, ...] = (),
    citation: tuple[str, ...] = ("art:6:1:a",),
    tags: tuple[str, ...] = (),
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        set_name=CaseSet.OWN,
        language=Language.EN,
        description=f"A made-up system ({case_id}).",
        label=CaseLabel(risk_class=risk_class, status=status, role=role, annex_point=annex_point),
        label_citation=citation,
        notes="Open question and readings." if status is Status.LEGALLY_AMBIGUOUS else None,
        tags=tags,
    )


def step(
    name: StepName,
    status: Status = Status.DECIDED,
    cited: Sequence[str] = (),
    decision: str = "A decision.",
    missing: FollowUpQuestion | None = None,
) -> StepResult:
    citations = tuple(
        Citation(provision_id=pid, document_id="ai-act", language=Language.EN, quote="Text.")
        for pid in cited
    )
    return StepResult(
        step=name,
        decision=decision,
        citations=citations,
        status=status,
        missing_fact=(missing or ASK) if status is Status.NEEDS_MORE_INFORMATION else None,
        open_question=OPEN if status is Status.LEGALLY_AMBIGUOUS else None,
    )


def scope_outcome(
    matched: bool, status: Status = Status.DECIDED, cited: Sequence[str] = ()
) -> CheckOutcome:
    return CheckOutcome(step=step(StepName.SCOPE, status, cited), matched=matched)


def high_risk_outcome(
    route: HighRiskRoute | None,
    point: str | None,
    status: Status = Status.DECIDED,
    decision: str = "A decision.",
    missing: FollowUpQuestion | None = None,
    cited: Sequence[str] = (),
) -> CheckOutcome:
    return CheckOutcome(
        step=step(StepName.HIGH_RISK, status, cited, decision=decision, missing=missing),
        high_risk_route=route,
        annex_point=point,
    )


def role_outcome(role: Role, status: Status = Status.DECIDED) -> CheckOutcome:
    return CheckOutcome(step=step(StepName.ROLE_OBLIGATIONS, status), role=RoleFinding(role=role))
