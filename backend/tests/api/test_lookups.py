"""The lookup routes (aiact/api/lookups.py) without a database: the arguments they pass on (never
the held-out opt-in), their error codes, and `GET /obligations` on the committed table. The
same routes against the local Supabase are in tests/db/test_api_lookups.py."""

from collections.abc import Iterator
from datetime import date

import httpx
import psycopg
import pytest
from fastapi import FastAPI

from aiact.api import lookups as lookups_module
from aiact.api.app import CORPUS_UNAVAILABLE
from aiact.api.dependencies import database
from aiact.db import DatabaseNotConfiguredError
from aiact.retrieval.documents import DocumentList
from aiact.retrieval.provisions import MAX_PROVISION_ID_CHARS, Provision, ProvisionNotFoundError
from aiact.schemas import DISCLAIMER_DE, DISCLAIMER_EN, DocumentStatus, Language, LawVersion

CONNECTION = object()
"""Stands in for the request's connection; the faked lookups only check they got it."""

PROVISION = Provision(
    provision_id="art:26:1",
    doc_key="ai-act-consolidated",
    document_title="Regulation (EU) 2024/1689 (consolidated)",
    doc_type="law",
    law_version=LawVersion.AMENDED,
    status=DocumentStatus.CONSOLIDATED,
    language=Language.DE,
    english_only=False,
    heading=None,
    text="Betreiber von Hochrisiko-KI-Systemen treffen geeignete technische …",
    valid_from=date(2026, 7, 27),
    valid_to=None,
    disclaimer=DISCLAIMER_DE,
)


@pytest.fixture(autouse=True)
def no_database(app: FastAPI) -> None:
    app.dependency_overrides[database] = lambda: CONNECTION


class Calls:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []


@pytest.fixture
def provision_calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    calls = Calls()

    def fake(*args: object, **kwargs: object) -> Provision:
        calls.calls.append((args, kwargs))
        return PROVISION

    monkeypatch.setattr(lookups_module, "get_provision", fake)
    return calls


@pytest.mark.anyio
async def test_a_provision_is_returned_in_the_language_asked_for(
    client: httpx.AsyncClient, provision_calls: Calls
) -> None:
    response = await client.get(
        "/provisions/art:26:1",
        params={"language": "de", "law_version": "amended", "as_of": "2026-10-06"},
    )
    assert response.status_code == 200
    assert Provision.model_validate(response.json()) == PROVISION
    [(args, kwargs)] = provision_calls.calls
    assert args == ("art:26:1", Language.DE, LawVersion.AMENDED, date(2026, 10, 6))
    assert kwargs == {"connection": CONNECTION}


@pytest.mark.anyio
async def test_the_held_out_opt_in_is_not_taken_from_the_query(
    client: httpx.AsyncClient, provision_calls: Calls
) -> None:
    response = await client.get("/provisions/guide:hr:ex:001", params={"include_held_out": "true"})
    assert response.status_code == 200
    [(_args, kwargs)] = provision_calls.calls
    assert "include_held_out" not in kwargs


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/provisions/Art 5", {}),
        ("/provisions/art:" + "1" * MAX_PROVISION_ID_CHARS, {}),
        ("/provisions/art:5", {"language": "fr"}),
        ("/provisions/art:5", {"as_of": "2024-07-31"}),  # before the AI Act entered into force
    ],
    ids=["malformed", "too_long", "language", "before_the_act"],
)
async def test_a_bad_lookup_is_a_422_before_the_database(
    client: httpx.AsyncClient, provision_calls: Calls, path: str, params: dict[str, str]
) -> None:
    assert (await client.get(path, params=params)).status_code == 422
    assert provision_calls.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ProvisionNotFoundError("no text of 'art:999'"), 404),
        (ValueError("as_of resolves only against the amended text"), 400),
    ],
)
async def test_lookup_errors_the_caller_can_fix_keep_their_message(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, error: Exception, status: int
) -> None:
    def fails(*_args: object, **_kwargs: object) -> Provision:
        raise error

    monkeypatch.setattr(lookups_module, "get_provision", fails)
    response = await client.get("/provisions/art:999")
    assert response.status_code == status
    assert response.json() == {"detail": str(error)}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [DatabaseNotConfiguredError("DATABASE_URL is not set"), psycopg.OperationalError("host x")],
)
async def test_an_unreachable_database_is_a_503_without_its_text(
    app: FastAPI, client: httpx.AsyncClient, error: Exception
) -> None:
    def unreachable() -> Iterator[object]:
        raise error
        yield  # a generator dependency, like `database`

    app.dependency_overrides[database] = unreachable
    for path in ("/provisions/art:5", "/documents"):
        response = await client.get(path)
        assert response.status_code == 503
        assert response.json() == {"detail": CORPUS_UNAVAILABLE}


@pytest.mark.anyio
async def test_documents_are_listed_in_the_language_asked_for(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    listed = DocumentList(documents=(), disclaimer=DISCLAIMER_DE)
    calls: list[tuple[object, object]] = []

    def fake(language: Language, *, connection: object) -> DocumentList:
        calls.append((language, connection))
        return listed

    monkeypatch.setattr(lookups_module, "list_documents", fake)
    response = await client.get("/documents", params={"language": "de"})
    assert response.status_code == 200
    assert DocumentList.model_validate(response.json()) == listed
    assert calls == [(Language.DE, CONNECTION)]


@pytest.mark.anyio
async def test_obligations_come_from_the_committed_table(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/obligations",
        params={"role": "deployer", "risk_class": "high_risk", "route": "annex_iii"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["law_version"] == "amended"
    assert body["disclaimer"] == DISCLAIMER_EN
    articles = {o["article"] for o in body["obligations"]}
    assert "art:26:1" in articles
    assert {o["applies_from"] for o in body["obligations"] if o["article"] == "art:26:1"} == {
        "2027-12-02"
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {"role": "deployer", "risk_class": "high_risk", "law_version": "original"},
        {"role": "user", "risk_class": "high_risk"},
        {"role": "deployer"},
    ],
    ids=["original_text", "unknown_role", "no_class"],
)
async def test_a_bad_obligations_query_is_a_422(
    client: httpx.AsyncClient, params: dict[str, str]
) -> None:
    assert (await client.get("/obligations", params=params)).status_code == 422
