"""The app as a whole (aiact/api/app.py, openapi.py): CORS for the configured origins only, the
operation ids the generated client uses, no retrieval opt-in anywhere in the schema, and the
committed `frontend/openapi.json` matching the app."""

import json

import httpx
import pytest
from fastapi.middleware.cors import CORSMiddleware

from aiact.api import create_app
from aiact.api.openapi import OPENAPI_FILE, is_openapi_current, openapi_json
from aiact.settings import Settings

ALLOWED = "http://localhost:5173"
OTHER = "https://evil.example"
HIDDEN = {"include_held_out", "exclude_source_example_ids"}
"""Retrieval options no client may set (decision 012)."""


@pytest.mark.anyio
async def test_cors_allows_the_configured_origins_only(client: httpx.AsyncClient) -> None:
    preflight = {"access-control-request-method": "POST"}
    allowed = await client.options("/classify", headers={"origin": ALLOWED, **preflight})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == ALLOWED
    assert "access-control-allow-credentials" not in allowed.headers
    refused = await client.options("/classify", headers={"origin": OTHER, **preflight})
    assert "access-control-allow-origin" not in refused.headers
    simple = await client.get(
        "/obligations?role=deployer&risk_class=minimal_risk", headers={"origin": OTHER}
    )
    assert "access-control-allow-origin" not in simple.headers


def test_the_cors_origins_come_from_the_settings() -> None:
    settings = Settings(_env_file=None, cors_origins="https://klar.example")  # pyright: ignore[reportCallIssue]
    app = create_app(settings)
    [cors] = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors.kwargs["allow_origins"] == ["https://klar.example"]


def test_the_operation_ids_are_the_route_names() -> None:
    schema = json.loads(openapi_json())
    ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert ids == {"classify", "get_provision", "list_obligations", "list_documents"}


def _property_names(value: object) -> set[str]:
    """Every parameter name and schema property name anywhere in an OpenAPI document."""
    if isinstance(value, list):
        return set().union(*(_property_names(item) for item in value))
    if not isinstance(value, dict):
        return set()
    names = set(value.get("properties", {})) if isinstance(value.get("properties"), dict) else set()
    if isinstance(value.get("name"), str) and "in" in value:
        names.add(value["name"])
    return names.union(*(_property_names(item) for item in value.values()))


def test_no_request_or_response_in_the_schema_carries_a_retrieval_option() -> None:
    names = _property_names(json.loads(openapi_json()))
    assert {"description", "provision_id", "risk_class"} <= names  # the walk finds fields
    assert names.isdisjoint(HIDDEN)


def test_the_committed_openapi_schema_matches_the_app() -> None:
    assert is_openapi_current(), (
        f"{OPENAPI_FILE} is stale: run `uv run aiact api openapi`, then `corepack pnpm gen:api` "
        "in frontend/"
    )
