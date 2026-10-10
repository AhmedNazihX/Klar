"""Failure cases grouped by step (aiact/eval/failures.py)."""

import pytest

from aiact.eval.cases import AppliedAILabel
from aiact.eval.failures import diverging_step, failure, failures_by_step, render_failures
from aiact.schemas import RiskClass, Role, StepName
from tests.eval.outcomes import (
    HIGH_ANNEX_POINT,
    appliedai_case,
    case,
    description_result,
    outcome,
    refused_result,
    result,
    thin_case,
)

R = RiskClass


@pytest.mark.parametrize(
    ("expected", "answered", "step"),
    [
        (R.HIGH_RISK, R.OUT_OF_SCOPE, StepName.SCOPE),
        (R.OUT_OF_SCOPE, R.PROHIBITED, StepName.SCOPE),
        (R.PROHIBITED, R.HIGH_RISK, StepName.PROHIBITED),
        (R.MINIMAL_RISK, R.PROHIBITED, StepName.PROHIBITED),
        (R.HIGH_RISK, R.LIMITED_RISK, StepName.HIGH_RISK),
        (R.MINIMAL_RISK, R.HIGH_RISK, StepName.HIGH_RISK),
        (R.LIMITED_RISK, R.MINIMAL_RISK, StepName.TRANSPARENCY),
        (R.MINIMAL_RISK, R.LIMITED_RISK, StepName.TRANSPARENCY),
    ],
)
def test_a_wrong_class_goes_to_the_first_check_that_parts_them(
    expected: RiskClass, answered: RiskClass, step: StepName
) -> None:
    assert diverging_step(expected, answered) is step


def test_a_right_answer_is_no_failure() -> None:
    assert failure(outcome(case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT))) is None


def test_a_class_miss_shows_both_classes() -> None:
    missed = outcome(case("a"), result(R.MINIMAL_RISK))
    assert failure(missed) == ("high_risk", "expected high_risk, got minimal_risk (decided)")


def test_a_wrong_annex_point_goes_to_the_high_risk_step() -> None:
    missed = outcome(case("a", annex_point="annex:III:1:a"))
    assert failure(missed) == ("high_risk", f"Annex point {HIGH_ANNEX_POINT}")


def test_a_wrong_role_goes_to_the_role_step() -> None:
    missed = outcome(case("a", role=Role.PROVIDER))
    assert failure(missed) == ("role_obligations", "expected role provider, got deployer")


def test_description_misses_go_to_the_facts_node() -> None:
    assert failure(outcome(thin_case("t"), result())) == ("facts", "answered with a class")
    asked = outcome(case("a"), description_result())
    assert failure(asked) == ("facts", "answered with a description request")


def test_an_appliedai_low_label_reads_as_a_low_class() -> None:
    missed = outcome(appliedai_case("ai-1", AppliedAILabel.LOW), result(R.HIGH_RISK))
    assert failure(missed) == ("high_risk", "expected minimal_risk, got high_risk (decided)")


def test_an_appliedai_unclear_miss_has_no_step() -> None:
    missed = outcome(appliedai_case("ai-1", AppliedAILabel.UNCLEAR), result(R.HIGH_RISK))
    group, _ = failure(missed) or ("", "")
    assert group == "uncertain status (appliedAI unclear)"


def test_failed_and_refused_cases() -> None:
    assert failure(outcome(case("a"), failed=True)) == (
        "no result (the classifier failed)",
        "no result",
    )
    assert failure(outcome(case("a"), refused_result())) is None


def test_failures_are_grouped_in_check_order() -> None:
    outcomes = [
        outcome(case("z", role=Role.PROVIDER)),
        outcome(case("b"), result(R.OUT_OF_SCOPE)),
        outcome(case("a"), result(R.OUT_OF_SCOPE)),
        outcome(case("c"), failed=True),
    ]
    groups = failures_by_step(outcomes)
    assert list(groups) == ["scope", "role_obligations", "no result (the classifier failed)"]
    assert groups["scope"] == [
        "a (expected high_risk, got out_of_scope (decided))",
        "b (expected high_risk, got out_of_scope (decided))",
    ]


def test_the_section_lists_each_group() -> None:
    lines = render_failures([outcome(case("a"), result(R.OUT_OF_SCOPE))])
    assert lines[0] == "### Failures by step"
    assert lines[-1] == "- **scope** (1): a (expected high_risk, got out_of_scope (decided))"
    assert render_failures([outcome(case("a"))])[-1] == "No failure cases."
