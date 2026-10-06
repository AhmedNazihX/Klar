"""The questions a step puts to the user, as the screens show them (E12; decision 026 items 4,
13, 18): a follow-up question with why it matters (`hint`), its answer options and, where the
step knows it, what a yes settles; and an open question of law with its two readings, each
titled, classed, explained, quoted from the step's own citations and with its consequence.

The model's reply carries only the plain shapes (`aiact.llm.replies`); everything added here is
built in code from the step's fixed texts, so no prompt changes."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from aiact.engine.nodes.high_risk_texts import point_name
from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.llm import replies
from aiact.schemas import (
    YES_NO,
    AnswerOutcome,
    Citation,
    FollowUpQuestion,
    Language,
    OpenQuestion,
    Reading,
    RiskClass,
    SettledBy,
    StepName,
)

EN, DE = Language.EN, Language.DE

HINTS: Mapping[Language, Mapping[StepName, str]] = {
    EN: {
        StepName.SCOPE: "The answer decides whether the AI Act applies to the system "
        "({provision}).",
        StepName.PROHIBITED: "The answer decides whether the system is a prohibited practice "
        "({provision}).",
        StepName.HIGH_RISK: "The answer decides whether the system is high-risk ({provision}).",
        StepName.TRANSPARENCY: "The answer decides whether a transparency duty applies "
        "({provision}).",
        StepName.ROLE_OBLIGATIONS: "The answer decides the company's role and its duties "
        "({provision}).",
    },
    DE: {
        StepName.SCOPE: "Die Antwort entscheidet, ob die KI-Verordnung für das System gilt "
        "({provision}).",
        StepName.PROHIBITED: "Die Antwort entscheidet, ob das System eine verbotene Praktik ist "
        "({provision}).",
        StepName.HIGH_RISK: "Die Antwort entscheidet, ob das System hochriskant ist ({provision}).",
        StepName.TRANSPARENCY: "Die Antwort entscheidet, ob eine Transparenzpflicht gilt "
        "({provision}).",
        StepName.ROLE_OBLIGATIONS: "Die Antwort entscheidet über die Rolle des Unternehmens und "
        "seine Pflichten ({provision}).",
    },
}
"""Why a step's question matters, naming the provision it decides; a question with a `reason`
(an Art. 25(1) switch) says why with that instead."""

DE_POINT_WORDS = ("Buchst.", "Ziff.")
"""The German words before a point and a sub-point: "Buchst. a", "Ziff. i"."""
DEFINITIONS_ARTICLE = "3"
"""Art. 3 numbers its definitions, which German calls "Nr.", not "Abs."."""


def provision_label(provision_id: str, language: Language) -> str:
    """How a question names a provision: `art:6:1:b` is "Art. 6(1)(b)" in English and "Art. 6
    Abs. 1 Buchst. b" in German, `art:3:3` "Art. 3(3)" or "Art. 3 Nr. 3", and an Annex point as
    the high-risk check names it (`point_name`). Any other id is returned as it is."""
    kind, *parts = provision_id.split(":")
    if kind == "annex" and len(parts) >= 2:
        return point_name(provision_id, language)
    if kind != "art" or not parts:
        return provision_id
    article, *rest = parts
    if language is EN:
        return f"Art. {article}" + "".join(f"({part})" for part in rest)
    if not rest:
        return f"Art. {article}"
    paragraph = "Nr." if article == DEFINITIONS_ARTICLE else "Abs."
    points = "".join(f" {DE_POINT_WORDS[min(n, 1)]} {part}" for n, part in enumerate(rest[1:]))
    return f"Art. {article} {paragraph} {rest[0]}{points}"


def hint(step: StepName, article: str, language: Language) -> str:
    """Why the answer to a `step` question about `article` matters."""
    return HINTS[language][step].format(provision=provision_label(article, language))


def ask(
    key: KeyQuestion,
    language: Language,
    step: StepName,
    *,
    text: str | None = None,
    if_yes: AnswerOutcome | None = None,
    citations: Sequence[Citation] = (),
) -> FollowUpQuestion:
    """The follow-up question for a key fact, about the provision it rests on: its text (or
    `text`, the question as the step words it), the hint, yes/no options for a yes/no question,
    and what a yes settles (`if_yes`, only on a yes/no question) and quotes (`citations`)."""
    why = key.reason[language] if key.reason else hint(step, key.article, language)
    return FollowUpQuestion(
        id=key.id,
        text=text or key.question[language],
        about=key.article,
        hint=why,
        options=YES_NO if key.is_yes_no else (),
        if_yes=if_yes if key.is_yes_no else None,
        citations=tuple(citations),
    )


def from_reply(question: replies.FollowUpQuestion) -> FollowUpQuestion:
    """A question the model wrote, as the contract carries it: answered in words, since its form
    is the model's."""
    return FollowUpQuestion(id=question.id, text=question.text, about=question.about)


# --- Open questions of law ----------------------------------------------------------------------


@dataclass(frozen=True)
class ReadingSide:
    """What a step knows about one reading besides its explanation: its title, what follows if
    it holds, the class it gives (None when it gives none by itself) and the provision it rests
    on, quoted from the step's citations."""

    title: str
    consequence: str
    risk_class: RiskClass | None = None
    provision_id: str | None = None


def quoted(provision_id: str | None, citations: Sequence[Citation]) -> Citation | None:
    """The step's citation of `provision_id`, or None when the step doesn't cite it."""
    return next((c for c in citations if c.provision_id == provision_id), None)


def open_question(
    plain: replies.OpenQuestion,
    stricter: ReadingSide,
    lenient: ReadingSide,
    citations: Sequence[Citation],
    settled_by: Sequence[SettledBy] = (),
) -> OpenQuestion:
    """The open question with its two readings structured, stricter first and applied: each
    reading's text is its explanation, and its citation is one of the step's `citations`."""
    readings = tuple(
        Reading(
            title=side.title,
            risk_class=side.risk_class,
            explanation=explanation,
            citation=quoted(side.provision_id, citations),
            consequence=side.consequence,
            is_applied=number == 0,
        )
        for number, (side, explanation) in enumerate(
            zip((stricter, lenient), plain.readings, strict=True)
        )
    )
    return OpenQuestion(question=plain.question, readings=readings, settled_by=tuple(settled_by))
