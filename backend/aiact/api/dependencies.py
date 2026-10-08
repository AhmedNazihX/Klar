"""What the routes get from FastAPI's dependency injection: the app's settings and limits, the
engine's node builder and a way to open a database connection. Tests override `node_builder`
and `database` (`app.dependency_overrides`)."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import cast

import psycopg
from fastapi import HTTPException, Request, status

from aiact import db
from aiact.api.rate_limit import ConcurrencyLimit, RateLimiter
from aiact.engine.classify import NodeBuilder, engine_nodes
from aiact.settings import Settings

ConnectionFactory = Callable[[], AbstractContextManager[psycopg.Connection]]
"""Opens a connection for one lookup; a route opens it only after its input is validated."""

UNKNOWN_CLIENT = "unknown"


@dataclass(frozen=True)
class ApiContext:
    """What `create_app` sets up once per app: its settings and its limits."""

    settings: Settings
    classify_limit: RateLimiter
    lookup_limit: RateLimiter
    classify_slots: ConcurrencyLimit
    export_limit: RateLimiter
    export_slots: ConcurrencyLimit


def context_for(settings: Settings) -> ApiContext:
    return ApiContext(
        settings=settings,
        classify_limit=RateLimiter(settings.rate_limit_classify),
        lookup_limit=RateLimiter(settings.rate_limit_lookups),
        classify_slots=ConcurrencyLimit(settings.classify_max_concurrent),
        export_limit=RateLimiter(settings.rate_limit_exports),
        export_slots=ConcurrencyLimit(settings.export_max_concurrent),
    )


def api_context(request: Request) -> ApiContext:
    """The context `create_app` put on the app's state."""
    return cast(ApiContext, request.app.state.context)


def node_builder() -> NodeBuilder:
    """The engine's own nodes (tests replace them with replayed or scripted ones)."""
    return engine_nodes


def database() -> ConnectionFactory:
    """Connections from DATABASE_URL, one per lookup, closed after it."""
    return db.connect


async def limit_classify(request: Request) -> None:
    _count(api_context(request).classify_limit, request)


async def limit_lookups(request: Request) -> None:
    _count(api_context(request).lookup_limit, request)


async def limit_exports(request: Request) -> None:
    _count(api_context(request).export_limit, request)


def client_key(request: Request) -> str:
    """The client's address, the rate limits' key: the connection's peer (X-Forwarded-For is
    never read here; uvicorn applies it only for API_FORWARDED_ALLOW_IPS)."""
    return request.client.host if request.client is not None else UNKNOWN_CLIENT


def _count(limiter: RateLimiter, request: Request) -> None:
    """Count the request for the client's address, and answer 429, with `Retry-After`, once
    its window is used up."""
    retry_after = limiter.acquire(client_key(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
