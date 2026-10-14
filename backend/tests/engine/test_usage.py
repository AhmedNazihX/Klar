"""The run's usage meter: each model reply and query embedding counted under its node (E10)."""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, SecretStr

from aiact.engine.usage import UsageMeter
from aiact.llm.embeddings import EmbeddingBatch, OpenRouterEmbeddings, format_query
from aiact.llm.structured import ChatRoute, json_schema_format
from aiact.schemas import StepName
from aiact.settings import Settings


def reply(cost: float | None, tokens: int) -> AIMessage:
    metadata = {"cost": cost} if cost is not None else {}
    return AIMessage(
        content="{}",
        response_metadata=metadata,
        usage_metadata={"input_tokens": tokens - 1, "output_tokens": 1, "total_tokens": tokens},
    )


def metered_chat(meter: UsageMeter, node: str, *replies: AIMessage) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter(replies), callbacks=[meter.chat_callback(node)])


def test_each_reply_is_counted_under_its_node() -> None:
    meter = UsageMeter()
    facts = metered_chat(meter, "facts", reply(0.001, 100))
    scope = metered_chat(meter, StepName.SCOPE, reply(0.002, 200), reply(0.003, 300))
    facts.invoke("a")
    scope.invoke("b")
    scope.invoke("c")  # e.g. the citation validator's re-run: both runs are paid

    usage = meter.usage()
    assert usage.cost_usd == pytest.approx(0.006)
    assert usage.tokens == 600
    assert set(usage.by_node) == {"facts", "scope"}
    assert usage.by_node["scope"].calls == 2
    assert usage.by_node["scope"].cost_usd == pytest.approx(0.005)
    assert usage.is_cost_complete


class Answer(BaseModel):
    value: int


def test_a_cut_off_reply_and_its_second_try_are_both_counted() -> None:
    """E20: a reply the output cap cut off is paid for too, and so is the one more try."""
    meter = UsageMeter()
    cut_off = reply(0.0066, 10000).model_copy(
        update={
            "content": '{"value": [1,2,3',
            "response_metadata": {"cost": 0.0066, "finish_reason": "length"},
        }
    )
    answered = reply(0.002, 700).model_copy(update={"content": '{"value": 2}'})
    chat = metered_chat(meter, StepName.HIGH_RISK, cut_off, answered)
    format_ = json_schema_format("answer", Answer)
    route = ChatRoute(chat, retry_cut_off=True)  # a classification run's route (engine_route)
    assert route.ask([HumanMessage("a")], format_, Answer) == Answer(value=2)
    usage = meter.usage().by_node["high_risk"]
    assert (usage.calls, usage.tokens) == (2, 10700)
    assert usage.cost_usd == pytest.approx(0.0086)


def test_a_reply_without_its_cost_is_counted_and_flagged() -> None:
    meter = UsageMeter()
    metered_chat(meter, "facts", reply(None, 50)).invoke("a")
    usage = meter.usage()
    assert (usage.cost_usd, usage.tokens) == (0.0, 50)
    assert not usage.is_cost_complete


class FakeEmbeddings(OpenRouterEmbeddings):
    """Answers `embed_batch` with a fixed vector and cost, without a network call."""

    def __init__(self, *, is_cost_known: bool = True) -> None:
        settings = Settings(
            _env_file=None,  # pyright: ignore[reportCallIssue]
            openrouter_api_key=SecretStr("k"),
            embedding_model="m",
            embedding_provider="p",
        )
        super().__init__(settings=settings)
        self.batches: list[list[str]] = []
        self.is_cost_known = is_cost_known

    def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        self.batches.append(texts)
        cost = 0.0001 if self.is_cost_known else 0.0
        known = self.is_cost_known
        return EmbeddingBatch([[1.0, 0.0]], tokens=7, cost_usd=cost, is_cost_known=known)


def test_a_query_embedding_is_embedded_as_embed_query_does_and_counted() -> None:
    meter = UsageMeter()
    inner = FakeEmbeddings()
    embedder = meter.embedder(StepName.HIGH_RISK, inner)
    assert embedder.embed_query("tenant scoring") == [1.0, 0.0]
    assert inner.batches == [[format_query("tenant scoring", inner.query_instruction)]]
    assert (embedder.model, embedder.dimensions) == (inner.model, inner.dimensions)
    usage = meter.usage()
    assert usage.by_node["high_risk"].cost_usd == 0.0001
    assert usage.tokens == 7
    assert usage.is_cost_complete


def test_an_embedding_without_its_cost_is_counted_and_flagged() -> None:
    meter = UsageMeter()
    meter.embedder(StepName.SCOPE, FakeEmbeddings(is_cost_known=False)).embed_query("q")
    usage = meter.usage()
    assert (usage.cost_usd, usage.tokens, usage.by_node["scope"].calls) == (0.0, 7, 1)
    assert not usage.is_cost_complete


def served_by(model: str) -> AIMessage:
    return AIMessage(content="{}", response_metadata={"cost": 0.0, "model_name": model})


def test_each_call_records_the_model_that_served_it() -> None:
    """Decision 033: a node's refused request and the second model's answer show apart."""
    meter = UsageMeter()
    luna, gemini = "openai/gpt-6-luna-20260922", "google/gemini-3.1-flash-lite"
    metered_chat(meter, StepName.SCOPE, served_by(luna)).invoke("a")
    metered_chat(meter, StepName.SCOPE, served_by(gemini)).invoke("a")
    metered_chat(meter, StepName.SCOPE, reply(0.001, 10)).invoke("b")  # no model named
    meter.embedder(StepName.SCOPE, FakeEmbeddings()).embed_query("q")
    models = meter.usage().by_node["scope"].models
    assert models == {luna: 1, gemini: 1, "unknown": 1, "m": 1}
