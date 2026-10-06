"""The questions a step puts to the user, as the screens show them (E12; decision 026 items 4,
13, 18): a follow-up question with why it matters (`hint`), its answer options and, where the
step knows it, what a yes settles; and an open question of law with its two readings, each
titled, classed, explained, quoted from the step's own citations and with its consequence.

The model's reply carries only the plain shapes (`aiact.llm.replies`); everything added here is
built in code from the step's fixed texts, so no prompt changes."""

from collections.abc import Mapping, Sequence

from aiact.engine.nodes.reading_side import ReadingSide
from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.llm import replies
from aiact.provision_names import annex_point_name, article_provision_name
from aiact.schemas import (
    YES_NO,
    AnswerOutcome,
    Citation,
    FollowUpQuestion,
    Language,
    OpenQuestion,
    Reading,
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
"""Why a step's question matters, naming the provision it decides."""

PROVIDER_SWITCH_HINT: Mapping[Language, str] = {
    EN: "A yes can make the company the provider of the system ({provision}).",
    DE: "Ein Ja kann das Unternehmen zum Anbieter des Systems machen ({provision}).",
}
"""The hint of a question whose yes may switch the company to provider (Art. 3(3), 25(1)): it
says what a yes may do, never that it is so."""

DEFINITIONS_ARTICLE = "3"
"""Art. 3 numbers its definitions, which German calls "Nr.", not "Abs."."""


def provision_label(provision_id: str, language: Language) -> str:
    """How a question names a provision, as `aiact.provision_names` does: `art:6:1:b` is "Art.
    6(1)(b)" or "Art. 6 Abs. 1 Buchst. b", an Annex point "Annex III point 5(a)"; a whole
    article is "Art. 50", and an Art. 3 definition "Art. 3(3)" or "Art. 3 Nr. 3". Any other id
    is returned as it is."""
    kind, *parts = provision_id.split(":")
    if kind == "annex" and len(parts) >= 2:
        return annex_point_name(provision_id, language)
    if kind != "art" or not parts:
        return provision_id
    if len(parts) == 1:
        return f"Art. {parts[0]}"
    name = article_provision_name(provision_id, language)
    if language is DE and parts[0] == DEFINITIONS_ARTICLE:
        return name.replace(" Abs. ", " Nr. ", 1)
    return name


def hint(step: StepName, article: str, language: Language) -> str:
    """Why the answer to a `step` question about `article` matters."""
    return HINTS[language][step].format(provision=provision_label(article, language))


def follow_up(
    question_id: str,
    text: str,
    article: str,
    why: str,
    *,
    is_yes_no: bool,
    if_yes: AnswerOutcome | None = None,
    citations: Sequence[Citation] = (),
) -> FollowUpQuestion:
    """A fixed follow-up question about `article`, with its hint (`why`), yes/no options for a
    yes/no question, and what a yes settles (`if_yes`, only on a yes/no question) and quotes."""
    return FollowUpQuestion(
        id=question_id,
        text=text,
        about=article,
        hint=why,
        options=YES_NO if is_yes_no else (),
        if_yes=if_yes if is_yes_no else None,
        citations=tuple(citations),
    )


def ask(
    key: KeyQuestion,
    language: Language,
    step: StepName,
    *,
    text: str | None = None,
    if_yes: AnswerOutcome | None = None,
    citations: Sequence[Citation] = (),
) -> FollowUpQuestion:
    """The follow-up question for a key fact (`follow_up`): its text, or `text` as the step words
    it; a provider switch's hint says what a yes may do."""
    label = provision_label(key.article, language)
    is_switch = key.is_provider_switch
    why = PROVIDER_SWITCH_HINT[language].format(provision=label) if is_switch else None
    return follow_up(
        key.id,
        text or key.question[language],
        key.article,
        why or hint(step, key.article, language),
        is_yes_no=key.is_yes_no,
        if_yes=if_yes,
        citations=citations,
    )


# --- Open questions of law ----------------------------------------------------------------------


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
