"""What the routes get from FastAPI's dependency injection: the app's settings and rate limiters,
the engine's node builder and a database connection. Tests override `node_builder` and
`database` (`app.dependency_overrides`)."""

from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

import psycopg
from fastapi import HTTPException, Request, status

from aiact import db
from aiact.api.rate_limit import RateLimiter
from aiact.engine.classify import NodeBuilder, engine_nodes
from aiact.settings import Settings


class Bucket(StrEnum):
    """The rate-limited groups of routes, each with its own limit."""

    CLASSIFY = "classify"
    LOOKUPS = "lookups"


@dataclass(frozen=True)
class ApiContext:
    """What `create_app` sets up once per app: its settings and one limiter per bucket."""

    settings: Settings
    limiters: Mapping[Bucket, RateLimiter]

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            settings=settings,
            limiters={
                Bucket.CLASSIFY: RateLimiter(settings.rate_limit_classify),
                Bucket.LOOKUPS: RateLimiter(settings.rate_limit_lookups),
            },
        )


def api_context(request: Request) -> ApiContext:
    context = getattr(request.app.state, "context", None)
    if not isinstance(context, ApiContext):
        raise RuntimeError("the app was not built by create_app")
    return context


def node_builder() -> NodeBuilder:
    """The engine's own nodes (tests replace them with replayed or scripted ones)."""
    return engine_nodes


def database() -> Iterator[psycopg.Connection]:
    """A connection from DATABASE_URL for one request, closed after it."""
    with db.connect() as connection:
        yield connection


UNKNOWN_CLIENT = "unknown"


def rate_limited(bucket: Bucket) -> Callable[[Request], Awaitable[None]]:
    """A dependency that counts the request against `bucket` for the client's address and
    answers 429, with `Retry-After`, once the window's limit is used up."""

    async def check(request: Request) -> None:
        limiter = api_context(request).limiters[bucket]
        client = request.client.host if request.client is not None else UNKNOWN_CLIENT
        retry_after = limiter.acquire(client)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return check
