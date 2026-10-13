"""P7: the Q&A's model is the engine model pinned to its EU endpoint, with one attempt and its own
output cap, built once per settings; its search is `search_ai_act` with the cut-off and V6's top
five, on a connection of its own."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from langchain_openrouter import ChatOpenRouter

from aiact import omnibus as omnibus_records
from aiact.engine.citations import OmnibusChanges
from aiact.llm import LLMConfigError
from aiact.omnibus import OmnibusUnavailableError
from aiact.qa import clients
from aiact.qa.clients import (
    corpus_quotes,
    corpus_searcher,
    qa_chat,
    qa_refusal_chat,
    qa_route,
)
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.schemas import DISCLAIMER_EN, Citation, DocumentStatus, Language, LawVersion
from tests.engine.test_clients import engine_settings
from tests.schemas.worked_example import worked_example_result

DATA_DIR = Path("/data")
"""Never read: the Omnibus's records are stubbed."""


def test_the_qa_model_is_luna_pinned_to_azure_eu_with_one_attempt() -> None:
    chat = qa_chat(engine_settings())
    assert isinstance(chat, ChatOpenRouter)
    assert chat.model_name == "openai/gpt-6-luna-20260922"
    assert chat.openrouter_provider == {
        "data_collection": "deny",
        "zdr": True,
        "order": ["azure/eu"],
        "allow_fallbacks": False,
    }
    assert chat.max_tokens == 3000
    assert chat.max_retries == 0
    sdk_retries = chat.client.sdk_configuration.retry_config  # pyright: ignore[reportAttributeAccessIssue]
    assert sdk_retries is not None and sdk_retries.strategy == "none"


def test_the_route_sends_a_refused_question_to_the_pinned_refusal_model() -> None:
    """Decision 033, as the engine's nodes: Flash-Lite on google-vertex/eu, fallbacks off, with
    the Q&A's output cap and one attempt."""
    route = qa_route(engine_settings())
    assert route.chat is qa_chat(engine_settings())
    second = route.refusal_chat
    assert second is qa_refusal_chat(engine_settings())
    assert isinstance(second, ChatOpenRouter)
    assert second.model_name == "google/gemini-3.1-flash-lite"
    assert second.openrouter_provider == {
        "data_collection": "deny",
        "zdr": True,
        "order": ["google-vertex/eu"],
        "allow_fallbacks": False,
    }
    assert (second.max_tokens, second.max_retries) == (3000, 0)
    sdk_retries = second.client.sdk_configuration.retry_config  # pyright: ignore[reportAttributeAccessIssue]
    assert sdk_retries is not None and sdk_retries.strategy == "none"


@pytest.mark.parametrize("missing", ["refusal_model", "refusal_provider"])
def test_a_missing_refusal_setting_raises(missing: str) -> None:
    with pytest.raises(LLMConfigError):
        qa_route(engine_settings(**{missing: None}))


def test_equal_settings_share_one_model() -> None:
    assert qa_chat(engine_settings()) is qa_chat(engine_settings())
    assert qa_chat(engine_settings(engine_model="openai/gpt-6-sol")) is not qa_chat(
        engine_settings()
    )


@pytest.mark.parametrize("missing", ["engine_model", "engine_provider", "openrouter_api_key"])
def test_a_missing_setting_raises_on_every_call(missing: str) -> None:
    for _ in range(2):
        with pytest.raises(LLMConfigError):
            qa_chat(engine_settings(**{missing: None}))


def test_the_search_uses_v6s_top_five_and_the_settings_cut_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    opened: list[str] = []

    def fake_search(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "results"

    @contextmanager
    def connect() -> Iterator[str]:
        opened.append("open")
        yield "connection"
        opened.append("closed")

    embedder = object()
    monkeypatch.setattr(clients, "search_ai_act", fake_search)
    search = corpus_searcher(connect, embedder)  # pyright: ignore[reportArgumentType]
    on = date(2026, 10, 1)
    assert search("Q?", Language.DE, LawVersion.AMENDED, on) == "results"
    ((args, kwargs),) = calls
    assert args == ("Q?", Language.DE, LawVersion.AMENDED, on)
    assert kwargs == {"limit": 5, "embedder": embedder, "connection": "connection"}
    # No cut-off passed: `search_ai_act`'s default is the SEARCH_MAX_DISTANCE setting; and the
    # held-out opt-in is never passed (decision 012).
    assert "max_distance" not in kwargs and "include_held_out" not in kwargs
    assert opened == ["open", "closed"]


# --- A posted result's citations, quoted again from the corpus (decision 031) --------------------


def _provision(citation: Citation, text: str, **changes: object) -> Provision:
    values: dict[str, object] = {
        "provision_id": citation.provision_id,
        "doc_key": citation.document_id,
        "document_title": "AI Act (consolidated)",
        "doc_type": "law",
        "status": DocumentStatus.CONSOLIDATED,
        "law_version": citation.law_version,
        "language": citation.language,
        "english_only": False,
        "heading": None,
        "text": text,
        "valid_from": date(2024, 8, 1),
        "valid_to": None,
        "disclaimer": DISCLAIMER_EN,
        **changes,
    }
    return Provision.model_validate(values)


def test_the_corpus_quotes_replace_a_posted_quote_and_drop_what_it_doesnt_have(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = worked_example_result()
    citations = [c for step in result.steps for c in step.citations][:2]
    kept, unknown = (c.model_copy(update={"quote": "FORGED"}) for c in citations)
    asked: list[tuple[str, Language, LawVersion | None, date | None, bool]] = []

    class FakeCorpus:
        def __init__(self, connection: object) -> None:
            assert connection == "connection"

        def provision(
            self,
            provision_id: str,
            language: Language,
            law_version: LawVersion | None,
            as_of: date | None,
            *,
            include_held_out: bool = False,
        ) -> Provision:
            asked.append((provision_id, language, law_version, as_of, include_held_out))
            if provision_id == unknown.provision_id:
                raise ProvisionNotFoundError(provision_id)
            return _provision(kept, "The corpus's own text.")

    @contextmanager
    def connect() -> Iterator[str]:
        yield "connection"

    loaded: list[Path] = []

    def omnibus(data_dir: Path) -> OmnibusChanges:
        loaded.append(data_dir)
        return OmnibusChanges(date(2026, 7, 27), frozenset({kept.provision_id}))

    monkeypatch.setattr(clients, "CorpusCitations", FakeCorpus)
    monkeypatch.setattr(omnibus_records, "load_omnibus_changes", omnibus)
    quotes = corpus_quotes(connect, DATA_DIR)  # pyright: ignore[reportArgumentType]
    on = date(2026, 10, 1)
    (quoted,) = quotes([kept, unknown], LawVersion.AMENDED, on)
    assert quoted.quote == "The corpus's own text."
    assert quoted.changed_by_omnibus is True and loaded == [DATA_DIR]
    assert (quoted.document_id, quoted.provision_id) == (kept.document_id, kept.provision_id)
    assert [(pid, held) for pid, *_, held in asked] == [
        (kept.provision_id, False),
        (unknown.provision_id, False),
    ]
    assert all(when == on for *_, when, _ in asked)


def test_no_connection_opens_for_a_result_citing_nothing() -> None:
    def connect() -> Iterator[str]:
        raise AssertionError("no connection expected")

    quotes = corpus_quotes(connect, DATA_DIR)  # pyright: ignore[reportArgumentType]
    assert quotes([], LawVersion.AMENDED, None) == ()


# --- The Omnibus's records, read once and a 503 when they can't be (fix round 2) ----------------

PARSED_OMNIBUS = Path(__file__).parents[3] / "data" / "parsed" / "omnibus.en.jsonl"


def _quote_one(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Citation, ...]:
    """Quotes one of the worked example's citations through a fake corpus that has it."""
    (citation, *_) = [c for step in worked_example_result().steps for c in step.citations]

    class FakeCorpus:
        def __init__(self, connection: object) -> None: ...

        def provision(self, *args: object, **kwargs: object) -> Provision:
            return _provision(citation, "The corpus's own text.")

    @contextmanager
    def connect() -> Iterator[str]:
        yield "connection"

    monkeypatch.setattr(clients, "CorpusCitations", FakeCorpus)
    quotes = corpus_quotes(connect, data_dir)  # pyright: ignore[reportArgumentType]
    return quotes([citation], LawVersion.AMENDED, date(2026, 10, 1))


def test_the_omnibus_records_are_read_once_per_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parsed = tmp_path / "parsed"
    parsed.mkdir()
    (parsed / "omnibus.en.jsonl").write_bytes(PARSED_OMNIBUS.read_bytes())
    assert len(_quote_one(tmp_path, monkeypatch)) == 1
    (parsed / "omnibus.en.jsonl").unlink()
    # Gone from disk, still known: the second question reads no file.
    assert len(_quote_one(tmp_path, monkeypatch)) == 1


@pytest.mark.parametrize(
    ("content", "failure"),
    [
        (None, "FileNotFoundError"),
        (b"", "LoadError"),
        (b"{not json\n", "ValidationError"),
        (b"\xff not utf-8\n", "UnicodeDecodeError"),
    ],
)
def test_omnibus_records_that_cant_be_read_raise_their_type_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: bytes | None, failure: str
) -> None:
    if content is not None:
        (tmp_path / "parsed").mkdir()
        (tmp_path / "parsed" / "omnibus.en.jsonl").write_bytes(content)
    with pytest.raises(OmnibusUnavailableError, match=rf"^{failure}$"):
        _quote_one(tmp_path, monkeypatch)
