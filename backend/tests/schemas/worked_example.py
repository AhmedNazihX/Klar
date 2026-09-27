"""INIT's worked example (recruitment tool → high_risk, deployer, Annex III 4(a)) as a result."""

from datetime import date

from aiact.schemas import (
    DISCLAIMER_EN,
    Citation,
    ClassificationResult,
    EvidenceTag,
    Fact,
    Language,
    LawVersion,
    Obligation,
    RiskClass,
    Role,
    SourceSpan,
    Status,
    StepName,
    StepResult,
)

DESCRIPTION = (
    "We're a 40-person logistics company. We use a tool that reads incoming job applications, "
    "scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't change it."
)
DOCUMENT_ID = "ai-act-consolidated-2026-07-27"
HIGH_RISK_DUTIES_FROM = date(2027, 12, 2)


def stated(phrase: str, text: str) -> Fact:
    """A stated fact whose span points at `phrase` in the description."""
    start = DESCRIPTION.index(phrase)
    return Fact(
        text=text,
        evidence=EvidenceTag.STATED,
        source_span=SourceSpan(start=start, end=start + len(phrase)),
    )


def cite(provision_id: str, quote: str) -> Citation:
    return Citation(
        provision_id=provision_id,
        document_id=DOCUMENT_ID,
        law_version=LawVersion.AMENDED,
        language=Language.EN,
        quote=quote,
    )


RANKS = stated(
    "scores them, and shows HR a ranked shortlist", "The tool scores and ranks applicants"
)
UNMODIFIED = stated("didn't change it", "The tool was not modified")
BOUGHT = stated("We bought it from a vendor", "The company uses a tool bought from a vendor")
NOT_REBRANDED = Fact(text="The tool is used under the vendor's name", evidence=EvidenceTag.ASSUMED)
EU_USE = Fact(text="The tool is used in the EU", evidence=EvidenceTag.ASSUMED)
NO_PRACTICE = Fact(text="No prohibited practice is described", evidence=EvidenceTag.INFERRED)
NO_INTERACTION = Fact(
    text="The tool doesn't interact with applicants or generate content",
    evidence=EvidenceTag.INFERRED,
)

STEPS = (
    StepResult(
        step=StepName.SCOPE,
        decision="In scope: an AI system used in the EU",
        facts_used=(RANKS, EU_USE),
        citations=(cite("art:3:1", "'AI system' means a machine-based system"),),
    ),
    StepResult(
        step=StepName.PROHIBITED,
        decision="No prohibited practice matches",
        facts_used=(NO_PRACTICE,),
        citations=(cite("art:5:1", "The following AI practices shall be prohibited:"),),
    ),
    StepResult(
        step=StepName.HIGH_RISK,
        decision="High-risk: recruitment use; ranking candidates is profiling, so Art. 6(3) "
        "does not exempt it",
        facts_used=(RANKS,),
        citations=(
            cite(
                "annex:III:4:a",
                "AI systems intended to be used for the recruitment or selection of natural "
                "persons, in particular to place targeted job advertisements, to analyse and "
                "filter job applications, and to evaluate candidates",
            ),
            cite(
                "art:6:3",
                "an AI system referred to in Annex III shall always be considered to be "
                "high-risk where the AI system performs profiling of natural persons",
            ),
        ),
    ),
    StepResult(
        step=StepName.TRANSPARENCY,
        decision="No separate transparency duty identified from the description",
        facts_used=(NO_INTERACTION,),
        citations=(
            cite(
                "art:50:1",
                "Providers shall ensure that AI systems intended to interact directly with "
                "natural persons are designed and developed in such a way that the natural "
                "persons concerned are informed that they are interacting with an AI system",
            ),
        ),
    ),
    StepResult(
        step=StepName.ROLE_OBLIGATIONS,
        decision="Stays a deployer: not modified, not rebranded, used for its intended purpose",
        facts_used=(BOUGHT, UNMODIFIED, NOT_REBRANDED),
        citations=(
            cite(
                "art:26:1",
                "Deployers of high-risk AI systems shall take appropriate technical and "
                "organisational measures to ensure they use such systems in accordance with "
                "the instructions for use accompanying the systems",
            ),
        ),
    ),
)

OBLIGATIONS = tuple(
    Obligation(duty=duty, article=article, applies_from=HIGH_RISK_DUTIES_FROM)
    for duty, article in (
        ("Use the system according to the provider's instructions", "art:26:1"),
        ("Assign human oversight to competent people", "art:26:2"),
        ("Keep the logs the system generates", "art:26:6"),
        ("Inform workers' representatives before use at the workplace", "art:26:7"),
        ("Inform applicants that the system is used to decide about them", "art:26:11"),
    )
)


def worked_example_result() -> ClassificationResult:
    return ClassificationResult(
        facts=(BOUGHT, RANKS, UNMODIFIED, NOT_REBRANDED, EU_USE),
        steps=STEPS,
        risk_class=RiskClass.HIGH_RISK,
        status=Status.DECIDED,
        role=Role.DEPLOYER,
        annex_point="annex:III:4:a",
        deciding_facts=(RANKS, UNMODIFIED, NOT_REBRANDED),
        obligations=OBLIGATIONS,
        law_version=LawVersion.AMENDED,
        as_of=date(2026, 9, 27),
        disclaimer=DISCLAIMER_EN,
        follow_up_questions=(
            "Do you use the tool under the vendor's name, without your own branding?",
            "Is the tool used in the EU?",
        ),
    )
