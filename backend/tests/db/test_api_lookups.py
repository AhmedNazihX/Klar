"""`GET /provisions/{id}` and `GET /documents` (aiact/api/lookups.py) against the local Supabase
Postgres, on two test documents loaded inside the `db` fixture's rolled-back transaction: a
guideline in English and German, and a code in English only. The app gets the test's connection
through the `database` dependency."""

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import nullcontext
from datetime import date

import httpx
import psycopg
import pytest
from fastapi import FastAPI

from aiact.api import create_app
from aiact.api.dependencies import database
from aiact.corpus.build import DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.fetch import DEFAULT_MANIFEST, load_manifest
from aiact.corpus.load import load_all
from aiact.retrieval.documents import DocumentInfo, DocumentList
from aiact.retrieval.provisions import Provision
from aiact.schemas import DISCLAIMER_DE, DocumentStatus, Language
from tests.api.conftest import api_settings
from tests.test_isolation import REQUIRE_CORPUS_ENV

pytestmark = pytest.mark.db

PUBLISHED = date(2026, 5, 19)
AFTER = "2026-10-06"


def document(doc_key: str, language: str, title: str, doc_type: str) -> DocumentRow:
    return DocumentRow(
        doc_key=doc_key,
        title=title,
        celex=None,
        doc_type=doc_type,  # pyright: ignore[reportArgumentType]
        is_amending=False,
        status="draft",  # pyright: ignore[reportArgumentType]
        law_version=None,
        language=language,  # pyright: ignore[reportArgumentType]
        published_on=PUBLISHED,
        in_force_from=None,
        source_url="https://ec.europa.eu/",
        sha256="d" * 64,
    )


GUIDE = "test-p1-guide"
CODE = "test-p1-code"
PARA = f"guide:{GUIDE}:para:1"
HELD_OUT = f"guide:{GUIDE}:ex:001"
LOADS = (
    DocumentLoad(document(GUIDE, "en", "Test guideline", "guideline"), (
        ProvisionRow(PARA, None, None, None, "Guidance on vorpalix systems.", PUBLISHED),
        ProvisionRow(HELD_OUT, None, None, None, "A held-out vorpalix example.", PUBLISHED,
                     source_example_id="hr-ex-001", is_held_out=True),
    )),
    DocumentLoad(document(GUIDE, "de", "Test-Leitlinie", "guideline"), (
        ProvisionRow(PARA, None, None, None, "Leitlinien zu Vorpalix-Systemen.", PUBLISHED),
    )),
    DocumentLoad(document(CODE, "en", "Test code of practice", "code"), (
        ProvisionRow(f"guide:{CODE}:para:1", None, None, None, "A code passage.", PUBLISHED),
    )),
)  # fmt: skip


@pytest.fixture
def app(db: psycopg.Connection) -> Iterator[FastAPI]:
    load_all(db, LOADS)
    built = create_app(api_settings())
    built.dependency_overrides[database] = lambda: lambda: nullcontext(db)
    yield built
    built.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.anyio
async def test_a_provision_is_quoted_in_german_when_asked(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/provisions/{PARA}", params={"language": "de", "as_of": AFTER})
    assert response.status_code == 200
    provision = Provision.model_validate(response.json())
    assert provision.text == "Leitlinien zu Vorpalix-Systemen."
    assert provision.language is Language.DE and not provision.english_only
    assert provision.disclaimer == DISCLAIMER_DE


@pytest.mark.anyio
async def test_a_held_out_example_is_not_found_even_when_asked_for(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(
        f"/provisions/{HELD_OUT}", params={"as_of": AFTER, "include_held_out": "true"}
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_documents_are_listed_in_german_with_the_english_fallback(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/documents", params={"language": "de"})
    assert response.status_code == 200
    listed = DocumentList.model_validate(response.json())
    assert listed.disclaimer == DISCLAIMER_DE
    ours = {d.doc_key: d for d in listed.documents if d.doc_key in {GUIDE, CODE}}
    assert ours[GUIDE] == DocumentInfo(
        doc_key=GUIDE,
        title="Test-Leitlinie",
        celex=None,
        doc_type="guideline",
        status=DocumentStatus.DRAFT,
        law_version=None,
        is_amending=False,
        language=Language.DE,
        english_only=False,
        published_on=PUBLISHED,
        in_force_from=None,
    )
    assert ours[CODE].title == "Test code of practice"
    assert ours[CODE].english_only and ours[CODE].language is Language.EN
    keys = [(d.doc_key, d.law_version) for d in listed.documents]
    assert len(keys) == len(set(keys))  # one row per text and law version


@pytest.fixture
def corpus(db: psycopg.Connection) -> psycopg.Connection:
    """The loaded corpus (its German texts included), inside the rolled-back test transaction."""
    row = db.execute("select count(*) from documents where doc_key = 'ai-act'").fetchone()
    if row is None or not row[0]:
        reason = "the corpus isn't loaded; run `aiact corpus load`"
        if os.environ.get(REQUIRE_CORPUS_ENV):
            pytest.fail(reason, pytrace=False)
        pytest.skip(reason)
    return db


@pytest.mark.anyio
async def test_the_corpus_lists_its_german_texts_under_their_german_titles(
    corpus: psycopg.Connection, client: httpx.AsyncClient
) -> None:
    """P32: the German titles come from the manifest through the corpus load, not from code."""
    german = {
        e.id: e.title
        for e in load_manifest(DEFAULT_MANIFEST).documents
        if e.language == "de" and e.available
    }
    response = await client.get("/documents", params={"language": "de"})
    assert response.status_code == 200
    listed = DocumentList.model_validate(response.json())
    titles = {d.doc_key: d.title for d in listed.documents if d.language is Language.DE}
    assert {key: titles.get(key) for key in german} == german
    assert titles["ai-act"] == "Verordnung (EU) 2024/1689 (KI-Verordnung)"
    assert titles["guide-prohibited"] == (
        "Leitlinien der Kommission zu verbotenen Praktiken der künstlichen Intelligenz"
    )
