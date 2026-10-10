"""Model-written texts in numbers (aiact/eval/texts.py)."""

from aiact.eval.texts import model_texts, render_texts
from aiact.schemas import Fact
from aiact.schemas.enums import EvidenceTag
from tests.eval.outcomes import case, outcome, result
from tests.schemas.builders import rebuild

LONG_FACT = Fact(text="x" * 412, evidence=EvidenceTag.ASSUMED)


def test_model_texts_cover_facts_questions_and_step_facts() -> None:
    base = result()
    texts = list(model_texts(base))
    assert all(fact.text in texts for fact in base.facts)
    assert all(question.text in texts for question in base.follow_up_questions)
    step_facts = [fact.text for step in base.steps for fact in step.facts_used]
    assert step_facts and all(text in texts for text in step_facts)


def test_the_section_reports_the_longest_text_and_the_counts() -> None:
    base = result()
    longer = rebuild(base, facts=(*base.facts, LONG_FACT))
    lines = render_texts([outcome(case("a"), longer), outcome(case("b"), failed=True)])
    assert "- Longest fact or question: 412 characters (cap 600)" in lines
    assert f"- Facts: {len(base.facts) + 1} over 1 results" in lines
    assert f"- Follow-up questions: {len(base.follow_up_questions)} over 1 results" in lines
