"""The skeletons of the heavy documents (INIT > Documentation drafting; P8b): the technical
documentation (Art. 11, Annex IV), the quality management system (Art. 17), the risk management
system (Art. 9) and the fundamental rights impact assessment (Art. 27).

Every section a provision requires appears, quoting its requirement word for word (`quotes.py`).
The sections the engine knows are pre-filled; the others are "To fill in" until the guided
interview's answers fill them, word for word (P9 writes them up as prose). A skeleton never holds
content the user didn't supply.
"""

from collections.abc import Mapping

from aiact.drafting.draft import Answers, draft_document
from aiact.drafting.models import DraftDocument, SizeClass
from aiact.drafting.skeletons.annex_iv import ANNEX_IV_SKELETON, SIMPLIFIED_FORM_NOTE
from aiact.drafting.skeletons.art_9 import ART_9_SKELETON
from aiact.drafting.skeletons.art_17 import ART_17_SKELETON
from aiact.drafting.skeletons.art_27 import ART_27_SKELETON
from aiact.drafting.templates import DocumentTemplate
from aiact.schemas import ClassificationResult, Language

SKELETON_TEMPLATES: tuple[DocumentTemplate, ...] = (
    ANNEX_IV_SKELETON,
    ART_17_SKELETON,
    ART_9_SKELETON,
    ART_27_SKELETON,
)
"""Every skeleton, in the order the documents list shows them. Their ids are the `document`
keys of the obligations seed (C9)."""


def skeleton_templates_for(result: ClassificationResult) -> tuple[DocumentTemplate, ...]:
    """The skeletons whose duty the result lists: Annex IV (Art. 11(1)), Art. 17 (Art. 16(c)) and
    Art. 9 (Art. 16(a)) for a high-risk provider, Art. 27 for a deployer the result lists the
    impact assessment for. The engine lists only the duties of the result's roles."""
    articles = {obligation.article for obligation in result.obligations}
    return tuple(template for template in SKELETON_TEMPLATES if template.article in articles)


def draft_skeletons(
    result: ClassificationResult,
    answers: Mapping[str, Answers],
    language: Language,
    size_class: SizeClass | None,
) -> tuple[DraftDocument, ...]:
    """Every skeleton the result calls for, drafted with the answers given per template id.

    `size_class` is the company profile's (P19), passed in by the caller, or None without a
    profile: an SME or a small mid-cap gets the note that a simplified Annex IV form is
    expected. The stated facts and the answers stay in the language the user wrote them in."""
    return tuple(
        draft_document(template, result, answers.get(template.id, {}), language, size_class)
        for template in skeleton_templates_for(result)
    )


__all__ = [
    "ANNEX_IV_SKELETON",
    "ART_9_SKELETON",
    "ART_17_SKELETON",
    "ART_27_SKELETON",
    "SIMPLIFIED_FORM_NOTE",
    "SKELETON_TEMPLATES",
    "draft_skeletons",
    "skeleton_templates_for",
]
