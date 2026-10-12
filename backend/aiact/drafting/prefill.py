"""The pre-filled sections: content taken from the classification result and nothing else.

Each `Fill` names what a section is filled with; `PREFILLS` maps it to the function that writes
it. The facts check (`checks.py`) verifies the written section against the result on its own,
without calling these functions.
"""

from collections.abc import Callable, Mapping
from enum import StrEnum

from aiact.dates import long_date
from aiact.drafting.vendor_letters import fills as vendor
from aiact.provision_names import annex_point_name, article_provision_name
from aiact.schemas import (
    ClassificationResult,
    EvidenceTag,
    Language,
    LegacyStatus,
    Obligation,
    RiskClass,
    Status,
)

EN, DE = Language.EN, Language.DE


class Fill(StrEnum):
    """What a pre-filled section holds."""

    SYSTEM_FACTS = "system_facts"
    """The facts the user stated about the system."""
    CLASSIFICATION_AND_DUTY = "classification_and_duty"
    """The class with its Annex point, and the document's duty with its date."""
    CHECKED = "checked"
    """The date checked and the text of the Act checked against (vendor letters)."""
    PROHIBITED_FINDING = "prohibited_finding"
    """The Art. 5(1) points the tool falls under, which the section quotes (vendor message)."""
    DECIDING_FACTS = "deciding_facts"
    """The facts the result rests on (vendor message)."""
    OPEN_QUESTION = "open_question"
    """The question of law the result leaves open (vendor request)."""
    READINGS = "readings"
    """The open question's two readings, the applied one marked (vendor request)."""
    SETTLED_BY = "settled_by"
    """What would settle the open question (vendor request)."""


class DutyDateError(ValueError):
    """The result lists the document's duty with more than one date, so no single date is right."""


class NoClassError(ValueError):
    """The result has no class (a needs-a-description result, E13, or a refused check, decision
    030), so no document states one."""


CLASS_NAMES: Mapping[Language, Mapping[RiskClass, str]] = {
    EN: {
        RiskClass.PROHIBITED: "prohibited",
        RiskClass.HIGH_RISK: "high-risk",
        RiskClass.LIMITED_RISK: "limited risk",
        RiskClass.MINIMAL_RISK: "minimal risk",
        RiskClass.OUT_OF_SCOPE: "out of scope",
    },
    DE: {
        RiskClass.PROHIBITED: "verboten",
        RiskClass.HIGH_RISK: "Hochrisiko",
        RiskClass.LIMITED_RISK: "begrenztes Risiko",
        RiskClass.MINIMAL_RISK: "minimales Risiko",
        RiskClass.OUT_OF_SCOPE: "Außerhalb des Anwendungsbereichs",
    },
}

ASSUMED: Mapping[Language, str] = {EN: "assumed", DE: "angenommen"}
"""The word that marks a class as a working assumption (the result is not decided)."""

LEGACY_ARTICLE = "art:111:2"
"""Where a legacy duty's "only after a significant change" comes from."""

TEXTS: Mapping[Language, Mapping[str, str]] = {
    EN: {
        "class": "Your classification: {name}.",
        Status.NEEDS_MORE_INFORMATION: "Your classification: {name}, assumed until you answer "
        "its open question.",
        Status.LEGALLY_AMBIGUOUS: "Your classification: {name}, assumed because the law leaves "
        "a point open.",
        "duty": "It lists the duty under {article}.",
        "duty_from": "It lists the duty under {article}, which applies from {date}.",
        "duty_legacy": "It lists the duty under {article}, which applies only after a "
        "significant change to the system ({legacy}).",
    },
    DE: {
        "class": "Ihre Einstufung: {name}.",
        Status.NEEDS_MORE_INFORMATION: "Ihre Einstufung: {name}, angenommen, bis Sie die offene "
        "Frage beantworten.",
        Status.LEGALLY_AMBIGUOUS: "Ihre Einstufung: {name}, angenommen, weil das Recht einen "
        "Punkt offenlässt.",
        "duty": "Sie nennt die Pflicht nach {article}.",
        "duty_from": "Sie nennt die Pflicht nach {article}, die ab dem {date} gilt.",
        "duty_legacy": "Sie nennt die Pflicht nach {article}, die erst nach einer erheblichen "
        "Änderung des Systems gilt ({legacy}).",
    },
}


def stated_facts(result: ClassificationResult) -> tuple[str, ...]:
    """The facts the user stated, in the result's order. Inferred and assumed facts are the
    engine's readings, not the user's words, so they stay out of a document."""
    return tuple(fact.text for fact in result.facts if fact.evidence is EvidenceTag.STATED)


def duty_obligation(result: ClassificationResult, article: str) -> Obligation | None:
    """The result's duty under `article`; None when the result doesn't list it (an Art. 50 duty
    appears in `obligations` only when the role carries it). The engine lists only the duties
    of the result's route, so one date is expected: raises DutyDateError for several."""
    duties = [item for item in result.obligations if item.article == article]
    timings = {(item.applies_from, item.legacy) for item in duties}
    if len(timings) > 1:
        raise DutyDateError(f"the result lists {article} with {len(timings)} different dates")
    return duties[0] if duties else None


def _system_facts(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    return stated_facts(result)


def _classification_and_duty(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    return (_class_sentence(result, language), _duty_sentence(result, language, article))


def _class_sentence(result: ClassificationResult, language: Language) -> str:
    risk_class = result.assessed_class
    if risk_class is None:
        raise NoClassError(
            "a result with no class (too thin to start, or a refused check) has no class to state"
        )
    name = CLASS_NAMES[language][risk_class]
    if result.annex_point is not None:
        name = f"{name}, {annex_point_name(result.annex_point, language)}"
    key = "class" if result.status is Status.DECIDED else result.status
    return TEXTS[language][key].format(name=name)


def _duty_sentence(result: ClassificationResult, language: Language, article: str) -> str:
    texts = TEXTS[language]
    name = article_provision_name(article, language)
    obligation = duty_obligation(result, article)
    if obligation is None:
        return texts["duty"].format(article=name)
    if obligation.legacy is LegacyStatus.UNCHANGED:
        legacy = article_provision_name(LEGACY_ARTICLE, language)
        return texts["duty_legacy"].format(article=name, legacy=legacy)
    when = long_date(obligation.applies_from, language)
    return texts["duty_from"].format(article=name, date=when)


Prefill = Callable[[ClassificationResult, Language, str], tuple[str, ...]]
"""(result, language, the document's article) → the section's paragraphs."""

PREFILLS: Mapping[Fill, Prefill] = {
    Fill.SYSTEM_FACTS: _system_facts,
    Fill.CLASSIFICATION_AND_DUTY: _classification_and_duty,
    Fill.CHECKED: vendor.checked_paragraphs,
    Fill.PROHIBITED_FINDING: vendor.finding_paragraphs,
    Fill.DECIDING_FACTS: vendor.deciding_fact_paragraphs,
    Fill.OPEN_QUESTION: vendor.question_paragraphs,
    Fill.READINGS: vendor.reading_paragraphs,
    Fill.SETTLED_BY: vendor.settled_by_paragraphs,
}

QUOTING_FILLS = frozenset({Fill.PROHIBITED_FINDING})
"""The fills whose section quotes the provisions it names (its `quotes`), with the text read
from the corpus (decision 031); the other fills quote none."""
