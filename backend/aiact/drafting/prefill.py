"""The pre-filled sections: content taken from the classification result and nothing else.

Each function maps a result to a section's paragraphs. The facts check (`checks.py`) calls the
same functions, so a pre-filled section matches the result exactly when it is what they return.
"""

from collections.abc import Callable, Mapping

from aiact.dates import long_date
from aiact.engine.nodes.high_risk_texts import point_name
from aiact.engine.nodes.transparency_texts import provision_name
from aiact.schemas import (
    ClassificationResult,
    EvidenceTag,
    HighRiskRoute,
    Language,
    LegacyStatus,
    Obligation,
    RiskClass,
    Status,
)

EN, DE = Language.EN, Language.DE

ROUTE_PREFIXES: Mapping[str, HighRiskRoute] = {
    "annex:III": HighRiskRoute.ANNEX_III,
    "annex:I": HighRiskRoute.ANNEX_I,
}
"""The route an Annex point belongs to, by its first two id parts."""

Prefill = Callable[[ClassificationResult, Language, str], tuple[str, ...]]
"""(result, language, the document's article) → the section's paragraphs."""

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
        "significant change to the system (Art. 111(2)).",
    },
    DE: {
        "class": "Ihre Einstufung: {name}.",
        Status.NEEDS_MORE_INFORMATION: "Ihre Einstufung: {name}, angenommen, bis Sie die offene "
        "Frage beantworten.",
        Status.LEGALLY_AMBIGUOUS: "Ihre Einstufung: {name}, angenommen, weil das Recht einen "
        "Punkt offenlässt.",
        "duty": "Sie nennt die Pflicht nach {article}.",
        "duty_from": "Sie nennt die Pflicht nach {article}, die ab dem {date} gilt.",
        "duty_legacy": "Sie nennt die Pflicht nach {article}, die erst nach einer wesentlichen "
        "Änderung des Systems gilt (Art. 111 Abs. 2).",
    },
}


def system_facts(result: ClassificationResult, language: Language, article: str) -> tuple[str, ...]:
    """The facts the user stated about the system, in the result's order. Inferred and assumed
    facts are the engine's readings, not the user's words, so they stay out of the document."""
    return tuple(fact.text for fact in result.facts if fact.evidence is EvidenceTag.STATED)


def classification_and_duty(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    """The class (with its Annex point, and whether it is only assumed) and the document's duty
    with the date the result gives for it."""
    return (_class_sentence(result, language), _duty_sentence(result, language, article))


def _class_sentence(result: ClassificationResult, language: Language) -> str:
    name = CLASS_NAMES[language][result.risk_class]
    if result.annex_point is not None:
        name = f"{name}, {point_name(result.annex_point, language)}"
    key = "class" if result.status is Status.DECIDED else result.status
    return TEXTS[language][key].format(name=name)


def _duty_sentence(result: ClassificationResult, language: Language, article: str) -> str:
    texts = TEXTS[language]
    name = provision_name(article, language)
    obligation = _obligation(result, article)
    if obligation is None:
        return texts["duty"].format(article=name)
    if obligation.legacy is LegacyStatus.UNCHANGED:
        return texts["duty_legacy"].format(article=name)
    when = long_date(obligation.applies_from, language)
    return texts["duty_from"].format(article=name, date=when)


def _obligation(result: ClassificationResult, article: str) -> Obligation | None:
    """The result's duty under `article` on the result's high-risk route; None when the result
    doesn't list it (an Art. 50 duty appears here only when the role carries it) or lists it
    with dates that differ and no route to choose between them."""
    route = ROUTE_PREFIXES.get(":".join((result.annex_point or "").split(":")[:2]))
    duties = [
        item
        for item in result.obligations
        if item.article == article and (route is None or item.high_risk_route in (None, route))
    ]
    timings = {(item.applies_from, item.legacy) for item in duties}
    return duties[0] if len(timings) == 1 else None
