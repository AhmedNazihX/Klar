"""The follow-up question's screen fields (E12): hint, answer options and what a yes settles."""

from datetime import date

import pytest
from pydantic import ValidationError

from aiact.schemas import (
    YES_NO,
    AnswerOption,
    AnswerOutcome,
    FollowUpQuestion,
    HighRiskRoute,
    RiskClass,
)

ANNEX_I_YES = AnswerOutcome(
    risk_class=RiskClass.HIGH_RISK,
    high_risk_route=HighRiskRoute.ANNEX_I,
    provision_id="annex:I:A:11",
    duties_from=date(2028, 8, 2),
)


def test_a_question_defaults_to_words_with_no_hint_or_outcome() -> None:
    question = FollowUpQuestion(id="output_use", text="Who reads the score?")
    assert (question.hint, question.options, question.if_yes, question.citations) == (
        None,
        (),
        None,
        (),
    )


def test_a_yes_no_question_carries_its_hint_options_and_what_a_yes_settles() -> None:
    question = FollowUpQuestion(
        id="third_party_assessment",
        text="Must the product undergo a third-party conformity assessment?",
        about="art:6:1:b",
        hint="The answer decides whether the system is high-risk (Art. 6(1)(b)).",
        options=YES_NO,
        if_yes=ANNEX_I_YES,
    )
    dumped = question.model_dump(mode="json")
    assert dumped["options"] == ["yes", "no", "not_sure"]
    assert dumped["if_yes"] == {
        "risk_class": "high_risk",
        "high_risk_route": "annex_i",
        "provision_id": "annex:I:A:11",
        "duties_from": "2028-08-02",
    }
    assert FollowUpQuestion.model_validate(dumped) == question


@pytest.mark.parametrize(
    "options",
    [
        (AnswerOption.YES, AnswerOption.NO),
        (AnswerOption.NO, AnswerOption.YES, AnswerOption.NOT_SURE),
    ],
)
def test_options_are_all_three_in_order_or_none(options: tuple[AnswerOption, ...]) -> None:
    with pytest.raises(ValidationError, match="options are either empty"):
        FollowUpQuestion(id="profiling", text="Does it profile people?", options=options)


def test_only_a_yes_no_question_says_what_a_yes_settles() -> None:
    with pytest.raises(ValidationError, match="if_yes needs a yes/no question"):
        FollowUpQuestion(id="output_use", text="Who reads the score?", if_yes=ANNEX_I_YES)


def test_there_is_no_if_no_field() -> None:
    """Decision 026 item 13: a "no" predicts no class; the screen shows a fixed sentence."""
    with pytest.raises(ValidationError, match="if_no"):
        FollowUpQuestion.model_validate(
            {"id": "profiling", "text": "Profiles?", "if_no": {"risk_class": "minimal_risk"}}
        )


def test_a_section_b_outcome_has_no_duties_date() -> None:
    outcome = AnswerOutcome(
        risk_class=RiskClass.HIGH_RISK,
        high_risk_route=HighRiskRoute.ANNEX_I,
        provision_id="annex:I:B:21",
    )
    assert outcome.duties_from is None


def test_only_a_high_risk_outcome_names_a_route() -> None:
    with pytest.raises(ValidationError, match="high_risk_route"):
        AnswerOutcome(risk_class=RiskClass.LIMITED_RISK, high_risk_route=HighRiskRoute.ANNEX_III)
