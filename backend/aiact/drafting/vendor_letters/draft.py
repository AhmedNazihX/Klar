"""Which vendor letter a classification result calls for, drafted with the user's answers.

No model is involved: a letter holds the result's facts, the user's answers word for word and
the template's fixed wording, nothing else (INIT > Documentation drafting). Draft only from a
result the backend validated, never from a row the browser wrote (P3's audit).
"""

from aiact.drafting.draft import Answers, draft_document
from aiact.drafting.models import DraftDocument
from aiact.drafting.templates import DocumentTemplate
from aiact.drafting.vendor_letters.fills import open_question, prohibited_quote
from aiact.drafting.vendor_letters.templates import AMBIGUOUS_REQUEST, PROHIBITED_MESSAGE
from aiact.schemas import ClassificationResult, Language


class NoVendorLetterError(ValueError):
    """The result calls for no vendor letter: it is neither a decided prohibited result nor a
    legally ambiguous one."""


def vendor_letter_for(result: ClassificationResult) -> DocumentTemplate | None:
    """The message for a decided prohibited result (the Art. 5 point its step cites), the
    request for a result that leaves a question of law open; None for any other result, a
    result that only needs more information included (the user answers its question)."""
    if prohibited_quote(result) is not None:
        return PROHIBITED_MESSAGE
    if open_question(result) is not None:
        return AMBIGUOUS_REQUEST
    return None


def draft_vendor_letter(
    result: ClassificationResult, answers: Answers, language: Language
) -> DraftDocument:
    """The letter the result calls for, with the answers given for it (by question key).

    `language` sets the template's wording and the notice; the result's facts, question and
    readings stay in the language the result was written in, and the answers in the user's.
    Raises NoVendorLetterError for a result that calls for none, and UnknownQuestionError for
    an answer to a question the letter doesn't ask."""
    template = vendor_letter_for(result)
    if template is None:
        raise NoVendorLetterError(
            "a vendor letter needs a decided prohibited result or a legally ambiguous one"
        )
    return draft_document(template, result, answers, language)
