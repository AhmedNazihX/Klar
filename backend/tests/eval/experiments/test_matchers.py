"""The shared replay states and label matchers (X2; used by the E3, E5 and E7 replays and the smoke
test). The replays themselves prove the matchers keep the committed recordings' outcomes; these
tests pin each rule with made-up outcomes."""

from datetime import date

import pytest

from aiact.engine.state import CheckOutcome
from aiact.eval.experiments import matchers
from aiact.eval.experiments.matchers import WORKED_EXAMPLE
from aiact.schemas import (
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    RiskClass,
    Role,
    Status,
    StepName,
)
from tests.eval.experiments.builders import (
    case,
    high_risk_outcome,
    role_outcome,
    scope_outcome,
    step,
)

AS_OF = date(2026, 9, 30)


# --- States -------------------------------------------------------------------------------------


def test_the_replay_state_has_no_facts_answers_exclusions_or_steps() -> None:
    assert matchers.replay_state(case("e-1"), AS_OF) == {
        "description": "A made-up system (e-1).",
        "language": Language.EN,
        "law_version": LawVersion.AMENDED,
        "as_of": AS_OF,
        "exclude_source_example_ids": (),
        "facts": (),
        "steps": (),
        "matches": (),
    }


def test_a_dated_case_replays_at_its_own_date() -> None:
    dated = case("c-1", RiskClass.PROHIBITED).model_copy(update={"as_of": date(2026, 12, 15)})
    assert matchers.replay_state(dated, AS_OF)["as_of"] == date(2026, 12, 15)
    assert matchers.role_check_state(dated, AS_OF)["as_of"] == date(2026, 12, 15)
    assert matchers.replay_state(case("c-2"), AS_OF)["as_of"] == AS_OF


@pytest.mark.parametrize(
    ("risk_class", "annex_point", "expected"),
    [
        (RiskClass.HIGH_RISK, ("annex:III:4:a",), {"high_risk_route": HighRiskRoute.ANNEX_III}),
        (RiskClass.HIGH_RISK, ("annex:I:A:11",), {"high_risk_route": HighRiskRoute.ANNEX_I}),
        (RiskClass.HIGH_RISK, (), {"high_risk_route": HighRiskRoute.ANNEX_III}),
        (RiskClass.LIMITED_RISK, (), {"transparency_duties": ("art:50:1",)}),
        (RiskClass.PROHIBITED, (), {"matches": (StepName.PROHIBITED,)}),
        (RiskClass.MINIMAL_RISK, (), {}),
    ],
)
def test_the_role_check_gets_the_class_the_label_settles(
    risk_class: RiskClass, annex_point: tuple[str, ...], expected: dict[str, object]
) -> None:
    labelled = case("d-1", risk_class, annex_point=annex_point)
    state = matchers.role_check_state(labelled, AS_OF)
    assert state == {**matchers.replay_state(labelled, AS_OF), **expected}


def test_the_role_check_runs_in_scope_on_a_labelled_role() -> None:
    assert matchers.runs_role_check(case("d-1"))
    assert not matchers.runs_role_check(case("d-2", RiskClass.OUT_OF_SCOPE))
    assert not matchers.runs_role_check(case("d-3", role=None))


# --- Scope --------------------------------------------------------------------------------------


def test_scope_matches_out_of_scope_with_the_label_citation_first() -> None:
    labelled = case("b-1", RiskClass.OUT_OF_SCOPE, citation=("art:2:3", "art:3:1"))
    assert matchers.scope_matches(scope_outcome(True, cited=("art:3:1", "art:2:3")), labelled)
    assert not matchers.scope_matches(scope_outcome(True, cited=("art:3:1",)), labelled)
    assert not matchers.scope_matches(scope_outcome(False, cited=("art:2:3",)), labelled)


def test_scope_matches_in_scope_on_the_status() -> None:
    labelled = case("b-2", RiskClass.MINIMAL_RISK, status=Status.LEGALLY_AMBIGUOUS)
    assert matchers.scope_matches(scope_outcome(False, Status.LEGALLY_AMBIGUOUS), labelled)
    assert not matchers.scope_matches(scope_outcome(False), labelled)


# --- High risk ----------------------------------------------------------------------------------


def test_high_risk_matches_the_annex_i_point_from_the_tags() -> None:
    labelled = case("e-1", tags=("annex_i_point:annex:I:A:11",))
    right = high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:A:11")
    assert matchers.high_risk_matches(right, labelled)
    wrong_route = high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:I:A:11")
    assert not matchers.high_risk_matches(wrong_route, labelled)
    wrong_point = high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:A:12")
    assert not matchers.high_risk_matches(wrong_point, labelled)


def test_the_worked_example_must_cite_art_6_3() -> None:
    """As its E5 replay requires: ranking is profiling, so Art. 6(3) is cited and rejected."""
    cited = high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:III:4:a", cited=("art:6:3",))
    assert matchers.high_risk_matches(cited, WORKED_EXAMPLE)
    second = high_risk_outcome(
        HighRiskRoute.ANNEX_III, "annex:III:4:a", cited=("annex:III:4:a", "art:6:3")
    )
    assert matchers.high_risk_matches(second, WORKED_EXAMPLE)  # not only the first citation
    uncited = high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:III:4:a", cited=("art:6:2",))
    assert not matchers.high_risk_matches(uncited, WORKED_EXAMPLE)
    wrong_route = high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:III:4:a", cited=("art:6:3",))
    assert not matchers.high_risk_matches(wrong_route, WORKED_EXAMPLE)


def test_a_label_point_in_annex_iii_expects_annex_iii() -> None:
    assert matchers.expected_route(case("e-9", annex_point=("annex:III:5:d",))) is (
        HighRiskRoute.ANNEX_III
    )
    assert matchers.expected_route(case("e-9")) is HighRiskRoute.ANNEX_I


@pytest.mark.parametrize(
    "points", [("annex:I:A:11", "annex:III:5:d"), ("annex:III:5:d", "annex:I:A:11")]
)
def test_a_label_on_both_annexes_sets_both_routes_whatever_the_order(
    points: tuple[str, ...],
) -> None:
    """The role check is told Annex I (the earlier check's route for an Annex I point), and the
    high-risk check is expected to prefer Annex III."""
    labelled = case("e-16", annex_point=points)
    state = matchers.role_check_state(labelled, AS_OF)
    assert state.get("high_risk_route") is HighRiskRoute.ANNEX_I
    assert matchers.expected_route(labelled) is HighRiskRoute.ANNEX_III


def test_any_of_several_label_points_matches() -> None:
    labelled = case("e-15", annex_point=("annex:III:5:a", "annex:III:5:d"))
    assert matchers.expected_route(labelled) is HighRiskRoute.ANNEX_III
    for point in ("annex:III:5:a", "annex:III:5:d"):
        outcome = high_risk_outcome(HighRiskRoute.ANNEX_III, point)
        assert matchers.high_risk_matches(outcome, labelled)
    other = high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:III:5:b")
    assert not matchers.high_risk_matches(other, labelled)


def test_high_risk_on_both_routes_expects_annex_iii() -> None:
    labelled = case("e-14", tags=("annex_i_point:annex:I:A:11", "also_route:annex_iii"))
    outcome = high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:I:A:11")
    assert matchers.high_risk_matches(outcome, labelled)


def test_high_risk_asks_the_tagged_missing_fact() -> None:
    labelled = case(
        "e-7",
        status=Status.NEEDS_MORE_INFORMATION,
        tags=("annex_i_point:annex:I:B:21", "missing_fact:third_party_assessment"),
    )
    asked = high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:B:21", Status.NEEDS_MORE_INFORMATION)
    assert matchers.high_risk_matches(asked, labelled)
    other = FollowUpQuestion(id="intended_purpose", text="What is it for?")
    wrong = high_risk_outcome(
        HighRiskRoute.ANNEX_I, "annex:I:B:21", Status.NEEDS_MORE_INFORMATION, missing=other
    )
    assert not matchers.high_risk_matches(wrong, labelled)


def test_a_decided_section_b_case_names_art_2_2() -> None:
    labelled = case("e-5", tags=("annex_i_point:annex:I:B:18", "annex_i_section:b"))
    named = "High-risk. Under Art. 2(2) only Art. 6(1) applies."
    assert matchers.high_risk_matches(
        high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:B:18", decision=named), labelled
    )
    assert not matchers.high_risk_matches(
        high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:B:18"), labelled
    )


def _exempt(cited: tuple[str, ...], status: Status = Status.DECIDED) -> CheckOutcome:
    return CheckOutcome(step=step(StepName.HIGH_RISK, status, cited), annex_iii_exempt=True)


EXEMPT_LABEL = case(
    "f-90",
    RiskClass.MINIMAL_RISK,
    citation=("annex:III:4:b", "art:6:3", "art:6:3:c"),
    tags=(matchers.EXEMPTION_TRAP,),
)
"""A made-up own/f-style case labelled not high-risk on an Art. 6(3) condition."""


def test_an_exemption_case_matches_an_exempt_step_on_its_point() -> None:
    """E19's own/f matcher: a case labelled on an Art. 6(3) condition matches a decided exempt
    step that cites one of its Annex III points and an Art. 6(3) condition."""
    exempt = _exempt(("annex:III:4:b", "art:6:2", "art:6:3", "art:6:3:c", "art:6:4"))
    assert matchers.high_risk_or_exempt_matches(exempt, EXEMPT_LABEL)
    assert not matchers.high_risk_matches(exempt, EXEMPT_LABEL)


@pytest.mark.parametrize(
    "outcome",
    [
        pytest.param(_exempt(("annex:III:4:a", "art:6:3:c")), id="another-point"),
        pytest.param(_exempt(("annex:III:4:b", "art:6:3")), id="no-condition-cited"),
        pytest.param(
            _exempt(("annex:III:4:b", "art:6:3:c"), Status.NEEDS_MORE_INFORMATION),
            id="not-decided",
        ),
        pytest.param(
            high_risk_outcome(HighRiskRoute.ANNEX_III, "annex:III:4:b", cited=("art:6:3",)),
            id="high-risk",
        ),
    ],
)
def test_an_exemption_case_matches_no_other_step(outcome: CheckOutcome) -> None:
    assert not matchers.high_risk_or_exempt_matches(outcome, EXEMPT_LABEL)


def test_only_a_case_tagged_on_art_6_3_accepts_an_exempt_step() -> None:
    untagged = EXEMPT_LABEL.model_copy(update={"tags": ()})
    exempt = _exempt(("annex:III:4:b", "art:6:3:c"))
    assert not matchers.high_risk_or_exempt_matches(exempt, untagged)
    not_high_risk = high_risk_outcome(None, None)
    assert matchers.high_risk_or_exempt_matches(not_high_risk, untagged)
    assert matchers.high_risk_or_exempt_matches(not_high_risk, EXEMPT_LABEL)


def test_a_not_high_risk_label_expects_no_route_and_its_status() -> None:
    labelled = case("e-2", RiskClass.MINIMAL_RISK)
    assert matchers.high_risk_matches(high_risk_outcome(None, None), labelled)
    routed = high_risk_outcome(HighRiskRoute.ANNEX_I, "annex:I:A:4")
    assert not matchers.high_risk_matches(routed, labelled)
    exempt = CheckOutcome(step=step(StepName.HIGH_RISK), annex_iii_exempt=True)
    assert not matchers.high_risk_matches(exempt, labelled)


# --- Role ---------------------------------------------------------------------------------------


def test_role_matches_the_role_and_an_ambiguous_status() -> None:
    assert matchers.role_matches(role_outcome(Role.DEPLOYER), case("d-1", role=Role.DEPLOYER))
    assert not matchers.role_matches(role_outcome(Role.PROVIDER), case("d-1", role=Role.DEPLOYER))
    ambiguous = case("d-2", status=Status.LEGALLY_AMBIGUOUS)
    assert matchers.role_matches(role_outcome(Role.PROVIDER, Status.LEGALLY_AMBIGUOUS), ambiguous)
    assert not matchers.role_matches(role_outcome(Role.PROVIDER), ambiguous)
    decided = case("d-3", role=Role.PROVIDER)
    asking = role_outcome(Role.PROVIDER, Status.NEEDS_MORE_INFORMATION)
    assert matchers.role_matches(asking, decided)  # the status counts only for an ambiguous label


def test_a_role_outcome_without_a_role_does_not_match() -> None:
    outcome = CheckOutcome(step=step(StepName.ROLE_OBLIGATIONS))
    assert not matchers.role_matches(outcome, case("d-1"))
