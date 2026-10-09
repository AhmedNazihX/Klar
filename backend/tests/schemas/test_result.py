import pytest
from pydantic import ValidationError

from aiact.schemas import (
    ClassificationResult,
    FollowUpQuestion,
    RiskClass,
    Role,
    Status,
    StepName,
)
from tests.schemas.builders import (
    ambiguous,
    dumped_steps,
    ends_early,
    missing_fact,
    rebuild,
    refused,
    steps_with,
    stored_before_decision_030,
)
from tests.schemas.worked_example import OBLIGATIONS, worked_example_result


def test_worked_example_is_a_valid_high_risk_deployer_result() -> None:
    result = worked_example_result()
    assert result.risk_class is RiskClass.HIGH_RISK
    assert result.role is Role.DEPLOYER
    assert result.annex_point == "annex:III:4:a"
    assert result.status is Status.DECIDED
    assert [step.step for step in result.steps] == list(StepName)


def test_result_round_trips_through_json() -> None:
    result = worked_example_result()
    assert ClassificationResult.model_validate_json(result.model_dump_json()) == result


def test_result_is_immutable() -> None:
    result = worked_example_result()
    with pytest.raises(ValidationError, match="frozen"):
        result.risk_class = RiskClass.MINIMAL_RISK  # pyright: ignore[reportAttributeAccessIssue]


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        rebuild(worked_example_result(), confidence=0.9)


# class-specific fields


def test_limited_risk_without_transparency_duties_is_rejected() -> None:
    with pytest.raises(ValidationError, match="transparency_duties"):
        rebuild(worked_example_result(), risk_class=RiskClass.LIMITED_RISK)


def test_limited_risk_with_transparency_duties_is_accepted() -> None:
    result = rebuild(
        worked_example_result(),
        risk_class=RiskClass.LIMITED_RISK,
        transparency_duties=("art:50:1",),
    )
    assert result.transparency_duties == ("art:50:1",)


@pytest.mark.parametrize(
    "field",
    [
        {"obligations": OBLIGATIONS},
        {"annex_point": "annex:III:4:a"},
        {"transparency_duties": ("art:50:1",)},
    ],
)
def test_out_of_scope_with_class_fields_is_rejected(field: dict[str, object]) -> None:
    result = ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(1), Status.DECIDED)
    with pytest.raises(ValidationError, match="out_of_scope result has no"):
        rebuild(result, **field)


# role


def test_role_step_without_role_is_rejected() -> None:
    with pytest.raises(ValidationError, match="role is set exactly"):
        rebuild(worked_example_result(), role=None)


def test_role_without_role_step_is_rejected() -> None:
    result = ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(1), Status.DECIDED)
    with pytest.raises(ValidationError, match="role is set exactly"):
        rebuild(result, role=Role.DEPLOYER)


def test_role_switch_reason_without_role_is_rejected() -> None:
    result = ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(1), Status.DECIDED)
    with pytest.raises(ValidationError, match="role_switch_reason and also_role need a role"):
        rebuild(result, role_switch_reason="Rebranded the system")


def test_also_role_without_role_is_rejected() -> None:
    result = ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(1), Status.DECIDED)
    with pytest.raises(ValidationError, match="role_switch_reason and also_role need a role"):
        rebuild(result, also_role=Role.DEPLOYER)


def test_also_role_is_kept_next_to_a_different_role() -> None:
    result = rebuild(worked_example_result(), role=Role.PROVIDER, also_role=Role.DEPLOYER)
    assert (result.role, result.also_role) == (Role.PROVIDER, Role.DEPLOYER)
    with pytest.raises(ValidationError, match="also_role must differ from role"):
        rebuild(worked_example_result(), also_role=Role.DEPLOYER)


def test_legal_review_is_an_optional_line() -> None:
    assert worked_example_result().legal_review is None
    line = "Have this result reviewed by a lawyer."
    assert rebuild(worked_example_result(), legal_review=line).legal_review == line


# steps the provider refused (decision 029)


def test_not_assessed_names_exactly_the_refused_steps() -> None:
    steps = steps_with(refused(StepName.HIGH_RISK))
    result = rebuild(
        worked_example_result(),
        steps=steps,
        status=Status.NEEDS_MORE_INFORMATION,
        not_assessed=(StepName.HIGH_RISK,),
    )
    assert result.not_assessed == (StepName.HIGH_RISK,)
    with pytest.raises(ValidationError, match="not_assessed must name exactly"):
        rebuild(result, not_assessed=())
    with pytest.raises(ValidationError, match="not_assessed must name exactly"):
        rebuild(worked_example_result(), not_assessed=(StepName.SCOPE,))


# a refused check gives no class (decision 030)


def _refused_result(
    name: StepName = StepName.PROHIBITED, **changes: object
) -> ClassificationResult:
    """The worked example with `name` refused: no class and nothing a class brings."""
    fields: dict[str, object] = {
        "steps": steps_with(refused(name)),
        "risk_class": None,
        "status": Status.NEEDS_MORE_INFORMATION,
        "annex_point": None,
        "obligations": (),
        "not_assessed": (name,),
    }
    return rebuild(worked_example_result(), **fields | changes)


@pytest.mark.parametrize("name", list(StepName))
def test_a_result_with_a_refused_check_may_have_no_class(name: StepName) -> None:
    role = None if name is StepName.ROLE_OBLIGATIONS else Role.DEPLOYER
    result = _refused_result(name, role=role)
    assert result.risk_class is None
    assert result.not_assessed == (name,)
    assert not result.needs_description
    assert ClassificationResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    "field",
    [
        {"annex_point": "annex:III:4:a"},
        {"transparency_duties": ("art:50:1",)},
        {"legal_review": "Have this result reviewed by a lawyer."},
        {"obligations": OBLIGATIONS},
    ],
)
def test_a_result_with_a_refused_check_lists_nothing_a_class_brings(
    field: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="refused check has no obligations"):
        _refused_result(StepName.PROHIBITED, **field)


def test_a_refused_role_step_sets_no_role() -> None:
    assert _refused_result(StepName.ROLE_OBLIGATIONS, role=None).role is None
    with pytest.raises(ValidationError, match="present and not refused"):
        _refused_result(StepName.ROLE_OBLIGATIONS, role=Role.DEPLOYER)


def test_a_result_stored_before_decision_030_still_loads() -> None:
    """Before X2b a refused step kept its stricter reading as the class (decision 029)."""
    stored = stored_before_decision_030(worked_example_result()).model_dump(mode="json")
    loaded = ClassificationResult.model_validate(stored)
    assert loaded.risk_class is RiskClass.HIGH_RISK
    assert loaded.assessed_class is None  # never stated: it rests on a check not assessed


def test_a_result_stored_before_decision_030_with_a_refused_role_step_keeps_its_role() -> None:
    """Under decision 029 a refused role step kept the role it assumed, next to the class."""
    stored = stored_before_decision_030(worked_example_result(), StepName.ROLE_OBLIGATIONS)
    loaded = ClassificationResult.model_validate(stored.model_dump(mode="json"))
    assert (loaded.risk_class, loaded.role) == (RiskClass.HIGH_RISK, Role.DEPLOYER)


def test_a_classified_result_states_its_class() -> None:
    assert worked_example_result().assessed_class is RiskClass.HIGH_RISK
    assert _refused_result().assessed_class is None


def test_a_result_with_steps_and_no_class_needs_a_refused_check() -> None:
    with pytest.raises(
        ValidationError, match="has a class unless the model provider refused a check"
    ):
        rebuild(worked_example_result(), risk_class=None, annex_point=None, obligations=())


def test_a_refused_result_cut_short_is_rejected() -> None:
    """A run with a refused check lists every check unless a stopping check decided."""
    with pytest.raises(ValidationError, match="lists every check, or ends after a stopping"):
        _refused_result(StepName.SCOPE, steps=steps_with(refused(StepName.SCOPE), 1), role=None)
    with pytest.raises(ValidationError, match="lists every check, or ends after a stopping"):
        _refused_result(
            StepName.PROHIBITED, steps=steps_with(refused(StepName.PROHIBITED), 2), role=None
        )


def test_a_refused_result_may_end_after_a_stopping_check_that_decided() -> None:
    """Scope refused, then a decided Art. 5 step ends the run: no class, two steps."""
    result = _refused_result(
        StepName.SCOPE, steps=steps_with(refused(StepName.SCOPE), 2), role=None
    )
    assert [step.step for step in result.steps] == [StepName.SCOPE, StepName.PROHIBITED]
    assert result.risk_class is None


# status derived from the steps


@pytest.mark.parametrize("status", [Status.NEEDS_MORE_INFORMATION, Status.LEGALLY_AMBIGUOUS])
def test_uncertain_result_without_an_uncertain_step_is_rejected(status: Status) -> None:
    with pytest.raises(ValidationError, match="steps imply status decided"):
        rebuild(worked_example_result(), status=status)


def test_decided_result_with_an_uncertain_step_is_rejected() -> None:
    steps = steps_with(ambiguous(StepName.HIGH_RISK))
    with pytest.raises(ValidationError, match="steps imply status legally_ambiguous"):
        rebuild(worked_example_result(), steps=steps)


def test_ambiguous_step_outranks_missing_information() -> None:
    steps = steps_with(missing_fact(StepName.SCOPE))
    steps[2] = ambiguous(StepName.HIGH_RISK).model_dump()
    with pytest.raises(ValidationError, match="steps imply status legally_ambiguous"):
        rebuild(worked_example_result(), status=Status.NEEDS_MORE_INFORMATION, steps=steps)
    result = rebuild(worked_example_result(), status=Status.LEGALLY_AMBIGUOUS, steps=steps)
    assert result.status is Status.LEGALLY_AMBIGUOUS


def test_needs_more_information_result_with_its_step_is_accepted() -> None:
    steps = steps_with(missing_fact(StepName.SCOPE))
    result = rebuild(worked_example_result(), status=Status.NEEDS_MORE_INFORMATION, steps=steps)
    missing = result.steps[0].missing_fact
    assert missing is not None
    assert missing.id == "eu_use"


# follow-up questions


def test_duplicate_follow_up_ids_are_rejected() -> None:
    good = worked_example_result()
    question = good.follow_up_questions[0].model_dump()
    with pytest.raises(ValidationError, match="ids must be unique"):
        rebuild(good, follow_up_questions=[question, question])


def test_missing_fact_absent_from_follow_ups_is_rejected() -> None:
    good = worked_example_result()
    steps = steps_with(missing_fact(StepName.SCOPE))
    with pytest.raises(ValidationError, match="must appear"):
        rebuild(
            good,
            status=Status.NEEDS_MORE_INFORMATION,
            steps=steps,
            follow_up_questions=good.follow_up_questions[:1],
        )


def test_missing_fact_with_different_follow_up_text_is_rejected() -> None:
    good = worked_example_result()
    reworded = FollowUpQuestion(id="eu_use", text="Where is the tool used?")
    with pytest.raises(ValidationError, match="same text"):
        rebuild(
            good,
            status=Status.NEEDS_MORE_INFORMATION,
            steps=steps_with(missing_fact(StepName.SCOPE)),
            follow_up_questions=(good.follow_up_questions[0], reworded),
        )


@pytest.mark.parametrize("bad_id", ["", "Ranks_People", "ranks-people", "1st", "a" * 65])
def test_follow_up_id_must_be_a_slug(bad_id: str) -> None:
    with pytest.raises(ValidationError, match="pattern"):
        FollowUpQuestion(id=bad_id, text="Does the tool rank people?")


def test_a_result_stored_before_e12_still_loads() -> None:
    """Stored benchmark predictions (eval_case_results) hold each reading as plain text and no
    law-text label; `aiact evaluate report` validates them again."""
    stored = worked_example_result().model_dump(mode="json", exclude={"law_text"})
    high_risk = next(step for step in stored["steps"] if step["step"] == "high_risk")
    high_risk.update(
        status="legally_ambiguous",
        open_question={"question": "Is ranking profiling?", "readings": ["Yes.", "No."]},
    )
    stored["status"] = "legally_ambiguous"
    result = ClassificationResult.model_validate(stored)
    question = result.steps[2].open_question
    assert question is not None
    stricter, lenient = question.readings
    assert (stricter.title, stricter.explanation, stricter.is_applied) == (None, "Yes.", True)
    assert (lenient.explanation, lenient.is_applied, lenient.risk_class) == ("No.", False, None)
    assert (stricter.citation, stricter.consequence) == (None, None)
    assert result.law_text.celex == "02024R1689-20260727"
