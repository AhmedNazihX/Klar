"""`POST /documents/vendor-letter`: the short vendor letter a classification result calls for
(P28; decision 026 item 3), with P8a's three automatic checks on it.

The body's result is validated here against the result contract (`ClassificationResult`'s own
rules) and nothing more: it may be a row the browser wrote or an imported file, so the letter
never takes the Act's text from it (decision 031). The message names the Art. 5(1) points the
result decided on and quotes each from the corpus, at the result's law version and date and in
the letter's language (`quoted_points`); a point the corpus doesn't have refuses the letter.
The result's facts and the user's answers are the user's own, and the letter says it is based
only on the description provided. The body takes the result as a JSON object, validated in the
route: the result model as a request body would split its schema into `-Input` and `-Output`
ones and rename the frontend's generated result types.

No model is involved. The corpus is read only for a prohibited result, over one connection,
through `get_provision` (held-out examples hidden; untraced, as no engine run is current), in
the threadpool, inside the lookups' rate limit; the body cap (`API_MAX_BODY_BYTES`) bounds the
result and the answers. Nothing here logs the result or the answers, and no error names any part
of them: a refused letter is a 422 with a fixed message, and a body that fails validation is the
app's 422, which quotes none of it (`errors.py`). A letter the drafter can't write from a valid
result logs one line naming the model and the failures' places, never their values.
"""

import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import date
from functools import partial
from pathlib import Path
from typing import Annotated, ClassVar

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field, JsonValue, StringConstraints, ValidationError, WithJsonSchema

from aiact.api.dependencies import (
    ApiContext,
    ConnectionFactory,
    api_context,
    database,
    limit_lookups,
)
from aiact.api.errors import MAX_ERRORS, UNPROCESSABLE, Unprocessable, invalid_field
from aiact.drafting import (
    Answers,
    CheckResult,
    DraftDocument,
    LawQuotes,
    NoVendorLetterError,
    UnknownPointError,
    UnknownQuestionError,
    draft_vendor_letter,
    quoted_points,
    run_checks,
)
from aiact.drafting.models import QuestionKey
from aiact.engine.citations import CitationSource, CorpusCitations, load_omnibus_changes
from aiact.engine.nodes.common import provision_citation
from aiact.schemas import Citation, ClassificationResult, Language, LawVersion
from aiact.schemas.base import ContractModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents", dependencies=[Depends(limit_lookups)], responses=UNPROCESSABLE
)

NO_LETTER = (
    "This result calls for no vendor letter: only a prohibited result or a legally ambiguous "
    "one does."
)
UNKNOWN_QUESTION = "An answer names a question the letter doesn't ask."
INVALID_RESULT = "The result is not a valid classification result."
UNKNOWN_POINT = "The result cites a point of Art. 5(1) the AI Act's text doesn't have."

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
    language: Language = Field(
        description="The language of the letter's wording, its quotes of the Act and the notice."
    )
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


SourceOpener = Callable[[], AbstractContextManager[CitationSource]]
"""Opens the corpus for one letter's lookups."""


@dataclass(frozen=True)
class CorpusQuotes:
    """`LawQuotes` over the corpus: each provision as the citation validator quotes it (the
    corpus row, marked when the Omnibus changed it), all of one letter's over one opening of
    the corpus."""

    open_source: SourceOpener
    data_dir: Path
    """Where the parsed Omnibus is, for its marker (`load_omnibus_changes`, read once)."""

    def __call__(
        self,
        provision_ids: Sequence[str],
        language: Language,
        law_version: LawVersion,
        as_of: date | None,
    ) -> tuple[Citation, ...]:
        omnibus = load_omnibus_changes(self.data_dir)
        with self.open_source() as source:
            found = [source.provision(pid, language, law_version, as_of) for pid in provision_ids]
        return tuple(
            provision_citation(provision).model_copy(
                update={"changed_by_omnibus": omnibus.marks(provision)}
            )
            for provision in found
        )


@contextmanager
def corpus_source(connect: ConnectionFactory) -> Iterator[CitationSource]:
    """The corpus over one connection, closed after the lookups."""
    with connect() as connection:
        yield CorpusCitations(connection)


def law_quotes(
    connect: Annotated[ConnectionFactory, Depends(database)],
    context: Annotated[ApiContext, Depends(api_context)],
) -> LawQuotes:
    """The corpus's text of the Act; a connection opens only when a letter quotes it. Tests
    override this dependency."""
    return CorpusQuotes(partial(corpus_source, connect), context.settings.aiact_data_dir)


@router.post(
    "/vendor-letter",
    name="draft_vendor_letter",
    response_model=VendorLetter,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": Unprocessable,
            "description": "Not a valid request or result, a result that calls for no vendor "
            "letter or cites a point of Art. 5(1) the Act doesn't have, or an answer to a "
            "question the letter doesn't ask; the body quotes none of it",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Too many requests"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "The corpus is unreachable"},
    },
)
def vendor_letter(
    body: VendorLetterRequest, quotes_from: Annotated[LawQuotes, Depends(law_quotes)]
) -> VendorLetter:
    """Draft the vendor letter the result calls for: a message about a prohibited result, or a
    request for the vendor's assessment of a legally ambiguous one. Guidance, not legal
    advice."""
    result = _valid_result(body.result)
    try:
        quotes = quoted_points(result, body.language, quotes_from)
    except UnknownPointError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, UNKNOWN_POINT) from None
    document = _letter(result, body.answers, body.language, quotes)
    checks = run_checks(document, result, body.answers, size_class=None, quotes=quotes)
    return VendorLetter(document=document, checks=checks)


def _valid_result(posted: dict[str, JsonValue]) -> ClassificationResult:
    """The posted result, if it keeps the result contract; a 422 that quotes none of it if not."""
    try:
        return ClassificationResult.model_validate(posted)
    except ValidationError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, INVALID_RESULT) from None


def _log_unwritable(exc: ValidationError) -> None:
    """One line on a letter the drafter couldn't write: the model and where each failure is,
    as the 422 body names them (`invalid_field`), never a value."""
    places = [invalid_field(dict(error)) for error in exc.errors(include_input=False)[:MAX_ERRORS]]
    where = ", ".join(f"{place.type} at {_place(place.loc)}" for place in places)
    logger.warning("vendor letter refused: %s %s (%s)", type(exc).__name__, exc.title, where)


def _place(loc: Sequence[str | int]) -> str:
    """A failure's field path (`paragraphs.0`), or the model for a failure of the whole."""
    return ".".join(map(str, loc)) or "the model"


def _letter(
    result: ClassificationResult, answers: Answers, language: Language, quotes: Sequence[Citation]
) -> DraftDocument:
    """The letter, or a 422 with a fixed message. A result that keeps the contract can still
    hold a text no letter can (a blank fact): that is not a valid result either."""
    try:
        return draft_vendor_letter(result, answers, language, quotes)
    except NoVendorLetterError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NO_LETTER) from None
    except UnknownQuestionError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, UNKNOWN_QUESTION) from None
    except ValidationError as exc:
        _log_unwritable(exc)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, INVALID_RESULT) from None
