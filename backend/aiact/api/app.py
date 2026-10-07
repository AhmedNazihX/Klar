"""The FastAPI app (P1): a thin client of the engine and the retrieval functions (INIT > Tech
stack). `create_app` builds it with its settings and, from the outside in:
- `TrustedHostMiddleware`: only `API_ALLOWED_HOSTS` in the Host header (against DNS rebinding);
- CORS for `CORS_ORIGINS` only, without credentials, exposing `Retry-After`;
- `BodySizeLimit`: a body over `API_MAX_BODY_BYTES` is a 413 before it is read;
- the routes, with their rate limits and the classification slots, and handlers that turn an
  unreachable database into a 503 without its error text, and a request that fails validation
  into a 422 that quotes none of it (`errors.py`).
`API_DOCS=false` hides /docs, /redoc and /openapi.json. `aiact api serve` runs the app;
`aiact api openapi` exports its schema for the frontend's generated client.
"""

import logging
from importlib.metadata import version

import psycopg
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from aiact.api import classify, documents, lookups
from aiact.api.body_limit import BodySizeLimit
from aiact.api.dependencies import context_for
from aiact.api.errors import invalid_request
from aiact.db import DatabaseNotConfiguredError
from aiact.settings import Settings, get_settings

logger = logging.getLogger(__name__)

TITLE = "AI Act Classification Assistant API"
DESCRIPTION = (
    "Classifies AI systems under the EU AI Act, step by step with citations, and looks up the "
    "texts and duties it relies on. Every result is guidance, not legal advice."
)
CORPUS_UNAVAILABLE = "The legal texts are not available right now. Please try again later."
ALLOWED_METHODS = ("GET", "POST")
ALLOWED_HEADERS = ("Content-Type",)
EXPOSED_HEADERS = ("Retry-After",)
DOCS_URL, REDOC_URL, OPENAPI_URL = "/docs", "/redoc", "/openapi.json"


def operation_id(route: APIRoute) -> str:
    """The route's name as its OpenAPI operation id, so the generated client's functions are
    `classify`, `getProvision`… rather than FastAPI's path-derived ids."""
    return route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    """The API with `settings` (default: the process's settings)."""
    settings = settings or get_settings()
    docs = settings.api_docs
    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version=version("aiact"),
        generate_unique_id_function=operation_id,
        docs_url=DOCS_URL if docs else None,
        redoc_url=REDOC_URL if docs else None,
        openapi_url=OPENAPI_URL if docs else None,
    )
    app.state.context = context_for(settings)
    # The last one added runs first.
    app.add_middleware(BodySizeLimit, max_bytes=settings.api_max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=list(ALLOWED_METHODS),
        allow_headers=list(ALLOWED_HEADERS),
        expose_headers=list(EXPOSED_HEADERS),
        allow_credentials=False,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.api_allowed_hosts))
    app.include_router(classify.router)
    app.include_router(lookups.router)
    app.include_router(documents.router)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.add_exception_handler(DatabaseNotConfiguredError, _corpus_unavailable)
    app.add_exception_handler(psycopg.OperationalError, _corpus_unavailable)
    return app


async def _corpus_unavailable(_request: Request, exc: Exception) -> JSONResponse:
    """503 for a database that is unset or unreachable; only the error's type is logged (its
    text may name the server)."""
    logger.error("corpus lookup failed: %s", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": CORPUS_UNAVAILABLE}
    )
