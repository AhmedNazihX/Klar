"""Made-up cases for the head-to-head tests (V10a); never benchmark cases."""

from aiact.eval.cases import (
    ART_6_3_FILTER,
    OUTSIDE_USE_CASE,
    SAFETY_COMPONENT,
    WITHIN_USE_CASE,
    BenchmarkCase,
    CaseLabel,
    CaseSet,
)
from aiact.schemas import Language, RiskClass, Status

R = RiskClass


def make_case(
    case_id: str,
    risk_class: RiskClass | None,
    *,
    set_name: CaseSet = CaseSet.OWN,
    language: Language = Language.EN,
    status: Status = Status.DECIDED,
    tags: tuple[str, ...] = (),
    bases: tuple[str, ...] = (),
    citation: tuple[str, ...] = ("art:6:2",),
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        set_name=set_name,
        language=language,
        description="A made-up system.",
        label=CaseLabel(risk_class=risk_class, status=status),
        label_citation=citation if risk_class else (),
        source_example_id="hr-ex-001" if bases else None,
        accepted_bases=bases,
        notes=None if status is Status.DECIDED else "What is open, and both readings.",
        tags=tags,
    )


def own(letter: str, risk_class: RiskClass, count: int) -> list[BenchmarkCase]:
    return [
        make_case(f"own-{letter}-{risk_class}-{n}", risk_class, tags=(f"category:{letter}",))
        for n in range(count)
    ]


def commission(
    area: str, risk_class: RiskClass, count: int, basis: str | None = None
) -> list[BenchmarkCase]:
    high_basis = SAFETY_COMPONENT if area == "annex_i" else WITHIN_USE_CASE
    chosen = basis or (high_basis if risk_class is R.HIGH_RISK else OUTSIDE_USE_CASE)
    return [
        make_case(
            f"cb-{area}-{risk_class}-{chosen}-{n}".replace("_", "-"),
            risk_class,
            set_name=CaseSet.COMMISSION_B,
            tags=(f"area:{area}",),
            bases=(chosen,),
        )
        for n in range(count)
    ]


NOT_DRAWABLE = [
    make_case("own-a-de-0", R.LIMITED_RISK, language=Language.DE, tags=("category:a",)),
    make_case("own-c-ambiguous-0", R.PROHIBITED, status=Status.LEGALLY_AMBIGUOUS),
    make_case("own-e-needs-info-0", R.HIGH_RISK, status=Status.NEEDS_MORE_INFORMATION),
    make_case("own-t-thin-0", None, status=Status.NEEDS_MORE_INFORMATION),
    make_case("academic-0001", R.HIGH_RISK, set_name=CaseSet.ACADEMIC),
]
"""German, ambiguous, needs-more-information, thin and non-headline cases: never drawn."""

POOL = [
    *own("a", R.LIMITED_RISK, 6),
    *own("b", R.OUT_OF_SCOPE, 6),
    *own("c", R.PROHIBITED, 6),
    *own("d", R.HIGH_RISK, 3),
    *own("d", R.MINIMAL_RISK, 2),
    *own("e", R.HIGH_RISK, 3),
    *own("e", R.MINIMAL_RISK, 2),
    *commission("annex_iii_4", R.HIGH_RISK, 5),
    *commission("annex_iii_4", R.MINIMAL_RISK, 5),
    *commission("annex_iii_5", R.MINIMAL_RISK, 4, basis=ART_6_3_FILTER),
    *commission("annex_i", R.HIGH_RISK, 2),
    *NOT_DRAWABLE,
]
"""A pool where every class has at least five drawable cases and every step at least four."""
