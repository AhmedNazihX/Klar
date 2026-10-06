"""Results and drafts the drafting tests share, derived from INIT's worked example."""

from collections.abc import Callable

from aiact.drafting import DraftDocument, DraftSection
from aiact.drafting.models import status_for, unanswered_count
from aiact.schemas import ClassificationResult, RiskClass
from tests.schemas.builders import rebuild
from tests.schemas.worked_example import worked_example_result

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
