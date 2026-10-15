"""The Art. 5 practices as the prohibited node reads them (E4): the model's answer (one part per
practice, fixed key facts each), and each practice's reading of it in three values (met, not met,
open on a fact), with what it cites and from when it applies. `prohibited` applies the dates and
settles the step; nothing here calls a model or reads the corpus.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol

from pydantic import Field

from aiact.engine.nodes import prohibited_texts as texts
from aiact.engine.nodes.key_facts import (
    Answer,
    Reading,
    Settled,
    either,
    every,
    need,
    negated,
)
from aiact.engine.nodes.open_in_law import (
    NOT_NAMED,
    HeldOpen,
    OpenOn,
    held_strict,
    raised,
    stays_open,
)
from aiact.llm.replies import OpenQuestion
from aiact.schemas import EvidenceTag, LawVersion
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
    explains every field instead. Each practice's `settled_in_law`, `open_question` and `open_on`
    come right after its facts, so the model answers them in that order every time. `open_on`
    names the key fact a question the law leaves open is about (E19, `open_in_law`); its values
    are the practice's key-fact fields, and "none"."""

    @property
    def is_known(self) -> bool:
        return True


class ManipulationOpenOn(StrEnum):
    NONE = NOT_NAMED
    MANIPULATIVE_TECHNIQUE = "manipulative_technique"
    DISTORTS_BEHAVIOUR = "distorts_behaviour"
    SIGNIFICANT_HARM = "significant_harm"


class ManipulationAnswer(PracticeSummary):
    manipulative_technique: Answer
    distorts_behaviour: Answer
    significant_harm: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    open_on: ManipulationOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class VulnerabilityOpenOn(StrEnum):
    NONE = NOT_NAMED
    EXPLOITS_VULNERABILITY = "exploits_vulnerability"
    DISTORTS_BEHAVIOUR = "distorts_behaviour"
    SIGNIFICANT_HARM = "significant_harm"


class VulnerabilityAnswer(PracticeSummary):
    exploits_vulnerability: Answer
    distorts_behaviour: Answer
    significant_harm: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    open_on: VulnerabilityOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class SexualMaterialOpenOn(StrEnum):
    NONE = NOT_NAMED
    INTIMATE_IMAGERY = "intimate_imagery"
    CHILD_ABUSE_MATERIAL = "child_abuse_material"
    ONLY_CONCEALS = "only_conceals"
    CONSENT = "consent"
    GENERATION_PURPOSE = "generation_purpose"
    FORESEEABLE_WITHOUT_SAFEGUARDS = "foreseeable_without_safeguards"
    DEPLOYER_GENERATION_PURPOSE = "deployer_generation_purpose"


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
    open_on: SexualMaterialOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class SocialScoringOpenOn(StrEnum):
    """Point (c) is met by (i) or (ii), so a question open on one of them decides nothing once
    the other is met (E4)."""

    NONE = NOT_NAMED
    SOCIAL_SCORING = "social_scoring"
    UNRELATED_CONTEXT = "unrelated_context_treatment"
    DISPROPORTIONATE = "disproportionate_treatment"


class SocialScoringAnswer(PracticeSummary):
    social_scoring: Answer
    unrelated_context_treatment: Answer
    disproportionate_treatment: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    open_on: SocialScoringOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class CrimeRiskOpenOn(StrEnum):
    NONE = NOT_NAMED
    CRIME_RISK_ASSESSMENT = "crime_risk_assessment"
    SOLELY_PROFILING = "solely_profiling"
    FACT_BASED_ASSESSMENT = "fact_based_assessment"


class CrimeRiskAnswer(PracticeSummary):
    crime_risk_assessment: Answer
    solely_profiling: Answer
    fact_based_assessment: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    open_on: CrimeRiskOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class FaceScrapingOpenOn(StrEnum):
    NONE = NOT_NAMED
    UNTARGETED_FACE_SCRAPING = "untargeted_face_scraping"


class FaceScrapingAnswer(PracticeSummary):
    untargeted_face_scraping: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    open_on: FaceScrapingOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class EmotionOpenOn(StrEnum):
    NONE = NOT_NAMED
    INFERS_EMOTIONS = "infers_emotions"
    WORKPLACE_OR_EDUCATION = "workplace_or_education"
    MEDICAL_OR_SAFETY = "medical_or_safety"


class EmotionAnswer(PracticeSummary):
    infers_emotions: Answer
    workplace_or_education: Answer
    medical_or_safety: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    open_on: EmotionOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class BiometricCategorisationOpenOn(StrEnum):
    NONE = NOT_NAMED
    BIOMETRIC_CATEGORISATION = "biometric_categorisation"
    SENSITIVE_TRAITS = "sensitive_traits"
    LAWFUL_LABELLING = "lawful_labelling"


class BiometricCategorisationAnswer(PracticeSummary):
    biometric_categorisation: Answer
    sensitive_traits: Answer
    lawful_labelling: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    open_on: BiometricCategorisationOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class RemoteIdentificationOpenOn(StrEnum):
    NONE = NOT_NAMED
    REAL_TIME_IDENTIFICATION = "real_time_identification"
    LAW_ENFORCEMENT_USE = "law_enforcement_use"
    OBJECTIVE = "objective"
    NATIONAL_LAW_AUTHORISATION = "national_law_authorisation"
    PRIOR_AUTHORISATION = "prior_authorisation"
    TARGETED_USE = "targeted_use"
    IMPACT_ASSESSMENT_REGISTRATION = "impact_assessment_registration"


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
    open_on: RemoteIdentificationOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


STRICT_VALUES: Mapping[str, Answer | RbiObjective] = {
    # (a) and (b)
    "manipulative_technique": Answer.YES,
    "exploits_vulnerability": Answer.YES,
    "distorts_behaviour": Answer.YES,
    "significant_harm": Answer.YES,
    # (ba) and (bb), with Art. 5(1a) and (1b)
    "intimate_imagery": Answer.YES,
    "child_abuse_material": Answer.YES,
    "only_conceals": Answer.NO,
    "consent": Answer.NO,
    "generation_purpose": Answer.YES,
    "foreseeable_without_safeguards": Answer.YES,
    "deployer_generation_purpose": Answer.YES,
    # (c) and (d)
    "social_scoring": Answer.YES,
    "unrelated_context_treatment": Answer.YES,
    "disproportionate_treatment": Answer.YES,
    "crime_risk_assessment": Answer.YES,
    "solely_profiling": Answer.YES,
    "fact_based_assessment": Answer.NO,
    # (e), (f) and (g)
    "untargeted_face_scraping": Answer.YES,
    "infers_emotions": Answer.YES,
    "workplace_or_education": Answer.YES,
    "medical_or_safety": Answer.NO,
    "biometric_categorisation": Answer.YES,
    "sensitive_traits": Answer.YES,
    "lawful_labelling": Answer.NO,
    # (h), with the conditions of Art. 5(2), (3) and (5) that permit a use
    "real_time_identification": Answer.YES,
    "law_enforcement_use": Answer.YES,
    "objective": RbiObjective.NONE,
    "national_law_authorisation": Answer.NO,
    "prior_authorisation": Answer.NO,
    "targeted_use": Answer.NO,
    "impact_assessment_registration": Answer.NO,
}
"""Each key fact's stricter value (B2): the one that keeps the practice prohibited. "yes" for a
condition of a practice, "no" for an exception or a condition that permits a use, and no
objective for Art. 5(1)(h)."""


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
    def open_on(self) -> StrEnum: ...
    @property
    def evidence(self) -> EvidenceTag: ...
    @property
    def fact(self) -> str: ...
    @property
    def fact_numbers(self) -> tuple[int, ...]: ...
    @property
    def is_known(self) -> bool: ...


def _part_facts(part: OpenOn) -> frozenset[str]:
    """The key facts of a practice's answer part: its `open_on` values but "none"."""
    return frozenset(value.value for value in type(part.open_on)) - {NOT_NAMED}


def _raised(part: OpenOn, gate_field: str, gate: Answer) -> bool:
    """`open_in_law.raised` for a practice's gate, its first key fact (E4)."""
    return raised(part, gate_field, gate, _part_facts(part))


SEXUAL_ROUTES = (
    "generation_purpose",
    "foreseeable_without_safeguards",
    "deployer_generation_purpose",
)
POINT_BA_FACTS = frozenset({"intimate_imagery", "only_conceals", "consent", *SEXUAL_ROUTES})
POINT_BB_FACTS = frozenset({"child_abuse_material", *SEXUAL_ROUTES})
"""The facts points (ba) and (bb) each read from the answer part they share."""


@dataclass(frozen=True)
class Practice:
    """One practice's reading: whether it is met, whether the description raises it at all (its
    first key fact isn't "no", `open_in_law.raised`), the answer part it rests on, what it
    cites, and from when it applies."""

    point: str
    reading: Reading
    is_raised: bool
    summary: PracticeFields
    cited: tuple[str, ...]
    applies_from: date = PROHIBITIONS_APPLY_FROM
    is_permitted_use: bool = False
    """An Art. 5(1)(h) use the exception allows: the Art. 5(4) notification applies."""
    facts: frozenset[str] | None = None
    """The key facts the practice reads; None for every fact of its answer part."""
    has_cue: bool = True
    """The description gives a sign of the practice, so a fact left open keeps it assumed
    (decision 010). Only Art. 5(1)(d) can lack one (`_profiling_practices`): a fact left open
    then asks its question without assuming the ban."""

    @property
    def is_open(self) -> bool:
        """The law leaves open whether the practice applies: only asked of a raised one. The
        fact it is open on is read on its stricter side (`practices`), so only another fact that
        rules the practice out settles it (E19, `open_in_law.stays_open`)."""
        part = _part_facts(self.summary)
        own = part if self.facts is None else self.facts
        return self.is_raised and stays_open(self.summary, self.reading.answer, own, part)


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
            is_raised=_raised(a, "manipulative_technique", a.manipulative_technique),
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
            is_raised=_raised(b, "exploits_vulnerability", b.exploits_vulnerability),
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
            is_raised=_raised(answer, "intimate_imagery", answer.intimate_imagery),
            summary=answer,
            cited=("art:5:1:ba", *route_points, *conceals, APPLICATION_DATES),
            applies_from=DECEMBER_PROHIBITIONS_APPLY_FROM,
            facts=POINT_BA_FACTS,
        ),
        Practice(
            point="art:5:1:bb",
            reading=every(need(answer.child_abuse_material, texts.CHILD_ABUSE_MATERIAL), routes),
            is_raised=_raised(answer, "child_abuse_material", answer.child_abuse_material),
            summary=answer,
            cited=("art:5:1:bb", *route_points, APPLICATION_DATES),
            applies_from=DECEMBER_PROHIBITIONS_APPLY_FROM,
            facts=POINT_BB_FACTS,
        ),
    )


def _other_alternative_met(answer: SocialScoringAnswer) -> bool:
    """Point (c) is met by (i) or (ii): an open question on one, with the other met, is moot."""
    if answer.social_scoring is not Answer.YES:
        return False
    other = {
        SocialScoringOpenOn.UNRELATED_CONTEXT: answer.disproportionate_treatment,
        SocialScoringOpenOn.DISPROPORTIONATE: answer.unrelated_context_treatment,
    }
    return other.get(answer.open_on) is Answer.YES


def _settled_if_moot(answer: SocialScoringAnswer) -> SocialScoringAnswer:
    """The answer, read as settled in law when its open question is moot (the other
    alternative is met), as a new copy; otherwise unchanged. Read before the open fact is held
    strict (`held_strict_answer`), so a moot alternative is neither held nor cited."""
    if not _other_alternative_met(answer):
        return answer
    return answer.model_copy(update={"settled_in_law": Settled.YES, "open_question": None})


def _has_crime_risk_cue(answer: CrimeRiskAnswer) -> bool:
    """Whether the description gives a sign of the practice of point (d) (user, 2026-10-15): a
    "yes" to either fact that describes it, that the system assesses a person's risk of
    offending, or that the assessment rests on profiling or personality traits alone. Art.
    5(1)(d) bans only that assessment, and spares support for a human assessment that rests on
    objective, verifiable facts linked to a criminal activity (recital 42). A description that
    says neither gives no sign of the ban, so the ban is not assumed: it is asked."""
    return Answer.YES in (answer.crime_risk_assessment, answer.solely_profiling)


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
            is_raised=_raised(c, "social_scoring", c.social_scoring),
            summary=c,
            cited=("art:5:1:c", *_yes_points(treatments)),
        ),
        Practice(
            point="art:5:1:d",
            reading=every(
                need(d.crime_risk_assessment, texts.CRIME_RISK_ASSESSMENT),
                need(d.solely_profiling, texts.SOLELY_PROFILING),
                need(d.fact_based_assessment, texts.FACT_BASED_ASSESSMENT, wanted=Answer.NO),
            ),
            is_raised=_raised(d, "crime_risk_assessment", d.crime_risk_assessment),
            summary=d,
            cited=("art:5:1:d",),
            has_cue=_has_crime_risk_cue(d),
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
            is_raised=_raised(e, "untargeted_face_scraping", e.untargeted_face_scraping),
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
            is_raised=_raised(f, "infers_emotions", f.infers_emotions)
            and _raised(f, "workplace_or_education", f.workplace_or_education),
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
            is_raised=_raised(g, "biometric_categorisation", g.biometric_categorisation),
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
        is_raised=_raised(answer, "real_time_identification", answer.real_time_identification),
        summary=answer,
        cited=("art:5:1:h", *conditions, *(("art:5:4",) if is_permitted else ())),
        is_permitted_use=is_permitted,
    )


def held_strict_answer(answer: ProhibitedAnswer) -> ProhibitedAnswer:
    """The answer with each practice's open fact (`open_on`) set to its stricter value (B2), as a
    new copy: the model's own answer to a fact the law leaves open never decides anything."""
    return answer.model_copy(
        update={
            "manipulation": _held(answer.manipulation),
            "vulnerability": _held(answer.vulnerability),
            "sexual_material": _held(answer.sexual_material),
            "social_scoring": _held(_settled_if_moot(answer.social_scoring)),
            "crime_risk": _held(answer.crime_risk),
            "face_scraping": _held(answer.face_scraping),
            "emotion_recognition": _held(answer.emotion_recognition),
            "biometric_categorisation": _held(answer.biometric_categorisation),
            "remote_identification": _held(answer.remote_identification),
        }
    )


def _held[P: HeldOpen](part: P) -> P:
    """`open_in_law.held_strict` for one practice's answer part."""
    return held_strict(part, STRICT_VALUES, _part_facts(part))


def practices(answer: ProhibitedAnswer, law_version: LawVersion) -> tuple[Practice, ...]:
    """Every Art. 5(1) practice read from the answer, each open fact held strict
    (`held_strict_answer`), in the order of the Act. The original text has no points (ba) or
    (bb), so they are left out for it."""
    held = held_strict_answer(answer)
    sexual = _sexual_material_practices(held.sexual_material)
    return (
        *_harm_practices(held),
        *(sexual if law_version is LawVersion.AMENDED else ()),
        *_profiling_practices(held),
        *_biometric_practices(held),
        _remote_identification(held.remote_identification),
    )
