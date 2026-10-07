"""Which vendor letter a classification result calls for, drafted with the user's answers.

No model is involved: a letter holds the result's facts, the user's answers word for word, the
template's fixed wording and, in the message, the Art. 5(1) points quoted from the corpus,
nothing else (INIT > Documentation drafting). A posted result is only checked against the result
contract, so the Act's text is never taken from it (decision 031): the caller reads the quotes
with `quoted_points` and passes them in.
"""

from collections.abc import Sequence

from aiact.drafting.draft import Answers, draft_document, refuse_unasked
from aiact.drafting.models import DraftDocument
from aiact.drafting.templates import DocumentTemplate
from aiact.drafting.vendor_letters.fills import deciding_points, open_question
from aiact.drafting.vendor_letters.templates import AMBIGUOUS_REQUEST, PROHIBITED_MESSAGE
from aiact.schemas import Citation, ClassificationResult, Language


class NoVendorLetterError(ValueError):
    """The result calls for no vendor letter: it is neither a decided prohibited result nor a
    legally ambiguous one."""


def vendor_letter_for(result: ClassificationResult) -> DocumentTemplate | None:
    """The message for a decided prohibited result (the Art. 5(1) points its step cites), the
    request for a result that leaves a question of law open; None for any other result, a
    result that only needs more information included (the user answers its question)."""
    if deciding_points(result):
        return PROHIBITED_MESSAGE
    if open_question(result) is not None:
        return AMBIGUOUS_REQUEST
    return None


def draft_vendor_letter(
    result: ClassificationResult,
    answers: Answers,
    language: Language,
    quotes: Sequence[Citation] = (),
) -> DraftDocument:
    """The letter the result calls for, with the answers given for it (by question key).

    `language` sets the template's wording, the notice and the message's `quotes`, the Art. 5(1)
    points `quoted_points` read from the corpus in that language; the result's facts, question
    and readings stay in the language the result was written in, and the answers in the
    user's. Raises NoVendorLetterError for a result that calls for none, and
    UnknownQuestionError for an answer to a question the letter doesn't ask."""
    template = vendor_letter_for(result)
    if template is None:
        raise NoVendorLetterError(
            "a vendor letter needs a decided prohibited result or a legally ambiguous one"
        )
    refuse_unasked(template, answers)
    return draft_document(template, result, answers, language, quotes=quotes)
