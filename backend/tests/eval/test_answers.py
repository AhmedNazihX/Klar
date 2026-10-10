"""Fixed answers for the downgrade rate's second run (aiact/eval/answers.py, decision 019)."""

import pytest

from aiact.eval.answers import DONT_KNOW, AnswerSourceError, fixed_answers
from aiact.eval.answers import _question_ids as question_ids  # pyright: ignore[reportPrivateUsage]
from aiact.eval.cases import BenchmarkCase
from aiact.schemas import Language
from tests.eval.outcomes import case


def soft_case(language: Language = Language.EN) -> BenchmarkCase:
    return case("soft").model_copy(
        update={
            "language": language,
            "key_fact_answers": {"annex_iii_use": "It ranks applicants.", "ai_system": "Yes."},
        }
    )


def test_dont_know_is_given_in_each_language() -> None:
    assert DONT_KNOW == {Language.EN: "don't know", Language.DE: "weiß nicht"}


def test_only_the_questions_asked_get_answers() -> None:
    """A stored answer to a question the run didn't ask is never appended."""
    answers = fixed_answers(soft_case(), ("annex_iii_use", "human_review"))
    assert answers == {"annex_iii_use": "It ranks applicants.", "human_review": "don't know"}


def test_a_german_case_answers_in_german() -> None:
    assert fixed_answers(soft_case(Language.DE), ("eu_use",)) == {"eu_use": "weiß nicht"}


def test_no_questions_means_no_answers_and_repeats_are_dropped() -> None:
    assert fixed_answers(soft_case(), ()) == {}
    assert list(fixed_answers(soft_case(), ("ai_system", "ai_system"))) == ["ai_system"]


def test_stored_question_ids_are_read_in_order() -> None:
    stored = [{"id": "b", "text": "B?"}, {"id": "a", "text": "A?"}]
    assert question_ids("c", stored) == ("b", "a")
    assert question_ids("c", None) == ()  # a failed case stored no result


@pytest.mark.parametrize("stored", [{"id": "a"}, [{"text": "no id"}], ["a"]])
def test_malformed_stored_questions_name_the_case(stored: object) -> None:
    with pytest.raises(AnswerSourceError, match="case c:"):
        question_ids("c", stored)
