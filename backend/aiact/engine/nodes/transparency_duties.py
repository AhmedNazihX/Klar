"""The Art. 50 duties as the transparency node reads them (E6): the model's answer (one part per
duty, the same key facts each, and when the system was first placed on the market), and each
duty's reading of it in three values (applies, does not apply, open on a fact). `transparency`
settles the step; nothing here calls a model or reads the corpus.

Art. 50(4) has two subparagraphs, deep fakes and text on matters of public interest, read as two
parts that both name `art:50:4`.
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import Field

from aiact.engine.nodes import transparency_texts as texts
from aiact.engine.nodes.key_facts import MAX_TEXT_CHARS as MAX_TEXT_CHARS  # re-exported (E6)
from aiact.engine.nodes.key_facts import Answer, Reading, Settled, ShortTexts, every, need
from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.llm.replies import OpenQuestion
from aiact.schemas import EvidenceTag
from aiact.schemas.base import ContractModel

# --- The model's answer -------------------------------------------------------------------------


class MarketTiming(StrEnum):
    """When the system was first made available, measured against Art. 111(4)'s 2 August 2026."""

    PLACED_BEFORE = "placed_on_market_before"
    IN_SERVICE_BEFORE = "only_put_into_service_before"
    LATER = "not_before"
    UNKNOWN = "unknown"


class DutyAnswer(ShortTexts):
    """One duty's answer, as `key_facts.facts_used` reads it: `covered` (the system is the kind
    the paragraph names) and `exception` (one of the paragraph's exceptions takes it out), then
    whether the law settles that reading. Its `fact` sums up the reading, so it always counts as
    settled (an open fact is asked through its own question). Enum fields carry no description:
    strict structured output rejects keywords next to a `$ref`; the prompt explains every field
    instead. The texts are bounded by `MAX_TEXT_CHARS` when the reply is checked, not in the
    schema, so the model's response format stays unchanged."""

    covered: Answer
    exception: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]

    @property
    def is_known(self) -> bool:
        return True

    def written(self) -> tuple[str | None, ...]:
        question = self.open_question
        return (self.fact, *((question.question, *question.readings) if question else ()))


class TransparencyAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill. One part per duty, in the
    order of Art. 50."""

    interaction: DutyAnswer
    synthetic_content: DutyAnswer
    emotion_biometric: DutyAnswer
    deep_fake: DutyAnswer
    public_interest_text: DutyAnswer
    market_timing: MarketTiming
    guidance_numbers: tuple[int, ...]


# --- Reading the key facts ----------------------------------------------------------------------


@dataclass(frozen=True)
class DutyRule:
    """A duty's paragraph and the questions that settle its two key facts."""

    provision: str
    covered: KeyQuestion
    exception: KeyQuestion


INTERACTION = DutyRule("art:50:1", texts.INTERACTS_DIRECTLY, texts.INTERACTION_OBVIOUS)
SYNTHETIC_CONTENT = DutyRule("art:50:2", texts.GENERATES_CONTENT, texts.SUBSTANTIAL_ALTERATION)
EMOTION_BIOMETRIC = DutyRule("art:50:3", texts.EMOTION_OR_BIOMETRIC, texts.LAW_ENFORCEMENT)
DEEP_FAKE = DutyRule("art:50:4", texts.DEEP_FAKE, texts.LAW_ENFORCEMENT)
PUBLIC_INTEREST_TEXT = DutyRule("art:50:4", texts.PUBLIC_INTEREST_TEXT, texts.EDITORIAL_CONTROL)


@dataclass(frozen=True)
class Duty:
    """One duty's reading: the paragraph it names, whether it applies, the answer part, and the
    question on the paragraph's exception, which settles the duty when the law leaves it open
    (E17)."""

    provision: str
    reading: Reading
    summary: DutyAnswer
    exception: KeyQuestion

    @property
    def is_raised(self) -> bool:
        """The description gives a reason to consider the duty (`covered` isn't "no")."""
        return self.summary.covered is not Answer.NO

    @property
    def is_open(self) -> bool:
        """The law leaves open whether the duty applies (only asked of a raised one)."""
        return self.is_raised and self.summary.settled_in_law is Settled.NO

    @property
    def is_listed(self) -> bool:
        """Listed on the result: it applies, is assumed until a fact is answered, or is held
        open in law (the stricter reading)."""
        return self.is_open or self.reading.answer is not Answer.NO


def _parts(answer: TransparencyAnswer) -> tuple[tuple[DutyAnswer, DutyRule], ...]:
    return (
        (answer.interaction, INTERACTION),
        (answer.synthetic_content, SYNTHETIC_CONTENT),
        (answer.emotion_biometric, EMOTION_BIOMETRIC),
        (answer.deep_fake, DEEP_FAKE),
        (answer.public_interest_text, PUBLIC_INTEREST_TEXT),
    )


def duties(answer: TransparencyAnswer) -> tuple[Duty, ...]:
    """Every duty read from the answer, in the order of Art. 50: the system is covered, and no
    exception takes it out."""
    return tuple(
        Duty(
            provision=rule.provision,
            reading=every(
                need(part.covered, rule.covered),
                need(part.exception, rule.exception, wanted=Answer.NO),
            ),
            summary=part,
            exception=rule.exception,
        )
        for part, rule in _parts(answer)
    )
