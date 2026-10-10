"""`POST /qa`: one question about the AI Act, or about one result, answered with the provisions
it rests on (P7; decision 026, Ask and Reviewer).

The body is the question, its language, the law version the screen shows and, for a question
about a result, the result as the browser holds it (validated against the result contract and
nothing more, as for the reports, decision 031; a question about a result reads the result's own
law version and date). It has no retrieval options: `include_held_out` never reaches the search
(decision 012). The answer is `aiact.qa.QaAnswer`, with the law version and the notice.

The route is plain `def`: the search reads Postgres through psycopg's sync driver and the model
call is sync, so FastAPI runs it in its threadpool. It has its own rate limit (`RATE_LIMIT_QA`),
and the app's body limit. A model that isn't configured is a 503 before anything is searched; a
search or model call that fails is a 503 with a fixed message (an unreachable database too, by
the app's handler). Nothing here logs the question, the result or the answer, and no error
quotes them: only the failure's type is logged.
"""

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from openrouter.errors import NoResponseError, OpenRouterError, ResponseValidationError
from pydantic import Field, StringConstraints, ValidationError

from aiact.api.dependencies import (
    ApiContext,
    ConnectionFactory,
    api_context,
    database,
    limit_qa,
)
from aiact.api.documents import ResultJson, valid_result
from aiact.api.errors import UNPROCESSABLE
from aiact.engine.clients import engine_embeddings
from aiact.llm import EmbeddingError, LLMConfigError
from aiact.llm.structured import ChatRoute, ProviderRefusalError
from aiact.qa import QaAnswer, Searcher, answer_question
from aiact.qa.clients import corpus_searcher, qa_route
from aiact.schemas import Language, LawVersion
from aiact.schemas.base import ContractModel

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 1000
"""A question, not a description: the artboards' longest is about 80 characters. Long free text
would also raise the search's keyword threshold (X1b: `SEARCH_MIN_KEYWORD_IDF` grows with the
query's length)."""
UNAVAILABLE = "Questions can't be answered right now. Please try again later."
ANSWER_FAILURES: tuple[type[Exception], ...] = (
    ProviderRefusalError,
    ValidationError,
    EmbeddingError,
    OpenRouterError,
    NoResponseError,
    ResponseValidationError,
    httpx.HTTPError,
    ValueError,
)
"""What a search's embedding or the model call raises when it fails: a refusal, a reply that
doesn't fit, no response, the provider's or the transport's error (ChatOpenRouter raises a
provider's error as a plain `ValueError`)."""

Question = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_CHARS)
]


class QuestionRequest(ContractModel):
    """One question, and the result it is about when it is asked on a result."""

    question: Question = Field(description="The question, in `language`.")
    language: Language = Field(description="The language of the question and the answer.")
    law_version: LawVersion = Field(
        default=LawVersion.AMENDED,
        description="The AI Act text to answer from; a question about a result reads the "
        "result's own.",
    )
    result: ResultJson | None = Field(
        default=None,
        description="The classification result the question is about, as `POST /classify` sent "
        "it; null for a general question.",
    )


def qa_model(context: Annotated[ApiContext, Depends(api_context)]) -> ChatRoute:
    """The Q&A's model (tests replace it); a 503 when it isn't configured."""
    try:
        return qa_route(context.settings)
    except LLMConfigError as exc:
        logger.error("question setup failed: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from None


def qa_search(
    context: Annotated[ApiContext, Depends(api_context)],
    connect: Annotated[ConnectionFactory, Depends(database)],
) -> Searcher:
    """The Q&A's corpus search (tests replace it); a 503 when the embeddings aren't configured."""
    try:
        return corpus_searcher(connect, engine_embeddings(context.settings))
    except LLMConfigError as exc:
        logger.error("question setup failed: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from None


router = APIRouter(responses=UNPROCESSABLE)


@router.post(
    "/qa",
    name="ask_question",
    response_model=QaAnswer,
    dependencies=[Depends(limit_qa)],
    responses={
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Too many questions"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The model or the legal texts are not available"
        },
    },
)
def ask_question(
    body: QuestionRequest,
    route: Annotated[ChatRoute, Depends(qa_model)],
    search: Annotated[Searcher, Depends(qa_search)],
) -> QaAnswer:
    """Answer a question about the AI Act, or about one result, from the AI Act and the
    Commission's guidance, citing the provisions the answer rests on. A question outside them,
    or one asking whether someone complies, gets a fixed answer with no citation. Guidance, not
    legal advice."""
    result = valid_result(body.result) if body.result is not None else None
    try:
        return answer_question(
            body.question,
            body.language,
            law_version=body.law_version,
            result=result,
            search=search,
            route=route,
        )
    except ANSWER_FAILURES as exc:
        logger.error("question failed: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from None
