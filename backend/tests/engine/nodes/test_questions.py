"""The questions a step puts to the user, as the screens show them (aiact/engine/nodes/questions.py,
E12): provision labels, hints, answer options and the structured readings."""

from datetime import date

import pytest

from aiact.engine.nodes import high_risk_texts, prohibited_texts, role_texts, transparency_texts
from aiact.engine.nodes.questions import (
    ReadingSide,
    ask,
    hint,
    open_question,
    provision_label,
)
from aiact.llm import replies
from aiact.schemas import (
    YES_NO,
    AnswerOutcome,
    Citation,
    HighRiskRoute,
    Language,
    LawVersion,
    RiskClass,
    StepName,
)

EN, DE = Language.EN, Language.DE
ART_6_3_A = Citation(
    provision_id="art:6:3:a",
    document_id="ai-act-consolidated",
    law_version=LawVersion.AMENDED,
    language=EN,
    quote="the AI system is intended to perform a narrow procedural task;",
)
POINT_4_A = ART_6_3_A.model_copy(update={"provision_id": "annex:III:4:a", "quote": "Recruitment"})
PLAIN = replies.OpenQuestion(
    question="Is copying CV fields a narrow procedural task?",
    readings=("It feeds the shortlist.", "It only copies fields."),
)


@pytest.mark.parametrize(
    ("provision_id", "english", "german"),
    [
        ("art:6:1:b", "Art. 6(1)(b)", "Art. 6 Abs. 1 Buchst. b"),
        ("art:3:3", "Art. 3(3)", "Art. 3 Nr. 3"),
        ("art:5:1:c:i", "Art. 5(1)(c)(i)", "Art. 5 Abs. 1 Buchst. c Ziff. i"),
        ("art:50", "Art. 50", "Art. 50"),
        ("annex:III:5:a", "Annex III point 5(a)", "Anhang III Nummer 5 Buchstabe a"),
        ("annex:I:A:11", "Annex I Section A point 11", "Anhang I Abschnitt A Nummer 11"),
        ("recital:12", "recital:12", "recital:12"),
    ],
)
def test_a_provision_is_labelled_as_the_act_writes_it(
    provision_id: str, english: str, german: str
) -> None:
    assert (provision_label(provision_id, EN), provision_label(provision_id, DE)) == (
        english,
        german,
    )


def test_the_hint_names_the_provision_the_answer_decides() -> None:
    assert hint(StepName.HIGH_RISK, "art:6:1:b", EN) == (
        "The answer decides whether the system is high-risk (Art. 6(1)(b))."
    )
    assert hint(StepName.HIGH_RISK, "art:6:1:b", DE) == (
        "Die Antwort entscheidet, ob das System hochriskant ist (Art. 6 Abs. 1 Buchst. b)."
    )


@pytest.mark.parametrize("step", list(StepName))
@pytest.mark.parametrize("language", [EN, DE])
def test_every_step_has_a_hint_in_both_languages(step: StepName, language: Language) -> None:
    assert "Art. 4" in hint(step, "art:4", language)


def test_a_yes_no_key_question_offers_yes_no_and_not_sure() -> None:
    question = ask(high_risk_texts.PROFILING, EN, StepName.HIGH_RISK)
    assert question.options == YES_NO
    assert question.about == "art:6:3"
    assert question.hint == "The answer decides whether the system is high-risk (Art. 6(3))."


@pytest.mark.parametrize(
    "key",
    [
        high_risk_texts.ANNEX_III_USE,
        high_risk_texts.PUBLIC_SCHEME,
        high_risk_texts.PERSON_REVIEW,
        prohibited_texts.SIGNIFICANT_HARM,
        transparency_texts.MARKET_DATE,
        role_texts.OPERATOR_ROLE,
    ],
)
def test_a_question_answered_in_words_offers_no_options_and_no_outcome(
    key: role_texts.KeyQuestion,
) -> None:
    outcome = AnswerOutcome(risk_class=RiskClass.HIGH_RISK)
    question = ask(key, EN, StepName.HIGH_RISK, if_yes=outcome)
    assert (question.options, question.if_yes) == ((), None)


@pytest.mark.parametrize(
    ("key", "english", "german"),
    [
        (role_texts.SWITCHES["own_brand"], "Art. 25(1)(a)", "Art. 25 Abs. 1 Buchst. a"),
        (role_texts.SWITCHES["changed_purpose"], "Art. 25(1)(c)", "Art. 25 Abs. 1 Buchst. c"),
        (
            role_texts.SWITCHES["substantial_modification"],
            "Art. 25(1)(b)",
            "Art. 25 Abs. 1 Buchst. b",
        ),
        (role_texts.OWN_NAME, "Art. 3(3)", "Art. 3 Nr. 3"),
        (role_texts.BUILDS_ON_GPAI, "Art. 3(68)", "Art. 3 Nr. 68"),
    ],
)
def test_a_provider_switch_says_what_a_yes_may_do_not_that_it_is_so(
    key: role_texts.KeyQuestion, english: str, german: str
) -> None:
    """The hint sits under the question that asks it, so it never states the finding."""
    assert ask(key, EN, StepName.ROLE_OBLIGATIONS).hint == (
        f"A yes can make the company the provider of the system ({english})."
    )
    assert ask(key, DE, StepName.ROLE_OBLIGATIONS).hint == (
        f"Ein Ja kann das Unternehmen zum Anbieter des Systems machen ({german})."
    )
    assert key.reason is None or ask(key, EN, StepName.ROLE_OBLIGATIONS).hint != key.reason[EN]


def test_a_role_question_that_switches_nothing_keeps_the_step_hint() -> None:
    question = ask(role_texts.OPERATOR_ROLE, EN, StepName.ROLE_OBLIGATIONS)
    assert question.hint == "The answer decides the company's role and its duties (Art. 3(3))."


def test_ask_carries_the_steps_wording_outcome_and_quotes() -> None:
    outcome = AnswerOutcome(
        risk_class=RiskClass.HIGH_RISK,
        high_risk_route=HighRiskRoute.ANNEX_III,
        provision_id="annex:III:4:a",
        duties_from=date(2027, 12, 2),
    )
    question = ask(
        high_risk_texts.PROFILING,
        EN,
        StepName.HIGH_RISK,
        text="Does it profile applicants?",
        if_yes=outcome,
        citations=(POINT_4_A,),
    )
    assert (question.text, question.if_yes, question.citations) == (
        "Does it profile applicants?",
        outcome,
        (POINT_4_A,),
    )


def test_the_readings_are_titled_classed_quoted_and_the_stricter_one_applied() -> None:
    stricter = ReadingSide(
        "Part of recruitment", "Duties apply.", RiskClass.HIGH_RISK, "annex:III:4:a"
    )
    lenient = ReadingSide("A narrow procedural task", "Document it.", None, "art:6:3:a")
    question = open_question(PLAIN, stricter, lenient, (POINT_4_A, ART_6_3_A))
    first, second = question.readings
    assert question.question == PLAIN.question
    assert (first.title, first.risk_class, first.citation, first.is_applied) == (
        "Part of recruitment",
        RiskClass.HIGH_RISK,
        POINT_4_A,
        True,
    )
    assert (second.explanation, second.citation, second.consequence, second.is_applied) == (
        "It only copies fields.",
        ART_6_3_A,
        "Document it.",
        False,
    )


def test_a_reading_quotes_nothing_the_step_doesnt_cite() -> None:
    same = ReadingSide("Title", "Consequence.", None, "art:6:3:a")
    question = open_question(PLAIN, same, same, (POINT_4_A,))
    assert [reading.citation for reading in question.readings] == [None, None]
    assert [reading.is_applied for reading in question.readings] == [True, False]
