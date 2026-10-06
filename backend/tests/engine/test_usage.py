"""The run's usage meter: each model reply and query embedding counted under its node (E10)."""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.engine.usage import UsageMeter
from aiact.llm.embeddings import EmbeddingBatch, OpenRouterEmbeddings, format_query
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


def test_a_reply_without_its_cost_is_counted_and_flagged() -> None:
    meter = UsageMeter()
    metered_chat(meter, "facts", reply(None, 50)).invoke("a")
    usage = meter.usage()
    assert (usage.cost_usd, usage.tokens) == (0.0, 50)
    assert not usage.is_cost_complete


class FakeEmbeddings(OpenRouterEmbeddings):
    """Answers `embed_batch` with a fixed vector and cost, without a network call."""

    def __init__(self) -> None:
        settings = Settings(
            _env_file=None,  # pyright: ignore[reportCallIssue]
            openrouter_api_key=SecretStr("k"),
            embedding_model="m",
            embedding_provider="p",
        )
        super().__init__(settings=settings)
        self.batches: list[list[str]] = []

    def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        self.batches.append(texts)
        return EmbeddingBatch(vectors=[[1.0, 0.0]], tokens=7, cost_usd=0.0001)


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
