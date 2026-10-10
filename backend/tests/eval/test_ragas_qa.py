"""V6 on P7's answers: `QaAnswerer` answers from the run's contexts with P7's prompt on the engine
model and returns what the user would be shown; `aiact evaluate ragas` uses it by default."""

import asyncio
import contextlib
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
    build_parts,
    context_text,
    metered_qa_chat,
)
from aiact.llm.structured import ChatRoute
from aiact.qa.answer import REPLY_FORMAT
from aiact.settings import Settings
from tests.engine.test_clients import engine_settings
from tests.eval.test_ragas_metrics import ART_5_1_F, ART_50_1, RECORDED_ITEM, hit, item, parts
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
    answer = asyncio.run(QaAnswerer(ChatRoute(chat)).answer(item(1), CONTEXTS))
    assert answer == "No: Art. 5(1)(f) prohibits it."
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
    assert asyncio.run(QaAnswerer(ChatRoute(chat)).answer(item(1), CONTEXTS)) == OUTSIDE_EN


def test_the_qa_answerer_is_named_qa_in_the_run_config() -> None:
    assert QaAnswerer(ChatRoute(scripted("answered", "A.", [1]))).name == "qa"
    assert ANSWERERS == ("qa", "plain_rag")
    assert (QA_ANSWERER, PLAIN_ANSWERER) == ("qa", "plain_rag")


def test_the_qa_model_is_metered_under_its_own_node_and_shares_its_client() -> None:
    meter = UsageMeter()
    chat = metered_qa_chat(engine_settings(), meter)
    assert isinstance(chat, ChatOpenRouter)
    assert chat.model_name == "openai/gpt-6-luna-20260922"
    assert chat.openrouter_provider is not None
    assert chat.openrouter_provider["order"] == ["azure/eu"]
    assert chat.openrouter_provider["allow_fallbacks"] is False
    (callback,) = chat.callbacks  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
    assert callback._node == QA_NODE  # pyright: ignore[reportAttributeAccessIssue]
    assert QA_NODE == "qa"
    again = metered_qa_chat(engine_settings(), meter)
    assert isinstance(again, ChatOpenRouter) and again.client is chat.client


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
    answerer = QaAnswerer(ChatRoute(metered_qa_chat(settings, meter)))
    answer = asyncio.run(answerer.answer(RECORDED_ITEM, CONTEXTS))
    assert answer != OUTSIDE_EN
    assert "5" in answer
    usage = meter.usage()
    assert usage.by_node[QA_NODE].calls == 1 and usage.cost_usd > 0
