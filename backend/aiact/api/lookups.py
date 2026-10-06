"""The lookups the interface reads besides a classification (P1): one provision's text, the
duties for a role and class, and the corpus's texts. Each wraps the retrieval or obligations
function the MCP tools wrap too, and returns its result, which carries the law version and the
"guidance, not legal advice" notice.

Held-out examples stay hidden: no route takes `include_held_out` (decision 012). The routes are
plain `def`: retrieval reads Postgres through psycopg's sync driver, so FastAPI runs them in
its threadpool and the event loop never waits on the database. A route opens its connection
only once FastAPI has validated the path and query, so a bad lookup is a 422 even while the
database is down.
"""

from datetime import date
from typing import Annotated, Any, Literal

from annotated_types import Ge
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError

from aiact.api.dependencies import ConnectionFactory, database, limit_lookups
from aiact.corpus.build import AI_ACT_IN_FORCE
from aiact.obligations.list import ObligationList, list_obligations
from aiact.retrieval.documents import DocumentList, list_documents
from aiact.retrieval.provisions import (
    MAX_PROVISION_ID_CHARS,
    PROVISION_ID_RE,
    Provision,
    ProvisionNotFoundError,
    get_provision,
)
from aiact.schemas import HighRiskRoute, Language, LawVersion, LegacyStatus, RiskClass, Role

router = APIRouter(dependencies=[Depends(limit_lookups)])

Connect = Annotated[ConnectionFactory, Depends(database)]
LanguageQuery = Annotated[
    Language, Query(description="The language of the text and the notice (en or de).")
]

DATABASE_DOWN: dict[int | str, dict[str, Any]] = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "The corpus is unreachable"}
}


@router.get(
    "/provisions/{provision_id}",
    name="get_provision",
    response_model=Provision,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Not a valid lookup"},
        status.HTTP_404_NOT_FOUND: {"description": "No text for that version, date and language"},
        **DATABASE_DOWN,
    },
)
def provision(
    provision_id: Annotated[
        str,
        Path(
            max_length=MAX_PROVISION_ID_CHARS,
            pattern=PROVISION_ID_RE.pattern,
            description="art:<n>[:<paragraph>[:<point>]], annex:<roman>[:<point>…], "
            "recital:<n> or guide:<doc_key>:…; e.g. art:26:1, annex:III:5:b.",
        ),
    ],
    connect: Connect,
    language: LanguageQuery = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
    as_of: Annotated[
        date | None,
        Query(description="The date whose text applies (default today); only for 'amended'."),
        Ge(AI_ACT_IN_FORCE),
    ] = None,
) -> Provision:
    """The exact text of one article, paragraph, annex point, recital or guideline passage, in
    the language asked for; the English text, with `english_only` set, when there is no German
    one."""
    try:
        with connect() as connection:
            return get_provision(provision_id, language, law_version, as_of, connection=connection)
    except ValidationError:
        raise  # our own result failed its contract: a bug, not the caller's error
    except ProvisionNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from None
    except ValueError as error:  # a malformed id or prefix, or `original` with as_of
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from None


@router.get("/obligations", name="list_obligations", response_model=ObligationList)
def obligations(
    role: Role,
    risk_class: RiskClass,
    route: Annotated[
        HighRiskRoute | None,
        Query(description="For a high-risk system: the route, which sets the dates."),
    ] = None,
    law_version: Literal["amended"] = "amended",
    language: LanguageQuery = Language.EN,
    legacy: Annotated[
        LegacyStatus | None,
        Query(description="Art. 111(2): a high-risk system placed on the market before its date."),
    ] = None,
) -> ObligationList:
    """The duties, article references and dates for a role and risk class (the duties are in
    English)."""
    return list_obligations(role, risk_class, route, law_version, language=language, legacy=legacy)


@router.get(
    "/documents", name="list_documents", response_model=DocumentList, responses=DATABASE_DOWN
)
def documents(connect: Connect, language: LanguageQuery = Language.EN) -> DocumentList:
    """The texts the answers draw on: title, status, law version and dates."""
    with connect() as connection:
        return list_documents(language, connection=connection)
