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

A reply the provider's content filter refused (decision 029) gives no facts and one question
asking for a person's review; the checks then read the description themselves.

The model also says whether the description states what the system decides and who it
affects (E13). When either is missing, the description is too thin to start: the outcome
asks only the three fixed questions of `DESCRIPTION_QUESTIONS` (artboard `ClassifyVague`), and
the graph ends the run before the checks with no class (decision 010 addendum).
"""

import re
import unicodedata
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import Field, ValidationError

from aiact.engine.nodes.common import BLOCKED
from aiact.engine.nodes.key_facts import ShortTexts
from aiact.engine.state import EngineState, FactsOutcome
from aiact.llm import engine_route, replies
from aiact.llm.structured import (
    ProviderRefusalError,
    describe_validation_error,
    json_schema_format,
)
from aiact.schemas import (
    DESCRIPTION_QUESTION_IDS,
    YES_NO,
    EvidenceTag,
    Fact,
    FollowUpQuestion,
    Language,
    SourceSpan,
)
from aiact.schemas.base import ContractModel
from aiact.settings import Settings

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "facts.md"
FACTS_INSTRUCTIONS = PROMPT_PATH.read_text(encoding="utf-8")

MAX_OUTPUT_TOKENS = 6000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005). On long
own-case descriptions the answer, mostly reasoning, reaches about 4,000 whatever the prompt (the
pre-E13 prompt used 2,472-3,950 live, own-c-17 3,910-4,000), so E13 raised it from 4,000
(decision 032)."""

QUOTE_EDGES = " \t\n\"'“”„«».,;:…‚‘’"  # noqa: RUF001 (typographic quotes, on purpose)
"""Punctuation and quote marks a model may add around a quote; trimmed before matching."""

CONFIRM_TEXT: dict[Language, str] = {
    Language.EN: "Please confirm: {fact}",
    Language.DE: "Bitte bestätigen Sie: {fact}",
}
"""The confirm question for an inferred or assumed fact that came without one."""

PERSON_REVIEW_ID = "facts_person_review"
PERSON_REVIEW_TEXT: dict[Language, str] = {
    Language.EN: "Please have a person review it: what does the system do, who uses it, and whom "
    "does it affect?",
    Language.DE: "Bitte lassen Sie sie von einem Menschen prüfen: Was tut das System, wer nutzt es "
    "und wen betrifft es?",
}
"""The question a refused reply asks instead of facts (decision 029), after the shared first
sentence (`common.BLOCKED`)."""

DESCRIPTION_TEXTS: dict[str, dict[Language, tuple[str, str]]] = {
    "what_it_decides": {
        Language.EN: (
            "What does it decide or suggest?",
            "For example: it ranks applicants, answers staff questions, plans shifts.",
        ),
        Language.DE: (
            "Was entscheidet es oder was schlägt es vor?",
            "Zum Beispiel: Es reiht Bewerbungen, beantwortet Fragen von Beschäftigten, plant "
            "Schichten.",
        ),
    },
    "who_it_affects": {
        Language.EN: ("Who does it affect?", "For example: applicants, your staff, customers."),
        Language.DE: (
            "Wen betrifft es?",
            "Zum Beispiel: Bewerbende, Ihre Beschäftigten, Kundschaft.",
        ),
    },
    "bought_or_built": {
        Language.EN: (
            "Did you buy it or build it?",
            "And whether you changed it or put your own name on it.",
        ),
        Language.DE: (
            "Haben Sie es gekauft oder selbst entwickelt?",
            "Und ob Sie es verändert oder Ihren eigenen Namen daraufgesetzt haben.",
        ),
    },
}
"""The question and its example line (the hint) for each needs-a-description question, as the
artboard `ClassifyVague` words them."""


def description_questions(language: Language) -> tuple[FollowUpQuestion, ...]:
    """The three questions a too-thin description asks, answered in words, in their fixed order."""
    texts = (DESCRIPTION_TEXTS[question_id][language] for question_id in DESCRIPTION_QUESTION_IDS)
    return tuple(
        FollowUpQuestion(id=question_id, text=text, hint=hint)
        for question_id, (text, hint) in zip(DESCRIPTION_QUESTION_IDS, texts, strict=True)
    )


WORD_CHAR = re.compile(r"\w")

GERMAN_ASCII = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
"""German letters spelled out in ASCII for ids; other accents are dropped (é → e)."""
CONFIRM_STEM = "confirm"
"""The first word of every fallback question id."""
MAX_SLUG_LENGTH = 64
"""The longest id `FollowUpQuestion` accepts (`SLUG_PATTERN`)."""


class ExtractedFact(ShortTexts):
    """One fact as the model returns it. Enum fields carry no description: strict structured
    output rejects keywords next to a `$ref`; the prompt explains every field instead."""

    text: str = Field(min_length=1)
    evidence: EvidenceTag
    quote: str | None = Field(description="For a stated fact: the passage, copied verbatim.")
    question: replies.FollowUpQuestion | None = Field(
        description="For an inferred or assumed fact: the question that confirms it."
    )

    def written(self) -> tuple[str | None, ...]:
        """The fact and its question. The quote isn't bounded: it must be found verbatim in the
        description (`find_span`), so it adds no prose of its own."""
        return (self.text, self.question.text if self.question else None)


class FactsAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill."""

    facts: tuple[ExtractedFact, ...]
    says_what_it_decides: bool = Field(
        description="Whether the description says what the system decides, suggests, produces "
        "or controls."
    )
    says_who_it_affects: bool = Field(
        description="Whether the description says whom (or, for no person, what) its outputs "
        "concern."
    )
    questions: tuple[replies.FollowUpQuestion, ...] = Field(
        description="Key-fact questions the description leaves open, most decisive first."
    )


FACTS_RESPONSE_FORMAT = json_schema_format("facts_answer", FactsAnswer)


class FactsOutputError(ValueError):
    """The model's answer isn't usable as facts (a broken output)."""


def _word_edges(pattern: str, trimmed: str) -> str:
    """`pattern` anchored so it can't start or end inside a word ("EU" never matches in "EUR").
    Only an edge that is a word character is anchored, so a quote may end in punctuation."""
    before = r"(?<!\w)" if WORD_CHAR.match(trimmed[0]) else ""
    after = r"(?!\w)" if WORD_CHAR.match(trimmed[-1]) else ""
    return f"{before}{pattern}{after}"


def find_span(description: str, quote: str) -> SourceSpan | None:
    """Where `quote` occurs in `description` as whole words, or None.

    An exact match comes first. Failing that, the quote matches ignoring case and with any run
    of whitespace standing for any other, since models tend to reflow a quoted line break.
    Both steps match whole words only, so a short invented quote can't land inside another word.
    """
    trimmed = quote.strip(QUOTE_EDGES)
    if not trimmed:
        return None
    exact = _word_edges(re.escape(trimmed), trimmed)
    loose = _word_edges(r"\s+".join(re.escape(word) for word in trimmed.split()), trimmed)
    match = re.search(exact, description) or re.search(loose, description, re.IGNORECASE)
    return SourceSpan(start=match.start(), end=match.end()) if match else None


def _fact(extracted: ExtractedFact, description: str) -> Fact:
    """The contract fact: a stated fact keeps its tag only if its quote is in the description."""
    if extracted.evidence is not EvidenceTag.STATED:
        return Fact(text=extracted.text, evidence=extracted.evidence)
    span = find_span(description, extracted.quote) if extracted.quote else None
    if span is None:
        return Fact(text=extracted.text, evidence=EvidenceTag.INFERRED)
    return Fact(text=extracted.text, evidence=EvidenceTag.STATED, source_span=span)


def fact_slug(text: str) -> str:
    """A question id from a fact's text: `confirm_` and as many of its words, in ASCII
    snake_case, as fit in an id. Only a first word too long to fit is cut.

    Stability trade-off: the id follows the fact's wording, not its position, so a re-run that
    phrases the fact the same way keys the user's earlier answer to it, even if the facts come
    back in another order. A re-run that words the fact differently gets a new id, and the
    question is asked again. The model's own question ids (given for most facts) avoid this.
    """
    german = text.lower().translate(GERMAN_ASCII)
    folded = unicodedata.normalize("NFKD", german).encode("ascii", "ignore").decode()
    slug = CONFIRM_STEM
    for word in re.findall(r"[a-z0-9]+", folded):
        longer = f"{slug}_{word}"
        if len(longer) > MAX_SLUG_LENGTH:
            return slug if slug != CONFIRM_STEM else longer[:MAX_SLUG_LENGTH]
        slug = longer
    return slug


def _unique(slug: str, taken: set[str]) -> str:
    """`slug`, or `slug_2`, `slug_3`, … when an earlier question already has that id. When the
    suffix wouldn't fit, whole words are dropped from the end first, never half a word."""
    candidate, number = slug, 1
    while candidate in taken:
        number += 1
        suffix = f"_{number}"
        base = slug
        while len(base) + len(suffix) > MAX_SLUG_LENGTH and "_" in base:
            base = base.rsplit("_", 1)[0]
        candidate = f"{base}{suffix}"
    return candidate


def _confirm_question(
    extracted: ExtractedFact, fact: Fact, language: Language, taken: set[str]
) -> FollowUpQuestion | None:
    """The question that confirms an inferred or assumed fact; none for a stated one. A fact
    without the model's own question gets one whose id comes from the fact's text."""
    if fact.evidence is EvidenceTag.STATED:
        return None
    if extracted.question is not None:
        return replies.as_contract(extracted.question)
    return confirm_question(fact, language, taken)


def confirm_question(fact: Fact, language: Language, taken: set[str]) -> FollowUpQuestion:
    """ "Please confirm: <fact>", answered yes or no, with an id from the fact's text
    (`fact_slug`) that no question in `taken` has yet. Also used by finalize for the checks'
    assumed deciding facts (E8)."""
    text = CONFIRM_TEXT[language].format(fact=fact.text)
    return FollowUpQuestion(id=_unique(fact_slug(fact.text), taken), text=text, options=YES_NO)


def to_outcome(answer: FactsAnswer, description: str, language: Language) -> FactsOutcome:
    """The facts and questions for the graph. Key-fact questions come first, then the
    confirm questions, each id once (the first one asked wins). A description that doesn't say
    what the system decides or who it affects asks only the three description questions."""
    facts = tuple(_fact(extracted, description) for extracted in answer.facts)
    if not (answer.says_what_it_decides and answer.says_who_it_affects):
        return FactsOutcome(
            facts=facts,
            follow_up_questions=description_questions(language),
            needs_description=True,
        )
    by_id: dict[str, FollowUpQuestion] = {}
    for question in answer.questions:
        by_id.setdefault(question.id, replies.as_contract(question))
    for extracted, fact in zip(answer.facts, facts, strict=True):
        question = _confirm_question(extracted, fact, language, set(by_id))
        if question is not None:
            by_id.setdefault(question.id, question)
    return FactsOutcome(facts=facts, follow_up_questions=tuple(by_id.values()))


def refusal_outcome(language: Language) -> FactsOutcome:
    """No facts, and the question that asks a person to review the description (decision 029)."""
    text = f"{BLOCKED[language]} {PERSON_REVIEW_TEXT[language]}"
    review = FollowUpQuestion(id=PERSON_REVIEW_ID, text=text)
    return FactsOutcome(follow_up_questions=(review,))


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

    def __init__(
        self,
        settings: Settings | None = None,
        chat: BaseChatModel | None = None,
        refusal_chat: BaseChatModel | None = None,
    ) -> None:
        """`chat` replaces the OpenRouter model (tests), and `refusal_chat` the second model a
        refused request goes to (decision 033; a `chat` alone has none, and gets no cut-off retry:
        E20). Raises `LLMConfigError` when `ENGINE_MODEL`, `ENGINE_PROVIDER`, `REFUSAL_MODEL`,
        `REFUSAL_PROVIDER` or the API key is not set: both models are always pinned to their EU
        endpoints with fallbacks off (decisions 005, 033), so descriptions stay in the EU."""
        self._route = engine_route(
            max_tokens=MAX_OUTPUT_TOKENS, settings=settings, chat=chat, refusal_chat=refusal_chat
        )

    def __call__(self, state: EngineState) -> FactsOutcome:
        """A reply the provider's content filter refused gives `refusal_outcome`. Raises
        `FactsOutputError` when any other reply doesn't fit `FactsAnswer`."""
        description, language = state["description"], state["language"]
        try:
            answer = self._route.ask(
                facts_messages(description, language), FACTS_RESPONSE_FORMAT, FactsAnswer
            )
        except ProviderRefusalError:
            return refusal_outcome(language)
        except ValidationError as exc:
            message = f"facts answer doesn't fit the schema: {describe_validation_error(exc)}"
            raise FactsOutputError(message) from None
        return to_outcome(answer, description, language)
