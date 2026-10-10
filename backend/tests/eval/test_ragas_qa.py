"""V6 on P7's answers: `QaAnswerer` answers from the run's contexts with P7's prompt on the engine
model and returns what the user would be shown; `aiact evaluate ragas` uses it by default."""

import asyncio
import contextlib
import dataclasses
import json

import pytest
from langchain_core.messages import AIMessage
from langchain_openrouter import ChatOpenRouter
from typer.testing import CliRunner
from vcr.errors import CannotOverwriteExistingCassetteException

from aiact.cli import app
from aiact.engine.usage import UsageMeter
from aiact.eval import ragas_metrics, records
from aiact.eval.ragas_metrics import (
    ANSWERERS,
    PLAIN_ANSWERER,
    QA_ANSWERER,
    QA_NODE,
    PlainAnswerer,
    QaAnswerer,
    RagasOptions,
    build_parts,
    context_text,
    metered_qa_route,
    run_ragas,
)
from aiact.llm.structured import ChatRoute
from aiact.qa.answer import REPLY_FORMAT
from aiact.settings import Settings
from tests.engine.test_clients import engine_settings
from tests.eval.test_ragas_metrics import (
    ART_5_1_F,
    ART_50_1,
    GIT_SHA,
    RECORDED_ITEM,
    FakeRetriever,
    FakeScorer,
    hit,
    item,
    parts,
)
from tests.eval.test_runner import MemoryStore
from tests.qa.test_answer import RecordingChat

OUTSIDE_EN = (
    "That's outside what I can answer. I cover the AI Act and the Commission's guidance on it, "
    "and they don't answer this question."
)
CONTEXTS = [
    context_text(hit("art:5:1:f", text=ART_5_1_F)),
    context_text(hit("art:50:1", text=ART_50_1)),
]


def scripted(kind: str, answer: str, cited: list[int]) -> RecordingChat:
    reply = json.dumps({"kind": kind, "answer": answer, "cited": cited})
    return RecordingChat(messages=iter([AIMessage(content=reply)]))


def test_the_qa_answerer_answers_from_the_run_contexts_with_p7s_prompt() -> None:
    chat = scripted("answered", "No: Art. 5(1)(f) prohibits it.", [1])
    answer = asyncio.run(QaAnswerer(ChatRoute(chat)).answer(item(1), CONTEXTS, found=True))
    assert (answer.text, answer.kind) == ("No: Art. 5(1)(f) prohibits it.", "answered")
    ((messages, options),) = chat.seen
    assert messages[1].text == (
        f"Sources:\n[1] {CONTEXTS[0]}\n\n[2] {CONTEXTS[1]}\n\nQuestion: Made-up question 1?"
    )
    assert options["response_format"] == REPLY_FORMAT


@pytest.mark.parametrize(
    ("kind", "cited"), [("outside_corpus", []), ("answered", []), ("answered", [7])]
)
def test_the_qa_answerer_returns_the_fixed_answer_the_user_would_see(
    kind: str, cited: list[int]
) -> None:
    chat = scripted(kind, "Under the DSA, yearly.", cited)
    answer = asyncio.run(QaAnswerer(ChatRoute(chat)).answer(item(1), CONTEXTS, found=True))
    assert (answer.text, answer.kind) == (OUTSIDE_EN, "outside_corpus")


def test_the_qa_answerer_is_named_qa_in_the_run_config() -> None:
    assert QaAnswerer(ChatRoute(scripted("answered", "A.", [1]))).name == "qa"
    assert ANSWERERS == ("qa", "plain_rag")
    assert (QA_ANSWERER, PLAIN_ANSWERER) == ("qa", "plain_rag")


def test_the_qa_models_are_metered_under_their_own_node_and_share_their_clients() -> None:
    """P7's route as the product runs it: Luna on azure/eu, and Flash-Lite on google-vertex/eu
    for a refused question (decision 033), both counted under the `qa` node."""
    meter = UsageMeter()
    route = metered_qa_route(engine_settings(), meter)
    expected = [
        (route.chat, "openai/gpt-6-luna-20260922", "azure/eu"),
        (route.refusal_chat, "google/gemini-3.1-flash-lite", "google-vertex/eu"),
    ]
    again = metered_qa_route(engine_settings(), meter)
    for chat, (model, slug, provider), shared in zip(
        (route.chat, route.refusal_chat),
        expected,
        (again.chat, again.refusal_chat),
        strict=True,
    ):
        assert model is chat
        assert isinstance(chat, ChatOpenRouter)
        assert (chat.model_name, chat.max_tokens, chat.max_retries) == (slug, 3000, 0)
        assert chat.openrouter_provider is not None
        assert chat.openrouter_provider["order"] == [provider]
        assert chat.openrouter_provider["allow_fallbacks"] is False
        (callback,) = chat.callbacks  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
        assert callback._node == QA_NODE  # pyright: ignore[reportAttributeAccessIssue]
        assert isinstance(shared, ChatOpenRouter) and shared.client is chat.client
    assert QA_NODE == "qa"


def test_hits_the_search_found_irrelevant_get_the_outside_answer_without_a_model_call() -> None:
    """The product never asks the model about hits the search didn't find relevant (C8)."""
    chat = scripted("answered", "Under Art. 5, yes.", [1])
    answer = asyncio.run(QaAnswerer(ChatRoute(chat)).answer(item(1), CONTEXTS, found=False))
    assert (answer.text, answer.kind) == (OUTSIDE_EN, "outside_corpus")
    assert chat.seen == []


@pytest.mark.parametrize(("found", "kind"), [(True, "answered"), (False, "outside_corpus")])
def test_a_run_passes_found_to_p7s_answerer_and_stores_the_answer_kind(
    found: bool, kind: str
) -> None:
    chat = scripted("answered", "No: Art. 5(1)(f) prohibits it.", [1])
    meter = UsageMeter()
    run_parts = dataclasses.replace(
        parts(meter), retriever=FakeRetriever(found=found), answerer=QaAnswerer(ChatRoute(chat))
    )
    store = MemoryStore()
    run_ragas((item(1),), run_parts, store, RagasOptions(GIT_SHA))
    ((_, record),) = store.cases
    assert record.predicted["answer_kind"] == kind
    assert len(chat.seen) == (1 if found else 0)


def test_the_run_config_names_the_answering_models() -> None:
    settings = engine_settings()
    default = build_parts(settings=settings)
    assert default.answer_model == {
        "model": "openai/gpt-6-luna-20260922",
        "provider": "azure/eu",
        "refusal_model": "google/gemini-3.1-flash-lite",
        "refusal_provider": "google-vertex/eu",
    }
    plain = build_parts(settings=settings, answerer="plain_rag")
    assert plain.answer_model == {"model": plain.model, "provider": plain.provider}
    store = MemoryStore()
    run_ragas(
        (item(1),),
        dataclasses.replace(default, scorer=FakeScorer(), retriever=FakeRetriever(hits=())),
        store,
        RagasOptions(GIT_SHA),
    )
    (config,) = (run["config"] for run in store.runs.values())
    assert isinstance(config, dict) and config["answer_model"] == default.answer_model
    for built in (default, plain):
        asyncio.run(_close(built))


async def _close(built: ragas_metrics.RagasParts) -> None:
    await built.aclose()


def test_build_parts_answers_with_p7_by_default_and_the_stand_in_on_request() -> None:
    settings = engine_settings()
    default = build_parts(settings=settings)
    assert isinstance(default.answerer, QaAnswerer)
    assert default.answerer.name == "qa"
    plain = build_parts(settings=settings, answerer="plain_rag")
    assert isinstance(plain.answerer, PlainAnswerer)
    for built in (default, plain):
        asyncio.run(_close(built))


def test_build_parts_rejects_an_unknown_answerer() -> None:
    with pytest.raises(ValueError, match="unknown answerer"):
        build_parts(settings=engine_settings(), answerer="oracle")


def test_the_command_defaults_to_p7s_answerer(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_build(top_k: int, **kwargs: object) -> ragas_metrics.RagasParts:
        seen.append(str(kwargs["answerer"]))
        return parts()

    store = MemoryStore()
    monkeypatch.setattr(ragas_metrics, "build_parts", fake_build)
    monkeypatch.setattr(records, "connect", contextlib.nullcontext)
    monkeypatch.setattr(records, "PostgresRunStore", lambda connection: store)
    runner = CliRunner()
    assert runner.invoke(app, ["evaluate", "ragas", "--subset", "1"]).exit_code == 0
    args = ["evaluate", "ragas", "--subset", "1", "--answerer", "plain_rag"]
    assert runner.invoke(app, args).exit_code == 0
    assert seen == ["qa", "plain_rag"]


def test_the_command_rejects_an_unknown_answerer() -> None:
    result = CliRunner().invoke(app, ["evaluate", "ragas", "--answerer", "oracle"])
    assert result.exit_code == 2
    assert "unknown --answerer 'oracle'" in result.stderr


def test_the_command_without_the_engine_model_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unconfigured = engine_settings(engine_model=None)
    monkeypatch.setattr(ragas_metrics, "get_settings", lambda: unconfigured)
    result = CliRunner().invoke(app, ["evaluate", "ragas"])
    assert result.exit_code == 2
    assert "ENGINE_MODEL" in result.stderr


LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"


@pytest.mark.xfail(
    strict=True,
    raises=CannotOverwriteExistingCassetteException,
    reason="recording pending (P7): uv run pytest tests/eval/test_ragas_qa.py -k luna "
    "--record-mode=once -q",
)
@pytest.mark.vcr
def test_luna_answers_a_question_from_its_contexts(openrouter_settings: Settings) -> None:
    """The engine provider accepts P7's reply format, and Luna answers from the contexts: the
    emotion-recognition ban, citing Art. 5(1)(f)."""
    settings = openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )
    meter = UsageMeter()
    answerer = QaAnswerer(metered_qa_route(settings, meter))
    answer = asyncio.run(answerer.answer(RECORDED_ITEM, CONTEXTS, found=True))
    assert answer.kind == "answered" and answer.text != OUTSIDE_EN
    assert "5" in answer.text
    usage = meter.usage()
    assert usage.by_node[QA_NODE].calls == 1 and usage.cost_usd > 0
