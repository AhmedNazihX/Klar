"""The Art. 5 practices as the prohibited node reads them (E4): the model's answer (one part per
practice, fixed key facts each), and each practice's reading of it in three values (met, not met,
open on a fact), with what it cites and from when it applies. `prohibited` applies the dates and
settles the step; nothing here calls a model or reads the corpus.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol

from pydantic import Field

from aiact.engine.nodes import prohibited_texts as texts
from aiact.engine.nodes.key_facts import Answer, Settled
from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.schemas import EvidenceTag, LawVersion, OpenQuestion
from aiact.schemas.base import ContractModel

PROHIBITIONS_APPLY_FROM = date(2025, 2, 2)
"""Art. 113(a): Chapters I and II, so Art. 5, apply from 2 February 2025."""
DECEMBER_PROHIBITIONS_APPLY_FROM = date(2026, 12, 2)
"""Art. 113(a): points (ba) and (bb) of Art. 5(1), and Art. 5(1a) and (1b), from 2 December 2026."""
APPLICATION_DATES = "art:113:a"


# --- The model's answer -------------------------------------------------------------------------


class RbiObjective(StrEnum):
    """The Art. 5(1)(h) objective a use is strictly necessary for: point (i), (ii) or (iii)."""

    NONE = "none"
    VICTIMS = "i"
    THREAT = "ii"
    SUSPECTS = "iii"
    UNKNOWN = "unknown"


class PracticeSummary(ContractModel):
    """A practice's answer as `key_facts.facts_used` reads it: its `fact` sums up the reading, so
    it always counts as settled (an open fact is asked through its own question). Enum fields
    carry no description: strict structured output rejects keywords next to a `$ref`; the prompt
    explains every field instead. Each practice's `settled_in_law` and `open_question` come right
    after its facts, so the model answers them in that order every time."""

    @property
    def is_known(self) -> bool:
        return True


class ManipulationAnswer(PracticeSummary):
    manipulative_technique: Answer
    distorts_behaviour: Answer
    significant_harm: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class VulnerabilityAnswer(PracticeSummary):
    exploits_vulnerability: Answer
    distorts_behaviour: Answer
    significant_harm: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class SexualMaterialAnswer(PracticeSummary):
    intimate_imagery: Answer
    child_abuse_material: Answer
    only_conceals: Answer
    consent: Answer
    generation_purpose: Answer
    foreseeable_without_safeguards: Answer
    deployer_generation_purpose: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class OpenCondition(StrEnum):
    """Which condition of Art. 5(1)(c) a question the law leaves open is about."""

    NONE = "none"
    SOCIAL_SCORING = "social_scoring"
    UNRELATED_CONTEXT = "i"
    DISPROPORTIONATE = "ii"


class SocialScoringAnswer(PracticeSummary):
    """`open_on` names the condition the open question concerns: point (c) is met by (i) or (ii),
    so a question open on one of them decides nothing once the other is met."""

    social_scoring: Answer
    unrelated_context_treatment: Answer
    disproportionate_treatment: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    open_on: OpenCondition
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class CrimeRiskAnswer(PracticeSummary):
    crime_risk_assessment: Answer
    solely_profiling: Answer
    fact_based_assessment: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class FaceScrapingAnswer(PracticeSummary):
    untargeted_face_scraping: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class EmotionAnswer(PracticeSummary):
    infers_emotions: Answer
    workplace_or_education: Answer
    medical_or_safety: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class BiometricCategorisationAnswer(PracticeSummary):
    biometric_categorisation: Answer
    sensitive_traits: Answer
    lawful_labelling: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class RemoteIdentificationAnswer(PracticeSummary):
    real_time_identification: Answer
    law_enforcement_use: Answer
    objective: RbiObjective
    national_law_authorisation: Answer
    prior_authorisation: Answer
    targeted_use: Answer
    impact_assessment_registration: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class ProhibitedAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill. One part per practice, in
    the order of Art. 5(1); (ba) and (bb) share one, as Art. 5(1a) reads them together."""

    manipulation: ManipulationAnswer
    vulnerability: VulnerabilityAnswer
    sexual_material: SexualMaterialAnswer
    social_scoring: SocialScoringAnswer
    crime_risk: CrimeRiskAnswer
    face_scraping: FaceScrapingAnswer
    emotion_recognition: EmotionAnswer
    biometric_categorisation: BiometricCategorisationAnswer
    remote_identification: RemoteIdentificationAnswer
    guidance_numbers: tuple[int, ...]


class PracticeFields(Protocol):
    """What every practice's answer has besides its own key facts."""

    @property
    def settled_in_law(self) -> Settled: ...
    @property
    def open_question(self) -> OpenQuestion | None: ...
    @property
    def evidence(self) -> EvidenceTag: ...
    @property
    def fact(self) -> str: ...
    @property
    def fact_numbers(self) -> tuple[int, ...]: ...
    @property
    def is_known(self) -> bool: ...


# --- Reading the key facts (three-valued: met, not met, open on a fact) -------------------------


@dataclass(frozen=True)
class Reading:
    """Whether a condition holds, and the question that settles it when a fact is open."""

    answer: Answer
    missing: KeyQuestion | None = None


MET, NOT_MET = Reading(Answer.YES), Reading(Answer.NO)


def need(answer: Answer, question: KeyQuestion, wanted: Answer = Answer.YES) -> Reading:
    """The condition "the key fact is `wanted`"; an exception is a condition wanted "no"."""
    if answer is Answer.UNKNOWN:
        return Reading(Answer.UNKNOWN, question)
    return MET if answer is wanted else NOT_MET


def every(*parts: Reading) -> Reading:
    """All conditions hold: one that fails settles it, else the first open one is asked."""
    if any(part.answer is Answer.NO for part in parts):
        return NOT_MET
    return next((part for part in parts if part.answer is Answer.UNKNOWN), MET)


def either(*parts: Reading) -> Reading:
    """One of the alternatives holds: one that holds settles it, else the first open one."""
    if any(part.answer is Answer.YES for part in parts):
        return MET
    return next((part for part in parts if part.answer is Answer.UNKNOWN), NOT_MET)


def negated(reading: Reading) -> Reading:
    flipped = {Answer.YES: Answer.NO, Answer.NO: Answer.YES, Answer.UNKNOWN: Answer.UNKNOWN}
    return Reading(flipped[reading.answer], reading.missing)


@dataclass(frozen=True)
class Practice:
    """One practice's reading: whether it is met, whether the description raises it at all (its
    first key fact isn't "no"), the answer part it rests on, what it cites, and from when it
    applies."""

    point: str
    reading: Reading
    is_raised: bool
    summary: PracticeFields
    cited: tuple[str, ...]
    applies_from: date = PROHIBITIONS_APPLY_FROM
    is_permitted_use: bool = False
    """An Art. 5(1)(h) use the exception allows: the Art. 5(4) notification applies."""
    is_settled_by_other_alternative: bool = False
    """The question the law leaves open is about one alternative of the practice, and the other
    alternative is met (Art. 5(1)(c)(i) or (ii)), so it decides nothing."""

    @property
    def is_open(self) -> bool:
        """The law leaves open whether the practice applies (only asked of a raised one)."""
        if self.is_settled_by_other_alternative:
            return False
        return self.is_raised and self.summary.settled_in_law is Settled.NO


def _yes_points(pairs: Sequence[tuple[Answer, str]]) -> tuple[str, ...]:
    return tuple(point for answer, point in pairs if answer is Answer.YES)


def _harm_practices(answer: ProhibitedAnswer) -> tuple[Practice, ...]:
    """(a) and (b): the technique or the vulnerability, a distorted decision, significant harm."""
    a, b = answer.manipulation, answer.vulnerability
    distorts, harm = texts.DISTORTS_BEHAVIOUR, texts.SIGNIFICANT_HARM
    return (
        Practice(
            point="art:5:1:a",
            reading=every(
                need(a.manipulative_technique, texts.MANIPULATIVE_TECHNIQUE),
                need(a.distorts_behaviour, distorts),
                need(a.significant_harm, harm),
            ),
            is_raised=a.manipulative_technique is not Answer.NO,
            summary=a,
            cited=("art:5:1:a",),
        ),
        Practice(
            point="art:5:1:b",
            reading=every(
                need(b.exploits_vulnerability, texts.EXPLOITS_VULNERABILITY),
                need(b.distorts_behaviour, distorts),
                need(b.significant_harm, harm),
            ),
            is_raised=b.exploits_vulnerability is not Answer.NO,
            summary=b,
            cited=("art:5:1:b",),
        ),
    )


def _sexual_material_practices(answer: SexualMaterialAnswer) -> tuple[Practice, ...]:
    """(ba) and (bb), each only through an Art. 5(1a) route; (ba) needs no consent, and Art.
    5(1b) takes a manipulation that shows no more out of it."""
    routes = either(
        need(answer.generation_purpose, texts.GENERATION_PURPOSE),
        need(answer.foreseeable_without_safeguards, texts.FORESEEABLE_WITHOUT_SAFEGUARDS),
        need(answer.deployer_generation_purpose, texts.DEPLOYER_GENERATION_PURPOSE),
    )
    route_points = _yes_points(
        (
            (answer.generation_purpose, "art:5:1a:a:i"),
            (answer.foreseeable_without_safeguards, "art:5:1a:a:ii"),
            (answer.deployer_generation_purpose, "art:5:1a:b"),
        )
    )
    conceals = ("art:5:1b",) if answer.only_conceals is Answer.YES else ()
    return (
        Practice(
            point="art:5:1:ba",
            reading=every(
                need(answer.intimate_imagery, texts.INTIMATE_IMAGERY),
                need(answer.only_conceals, texts.ONLY_CONCEALS, wanted=Answer.NO),
                need(answer.consent, texts.CONSENT, wanted=Answer.NO),
                routes,
            ),
            is_raised=answer.intimate_imagery is not Answer.NO,
            summary=answer,
            cited=("art:5:1:ba", *route_points, *conceals, APPLICATION_DATES),
            applies_from=DECEMBER_PROHIBITIONS_APPLY_FROM,
        ),
        Practice(
            point="art:5:1:bb",
            reading=every(need(answer.child_abuse_material, texts.CHILD_ABUSE_MATERIAL), routes),
            is_raised=answer.child_abuse_material is not Answer.NO,
            summary=answer,
            cited=("art:5:1:bb", *route_points, APPLICATION_DATES),
            applies_from=DECEMBER_PROHIBITIONS_APPLY_FROM,
        ),
    )


def _other_alternative_met(answer: SocialScoringAnswer) -> bool:
    """Point (c) is met by (i) or (ii): an open question on one, with the other met, is moot."""
    if answer.social_scoring is not Answer.YES:
        return False
    other = {
        OpenCondition.UNRELATED_CONTEXT: answer.disproportionate_treatment,
        OpenCondition.DISPROPORTIONATE: answer.unrelated_context_treatment,
    }
    return other.get(answer.open_on) is Answer.YES


def _profiling_practices(answer: ProhibitedAnswer) -> tuple[Practice, ...]:
    """(c) social scoring and (d) crime prediction from profiling alone."""
    c, d = answer.social_scoring, answer.crime_risk
    treatments = (
        (c.unrelated_context_treatment, "art:5:1:c:i"),
        (c.disproportionate_treatment, "art:5:1:c:ii"),
    )
    return (
        Practice(
            point="art:5:1:c",
            reading=every(
                need(c.social_scoring, texts.SOCIAL_SCORING),
                either(
                    need(c.unrelated_context_treatment, texts.UNRELATED_CONTEXT_TREATMENT),
                    need(c.disproportionate_treatment, texts.DISPROPORTIONATE_TREATMENT),
                ),
            ),
            is_raised=c.social_scoring is not Answer.NO,
            summary=c,
            cited=("art:5:1:c", *_yes_points(treatments)),
            is_settled_by_other_alternative=_other_alternative_met(c),
        ),
        Practice(
            point="art:5:1:d",
            reading=every(
                need(d.crime_risk_assessment, texts.CRIME_RISK_ASSESSMENT),
                need(d.solely_profiling, texts.SOLELY_PROFILING),
                need(d.fact_based_assessment, texts.FACT_BASED_ASSESSMENT, wanted=Answer.NO),
            ),
            is_raised=d.crime_risk_assessment is not Answer.NO,
            summary=d,
            cited=("art:5:1:d",),
        ),
    )


def _biometric_practices(answer: ProhibitedAnswer) -> tuple[Practice, ...]:
    """(e) untargeted face scraping, (f) emotion recognition at work or in education, (g)
    biometric categorisation by sensitive traits."""
    e, f, g = answer.face_scraping, answer.emotion_recognition, answer.biometric_categorisation
    return (
        Practice(
            point="art:5:1:e",
            reading=need(e.untargeted_face_scraping, texts.UNTARGETED_FACE_SCRAPING),
            is_raised=e.untargeted_face_scraping is not Answer.NO,
            summary=e,
            cited=("art:5:1:e",),
        ),
        Practice(
            point="art:5:1:f",
            reading=every(
                need(f.infers_emotions, texts.INFERS_EMOTIONS),
                need(f.workplace_or_education, texts.WORKPLACE_OR_EDUCATION),
                need(f.medical_or_safety, texts.MEDICAL_OR_SAFETY, wanted=Answer.NO),
            ),
            is_raised=Answer.NO not in (f.infers_emotions, f.workplace_or_education),
            summary=f,
            cited=("art:5:1:f",),
        ),
        Practice(
            point="art:5:1:g",
            reading=every(
                need(g.biometric_categorisation, texts.BIOMETRIC_CATEGORISATION),
                need(g.sensitive_traits, texts.SENSITIVE_TRAITS),
                need(g.lawful_labelling, texts.LAWFUL_LABELLING, wanted=Answer.NO),
            ),
            is_raised=g.biometric_categorisation is not Answer.NO,
            summary=g,
            cited=("art:5:1:g",),
        ),
    )


OBJECTIVE_ANSWERS = {
    RbiObjective.NONE: Answer.NO,
    RbiObjective.UNKNOWN: Answer.UNKNOWN,
    RbiObjective.VICTIMS: Answer.YES,
    RbiObjective.THREAT: Answer.YES,
    RbiObjective.SUSPECTS: Answer.YES,
}
EXCEPTION_CONDITIONS = ("art:5:2", "art:5:3", "art:5:5")


def _remote_identification(answer: RemoteIdentificationAnswer) -> Practice:
    """(h): banned for law enforcement unless the use serves a listed objective and meets every
    condition of Art. 5(2), (3) and (5); then it is permitted, and Art. 5(4) applies."""
    is_law_enforcement = (
        answer.real_time_identification is Answer.YES and answer.law_enforcement_use is Answer.YES
    )
    permitted = every(
        need(OBJECTIVE_ANSWERS[answer.objective], texts.RBI_OBJECTIVE),
        need(answer.national_law_authorisation, texts.NATIONAL_LAW),
        need(answer.prior_authorisation, texts.PRIOR_AUTHORISATION),
        need(answer.targeted_use, texts.TARGETED_USE),
        need(answer.impact_assessment_registration, texts.IMPACT_ASSESSMENT_REGISTRATION),
    )
    objective = OBJECTIVE_ANSWERS[answer.objective] is Answer.YES
    objective_point = (f"art:5:1:h:{answer.objective.value}",) if objective else ()
    conditions = (*objective_point, *EXCEPTION_CONDITIONS) if is_law_enforcement else ()
    is_permitted = is_law_enforcement and permitted.answer is Answer.YES
    return Practice(
        point="art:5:1:h",
        reading=every(
            need(answer.real_time_identification, texts.REAL_TIME_IDENTIFICATION),
            need(answer.law_enforcement_use, texts.LAW_ENFORCEMENT_USE),
            negated(permitted),
        ),
        is_raised=answer.real_time_identification is not Answer.NO,
        summary=answer,
        cited=("art:5:1:h", *conditions, *(("art:5:4",) if is_permitted else ())),
        is_permitted_use=is_permitted,
    )


def practices(answer: ProhibitedAnswer, law_version: LawVersion) -> tuple[Practice, ...]:
    """Every Art. 5(1) practice read from the answer, in the order of the Act. The original
    text has no points (ba) or (bb), so they are left out for it."""
    sexual = _sexual_material_practices(answer.sexual_material)
    return (
        *_harm_practices(answer),
        *(sexual if law_version is LawVersion.AMENDED else ()),
        *_profiling_practices(answer),
        *_biometric_practices(answer),
        _remote_identification(answer.remote_identification),
    )
