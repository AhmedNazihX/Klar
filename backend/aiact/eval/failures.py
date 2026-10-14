"""A run's failure cases, grouped by the engine step to look at first (V8: to guide the fixes).

Each missed case is put under one step, read from the label and the result alone (no trace):
- **a wrong class** goes to the first check, in the Act's order, where the expected and the
  answered class part ways: either is `out_of_scope` -> scope; either is `prohibited` ->
  prohibited; either is `high_risk` -> high_risk; otherwise (limited against minimal) ->
  transparency. An appliedAI `low` label reads as `minimal_risk`, as its mapping accepts either
  low class;
- **a right class with a wrong Annex point** -> high_risk; **a wrong role** -> role_obligations;
- **a thin case answered with a class, or another case answered with a description request**
  -> facts (E13);
- **no result** (the classifier failed) is listed apart, as is an uncertain-status miss on an
  appliedAI `unclear` label, which no step decides on its own.
Not-assessed cases (decision 030) aren't failures: the refusal section lists them. Legally
ambiguous labels aren't scored on their class (`metrics.risk_class_match`), so they never land
here. The list names case ids and classes only, never a description.
"""

from collections import defaultdict
from collections.abc import Sequence
from enum import StrEnum

from aiact.eval.cases import AppliedAILabel, CaseLabel
from aiact.eval.metrics import (
    APPLIEDAI_CLASS,
    Outcome,
    annex_point_match,
    description_asked,
    description_asked_wrongly,
    is_not_assessed,
    risk_class_match,
    role_match,
)
from aiact.schemas import RiskClass, StepName

FACTS_GROUP = "facts"
"""The facts node, which ends a run that asks for a description (E13); not a `StepName`."""
FAILED_GROUP = "no result (the classifier failed)"
STATUS_GROUP = "uncertain status (appliedAI unclear)"
GROUP_ORDER: tuple[str, ...] = (
    FACTS_GROUP,
    *(step.value for step in StepName),
    STATUS_GROUP,
    FAILED_GROUP,
)
DIVERGING_CLASSES: tuple[tuple[RiskClass, StepName], ...] = (
    (RiskClass.OUT_OF_SCOPE, StepName.SCOPE),
    (RiskClass.PROHIBITED, StepName.PROHIBITED),
    (RiskClass.HIGH_RISK, StepName.HIGH_RISK),
)
"""The first check, in the Act's order, that decides a class; anything else is Art. 50's."""


def diverging_step(expected: RiskClass, answered: RiskClass) -> StepName:
    """The first check where `expected` and `answered` part ways."""
    pair = {expected, answered}
    return next((step for cls, step in DIVERGING_CLASSES if cls in pair), StepName.TRANSPARENCY)


def _expected_class(outcome: Outcome) -> RiskClass | None:
    label = outcome.case.label
    if isinstance(label, CaseLabel):
        return label.risk_class
    if label is AppliedAILabel.LOW:
        return RiskClass.MINIMAL_RISK
    return APPLIEDAI_CLASS.get(label)


def failure(outcome: Outcome) -> tuple[str, str] | None:
    """The group a missed case goes under and what it shows (expected against answered), or
    None when the case isn't a failure."""
    result = outcome.result
    if is_not_assessed(outcome):
        return None
    if result is None:
        return (FAILED_GROUP, "no result") if _is_scored(outcome) else None
    if description_asked(outcome) is False or description_asked_wrongly(outcome) is True:
        shown = "a class" if result.risk_class else "a description request"
        return FACTS_GROUP, f"answered with {shown}"
    if risk_class_match(outcome) is False and result.risk_class is not None:
        expected = _expected_class(outcome)
        shown = f"expected {_name(expected)}, got {result.risk_class.value} ({result.status.value})"
        if expected is None:
            return STATUS_GROUP, shown
        return diverging_step(expected, result.risk_class).value, shown
    if annex_point_match(outcome) is False:
        return StepName.HIGH_RISK.value, f"Annex point {result.annex_point}"
    if role_match(outcome) is False:
        label = outcome.case.label
        expected_role = label.role if isinstance(label, CaseLabel) else None
        return StepName.ROLE_OBLIGATIONS.value, (
            f"expected role {_name(expected_role)}, got {_name(result.role)}"
        )
    return None


def _is_scored(outcome: Outcome) -> bool:
    """Whether a failed case counts as a miss somewhere (a thin or a class-scored label)."""
    return description_asked(outcome) is False or risk_class_match(outcome) is False


def _name(value: StrEnum | None) -> str:
    return "none" if value is None else value.value


def failures_by_step(outcomes: Sequence[Outcome]) -> dict[str, list[str]]:
    """Each group's failed cases, as `<case id> (<what it shows>)`, in check order."""
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for outcome in sorted(outcomes, key=lambda o: o.case.id):
        found = failure(outcome)
        if found is not None:
            group, shown = found
            groups[group].append(f"{outcome.case.id} ({shown})")
    return {group: groups[group] for group in GROUP_ORDER if groups[group]}


def render_failures(outcomes: Sequence[Outcome], *, should_name_cases: bool = True) -> list[str]:
    """The run report's failure section, as markdown lines; without `should_name_cases`, each
    group's count only (a Pile B run's printed report, V11)."""
    groups = failures_by_step(outcomes)
    lines = ["### Failures by step", ""]
    if not groups:
        return [*lines, "No failure cases."]
    for group, cases in groups.items():
        named = f": {'; '.join(cases)}" if should_name_cases else ""
        lines.append(f"- **{group}** ({len(cases)}){named}")
    return lines
