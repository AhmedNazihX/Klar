"""The app as a whole (aiact/api/app.py, openapi.py): CORS for the configured origins only, the
operation ids the generated client uses, no retrieval opt-in anywhere in the schema, and the
committed `frontend/openapi.json` matching the app."""

import json

import httpx
import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from aiact.api import create_app
from aiact.api.openapi import OPENAPI_FILE, is_openapi_current, openapi_json
from aiact.settings import Settings
from tests.api.conftest import BASE_URL, api_settings

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


@pytest.mark.anyio
async def test_a_browser_can_read_retry_after(client: httpx.AsyncClient) -> None:
    """A 429 or a busy 503 says when to try again; CORS must expose the header to the page."""
    path = "/obligations?role=deployer&risk_class=minimal_risk"
    responses = [await client.get(path, headers={"origin": ALLOWED}) for _ in range(121)]
    refused = responses[-1]
    assert refused.status_code == 429
    assert refused.headers["access-control-allow-origin"] == ALLOWED
    assert "retry-after" in refused.headers["access-control-expose-headers"].lower()


@pytest.mark.anyio
async def test_a_foreign_host_header_is_a_400(client: httpx.AsyncClient) -> None:
    """Against DNS rebinding: only API_ALLOWED_HOSTS are answered."""
    path = "/obligations?role=deployer&risk_class=minimal_risk"
    assert (await client.get(path)).status_code == 200
    assert (await client.get(path, headers={"host": "attacker.example"})).status_code == 400


def test_the_default_allowed_hosts_are_local() -> None:
    app = create_app(Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    [hosts] = [m for m in app.user_middleware if m.cls is TrustedHostMiddleware]
    assert hosts.kwargs["allowed_hosts"] == ["localhost", "127.0.0.1"]


@pytest.mark.anyio
@pytest.mark.parametrize(("docs", "status"), [(True, 200), (False, 404)])
async def test_the_docs_follow_the_setting(docs: bool, status: int) -> None:
    app = create_app(api_settings(api_docs=docs))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await client.get(path)).status_code == status, path


def test_the_export_is_the_same_with_the_docs_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_DOCS", "false")
    assert is_openapi_current()


def test_the_cors_origins_come_from_the_settings() -> None:
    settings = Settings(_env_file=None, cors_origins="https://klar.example")  # pyright: ignore[reportCallIssue]
    app = create_app(settings)
    [cors] = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors.kwargs["allow_origins"] == ["https://klar.example"]


def test_the_operation_ids_are_the_route_names() -> None:
    schema = json.loads(openapi_json())
    ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert ids == {
        "classify",
        "get_provision",
        "list_obligations",
        "list_documents",
        "list_result_documents",
        "draft_document",
        "export_document",
        "draft_vendor_letter",
        "export_result_report",
        "export_inventory_report",
    }


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
