"""What one classification spent, per node (E10; the V1 runner's per-case cost).

Every engine node's chat model gets a callback from the run's `UsageMeter`, and every search
embeds through a `MeteredEmbedder`, so each paid call is counted under the node that made it.
A step the citation validator runs twice (E9) counts both runs. Cost is OpenRouter's
`usage.cost` for each reply and each embedding request; a call without it counts its tokens
at no cost, and the run's `is_cost_complete` says so. Each call also records the model that
served it (the reply's `model`, or the embedding model), so a request the engine provider
refused and the second model answered (decision 033) shows under both.
"""

import threading
from collections.abc import Mapping

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult

from aiact.llm.chat import reply_model, reply_usage
from aiact.llm.embeddings import OpenRouterEmbeddings
from aiact.schemas.base import ContractModel

UNKNOWN_MODEL = "unknown"
"""Where a call counts when its reply names no model."""


class NodeUsage(ContractModel):
    """The paid calls of one node: model replies and query embeddings."""

    cost_usd: float = 0.0
    tokens: int = 0
    calls: int = 0
    models: Mapping[str, int] = {}
    """The calls by the model that served them."""


class RunUsage(ContractModel):
    """What one run spent: the totals, and the same per node (`facts`, a check, …)."""

    cost_usd: float = 0.0
    tokens: int = 0
    by_node: Mapping[str, NodeUsage] = {}
    is_cost_complete: bool = True
    """False when a reply came without its cost, so `cost_usd` is too low."""


class UsageMeter:
    """The paid calls of one run, counted per node. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_node: dict[str, NodeUsage] = {}
        self._is_cost_complete = True

    def add(self, node: str, cost_usd: float | None, tokens: int, model: str | None = None) -> None:
        """Count one call of `node` served by `model` (None: `UNKNOWN_MODEL`); a call without
        its cost counts as free and is flagged."""
        key = str(node)  # a StepName counts under its value
        served = model or UNKNOWN_MODEL
        with self._lock:
            before = self._by_node.get(key, NodeUsage())
            self._by_node = {
                **self._by_node,
                key: NodeUsage(
                    cost_usd=before.cost_usd + (cost_usd or 0.0),
                    tokens=before.tokens + tokens,
                    calls=before.calls + 1,
                    models={**before.models, served: before.models.get(served, 0) + 1},
                ),
            }
            self._is_cost_complete = self._is_cost_complete and cost_usd is not None

    def usage(self) -> RunUsage:
        with self._lock:
            by_node = dict(self._by_node)
            is_complete = self._is_cost_complete
        return RunUsage(
            cost_usd=sum(node.cost_usd for node in by_node.values()),
            tokens=sum(node.tokens for node in by_node.values()),
            by_node=by_node,
            is_cost_complete=is_complete,
        )

    def chat_callback(self, node: str) -> BaseCallbackHandler:
        """A callback for `node`'s chat model that counts every reply it gets."""
        return _ChatUsage(self, node)

    def embedder(self, node: str, inner: OpenRouterEmbeddings) -> "MeteredEmbedder":
        """`inner` with every query embedding counted under `node`."""
        return MeteredEmbedder(self, node, inner)


class _ChatUsage(BaseCallbackHandler):
    def __init__(self, meter: UsageMeter, node: str) -> None:
        self._meter = meter
        self._node = node

    def on_llm_end(self, response: LLMResult, **kwargs: object) -> None:
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                if isinstance(message, AIMessage):
                    self._meter.add(self._node, *reply_usage(message), reply_model(message))
                else:
                    self._meter.add(self._node, None, 0, None)


class MeteredEmbedder:
    """A `QueryEmbedder` over `OpenRouterEmbeddings` that counts each query's cost."""

    def __init__(self, meter: UsageMeter, node: str, inner: OpenRouterEmbeddings) -> None:
        self._meter = meter
        self._node = node
        self._inner = inner
        self.model = inner.model
        self.dimensions = inner.dimensions

    def embed_query(self, text: str) -> list[float]:
        """The query's vector, as `OpenRouterEmbeddings.embed_query` makes it."""
        batch = self._inner.embed_batch([self._inner.query_text(text)])
        cost = batch.cost_usd if batch.is_cost_known else None
        self._meter.add(self._node, cost, batch.tokens, self.model)
        return batch.vectors[0]
