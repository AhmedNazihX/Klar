"""What the high-risk step adds to its questions for the screens
(aiact/engine/nodes/high_risk_questions.py, E12; decision 026 items 4, 13 and 18)."""

import re
from datetime import date

import pytest

from aiact.engine.nodes.high_risk import Art63Condition
from aiact.engine.nodes.high_risk_questions import settled_by
from aiact.engine.nodes.key_facts import Answer
from aiact.engine.state import CheckOutcome
from aiact.schemas import (
    YES_NO,
    AnswerOutcome,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    OpenQuestion,
    RiskClass,
    SettledBy,
    SettledByKind,
)
from tests.engine.nodes.test_high_risk import (
    OPEN,
    RANKS_APPLICANTS,
    YES,
    annex_i,
    annex_iii,
    answer,
    art_6_3,
    outcome,
)

UNKNOWN = Answer.UNKNOWN
MDR = "annex:I:A:11"
NOT_HIGH_RISK_SENTENCE = (
    "If this holds, this point does not make the system high-risk. The transparency check then "
    "decides whether any duties apply."
)
"""Decision 026 item 13: no class is predicted for a "no"."""


def missing(result: CheckOutcome) -> FollowUpQuestion:
    question = result.step.missing_fact
    assert question is not None
    return question


def opened(result: CheckOutcome) -> OpenQuestion:
    question = result.step.open_question
    assert question is not None
    return question


# --- The decisive question and what a yes settles -----------------------------------------------


def test_the_annex_i_question_names_the_law_quotes_art_6_1_and_the_entry_and_knows_a_yes() -> None:
    """Decision 026 item 18: If yes: High-risk, Annex I, duties from 2 August 2028."""
    question = missing(outcome(answer(one=annex_i(MDR, YES, YES, UNKNOWN))))
    assert question.id == "third_party_assessment"
    assert "Regulation (EU) 2017/745 on medical devices" in question.text
    assert [c.provision_id for c in question.citations] == [MDR, "art:6:1"]
    assert question.options == YES_NO
    assert question.hint == "The answer decides whether the system is high-risk (Art. 6(1)(b))."
    assert question.if_yes == AnswerOutcome(
        risk_class=RiskClass.HIGH_RISK,
        high_risk_route=HighRiskRoute.ANNEX_I,
        provision_id=MDR,
        duties_from=date(2028, 8, 2),
    )


def test_the_annex_i_question_reads_in_german() -> None:
    question = missing(outcome(answer(one=annex_i(MDR, YES, YES, UNKNOWN)), Language.DE))
    assert "Verordnung (EU) 2017/745 über Medizinprodukte" in question.text
    assert question.hint == (
        "Die Antwort entscheidet, ob das System hochriskant ist (Art. 6 Abs. 1 Buchst. b)."
    )


def test_a_section_b_yes_sets_no_duties_date() -> None:
    """Art. 2(2): the duties come from the sector law, so the AI Act gives no date."""
    question = missing(outcome(answer(one=annex_i("annex:I:B:21", YES, YES, UNKNOWN))))
    assert question.if_yes is not None
    assert (question.if_yes.provision_id, question.if_yes.duties_from) == ("annex:I:B:21", None)


def test_a_yes_settles_nothing_while_another_annex_i_fact_is_open() -> None:
    question = missing(outcome(answer(one=annex_i(MDR, YES, UNKNOWN, UNKNOWN))))
    assert question.id == "safety_component"
    assert question.options == YES_NO
    assert question.if_yes is None


def test_a_yes_to_profiling_makes_the_listed_use_high_risk() -> None:
    result = outcome(answer(RANKS_APPLICANTS, art_6_3(Art63Condition.B, UNKNOWN)))
    question = missing(result)
    assert question.id == "profiling"
    assert question.if_yes == AnswerOutcome(
        risk_class=RiskClass.HIGH_RISK,
        high_risk_route=HighRiskRoute.ANNEX_III,
        provision_id="annex:III:4:a",
        duties_from=date(2027, 12, 2),
    )
    assert [c.provision_id for c in question.citations] == ["annex:III:4:a"]


def test_a_yes_to_judicial_use_makes_point_8a_high_risk() -> None:
    question = missing(outcome(answer(annex_iii("annex:III:8:a", YES, public_authority=UNKNOWN))))
    assert question.id == "judicial_use"
    assert question.if_yes is not None
    assert question.if_yes.provision_id == "annex:III:8:a"


def test_a_yes_settles_nothing_when_the_exemption_may_still_apply() -> None:
    """Judicial use unknown, and a condition met without profiling: a yes lists the use, but
    the Art. 6(3) exemption then applies, so the step doesn't know a class."""
    iii = annex_iii("annex:III:8:a", YES, public_authority=UNKNOWN)
    question = missing(outcome(answer(iii, art_6_3(Art63Condition.A, Answer.NO))))
    assert question.id == "judicial_use"
    assert question.if_yes is None


def test_an_either_or_question_offers_no_options() -> None:
    question = missing(outcome(answer(annex_iii("annex:III:5:a", YES, public_authority=UNKNOWN))))
    assert question.id == "public_scheme"
    assert (question.options, question.if_yes) == ((), None)


def test_the_other_routes_question_knows_its_yes_but_quotes_nothing() -> None:
    """Open on both routes: the Annex III fact is the missing one; the Annex I question is
    asked too, with what a yes settles, but only the step's missing fact quotes its route."""
    iii = (RANKS_APPLICANTS, art_6_3(Art63Condition.B, UNKNOWN))
    result = outcome(answer(*iii, one=annex_i(MDR, YES, YES, UNKNOWN)))
    assert missing(result).id == "profiling"
    [other] = [q for q in result.follow_up_questions if q.id != "profiling"]
    assert other.id == "third_party_assessment"
    assert other.citations == ()
    assert other.if_yes is not None
    assert other.if_yes.high_risk_route is HighRiskRoute.ANNEX_I


# --- The readings of an open question -----------------------------------------------------------


def test_an_open_annex_i_question_reads_high_risk_against_art_6_1_not_met() -> None:
    result = outcome(answer(one=annex_i(MDR, YES, YES, YES, open_question=OPEN)))
    stricter, lenient = opened(result).readings
    assert (stricter.title, stricter.risk_class, stricter.is_applied) == (
        "High-risk under Art. 6(1)",
        RiskClass.HIGH_RISK,
        True,
    )
    assert stricter.consequence == "If this holds, the high-risk duties apply from 2 August 2028."
    assert (lenient.title, lenient.risk_class, lenient.consequence) == (
        "Art. 6(1) not met",
        None,
        NOT_HIGH_RISK_SENTENCE,
    )
    for reading in (stricter, lenient):
        assert reading.citation is not None
        assert reading.citation.provision_id == "art:6:1"
        assert reading.citation in result.step.citations


def test_an_open_art_6_3_question_reads_high_risk_against_exempt() -> None:
    """The ResultAmbiguous artboard: the Annex III point against the Art. 6(3) condition, and
    the provider's own assessment among what would settle it."""
    result = outcome(
        answer(RANKS_APPLICANTS, art_6_3(Art63Condition.A, Answer.NO, open_question=OPEN))
    )
    question = opened(result)
    stricter, lenient = question.readings
    assert stricter.title == "High-risk under Annex III point 4(a)"
    assert stricter.consequence == "If this holds, the high-risk duties apply from 2 December 2027."
    assert stricter.citation is not None and stricter.citation.provision_id == "annex:III:4:a"
    assert lenient.title == "Exempt under Art. 6(3)"
    assert lenient.citation is not None and lenient.citation.provision_id == "art:6:3:a"
    assert lenient.consequence is not None and "Art. 6(4)" in lenient.consequence
    assert [item.kind for item in question.settled_by] == [
        SettledByKind.GUIDANCE,
        SettledByKind.PROVIDER,
    ]


def test_an_open_annex_iii_listing_reads_high_risk_against_not_covered() -> None:
    result = outcome(answer(annex_iii("annex:III:4:a", Answer.NO, open_question=OPEN)))
    question = opened(result)
    stricter, lenient = question.readings
    assert lenient.title == "Not covered by Annex III point 4(a)"
    assert lenient.consequence == NOT_HIGH_RISK_SENTENCE
    assert stricter.citation == lenient.citation
    assert [item.kind for item in question.settled_by] == [SettledByKind.GUIDANCE]


def test_the_readings_read_in_german() -> None:
    result = outcome(answer(one=annex_i(MDR, YES, YES, YES, open_question=OPEN)), Language.DE)
    stricter, lenient = opened(result).readings
    assert stricter.title == "Hochrisiko nach Art. 6 Abs. 1"
    assert stricter.consequence == (
        "Gilt diese Lesart, gelten die Hochrisiko-Pflichten ab dem 2. August 2028."
    )
    assert lenient.title == "Art. 6 Abs. 1 nicht erfüllt"


# --- What would settle it (decision 026 item 4) -------------------------------------------------


SETTLED_BY_TEXTS = {
    Language.EN: (
        "Final Commission guidelines on high-risk classification (still a draft, 19 May 2026)",
        "The provider's own Art. 6(3) assessment, documented under Art. 6(4), if it made one",
    ),
    Language.DE: (
        "Endgültige Leitlinien der Kommission zur Einstufung als Hochrisiko (noch ein Entwurf, "
        "19. Mai 2026)",
        "Die eigene Bewertung des Anbieters nach Art. 6 Abs. 3, dokumentiert nach Art. 6 Abs. 4, "
        "falls er eine vorgenommen hat",
    ),
}
"""Every text that may name what would settle an open question, word for word."""
NO_PROMISE = re.compile(
    r"re-?check|again|review|update|notify|klar|erneut|wieder|\bneu|aktualis|benachrichtig",
    re.IGNORECASE,
)
"""Words a promise to look at the result again would need (decision 026 item 4)."""


@pytest.mark.parametrize("language", [Language.EN, Language.DE])
def test_what_would_settle_it_is_exactly_the_approved_texts(language: Language) -> None:
    guidelines, provider = SETTLED_BY_TEXTS[language]
    assert settled_by(language, is_open_on_exemption=True) == (
        SettledBy(kind=SettledByKind.GUIDANCE, text=guidelines),
        SettledBy(kind=SettledByKind.PROVIDER, text=provider),
    )
    assert settled_by(language, is_open_on_exemption=False) == (
        SettledBy(kind=SettledByKind.GUIDANCE, text=guidelines),
    )


@pytest.mark.parametrize("text", [t for texts in SETTLED_BY_TEXTS.values() for t in texts])
def test_nothing_promises_to_look_again(text: str) -> None:
    assert NO_PROMISE.search(text) is None


# --- No yes is promised while a fact or the law is still open (fix round 1) ----------------------


def no_outcome_anywhere(result: CheckOutcome) -> bool:
    return all(question.if_yes is None for question in result.follow_up_questions)


def test_a_yes_on_who_uses_it_settles_nothing_while_the_use_itself_is_open() -> None:
    """Point 8(a) with the use unknown: the authority question is asked, but a yes to it
    doesn't make the use listed."""
    result = outcome(answer(annex_iii("annex:III:8:a", UNKNOWN, public_authority=UNKNOWN)))
    assert result.step.missing_fact is not None
    assert no_outcome_anywhere(result)


def test_no_annex_i_yes_is_promised_while_the_law_leaves_the_route_open() -> None:
    result = outcome(answer(one=annex_i(MDR, YES, YES, UNKNOWN, open_question=OPEN)))
    assert "third_party_assessment" in [q.id for q in result.follow_up_questions]
    assert no_outcome_anywhere(result)


def test_no_annex_iii_yes_is_promised_while_the_law_leaves_the_exemption_open() -> None:
    result = outcome(
        answer(RANKS_APPLICANTS, art_6_3(Art63Condition.A, UNKNOWN, open_question=OPEN))
    )
    assert "profiling" in [q.id for q in result.follow_up_questions]
    assert no_outcome_anywhere(result)
