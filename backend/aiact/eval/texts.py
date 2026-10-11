"""The model-written texts of a run's results, in numbers (BACKLOG > V8, from E8 and E13).

E8 bounds every text a model writes into a step at `key_facts.MAX_TEXT_CHARS` (a longer one is a
broken output); the first full run says how close the answers come. E13's shorter facts prompt
moved some facts into questions, so the run reports facts and follow-up questions per result to
show a drop in what the checks were given or a rise in questions. Only lengths and counts are
reported, never a text.
"""

from collections.abc import Iterable, Sequence

from aiact.engine.nodes.key_facts import MAX_TEXT_CHARS
from aiact.eval.metrics import Outcome
from aiact.schemas.result import ClassificationResult


def model_texts(result: ClassificationResult) -> Iterable[str]:
    """The texts a model wrote into a result: every fact (the result's and each step's) and
    every question (follow-up questions, each step's missing fact and open question)."""
    yield from (fact.text for fact in result.facts)
    yield from (question.text for question in result.follow_up_questions)
    for step in result.steps:
        yield from (fact.text for fact in step.facts_used)
        if step.missing_fact is not None:
            yield step.missing_fact.text
        if step.open_question is not None:
            yield step.open_question.question


def render_texts(outcomes: Sequence[Outcome]) -> list[str]:
    """The run report's text section, as markdown lines."""
    results = [outcome.result for outcome in outcomes if outcome.result is not None]
    longest = max((len(text) for r in results for text in model_texts(r)), default=0)
    facts = sum(len(r.facts) for r in results)
    questions = sum(len(r.follow_up_questions) for r in results)
    return [
        "### Model-written texts",
        "",
        f"- Longest fact or question: {longest} characters (cap {MAX_TEXT_CHARS})",
        f"- Facts: {facts} over {len(results)} results",
        f"- Follow-up questions: {questions} over {len(results)} results",
    ]
