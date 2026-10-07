"""Results the vendor-letter tests share: a decided prohibited result and legally ambiguous
ones, derived from INIT's worked example (the recorded ones are in `recorded_results.py`)."""

from aiact.schemas import (
    Citation,
    ClassificationResult,
    EvidenceTag,
    Fact,
    OpenQuestion,
    Reading,
    RiskClass,
    SettledBy,
    SettledByKind,
    Status,
    StepName,
    StepResult,
)
from tests.schemas.builders import ends_early, rebuild, steps_with
from tests.schemas.worked_example import STEPS, cite, worked_example_result

EMOTIONS_QUOTE = (
    "the placing on the market, the putting into service for this specific purpose, or the use "
    "of AI systems to infer emotions of a natural person in the areas of workplace and "
    "education institutions"
)
EMOTIONS = cite("art:5:1:f", EMOTIONS_QUOTE)
SCORES_MOODS = Fact(
    text="The tool scores the mood of call-centre staff from their voices",
    evidence=EvidenceTag.INFERRED,
)
FEEDS_BONUS = Fact(text="The scores feed into staff bonuses", evidence=EvidenceTag.ASSUMED)
GUIDANCE = cite("guide:guide-prohibited:para:254", "(254) A call centre using webcams")


def prohibited_step(*citations: Citation) -> StepResult:
    """A decided Art. 5(1)(f) match, citing `citations` (default: the point and a guideline)."""
    return StepResult(
        step=StepName.PROHIBITED,
        decision="Prohibited under Art. 5(1)(f).",
        facts_used=(SCORES_MOODS, FEEDS_BONUS),
        citations=citations or (EMOTIONS, GUIDANCE),
    )


def prohibited_result(step: StepResult | None = None, **changes: object) -> ClassificationResult:
    """The worked example ended at a decided Art. 5(1)(f) match."""
    deciding = step or prohibited_step()
    steps = [STEPS[0].model_dump(), deciding.model_dump()]
    result = ends_early(RiskClass.PROHIBITED, steps, Status.DECIDED)
    return rebuild(result, **{"deciding_facts": deciding.facts_used, **changes})


ART_6_3 = cite("art:6:3:a", "the AI system is intended to perform a narrow procedural task")
ANNEX_III_4_A = STEPS[2].citations[0]

EXEMPTION_QUESTION = OpenQuestion(
    question="Is ranking applicants only a narrow procedural task under Art. 6(3)(a)?",
    readings=(
        Reading(
            title="High-risk under Annex III point 4(a)",
            risk_class=RiskClass.HIGH_RISK,
            explanation="Ranking applicants shapes who gets hired.",
            citation=ANNEX_III_4_A,
            consequence="If this holds, the high-risk duties apply from 2 December 2027.",
            is_applied=True,
        ),
        Reading(
            title="Exempt under Art. 6(3)",
            explanation="The ranking only sorts applications for a person to read.",
            citation=ART_6_3,
            consequence="If this holds, the provider must document its assessment that the "
            "exemption applies before placing it on the market, and register it (Art. 6(4), "
            "49(2)).",
        ),
    ),
    settled_by=(
        SettledBy(
            kind=SettledByKind.GUIDANCE,
            text="Final Commission guidelines on high-risk classification (still a draft, "
            "19 May 2026)",
        ),
        SettledBy(
            kind=SettledByKind.PROVIDER,
            text="The provider's own Art. 6(3) assessment, documented under Art. 6(4), if it "
            "made one",
        ),
    ),
)


def exemption_result() -> ClassificationResult:
    """The worked example with its Art. 6(3) exemption left open in law (ResultAmbiguous)."""
    step = StepResult(
        step=StepName.HIGH_RISK,
        decision="Assumed high-risk until the Art. 6(3) question is settled",
        facts_used=STEPS[2].facts_used,
        citations=(ANNEX_III_4_A, ART_6_3),
        status=Status.LEGALLY_AMBIGUOUS,
        open_question=EXEMPTION_QUESTION,
    )
    return rebuild(worked_example_result(), status=Status.LEGALLY_AMBIGUOUS, steps=steps_with(step))
