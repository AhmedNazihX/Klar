"""`POST /documents/vendor-letter`: the short vendor letter a classification result calls for
(P28; decision 026 item 3), with P8a's three automatic checks on it.

The body's result is validated here against the result contract (`ClassificationResult`'s own
rules), so a letter is drafted from a result the backend validated, never from a row the browser
wrote unchecked (P3's audit). The body takes it as a JSON object, validated in the route: the
result model as a request body would split its schema into `-Input` and `-Output` ones and
rename the frontend's generated result types. A result that breaks the contract is a 422 with a
fixed message that quotes none of it.

No model and no database are involved: the letter holds the result's facts, the user's answers
word for word and the template's wording. The route shares the lookups' rate limit; the body
cap (`API_MAX_BODY_BYTES`) bounds the result and the answers. Nothing here logs the result or
the answers, and an error names no part of them.
"""

from collections.abc import Mapping
from typing import Annotated, ClassVar

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field, JsonValue, StringConstraints, ValidationError, WithJsonSchema

from aiact.api.dependencies import limit_lookups
from aiact.drafting import (
    CheckResult,
    DraftDocument,
    NoVendorLetterError,
    UnknownQuestionError,
    draft_vendor_letter,
    run_checks,
)
from aiact.drafting.models import QuestionKey
from aiact.schemas import ClassificationResult, Language
from aiact.schemas.base import ContractModel

router = APIRouter(prefix="/documents", dependencies=[Depends(limit_lookups)])

NO_LETTER = (
    "This result calls for no vendor letter: only a prohibited result or a legally ambiguous "
    "one does."
)
UNKNOWN_QUESTION = "An answer names a question the letter doesn't ask."
INVALID_RESULT = "The result is not a valid classification result."

ResultJson = Annotated[
    dict[str, JsonValue],
    WithJsonSchema(
        {
            "type": "object",
            "additionalProperties": True,
            "description": "A `ClassificationResult`, as the `result` event of `POST /classify` "
            "carries it; the route validates it against the result contract.",
        }
    ),
]
"""A `ClassificationResult` as JSON, validated by the route."""


class VendorLetterRequest(ContractModel):
    """A classification result, the letter's language and the answers given so far."""

    MAX_ANSWERS: ClassVar[int] = 10
    """Well above the three questions a letter asks."""
    MAX_ANSWER_CHARS: ClassVar[int] = 2_000

    result: ResultJson = Field(
        description="The classification result, as `POST /classify` sent it."
    )
    language: Language = Field(description="The language of the letter's wording and notice.")
    answers: Mapping[
        QuestionKey, Annotated[str, StringConstraints(max_length=MAX_ANSWER_CHARS)]
    ] = Field(
        default_factory=dict,
        max_length=MAX_ANSWERS,
        description="The interview answers by question key (vendor, tool_name, sender); a "
        'question left out stays "To fill in".',
    )


class VendorLetter(ContractModel):
    """The drafted letter (labelled DRAFT, with the notice) and the automatic checks on it."""

    document: DraftDocument
    checks: tuple[CheckResult, ...]


@router.post(
    "/vendor-letter",
    name="draft_vendor_letter",
    response_model=VendorLetter,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Not a valid result, a result that calls for no vendor letter, or an "
            "answer to a question the letter doesn't ask"
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Too many requests"},
    },
)
def vendor_letter(body: VendorLetterRequest) -> VendorLetter:
    """Draft the vendor letter the result calls for: a message about a prohibited result, or a
    request for the vendor's assessment of a legally ambiguous one. Guidance, not legal
    advice."""
    try:
        result = ClassificationResult.model_validate(body.result)
    except ValidationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, INVALID_RESULT) from None
    try:
        document = draft_vendor_letter(result, body.answers, body.language)
    except NoVendorLetterError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NO_LETTER) from None
    except UnknownQuestionError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, UNKNOWN_QUESTION) from None
    checks = run_checks(document, result, body.answers, size_class=None)
    return VendorLetter(document=document, checks=checks)
