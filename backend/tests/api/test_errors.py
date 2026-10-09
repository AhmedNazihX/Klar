"""The app's 422 for a request that fails validation (aiact/api/errors.py): each failure's type
and the start of its location, never the input, on every route, at any nesting depth, and the
one 422 schema the routes document."""

import json
import logging

import httpx
import pytest
from fastapi import FastAPI

from aiact.api.errors import (
    INVALID_REQUEST,
    MAX_ERRORS,
    MAX_LOC_PART_CHARS,
    MAX_LOC_PARTS,
    Unprocessable,
)
from aiact.api.openapi import openapi_json
from tests.api.conftest import use_builder
from tests.api.test_classify import never_built
from tests.drafting.vendor_builders import prohibited_result

pytestmark = pytest.mark.anyio

SECRET = "Jana Berg, the applicant we turned down on 3 May"
"""Text the client sent that no 422 may quote."""
DEPTH = 5_000
"""Deep enough that FastAPI's own handler raised RecursionError encoding the input: a 500."""
CLASSIFY_BODY = {"description": "A tool that ranks applicants.", "language": "en"}


def _nested(depth: int) -> str:
    """A JSON object nested `depth` levels deep, holding the secret at the bottom."""
    return '{"a":' * depth + json.dumps(SECRET) + "}" * depth


def _letter_body(**changes: object) -> dict[str, object]:
    result = prohibited_result().model_dump(mode="json")
    return {"result": result, "language": "en", **changes}


def _refused(response: httpx.Response) -> Unprocessable:
    """The 422 body, checked to quote nothing the client sent."""
    assert response.status_code == 422, response.text
    assert SECRET not in response.text
    body = Unprocessable.model_validate(response.json())
    assert body.detail == INVALID_REQUEST
    assert body.errors
    assert all(len(error.loc) <= MAX_LOC_PARTS for error in body.errors)
    return body


async def test_an_over_long_answer_is_not_echoed(client: httpx.AsyncClient) -> None:
    answer = f"{SECRET} " * 200
    response = await client.post(
        "/documents/vendor-letter", json=_letter_body(answers={"vendor": answer})
    )
    [error] = _refused(response).errors
    assert (error.type, error.loc) == ("string_too_long", ("body", "answers"))


async def test_an_over_long_answer_is_not_logged(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    answer = f"{SECRET} " * 200
    with caplog.at_level(logging.DEBUG):
        response = await client.post(
            "/documents/vendor-letter", json=_letter_body(answers={"vendor": answer})
        )
    _refused(response)
    assert SECRET not in caplog.text


async def test_a_bad_key_and_a_bad_language_are_not_echoed(client: httpx.AsyncClient) -> None:
    body = _letter_body(answers={SECRET: "x"}, language=SECRET, **{SECRET: True})
    response = await client.post("/documents/vendor-letter", json=body)
    errors = _refused(response).errors
    assert {(error.type, error.loc[:2]) for error in errors} >= {
        ("string_pattern_mismatch", ("body", "answers")),
        ("enum", ("body", "language")),
    }
    [extra] = [error for error in errors if error.type == "extra_forbidden"]
    assert extra.loc == ("body", SECRET[:MAX_LOC_PART_CHARS])
    assert MAX_LOC_PART_CHARS == 40


async def test_a_deeply_nested_result_is_a_422_not_a_500(client: httpx.AsyncClient) -> None:
    content = '{"language": "en", "result": ' + _nested(DEPTH) + "}"
    response = await client.post(
        "/documents/vendor-letter",
        content=content,
        headers={"content-type": "application/json"},
    )
    _refused(response)


async def test_an_over_long_description_is_not_echoed_by_classify(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    use_builder(app, never_built)
    body = {**CLASSIFY_BODY, "description": f"{SECRET} " * 2_000}
    [error] = _refused(await client.post("/classify", json=body)).errors
    assert (error.type, error.loc) == ("string_too_long", ("body", "description"))


async def test_a_deeply_nested_classify_body_is_a_422_not_a_500(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    use_builder(app, never_built)
    content = '{"language": "en", "description": ' + _nested(DEPTH) + "}"
    response = await client.post(
        "/classify", content=content, headers={"content-type": "application/json"}
    )
    _refused(response)


async def test_the_failures_listed_are_capped(app: FastAPI, client: httpx.AsyncClient) -> None:
    use_builder(app, never_built)
    extra = {f"field_{number}": SECRET for number in range(MAX_ERRORS + 5)}
    errors = _refused(await client.post("/classify", json={**CLASSIFY_BODY, **extra})).errors
    assert (len(errors), MAX_ERRORS) == (20, 20)


async def test_a_bad_query_is_not_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/documents", params={"language": SECRET})
    [error] = _refused(response).errors
    assert (error.type, error.loc) == ("enum", ("query", "language"))


def test_every_route_documents_the_one_422_schema() -> None:
    schema = json.loads(openapi_json())
    refused = {
        f"{method.upper()} {path}": operation["responses"]["422"]["content"]["application/json"]
        for path, item in schema["paths"].items()
        for method, operation in item.items()
    }
    assert set(refused) == {
        "POST /classify",
        "GET /provisions/{provision_id}",
        "GET /obligations",
        "GET /documents",
        "POST /documents/vendor-letter",
        "POST /documents/list",
        "POST /documents/draft",
        "POST /documents/export",
        "POST /reports/result",
        "POST /reports/inventory",
    }
    assert all(
        body["schema"] == {"$ref": "#/components/schemas/Unprocessable"}
        for body in refused.values()
    )
    schemas = schema["components"]["schemas"]
    assert "Unprocessable" in schemas
    assert "HTTPValidationError" not in schemas
