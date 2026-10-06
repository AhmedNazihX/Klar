"""The facts check's verification of each pre-filled section, read directly from the result.

It never calls the drafter's `prefill` functions, so a drafting bug can't pass its own check: the
system section must hold exactly the result's stated facts, the class sentence must name the
result's class and Annex point (marked assumed exactly when the result isn't decided), and the
duty sentence must give the result's date for the document's duty. Problems name sections and
positions, never the user's text.
"""

import re
from collections.abc import Mapping

from aiact.dates import MONTHS, long_date
from aiact.drafting.models import DraftSection, Provenance
from aiact.drafting.prefill import ASSUMED, CLASS_NAMES, LEGACY_ARTICLE, Fill
from aiact.drafting.templates import ClassificationSection
from aiact.provision_names import annex_point_name, article_provision_name
from aiact.schemas import ClassificationResult, EvidenceTag, Language, LegacyStatus, Status

DATE_PATTERNS: Mapping[Language, re.Pattern[str]] = {
    Language.EN: re.compile(rf"\b\d{{1,2}} (?:{'|'.join(MONTHS['en'])}) \d{{4}}\b"),
    Language.DE: re.compile(rf"\b\d{{1,2}}\. (?:{'|'.join(MONTHS['de'])}) \d{{4}}\b"),
}
"""A long date as `aiact.dates.long_date` writes it."""

ANNEX_MENTION = re.compile(r"(?:Annex|Anhang) I[^,]*?(?=[,.](?:\s|$))")
"""An Annex point named in a sentence, up to the comma or full stop that ends it."""


def prefilled_problems(
    spec: ClassificationSection,
    section: DraftSection,
    result: ClassificationResult,
    language: Language,
    article: str,
) -> list[str]:
    """What in the pre-filled `section` doesn't match the result; empty when it all does."""
    match spec.fill:
        case Fill.SYSTEM_FACTS:
            return _system_problems(spec, section, result, language)
        case Fill.CLASSIFICATION_AND_DUTY:
            return _duty_problems(section, result, language, article)


def _system_problems(
    spec: ClassificationSection,
    section: DraftSection,
    result: ClassificationResult,
    language: Language,
) -> list[str]:
    """Every paragraph is a fact the user stated, in the result's order, and none is left out;
    with no stated fact, the section says so in the template's fixed line."""
    key = spec.key
    stated = [fact.text for fact in result.facts if fact.evidence is EvidenceTag.STATED]
    if not stated:
        empty = (spec.empty[language],) if spec.empty else ()
        is_said = section.provenance is Provenance.TEMPLATE and section.paragraphs == empty
        return [] if is_said else [f"section {key!r} must say that no facts were stated"]
    if section.provenance is not Provenance.CLASSIFICATION:
        return [f"section {key!r} must hold the stated facts"]
    paragraphs = list(section.paragraphs)
    problems = [
        f"section {key!r}: paragraph {number} is not a fact stated in the result"
        for number, text in enumerate(paragraphs, start=1)
        if text not in stated
    ]
    problems += [
        f"section {key!r} leaves out stated fact {number}"
        for number, text in enumerate(stated, start=1)
        if text not in paragraphs
    ]
    if not problems and paragraphs != stated:
        problems.append(f"section {key!r} doesn't keep the result's order of facts")
    return problems


def _duty_problems(
    section: DraftSection, result: ClassificationResult, language: Language, article: str
) -> list[str]:
    key = section.key
    if section.provenance is not Provenance.CLASSIFICATION or len(section.paragraphs) != 2:
        return [f"section {key!r} must hold the class and the duty, from the classification"]
    class_sentence, duty_sentence = section.paragraphs
    problems = _class_problems(class_sentence, result, language)
    problems += _date_problems(duty_sentence, result, language, article)
    if not _names(duty_sentence, article_provision_name(article, language)):
        problems.append(f"section {key!r} doesn't name the duty {article}")
    return [f"section {key!r}: {problem}" for problem in problems]


def _class_problems(sentence: str, result: ClassificationResult, language: Language) -> list[str]:
    """The sentence names the result's class and Annex point and nothing else, and is marked
    assumed exactly when the result isn't decided."""
    problems = []
    named = [risk_class for risk_class, name in CLASS_NAMES[language].items() if name in sentence]
    if named != [result.risk_class]:
        problems.append("the class is not the result's")
    expected = [annex_point_name(result.annex_point, language)] if result.annex_point else []
    if ANNEX_MENTION.findall(sentence) != expected:
        problems.append("the Annex point is not the result's")
    is_assumed = result.status is not Status.DECIDED
    if (ASSUMED[language] in sentence) != is_assumed:
        marking = "must be" if is_assumed else "must not be"
        problems.append(f"the class {marking} marked assumed")
    return problems


def _date_problems(
    sentence: str, result: ClassificationResult, language: Language, article: str
) -> list[str]:
    """The sentence gives the date of the result's obligation under `article`, the Art. 111(2)
    wording for a legacy duty, or no date when the result lists none."""
    duties = [item for item in result.obligations if item.article == article]
    timings = {(item.applies_from, item.legacy) for item in duties}
    if len(timings) > 1:
        return [f"the result lists {article} with several dates"]
    is_legacy = bool(duties) and duties[0].legacy is LegacyStatus.UNCHANGED
    expected = {long_date(duties[0].applies_from, language)} if duties and not is_legacy else set()
    problems = []
    if set(DATE_PATTERNS[language].findall(sentence)) != expected:
        problems.append("the date is not the result's")
    if _names(sentence, article_provision_name(LEGACY_ARTICLE, language)) != is_legacy:
        problems.append("the Art. 111(2) wording doesn't match the result")
    return problems


def _names(sentence: str, provision: str) -> bool:
    """Whether `sentence` names `provision` itself, not a longer one it begins
    ("Art. 26 Abs. 1" is not named by "Art. 26 Abs. 11")."""
    return re.search(re.escape(provision) + r"(?![\w(])", sentence) is not None
