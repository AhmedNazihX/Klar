"""The API's 422 body, one shape for every route: a fixed message, and for a request that fails
validation, each failure's type and where it is, but never the input itself.

FastAPI's own handler echoes each failure's `input` and `ctx`: an over-long description or
answer, a forged result or a bad key would come back in the response, and a deeply nested body
makes its JSON encoder raise RecursionError, a 500. `invalid_request` returns only `type` and
the first parts of `loc` (cut short, since a part can be a key the client sent) for the first
`MAX_ERRORS` failures, logs nothing, and never walks the input, so any depth is safe. A route's
own 422 (`HTTPException`) has the same shape with no `errors`.
"""

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field

from aiact.schemas.base import ContractModel

INVALID_REQUEST = "The request is not valid."
MAX_ERRORS = 20
"""The failures listed; a body can fail in many places at once."""
MAX_LOC_PARTS = 2
"""Where a failure is: `body` or `query`, and the field (deeper parts can be the client's keys)."""
MAX_LOC_PART_CHARS = 40
"""A field the model doesn't have (`extra_forbidden`) is named by the client: cut short."""


class InvalidField(ContractModel):
    """One validation failure: its type (e.g. `string_too_long`) and where it is."""

    type: str
    loc: tuple[str | int, ...] = Field(
        description='Where it failed, e.g. ["body", "answers"]; at most two parts.'
    )


class Unprocessable(ContractModel):
    """A 422: why the request can't be processed, quoting none of it."""

    detail: str
    errors: tuple[InvalidField, ...] = Field(
        default=(), description="The validation failures, when the request failed validation."
    )


UNPROCESSABLE_DESCRIPTION = "Not a valid request; the body quotes none of it"
UNPROCESSABLE: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": Unprocessable,
        "description": UNPROCESSABLE_DESCRIPTION,
    }
}
"""The 422 every JSON router documents (FastAPI's default schema lists the input it echoes)."""
UNPROCESSABLE_BESIDE_A_STREAM: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": UNPROCESSABLE_DESCRIPTION,
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Unprocessable"}}},
    }
}
"""The same 422 for a route whose own response is a stream (`POST /classify`): a `model` would be
documented under the stream's media type, so the schema is named by reference (the JSON routes
register it)."""


def _loc_part(part: object) -> str | int:
    if isinstance(part, int):
        return part
    return str(part)[:MAX_LOC_PART_CHARS]


def invalid_field(error: dict[str, Any]) -> InvalidField:
    """A failure's type and the start of its location, nothing else."""
    loc = error.get("loc", ())
    return InvalidField(
        type=str(error.get("type", "")),
        loc=tuple(_loc_part(part) for part in loc[:MAX_LOC_PARTS]),
    )


async def invalid_request(_request: Request, exc: Exception) -> JSONResponse:
    """422 for a request that fails validation, with each failure's type and location only."""
    errors = exc.errors() if isinstance(exc, RequestValidationError) else ()
    body = Unprocessable(
        detail=INVALID_REQUEST, errors=tuple(invalid_field(e) for e in errors[:MAX_ERRORS])
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=body.model_dump(mode="json")
    )
