"""Which short deployer documents a classification result calls for, drafted with the user's
answers (`draft.py` drafts each one).

No model is involved: a draft holds the result's facts, the user's answers word for word and the
template's fixed wording, nothing else (INIT > Documentation drafting). Draft only from a result
the backend validated, never from a row the browser wrote (P3's audit).
"""

from collections.abc import Mapping

from aiact.drafting.draft import Answers, draft_document
from aiact.drafting.models import DraftDocument
from aiact.drafting.templates import DEPLOYER_TEMPLATES, DocumentTemplate
from aiact.schemas import ClassificationResult, Language, Role


def deployer_templates_for(result: ClassificationResult) -> tuple[DocumentTemplate, ...]:
    """The documents the result calls for when the company is a deployer (its role, or the role
    it keeps next to it): one per Art. 26 duty listed, and a disclosure text per deployer duty
    of Art. 50 listed ((3) and (4)). None for any other role."""
    if Role.DEPLOYER not in (result.role, result.also_role):
        return ()
    articles = {obligation.article for obligation in result.obligations}
    articles |= set(result.transparency_duties)
    return tuple(template for template in DEPLOYER_TEMPLATES if template.article in articles)


def draft_deployer_documents(
    result: ClassificationResult,
    answers: Mapping[str, Answers],
    language: Language,
) -> tuple[DraftDocument, ...]:
    """Every document the result calls for, drafted with the answers given per template id.
    Answers for a template the result doesn't call for are kept for a later run, not used.

    `language` sets the template's wording and the notice. The stated facts and the answers stay
    in the language the user wrote them in, even in a draft in the other language: translating
    them would be content the user didn't supply."""
    return tuple(
        draft_document(template, result, answers.get(template.id, {}), language)
        for template in deployer_templates_for(result)
    )
