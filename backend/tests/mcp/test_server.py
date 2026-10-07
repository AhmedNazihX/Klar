"""The MCP server (aiact/mcp/server.py) run in-process through the SDK's in-memory client: the
tool list and schemas, argument validation, and `list_obligations`, which needs no database
(the searches and lookups against the database are in tests/db/test_mcp_server.py)."""

from collections.abc import AsyncIterator
from contextlib import AbstractContextManager, nullcontext
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from aiact.llm import EmbeddingError
from aiact.mcp import server as server_module
from aiact.mcp.server import MAX_PROVISION_ID_CHARS, MAX_QUERY_CHARS, build_server
from aiact.obligations import list as obligations_module
from aiact.obligations.list import ObligationList, load_table
from aiact.retrieval.provisions import Provision
from aiact.schemas import DISCLAIMER_DE, DISCLAIMER_EN

TOOLS = {"search_ai_act", "get_provision", "list_obligations"}
HIDDEN_ARGUMENTS = {"include_held_out", "exclude_source_example_ids", "max_distance"}
"""Search options an outside agent must never set (decision 012; C8's cut-off is the server's)."""


class NoConnection:
    """Fails the call if it gets as far as using the database."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"the database was used ({name})")


def _no_connection() -> AbstractContextManager[Any]:
    return nullcontext(NoConnection())


class NoEmbedder:
    """Fails the test if a call gets as far as embedding the query."""

    model = "test/none"
    dimensions = 3

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("the query was embedded")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    server = build_server(connect=_no_connection, embedder=NoEmbedder())
    async with Client(server) as connected:
        yield connected


def _error_text(result: CallToolResult) -> str:
    assert result.is_error, result
    return " ".join(part.text for part in result.content if isinstance(part, TextContent))


@pytest.mark.anyio
async def test_the_server_lists_the_three_lookup_tools_as_read_only(client: Client) -> None:
    tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == TOOLS
    for tool in tools:
        assert tool.annotations is not None and tool.annotations.read_only_hint
        assert tool.output_schema is not None
        assert tool.description and "\n    " not in tool.description  # no source indentation
        assert {"law_version", "disclaimer"} <= set(tool.output_schema["properties"])


@pytest.mark.anyio
async def test_no_tool_exposes_the_held_out_or_exclude_options(client: Client) -> None:
    for tool in (await client.list_tools()).tools:
        assert set(tool.input_schema["properties"]).isdisjoint(HIDDEN_ARGUMENTS), tool.name


@pytest.mark.anyio
async def test_search_exposes_found_and_each_hits_similarity(client: Client) -> None:
    tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    schema = tools["search_ai_act"].output_schema
    assert schema is not None
    assert "found" in schema["properties"]
    assert "similarity" in schema["$defs"]["SearchHit"]["properties"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("search_ai_act", {"query": ""}, "at least 1 character"),
        ("search_ai_act", {"query": "x" * (MAX_QUERY_CHARS + 1)}, "at most 4000 characters"),
        ("search_ai_act", {"query": "credit", "language": "fr"}, "'en' or 'de'"),
        ("search_ai_act", {"query": "credit", "law_version": "draft"}, "'original' or 'amended'"),
        ("search_ai_act", {"query": "credit", "as_of": "2026-13-01"}, "valid date"),
        ("search_ai_act", {"query": "credit", "as_of": "2020-01-01"}, "greater than or equal"),
        ("search_ai_act", {"query": "credit", "limit": 0}, "greater than or equal to 1"),
        ("search_ai_act", {"query": "credit", "limit": 51}, "less than or equal to 50"),
        ("search_ai_act", {"query": "credit", "doc_types": ["faq"]}, "'law', 'guideline'"),
        ("search_ai_act", {"query": "credit", "doc_types": []}, "at least 1 item"),
        ("get_provision", {"provision_id": "art 5; drop table"}, "should match pattern"),
        ("get_provision", {"provision_id": "art:" + "1" * MAX_PROVISION_ID_CHARS}, "at most 200"),
        ("list_obligations", {"role": "auditor", "risk_class": "high_risk"}, "'provider'"),
        ("list_obligations", {"role": "deployer", "risk_class": "high_risk", "route": "x"}, ""),
        (
            "list_obligations",
            {"role": "deployer", "risk_class": "high_risk", "law_version": "original"},
            "Input should be 'amended'",
        ),
    ],
)
async def test_bad_arguments_are_rejected_before_any_lookup(
    client: Client, tool: str, arguments: dict[str, object], message: str
) -> None:
    """NoConnection and NoEmbedder would fail the call with a masked crash instead."""
    text = _error_text(await client.call_tool(tool, arguments))
    assert f"Error executing tool {tool}: " in text
    assert message in text


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        (
            "search_ai_act",
            {"query": "credit", "law_version": "original", "as_of": "2026-09-30"},
            "as_of resolves only against the amended text",
        ),
        (
            "search_ai_act",
            {"query": "   "},
            "the search query is empty",
        ),
        (
            "get_provision",
            {"provision_id": "art:4", "law_version": "original", "as_of": "2026-09-30"},
            "as_of resolves only against the amended text",
        ),
        ("get_provision", {"provision_id": "chapter:3"}, "unknown provision id prefix"),
    ],
)
async def test_errors_the_caller_can_fix_come_back_with_their_message(
    client: Client, tool: str, arguments: dict[str, object], message: str
) -> None:
    assert message in _error_text(await client.call_tool(tool, arguments))


@pytest.mark.anyio
async def test_a_crash_keeps_its_text_on_the_server(client: Client) -> None:
    """NoConnection raises an AssertionError: the caller sees only the tool name."""
    result = await client.call_tool("get_provision", {"provision_id": "art:4"})
    assert _error_text(result) == "Error executing tool get_provision"


@pytest.mark.anyio
async def test_list_obligations_returns_the_duties_with_version_and_notice(
    client: Client,
) -> None:
    arguments = {"role": "deployer", "risk_class": "high_risk", "route": "annex_iii"}
    result = await client.call_tool("list_obligations", arguments)
    assert not result.is_error
    obligations = ObligationList.model_validate(result.structured_content)
    assert obligations.law_version == "amended"
    assert obligations.disclaimer == DISCLAIMER_EN
    art_26_1 = [duty for duty in obligations.obligations if duty.article == "art:26:1"]
    assert [duty.applies_from for duty in art_26_1] == [date(2027, 12, 2)]


@pytest.mark.anyio
async def test_list_obligations_gives_the_notice_in_german(client: Client) -> None:
    arguments = {"role": "provider", "risk_class": "limited_risk", "language": "de"}
    result = await client.call_tool("list_obligations", arguments)
    assert ObligationList.model_validate(result.structured_content).disclaimer == DISCLAIMER_DE


@pytest.mark.anyio
async def test_list_obligations_carries_the_screens_texts(client: Client) -> None:
    """The labels in both languages, the German duty, the provider group and the document (C9)."""
    arguments = {"role": "provider", "risk_class": "high_risk", "route": "annex_iii"}
    result = await client.call_tool("list_obligations", arguments)
    assert isinstance(result.structured_content, dict)
    duties = result.structured_content["obligations"]
    art_11 = next(duty for duty in duties if duty["article"] == "art:11:1")
    assert art_11["label_en"] == "Write the technical documentation and keep it up to date"
    assert art_11["label_de"] == "Die technische Dokumentation erstellen und aktuell halten"
    assert art_11["duty_de"].startswith("Die technische Dokumentation (Anhang IV) erstellen")
    assert art_11["group"] == "prove"
    assert art_11["document"] == "annex_iv_technical_documentation"


class FailingEmbedder(NoEmbedder):
    """The embeddings API fails with details a caller must not see."""

    def embed_query(self, text: str) -> list[float]:
        raise EmbeddingError("upstream 500 secret-detail")


@pytest.mark.anyio
async def test_an_embedding_failure_says_so_without_its_details() -> None:
    server = build_server(connect=_no_connection, embedder=FailingEmbedder())
    async with Client(server) as client:
        text = _error_text(await client.call_tool("search_ai_act", {"query": "credit"}))
    assert "the query could not be embedded just now" in text
    assert "secret-detail" not in text


@pytest.mark.anyio
async def test_a_broken_obligations_table_is_a_crash_without_its_path(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`load_table` raises ObligationsError (a ValueError) naming the file: that is ours."""
    missing = tmp_path / "obligations.yaml"
    monkeypatch.setattr(obligations_module, "default_table", lambda: load_table(missing))
    arguments = {"role": "deployer", "risk_class": "high_risk"}
    text = _error_text(await client.call_tool("list_obligations", arguments))
    assert text == "Error executing tool list_obligations"


OTHER_VERSION_TABLE = """\
law_version: original
checked_on: 2026-09-28
dates_reviewed: true
obligations:
  - key: ai-literacy
    roles: [deployer]
    risk_classes: [high_risk]
    duty: Support AI literacy.
    duty_de: KI-Kompetenz fördern.
    label_en: Support AI literacy
    label_de: KI-Kompetenz fördern
    article: art:4
    applies_from: 2025-02-02
"""


@pytest.mark.anyio
async def test_a_law_version_the_table_lacks_comes_back_with_its_message(
    client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "obligations.yaml"
    path.write_text(OTHER_VERSION_TABLE, encoding="utf-8")
    monkeypatch.setattr(obligations_module, "default_table", lambda: load_table(path))
    arguments = {"role": "deployer", "risk_class": "high_risk"}
    text = _error_text(await client.call_tool("list_obligations", arguments))
    assert "holds the original text, not amended" in text


@pytest.mark.anyio
async def test_a_failed_validation_inside_a_lookup_is_a_crash(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pydantic ValidationError is a ValueError, but it is our bug, not the caller's."""

    def invalid_lookup(*args: object, **kwargs: object) -> Provision:
        return Provision.model_validate({"provision_id": "art:4"})

    monkeypatch.setattr(server_module, "get_provision", invalid_lookup)
    result = await client.call_tool("get_provision", {"provision_id": "art:4"})
    assert _error_text(result) == "Error executing tool get_provision"
