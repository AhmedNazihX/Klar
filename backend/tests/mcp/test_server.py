"""The MCP server (aiact/mcp/server.py) run in-process through the SDK's in-memory client: the
tool list and schemas, argument validation, `list_obligations`, which needs no database (the
searches and lookups against the database are in tests/db/test_mcp_server.py), and
`classify_system` over scripted engine nodes (no model, database or network) on the caller's own
OpenRouter key."""

import logging
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from langchain_openrouter import ChatOpenRouter
from mcp import Client
from mcp.types import CallToolResult, TextContent
from openrouter.components.security import Security
from pydantic import SecretStr

from aiact.engine import classify as classify_module
from aiact.engine.classify import engine_nodes
from aiact.engine.clients import engine_chats, engine_embeddings, refusal_chats
from aiact.engine.graph import EngineNodes
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.engine.usage import UsageMeter
from aiact.llm import EmbeddingError, OpenRouterEmbeddings
from aiact.mcp import server as server_module
from aiact.mcp.server import (
    MAX_PROVISION_ID_CHARS,
    MAX_QUERY_CHARS,
    MISSING_KEY,
    build_server,
    own_key_settings,
)
from aiact.obligations import list as obligations_module
from aiact.obligations.list import ObligationList, load_table
from aiact.retrieval.provisions import Provision
from aiact.schemas import (
    DISCLAIMER_DE,
    DISCLAIMER_EN,
    STEP_ORDER,
    Citation,
    ClassificationResult,
    Language,
    LawVersion,
    RiskClass,
    StepName,
    StepResult,
)
from aiact.settings import Settings, get_settings
from tests.conftest import REFUSAL_ROUTE

LOOKUPS = {"search_ai_act", "get_provision", "list_obligations"}
TOOLS = {*LOOKUPS, "classify_system"}
HIDDEN_ARGUMENTS = {"include_held_out", "exclude_source_example_ids", "max_distance"}
"""Search options an outside agent must never set (decision 012; C8's cut-off is the server's);
tests/test_isolation.py checks the same names."""


def property_names(schema: object) -> set[str]:
    """Every property name anywhere in a JSON Schema: the top level, nested objects, `$defs`,
    `anyOf` branches and array items, so an opt-in inside a model argument is found too."""
    if isinstance(schema, list):
        return set().union(*(property_names(item) for item in schema))
    if not isinstance(schema, dict):
        return set()
    properties = schema.get("properties")
    names = set(properties) if isinstance(properties, dict) else set()
    return names.union(*(property_names(value) for value in schema.values()))


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


@pytest.fixture(autouse=True)
def _only_fake_keys(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The environment carries the fake keys, and an environment variable beats backend/.env: a
    `get_settings()` reach (a bug these tests catch) never brings a real key into a test."""
    monkeypatch.setenv("OPENROUTER_API_KEY", APP_KEY)
    monkeypatch.setenv("MCP_OPENROUTER_API_KEY", OWN_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    server = build_server(connect=_no_connection, embedder=NoEmbedder())
    async with Client(server) as connected:
        yield connected


def _error_text(result: CallToolResult) -> str:
    assert result.is_error, result
    return " ".join(part.text for part in result.content if isinstance(part, TextContent))


@pytest.mark.anyio
async def test_the_server_lists_the_lookups_as_read_only_and_classify_as_paid(
    client: Client,
) -> None:
    tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == TOOLS
    for tool in tools:
        assert tool.annotations is not None
        # A classification spends the user's credit: a client must not run it unasked.
        assert tool.annotations.read_only_hint is (tool.name in LOOKUPS)
        # A lookup gives the same answer twice; a classification is a model's reading.
        assert tool.annotations.idempotent_hint is (tool.name in LOOKUPS)
        assert tool.annotations.open_world_hint is (tool.name not in LOOKUPS)
        assert tool.output_schema is not None
        assert tool.description and "\n    " not in tool.description  # no source indentation
        assert {"law_version", "disclaimer"} <= set(tool.output_schema["properties"])


@pytest.mark.anyio
async def test_no_tool_exposes_the_held_out_or_exclude_options(client: Client) -> None:
    for tool in (await client.list_tools()).tools:
        assert property_names(tool.input_schema).isdisjoint(HIDDEN_ARGUMENTS), tool.name


def test_property_names_reach_nested_objects_and_defs() -> None:
    """An opt-in in a model argument: under `$defs`, behind an `anyOf`, or in an array's items."""
    schema = {
        "properties": {
            "query": {"type": "string"},
            "options": {"anyOf": [{"$ref": "#/$defs/Options"}, {"type": "null"}]},
            "filters": {"items": {"properties": {"max_distance": {"type": "number"}}}},
        },
        "$defs": {"Options": {"properties": {"include_held_out": {"type": "boolean"}}}},
    }
    assert property_names(schema) == {
        "query",
        "options",
        "filters",
        "max_distance",
        "include_held_out",
    }


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


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("legacy", "applies_from"),
    [
        # Duties only after a significant change: the date stays the route's own.
        ("legacy_unchanged", date(2027, 12, 2)),
        # A public-authority system: providers and deployers comply by 2 August 2030.
        ("legacy_public_authority", date(2030, 8, 2)),
    ],
)
async def test_list_obligations_takes_the_art_111_2_status(
    client: Client, legacy: str, applies_from: date
) -> None:
    """C7b: the deployer's Art. 26 duty, dated 2 December 2027 without a status (see above),
    is marked with the system's Art. 111(2) status."""
    arguments = {
        "role": "deployer",
        "risk_class": "high_risk",
        "route": "annex_iii",
        "legacy": legacy,
    }
    result = await client.call_tool("list_obligations", arguments)
    obligations = ObligationList.model_validate(result.structured_content)
    [art_26_1] = [duty for duty in obligations.obligations if duty.article == "art:26:1"]
    assert art_26_1.legacy == legacy
    assert art_26_1.applies_from == applies_from


@pytest.mark.anyio
async def test_list_obligations_rejects_an_unknown_art_111_2_status(client: Client) -> None:
    arguments = {"role": "deployer", "risk_class": "high_risk", "legacy": "grandfathered"}
    text = _error_text(await client.call_tool("list_obligations", arguments))
    assert "'legacy_unchanged' or 'legacy_public_authority'" in text


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
    assert "not modelled for the amended text: the table holds the original text" in text


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


# --- classify_system ----------------------------------------------------------------------------

APP_KEY = "sk-or-v1-the-apps-own-key"
OWN_KEY = "sk-or-v1-the-mcp-users-key"
DESCRIPTION = (
    "We use a tool that reads incoming job applications, scores them, and shows HR a ranked "
    "shortlist. We bought it from a vendor and didn't change it."
)
SECRET = "the-model-quoted-this-description"
"""Text a failed node's `__cause__` carries (pydantic's input_value fragment of a reply)."""
HIGH_RISK_STEP = StepResult(
    step=StepName.HIGH_RISK,
    decision="High-risk: recruitment (Annex III point 4(a)).",
    citations=(
        Citation(
            provision_id="annex:III:4:a",
            document_id="ai-act-consolidated",
            law_version=LawVersion.AMENDED,
            language=Language.EN,
            quote="recruitment or selection of natural persons",
        ),
    ),
)
SCRIPT = Script(
    checks={StepName.HIGH_RISK: CheckOutcome(step=HIGH_RISK_STEP)}, risk_class=RiskClass.HIGH_RISK
)


def _on_own_key(key: SecretStr | str | None) -> bool:
    """Whether `key` is the MCP user's own. A bool, so a failing assert prints no key."""
    value = key.get_secret_value() if isinstance(key, SecretStr) else key
    return value == OWN_KEY


def _embedder_key(embedder: OpenRouterEmbeddings) -> str | None:
    """The key the embedder's OpenRouter client sends."""
    security = embedder._client.sdk_configuration.security
    return security.api_key if isinstance(security, Security) else None


def mcp_settings(**values: object) -> Settings:
    """Settings with the app's key and the MCP user's own, unless `values` say otherwise."""
    configured: dict[str, object] = {
        "openrouter_api_key": SecretStr(APP_KEY),
        "mcp_openrouter_api_key": SecretStr(OWN_KEY),
        **values,
    }
    return Settings(_env_file=None, **configured)  # pyright: ignore[reportCallIssue]


@dataclass
class ScriptedEngine:
    """Scripted nodes that note the settings each run is built with and the input it reads;
    `failing` names a check that raises."""

    failing: StepName | None = None
    settings: list[Settings] = field(default_factory=list)
    inputs: list[EngineState] = field(default_factory=list)

    def build(self, settings: Settings, meter: UsageMeter) -> EngineNodes:
        self.settings.append(settings)
        nodes = scripted_nodes(SCRIPT)

        def facts(state: EngineState) -> FactsOutcome:
            self.inputs.append(state)
            return nodes.facts(state)

        checks = dict(nodes.checks)
        if self.failing is not None:
            checks[self.failing] = _fails
        return EngineNodes(facts=facts, checks=checks, finalize=nodes.finalize)


def _fails(_state: EngineState) -> CheckOutcome:
    """The node's own error, so the secret sits on `ClassificationFailedError.__cause__`."""
    raise ValueError(f"input_value='{SECRET}'")


async def _classify(
    arguments: Mapping[str, object], engine: ScriptedEngine, settings: Settings | None = None
) -> CallToolResult:
    server = build_server(
        connect=_no_connection,
        embedder=NoEmbedder(),
        settings=settings or mcp_settings(),
        build_nodes=engine.build,
    )
    async with Client(server) as client:
        return await client.call_tool("classify_system", dict(arguments))


@pytest.mark.anyio
@pytest.mark.parametrize(("language", "notice"), [("en", DISCLAIMER_EN), ("de", DISCLAIMER_DE)])
async def test_classify_system_returns_the_engines_result_with_version_and_notice(
    language: str, notice: str
) -> None:
    engine = ScriptedEngine()
    arguments = {"description": DESCRIPTION, "language": language, "as_of": "2026-10-06"}
    result = await _classify(arguments, engine)
    assert not result.is_error, result
    classification = ClassificationResult.model_validate(result.structured_content)
    assert classification.risk_class is RiskClass.HIGH_RISK
    assert [step.step for step in classification.steps] == list(STEP_ORDER)
    [high_risk] = [step for step in classification.steps if step.step is StepName.HIGH_RISK]
    assert [citation.provision_id for citation in high_risk.citations] == ["annex:III:4:a"]
    assert classification.law_version is LawVersion.AMENDED
    assert classification.as_of == date(2026, 10, 6)
    assert classification.disclaimer == notice
    [state] = engine.inputs
    assert state["description"] == DESCRIPTION
    assert state.get("language") == language
    # Decision 012: an MCP run never sees the held-out examples and excludes none of its own.
    assert state.get("include_held_out") is False
    assert state.get("exclude_source_example_ids") == ()


@pytest.mark.anyio
async def test_classify_system_takes_the_law_version_and_reads_today_by_default() -> None:
    engine = ScriptedEngine()
    arguments = {"description": DESCRIPTION, "law_version": "original"}
    result = await _classify(arguments, engine)
    classification = ClassificationResult.model_validate(result.structured_content)
    assert classification.law_version is LawVersion.ORIGINAL
    assert classification.as_of == date.today()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("language", "heading"),
    [("en", "Answers to follow-up questions:"), ("de", "Antworten auf Rückfragen:")],
)
async def test_answers_reach_the_description_the_engine_reads(language: str, heading: str) -> None:
    """Decision 019: the answers are appended under a heading, one line each."""
    engine = ScriptedEngine()
    answers = {"uses_biometrics": "No, it only reads\ntyped text.", "is_provider": "No."}
    arguments = {"description": DESCRIPTION, "language": language, "answers": answers}
    assert not (await _classify(arguments, engine)).is_error
    [state] = engine.inputs
    assert state["description"] == (
        f"{DESCRIPTION}\n\n{heading}\n"
        "- uses_biometrics: No, it only reads typed text.\n- is_provider: No."
    )


@pytest.mark.anyio
async def test_the_run_goes_on_the_callers_own_key() -> None:
    engine = ScriptedEngine()
    assert not (await _classify({"description": DESCRIPTION}, engine)).is_error
    [settings] = engine.settings
    assert _on_own_key(settings.openrouter_api_key), "the run is not on the caller's own key"


def _routed_settings() -> Settings:
    """`mcp_settings` with every model of a run routed, as a deployed server has them."""
    return mcp_settings(
        engine_model="openai/gpt-6-luna-20260922",
        engine_provider="azure/eu",
        embedding_model="qwen/qwen3-embedding-8b",
        embedding_provider="nebius",
        **REFUSAL_ROUTE,
    )


def test_the_engines_models_are_built_on_the_callers_own_key() -> None:
    """Every paid call of a run: each node's engine and refusal model, and the query embedder."""
    settings = own_key_settings(_routed_settings())
    models = [*engine_chats(settings).values(), *refusal_chats(settings).values()]
    assert len(models) == 12
    for model in models:
        assert isinstance(model, ChatOpenRouter)
        assert _on_own_key(model.openrouter_api_key), "a model is not on the caller's own key"
    embedder_on_own_key = _on_own_key(_embedder_key(engine_embeddings(settings)))
    assert embedder_on_own_key, "the embedder is not on the caller's own key"


def test_the_engines_own_nodes_embed_on_the_callers_own_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production `build_nodes` passes the run's settings to the query embedder. Building
    the nodes calls no model and opens no connection."""
    built: list[OpenRouterEmbeddings] = []

    def noting_embeddings(settings: Settings) -> OpenRouterEmbeddings:
        built.append(engine_embeddings(settings))
        return built[-1]

    monkeypatch.setattr(classify_module, "engine_embeddings", noting_embeddings)
    engine_nodes(own_key_settings(_routed_settings()), UsageMeter())
    [embedder] = built
    embedder_on_own_key = _on_own_key(_embedder_key(embedder))
    assert embedder_on_own_key, "the nodes' embedder is not on the caller's own key"


def test_every_run_reuses_the_clients_built_on_the_callers_key() -> None:
    """E15: each call makes its own copy of the settings; equal copies find the clients the
    first run built, so no run builds (and leaks) a client of its own."""
    settings = _routed_settings()
    first, again = own_key_settings(settings), own_key_settings(settings)
    assert first == again
    assert engine_chats(first) is engine_chats(again)
    assert refusal_chats(first) is refusal_chats(again)
    assert engine_embeddings(first) is engine_embeddings(again)


@pytest.mark.anyio
@pytest.mark.parametrize("own_key", [None, SecretStr(""), SecretStr("   ")])
async def test_without_its_own_key_classify_system_refuses_before_any_model_call(
    own_key: SecretStr | None, caplog: pytest.LogCaptureFixture
) -> None:
    """The app's OPENROUTER_API_KEY is set, and still never used."""
    engine = ScriptedEngine()
    with caplog.at_level(logging.DEBUG):
        result = await _classify(
            {"description": DESCRIPTION}, engine, mcp_settings(mcp_openrouter_api_key=own_key)
        )
    text = _error_text(result)
    assert text == f"Error executing tool classify_system: {MISSING_KEY}"
    assert "MCP_OPENROUTER_API_KEY" in text
    assert engine.settings == []
    assert APP_KEY not in caplog.text


@pytest.mark.anyio
async def test_the_default_engine_is_never_built_without_the_callers_key() -> None:
    """The production path (the engine's own nodes, which these settings' missing model ids
    would turn into a crash) stops at the key check."""
    server = build_server(settings=mcp_settings(mcp_openrouter_api_key=None))
    async with Client(server) as client:
        result = await client.call_tool("classify_system", {"description": DESCRIPTION})
    assert MISSING_KEY in _error_text(result)


@pytest.mark.anyio
async def test_classify_system_takes_only_the_requests_fields_within_its_limits(
    client: Client,
) -> None:
    """ClassifyRequest's limits (E10): 20,000 characters, 40 answers of 1,000."""
    tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    schema = tools["classify_system"].input_schema
    assert set(schema["properties"]) == {
        "description",
        "language",
        "law_version",
        "as_of",
        "answers",
    }
    assert schema["required"] == ["description"]
    assert schema["properties"]["description"]["maxLength"] == 20_000
    answers = schema["properties"]["answers"]["anyOf"][0]
    assert answers["maxProperties"] == 40
    [answer] = answers["patternProperties"].values()
    assert answer["maxLength"] == 1_000


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"description": ""}, "at least 1 character"),
        ({"description": "x" * 20_001}, "at most 20000 characters"),
        ({"description": DESCRIPTION, "language": "fr"}, "'en' or 'de'"),
        ({"description": DESCRIPTION, "law_version": "draft"}, "'original' or 'amended'"),
        ({"description": DESCRIPTION, "as_of": "2020-01-01"}, "greater than or equal"),
        ({"description": DESCRIPTION, "answers": {"Bad key": "No."}}, "should match pattern"),
        ({"description": DESCRIPTION, "answers": {"q": ""}}, "at least 1 character"),
        ({"description": DESCRIPTION, "answers": {"q": "x" * 1_001}}, "at most 1000 characters"),
        (
            {"description": DESCRIPTION, "answers": {f"q{n}": "No." for n in range(41)}},
            "at most 40 items",
        ),
    ],
)
async def test_bad_classify_arguments_are_rejected_before_the_engine(
    arguments: dict[str, object], message: str
) -> None:
    engine = ScriptedEngine()
    text = _error_text(await _classify(arguments, engine))
    assert "Error executing tool classify_system: " in text
    assert message in text
    assert engine.settings == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"description": " \n\t "}, "the description is blank"),
        ({"description": DESCRIPTION, "answers": {"q": "   "}}, "an answer is blank"),
    ],
)
async def test_blank_text_is_refused_without_quoting_the_request(
    arguments: dict[str, object], message: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The model validator's own pydantic error would carry the whole request as its input."""
    engine = ScriptedEngine()
    with caplog.at_level(logging.DEBUG):
        text = _error_text(await _classify(arguments, engine))
    assert message in text
    assert engine.settings == []
    for seen in (text, caplog.text):
        assert DESCRIPTION not in seen
        assert "input_value" not in seen


@pytest.mark.anyio
async def test_a_failed_check_names_the_check_and_nothing_else(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = ScriptedEngine(failing=StepName.HIGH_RISK)
    with caplog.at_level(logging.DEBUG):
        result = await _classify({"description": DESCRIPTION}, engine)
    text = _error_text(result)
    assert "the high_risk node failed, so the run gives no class" in text
    # One possible cause among others: a paused database fails the run the same way.
    assert text.endswith(
        ". Try again later; if it keeps failing, the cause may be MCP_OPENROUTER_API_KEY (not a "
        "valid OpenRouter key, or out of credit) or this server's database connection"
    )
    assert result.structured_content is None
    for seen in (text, caplog.text):
        for private in (SECRET, DESCRIPTION, OWN_KEY, APP_KEY, "Traceback"):
            assert private not in seen
