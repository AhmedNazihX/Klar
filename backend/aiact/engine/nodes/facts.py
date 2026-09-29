"""The facts node: facts with evidence tags, and the key-fact questions they raise (E2).

The engine model reads the description once, with the fixed instructions in
`prompts/facts.md` first and the description last, so the shared prefix is cached (005).
It returns each fact with its evidence tag. A stated fact comes with a verbatim quote,
which this node locates in the description to set the fact's source span: models are poor
at character offsets but good at copying. A stated fact whose quote can't be found is not
trusted: it becomes an inferred fact, so every stated fact points into the description.

Every inferred or assumed fact gets a "please confirm" question (INIT > Evidence tags), and
the model adds the questions whose answer could change a check, including the features that
flip an outcome when present (decision 001, product rule).
"""

import re
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import Field, ValidationError

from aiact.engine.state import EngineState, FactsOutcome
from aiact.llm import chat_model
from aiact.llm.routing import require_setting
from aiact.llm.structured import describe_validation_error, json_schema_format
from aiact.schemas import EvidenceTag, Fact, FollowUpQuestion, Language, SourceSpan
from aiact.schemas.base import ContractModel
from aiact.settings import Settings, get_settings

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "facts.md"
FACTS_INSTRUCTIONS = PROMPT_PATH.read_text(encoding="utf-8")

MAX_OUTPUT_TOKENS = 4000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005)."""

QUOTE_EDGES = " \t\n\"'“”„«».,;:…‚‘’"  # noqa: RUF001 (typographic quotes, on purpose)
"""Punctuation and quote marks a model may add around a quote; trimmed before matching."""

CONFIRM_TEXT: dict[Language, str] = {
    Language.EN: "Please confirm: {fact}",
    Language.DE: "Bitte bestätigen Sie: {fact}",
}
"""The confirm question for an inferred or assumed fact that came without one."""


class ExtractedFact(ContractModel):
    """One fact as the model returns it. Enum fields carry no description: strict structured
    output rejects keywords next to a `$ref`; the prompt explains every field instead."""

    text: str = Field(min_length=1)
    evidence: EvidenceTag
    quote: str | None = Field(description="For a stated fact: the passage, copied verbatim.")
    question: FollowUpQuestion | None = Field(
        description="For an inferred or assumed fact: the question that confirms it."
    )


class FactsAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill."""

    facts: tuple[ExtractedFact, ...]
    questions: tuple[FollowUpQuestion, ...] = Field(
        description="Key-fact questions the description leaves open, most decisive first."
    )


FACTS_RESPONSE_FORMAT = json_schema_format("facts_answer", FactsAnswer)


class FactsOutputError(ValueError):
    """The model's answer isn't usable as facts (a broken output)."""


def find_span(description: str, quote: str) -> SourceSpan | None:
    """Where `quote` occurs in `description`, or None.

    An exact match comes first. Failing that, the quote matches ignoring case and with any run
    of whitespace standing for any other, since models tend to reflow a quoted line break.
    """
    trimmed = quote.strip(QUOTE_EDGES)
    if not trimmed:
        return None
    start = description.find(trimmed)
    if start >= 0:
        return SourceSpan(start=start, end=start + len(trimmed))
    pattern = r"\s+".join(re.escape(word) for word in trimmed.split())
    match = re.search(pattern, description, re.IGNORECASE)
    return SourceSpan(start=match.start(), end=match.end()) if match else None


def _fact(extracted: ExtractedFact, description: str) -> Fact:
    """The contract fact: a stated fact keeps its tag only if its quote is in the description."""
    if extracted.evidence is not EvidenceTag.STATED:
        return Fact(text=extracted.text, evidence=extracted.evidence)
    span = find_span(description, extracted.quote) if extracted.quote else None
    if span is None:
        return Fact(text=extracted.text, evidence=EvidenceTag.INFERRED)
    return Fact(text=extracted.text, evidence=EvidenceTag.STATED, source_span=span)


def _confirm_question(
    extracted: ExtractedFact, fact: Fact, number: int, language: Language
) -> FollowUpQuestion | None:
    """The question that confirms an inferred or assumed fact; none for a stated one."""
    if fact.evidence is EvidenceTag.STATED:
        return None
    if extracted.question is not None:
        return extracted.question
    text = CONFIRM_TEXT[language].format(fact=fact.text)
    return FollowUpQuestion(id=f"confirm_fact_{number}", text=text)


def to_outcome(answer: FactsAnswer, description: str, language: Language) -> FactsOutcome:
    """The facts and questions for the graph. Key-fact questions come first, then the
    confirm questions, each id once (the first one asked wins)."""
    facts = tuple(_fact(extracted, description) for extracted in answer.facts)
    confirms = (
        _confirm_question(extracted, fact, number, language)
        for number, (extracted, fact) in enumerate(zip(answer.facts, facts, strict=True), 1)
    )
    by_id: dict[str, FollowUpQuestion] = {}
    for question in (*answer.questions, *confirms):
        if question is not None and question.id not in by_id:
            by_id[question.id] = question
    return FactsOutcome(facts=facts, follow_up_questions=tuple(by_id.values()))


def facts_messages(description: str, language: Language) -> list[BaseMessage]:
    """The fixed instructions first and the description last, so the prefix is cached (005)."""
    return [
        SystemMessage(FACTS_INSTRUCTIONS),
        HumanMessage(
            f"Language for facts and questions: {language.value}\n\nDescription:\n{description}"
        ),
    ]


class FactExtractor:
    """The facts node for the graph: `EngineNodes(facts=FactExtractor(), …)`."""

    def __init__(self, settings: Settings | None = None, chat: BaseChatModel | None = None) -> None:
        """`chat` replaces the OpenRouter model (tests). Raises `LLMConfigError` when
        `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set: the model is always pinned
        to its EU endpoint with fallbacks off (decision 005), so descriptions stay in the EU."""
        settings = settings or get_settings()
        model_id = require_setting(settings.engine_model, "ENGINE_MODEL")
        provider = require_setting(settings.engine_provider, "ENGINE_PROVIDER")
        self._model = chat or chat_model(
            model=model_id,
            provider_order=[provider],
            allow_fallbacks=False,
            max_tokens=MAX_OUTPUT_TOKENS,
            settings=settings,
        )

    def __call__(self, state: EngineState) -> FactsOutcome:
        """Raises `FactsOutputError` when the reply doesn't fit `FactsAnswer`."""
        description, language = state["description"], state["language"]
        reply = self._model.invoke(
            facts_messages(description, language), response_format=FACTS_RESPONSE_FORMAT
        )
        try:
            answer = FactsAnswer.model_validate_json(reply.text)
        except ValidationError as exc:
            message = f"facts answer doesn't fit the schema: {describe_validation_error(exc)}"
            raise FactsOutputError(message) from exc
        return to_outcome(answer, description, language)
