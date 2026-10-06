"""Results and drafts the drafting tests share, derived from INIT's worked example."""

from collections.abc import Callable

from aiact.drafting import DraftDocument, DraftSection
from aiact.drafting.models import status_for, unanswered_count
from aiact.schemas import ClassificationResult, LegacyStatus, RiskClass, Role, Status, StepName
from tests.schemas.builders import ambiguous, missing_fact, rebuild, steps_with
from tests.schemas.worked_example import EU_USE, worked_example_result

WORKERS = "art_26_7_workers"
WORKERS_ANSWERS = {
    "recipients": "The works council of the Hamburg site.",
    "tool_and_supplier": "TalentRank, supplied by Rank GmbH.",
    "start_date": "1 March 2027.",
    "reviewer": "HR team lead, as named in the human oversight record.",
}


def limited_risk_result(*duties: str) -> ClassificationResult:
    """The worked example as a limited-risk system with the given Art. 50 duties."""
    return rebuild(
        worked_example_result(),
        risk_class=RiskClass.LIMITED_RISK,
        annex_point=None,
        obligations=(),
        transparency_duties=duties,
    )


def with_sections(document: DraftDocument, sections: tuple[DraftSection, ...]) -> DraftDocument:
    """A valid copy of `document` with other sections (its status follows them)."""
    unanswered = unanswered_count(sections)
    return DraftDocument.model_validate(
        {
            **document.model_dump(),
            "sections": [section.model_dump() for section in sections],
            "unanswered": unanswered,
            "status": status_for(unanswered),
        }
    )


def edit_section(
    document: DraftDocument, key: str, edit: Callable[[DraftSection], DraftSection]
) -> DraftDocument:
    """`document` with the section `key` replaced by `edit(section)`."""
    return with_sections(
        document,
        tuple(edit(section) if section.key == key else section for section in document.sections),
    )


def changed(section: DraftSection, **changes: object) -> DraftSection:
    """A validated copy of `section` with `changes`."""
    return DraftSection.model_validate({**section.model_dump(), **changes})


def needs_information_result() -> ClassificationResult:
    """The worked example paused at the high-risk check for a missing fact."""
    step = missing_fact(StepName.HIGH_RISK)
    return rebuild(
        worked_example_result(), status=Status.NEEDS_MORE_INFORMATION, steps=steps_with(step)
    )


def ambiguous_result() -> ClassificationResult:
    """The worked example with the high-risk check left open in law."""
    step = ambiguous(StepName.HIGH_RISK)
    return rebuild(worked_example_result(), status=Status.LEGALLY_AMBIGUOUS, steps=steps_with(step))


def legacy_result() -> ClassificationResult:
    """The worked example as an Art. 111(2) legacy system: its duties apply only after a
    significant change."""
    result = worked_example_result()
    obligations = tuple(
        item.model_copy(update={"legacy": LegacyStatus.UNCHANGED}) for item in result.obligations
    )
    return rebuild(result, obligations=obligations)


def no_stated_facts_result() -> ClassificationResult:
    """The worked example with only an assumed fact."""
    return rebuild(worked_example_result(), facts=(EU_USE,), deciding_facts=())


def provider_also_deployer_result() -> ClassificationResult:
    return rebuild(worked_example_result(), role=Role.PROVIDER, also_role=Role.DEPLOYER)


def fresh_results() -> tuple[ClassificationResult, ...]:
    """Every kind of result the drafter handles, for checks that must pass on fresh drafts."""
    return (
        worked_example_result(),
        limited_risk_result("art:50:1", "art:50:2", "art:50:3", "art:50:4"),
        needs_information_result(),
        ambiguous_result(),
        legacy_result(),
        no_stated_facts_result(),
        provider_also_deployer_result(),
    )
