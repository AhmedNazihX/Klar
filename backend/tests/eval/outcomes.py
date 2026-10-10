"""Made-up cases and results for the metric tests; never benchmark cases."""

from aiact.eval.cases import AppliedAILabel, BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.metrics import Outcome
from aiact.schemas import ClassificationResult, Language, RiskClass, Role, Status, StepName
from tests.schemas.builders import (
    ambiguous,
    dumped_steps,
    ends_early,
    missing_fact,
    needs_description,
    rebuild,
    refused,
)
from tests.schemas.builders import steps_with as replaced_steps
from tests.schemas.worked_example import worked_example_result

HIGH_ANNEX_POINT = "annex:III:4:a"
WORKED_EXAMPLE_PROVISIONS = frozenset(
    {"art:3:1", "art:5:1", "annex:III:4:a", "art:6:3", "art:50:1", "art:26:1"}
)
"""Every provision the worked example cites, one citation each."""


def case(
    case_id: str,
    risk_class: RiskClass = RiskClass.HIGH_RISK,
    *,
    status: Status = Status.DECIDED,
    role: Role | None = None,
    annex_point: str | None = None,
    set_name: CaseSet = CaseSet.OWN,
    tags: tuple[str, ...] = (),
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        set_name=set_name,
        language=Language.EN,
        description="A made-up system.",
        label=CaseLabel(
            risk_class=risk_class, status=status, role=role, annex_point=_points(annex_point)
        ),
        label_citation=("art:6:2",),
        notes="Open question and both readings." if status is Status.LEGALLY_AMBIGUOUS else None,
        tags=tags,
    )


def thin_case(case_id: str) -> BenchmarkCase:
    """A thin-description case: its label expects no class (E13)."""
    return BenchmarkCase(
        id=case_id,
        set_name=CaseSet.OWN,
        language=Language.EN,
        description="We use AI.",
        label=CaseLabel(risk_class=None, status=Status.NEEDS_MORE_INFORMATION),
        notes="It says neither what the tool decides nor whom it affects.",
    )


def description_result() -> ClassificationResult:
    """A needs-a-description result: no steps, no class."""
    return needs_description()


def refused_result(name: StepName = StepName.PROHIBITED) -> ClassificationResult:
    """The worked example with its `name` check refused by both models: no class (decision
    030)."""
    return rebuild(
        worked_example_result(),
        steps=replaced_steps(refused(name)),
        risk_class=None,
        status=Status.NEEDS_MORE_INFORMATION,
        annex_point=None,
        obligations=(),
        not_assessed=(name,),
    )


def _points(annex_point: str | None) -> tuple[str, ...]:
    return (annex_point,) if annex_point else ()


def appliedai_case(case_id: str, label: AppliedAILabel) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        set_name=CaseSet.APPLIEDAI,
        language=Language.DE,
        description="Ein erfundenes System.",
        label=label,
    )


def result(
    risk_class: RiskClass = RiskClass.HIGH_RISK, status: Status = Status.DECIDED, **changes: object
) -> ClassificationResult:
    """A valid result of the given class and status, derived from the worked example."""
    base = worked_example_result()
    if risk_class is RiskClass.OUT_OF_SCOPE:
        return ends_early(risk_class, dumped_steps(1), Status.DECIDED)
    if risk_class is RiskClass.PROHIBITED:
        return ends_early(risk_class, dumped_steps(2), Status.DECIDED)
    fields: dict[str, object] = {"risk_class": risk_class, **_uncertain_steps(status)}
    if risk_class is not RiskClass.HIGH_RISK:
        fields |= {"annex_point": None, "obligations": ()}
    if risk_class is RiskClass.LIMITED_RISK:
        fields["transparency_duties"] = ("art:50:1",)
    return rebuild(base, **fields | changes)


def _uncertain_steps(status: Status) -> dict[str, object]:
    if status is Status.LEGALLY_AMBIGUOUS:
        return {"status": status, "steps": replaced_steps(ambiguous(StepName.HIGH_RISK))}
    if status is Status.NEEDS_MORE_INFORMATION:
        return {"status": status, "steps": replaced_steps(missing_fact(StepName.HIGH_RISK))}
    return {}


def outcome(
    label: BenchmarkCase, predicted: ClassificationResult | None = None, *, failed: bool = False
) -> Outcome:
    """An outcome; without a prediction the worked example's result is used unless `failed`."""
    if failed:
        return Outcome(case=label, result=None)
    return Outcome(case=label, result=predicted or result())
