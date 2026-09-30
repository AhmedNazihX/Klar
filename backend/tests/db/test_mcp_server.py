"""The MCP server's `search_ai_act` and `get_provision` tools (aiact/mcp/server.py) run in-process
against the local Supabase Postgres.

The tests load one guideline of their own (`test-p2a-guide`) inside the `db` fixture's rolled-back
transaction, with a made-up word (vorpalix) the real corpus never uses and 3-dimensional vectors
under a test model, so neither search arm can reach the real corpus and the tests run on an empty
database (CI). The server gets the test's connection and a fixed query embedder. The last test
reads the loaded corpus and skips when it isn't there.
"""

from collections.abc import AsyncIterator
from contextlib import AbstractContextManager, nullcontext
from datetime import date

import psycopg
import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from aiact.corpus.build import DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.embed import vector_literal
from aiact.corpus.load import load_all
from aiact.mcp.server import build_server
from aiact.retrieval.provisions import Provision
from aiact.retrieval.search import SearchResults
from aiact.schemas import DISCLAIMER_DE, DISCLAIMER_EN, Language, LawVersion

pytestmark = pytest.mark.db

TEST_MODEL = "test-p2a/fake"
PUBLISHED = date(2026, 5, 19)
AFTER_OMNIBUS = "2026-09-29"
QUERY_VECTOR = [1.0, 0.0, 0.0]

GUIDE = DocumentRow(
    doc_key="test-p2a-guide",
    title="Test guideline",
    celex=None,
    doc_type="guideline",
    is_amending=False,
    status="draft",
    law_version=None,
    language="en",
    published_on=PUBLISHED,
    in_force_from=None,
    source_url="https://ec.europa.eu/",
    sha256="c" * 64,
)
VISIBLE_ID = "guide:test-p2a-guide:para:1"
HELD_OUT_ID = "guide:test-p2a-guide:ex:001"
LOADS = (
    DocumentLoad(GUIDE, (
        ProvisionRow(VISIBLE_ID, None, None, "I. Purpose", "Guidance on vorpalix systems.",
                     PUBLISHED),
        ProvisionRow(HELD_OUT_ID, None, None, None, "A held-out vorpalix example.", PUBLISHED,
                     source_example_id="hr-ex-001", is_held_out=True),
    )),
)  # fmt: skip

EMBED = """
    insert into provision_embeddings (provision_row_id, model, dims, embedding, content_sha256)
    select p.id, %(model)s, 3, %(vector)s::extensions.vector, p.content_sha256
    from provisions p join documents d on d.id = p.document_id
    where d.doc_key = 'test-p2a-guide' and p.provision_id = %(provision_id)s
"""


class FixedEmbedder:
    """Returns the same vector for any query, under the test model."""

    model = TEST_MODEL
    dimensions = len(QUERY_VECTOR)

    def embed_query(self, text: str) -> list[float]:
        return QUERY_VECTOR


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def corpus(db: psycopg.Connection) -> psycopg.Connection:
    load_all(db, LOADS)
    # The held-out row is the query's exact match: only the filter keeps it out.
    for provision_id, vector in ((VISIBLE_ID, [0.9, 0.1, 0.0]), (HELD_OUT_ID, QUERY_VECTOR)):
        params = {
            "model": TEST_MODEL,
            "vector": vector_literal(vector),
            "provision_id": provision_id,
        }
        db.execute(EMBED, params)
    return db


def _server_on(connection: psycopg.Connection) -> Client:
    def connect() -> AbstractContextManager[psycopg.Connection]:
        return nullcontext(connection)

    return Client(build_server(connect=connect, embedder=FixedEmbedder()))


@pytest.fixture
async def client(corpus: psycopg.Connection) -> AsyncIterator[Client]:
    async with _server_on(corpus) as connected:
        yield connected


def _ok(result: CallToolResult) -> dict[str, object]:
    assert not result.is_error, result.content
    assert result.structured_content is not None
    return result.structured_content


def _error_text(result: CallToolResult) -> str:
    assert result.is_error, result
    return " ".join(part.text for part in result.content if isinstance(part, TextContent))


async def _search(client: Client, **arguments: object) -> SearchResults:
    base = {"query": "vorpalix", "as_of": AFTER_OMNIBUS, "doc_types": ["guideline"]}
    result = await client.call_tool("search_ai_act", base | arguments)
    return SearchResults.model_validate(_ok(result))


@pytest.mark.anyio
async def test_search_returns_hits_with_version_notice_found_and_similarity(
    client: Client,
) -> None:
    results = await _search(client)
    hits = [hit for hit in results.hits if hit.doc_key == "test-p2a-guide"]
    assert [hit.provision_id for hit in hits] == [VISIBLE_ID]
    assert results.found
    assert hits[0].similarity is not None and hits[0].similarity > 0.9
    assert results.law_version is LawVersion.AMENDED
    assert results.as_of == date(2026, 9, 29)
    assert results.disclaimer == DISCLAIMER_EN


@pytest.mark.anyio
async def test_search_never_returns_a_held_out_row_even_when_asked(client: Client) -> None:
    """The opt-in isn't a tool argument; an extra `include_held_out` is dropped unused."""
    for extra in ({}, {"include_held_out": True, "exclude_source_example_ids": []}):
        results = await _search(client, **extra)
        assert HELD_OUT_ID not in {hit.provision_id for hit in results.hits}


@pytest.mark.anyio
async def test_a_german_search_carries_the_german_notice(client: Client) -> None:
    results = await _search(client, language="de")
    assert results.language is Language.DE
    assert results.disclaimer == DISCLAIMER_DE
    assert all(hit.language is Language.DE for hit in results.hits)


@pytest.mark.anyio
async def test_get_provision_returns_the_text_with_version_and_notice(client: Client) -> None:
    result = await client.call_tool(
        "get_provision", {"provision_id": VISIBLE_ID, "as_of": AFTER_OMNIBUS}
    )
    provision = Provision.model_validate(_ok(result))
    assert provision.text == "Guidance on vorpalix systems."
    assert provision.doc_key == "test-p2a-guide"
    assert provision.law_version is None  # guidance belongs to neither text
    assert (provision.language, provision.english_only) == (Language.EN, False)
    assert provision.disclaimer == DISCLAIMER_EN


@pytest.mark.anyio
async def test_get_provision_falls_back_to_english_for_german(client: Client) -> None:
    arguments = {"provision_id": VISIBLE_ID, "language": "de", "as_of": AFTER_OMNIBUS}
    provision = Provision.model_validate(_ok(await client.call_tool("get_provision", arguments)))
    assert (provision.language, provision.english_only) == (Language.EN, True)
    assert provision.disclaimer == DISCLAIMER_DE


@pytest.mark.anyio
async def test_a_held_out_or_missing_provision_is_a_tool_error(client: Client) -> None:
    for provision_id in (HELD_OUT_ID, "guide:test-p2a-guide:para:99"):
        arguments = {"provision_id": provision_id, "include_held_out": True}
        text = _error_text(await client.call_tool("get_provision", arguments))
        assert f"no text of {provision_id!r}" in text


@pytest.mark.anyio
async def test_the_loaded_art_4_original_and_amended(db: psycopg.Connection) -> None:
    loaded = db.execute(
        "select count(*) from documents where doc_key in ('ai-act', 'ai-act-consolidated')"
    ).fetchone()
    if loaded is None or loaded[0] < 4:
        pytest.skip("the corpus isn't loaded; run `aiact corpus load`")
    async with _server_on(db) as client:
        original = await client.call_tool(
            "get_provision", {"provision_id": "art:4", "law_version": "original"}
        )
        amended = await client.call_tool(
            "get_provision", {"provision_id": "art:4", "as_of": AFTER_OMNIBUS}
        )
    assert "to ensure, to their best extent" in Provision.model_validate(_ok(original)).text
    after = Provision.model_validate(_ok(amended))
    assert "support the development of AI literacy" in after.text
    assert after.law_version is LawVersion.AMENDED
