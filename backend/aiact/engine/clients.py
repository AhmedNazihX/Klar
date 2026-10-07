"""The engine's model clients, built once per process (E15).

Each chat model and the embeddings client hold their own HTTP clients. ChatOpenRouter builds a
sync and an async httpx client for its attribution header and hands them to the OpenRouter SDK,
which then never closes them (they are the caller's), so a run that built its own models left
them in reference cycles until a full garbage collection. The engine model of every node, with
that node's output cap, and the query embedder are therefore built here on first use and shared
by every later run with the same settings: the API's, the benchmark runner's and
`classify_system`'s. A run never changes them: its nodes take a copy of their model with the
run's usage callback (`engine_nodes`; the copy shares the client), and wrap the embedder in the
run's `MeteredEmbedder`. The httpx clients are safe to share between the API's worker threads.
"""

import threading
from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

from langchain_core.language_models import BaseChatModel

from aiact.engine.graph import FACTS
from aiact.engine.nodes.facts import MAX_OUTPUT_TOKENS as FACTS_TOKENS
from aiact.engine.nodes.high_risk import MAX_OUTPUT_TOKENS as HIGH_RISK_TOKENS
from aiact.engine.nodes.prohibited import MAX_OUTPUT_TOKENS as PROHIBITED_TOKENS
from aiact.engine.nodes.role_obligations import MAX_OUTPUT_TOKENS as ROLE_TOKENS
from aiact.engine.nodes.scope import MAX_OUTPUT_TOKENS as SCOPE_TOKENS
from aiact.engine.nodes.transparency import MAX_OUTPUT_TOKENS as TRANSPARENCY_TOKENS
from aiact.llm import OpenRouterEmbeddings, engine_chat_model
from aiact.schemas import StepName
from aiact.settings import Settings

NODE_TOKENS: Mapping[str, int] = MappingProxyType(
    {
        FACTS: FACTS_TOKENS,
        StepName.SCOPE: SCOPE_TOKENS,
        StepName.PROHIBITED: PROHIBITED_TOKENS,
        StepName.HIGH_RISK: HIGH_RISK_TOKENS,
        StepName.TRANSPARENCY: TRANSPARENCY_TOKENS,
        StepName.ROLE_OBLIGATIONS: ROLE_TOKENS,
    }
)
"""Every node that calls the engine model, with its output cap."""

KEPT_SETTINGS = 4
"""How many different settings keep their clients at once: a process runs on one; tests use a
few. Clients of settings dropped from the cache go at the next garbage collection."""

_BUILDING = threading.Lock()
"""Two runs that start together build one set of clients."""


def engine_chats(settings: Settings) -> Mapping[str, BaseChatModel]:
    """The engine model of every node in `NODE_TOKENS`, by node name, each with its node's output
    cap and pinned to `ENGINE_PROVIDER` with fallbacks off (decision 005): built on the first call
    with these settings, the same models on every later one. Raises `LLMConfigError` when
    `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set (nothing is kept then)."""
    with _BUILDING:
        return _chats(settings)  # pyright: ignore[reportArgumentType]: frozen, so hashable


def engine_embeddings(settings: Settings) -> OpenRouterEmbeddings:
    """The query embedder of the settings' `EMBEDDING_*` model and provider: built on the first
    call with these settings, the same one on every later one. Raises `LLMConfigError` when the
    model, the provider or the API key is not set (nothing is kept then)."""
    with _BUILDING:
        return _embeddings(settings)  # pyright: ignore[reportArgumentType]: frozen, so hashable


@lru_cache(maxsize=KEPT_SETTINGS)
def _chats(settings: Settings) -> Mapping[str, BaseChatModel]:
    return MappingProxyType(
        {
            node: engine_chat_model(max_tokens=tokens, settings=settings)
            for node, tokens in NODE_TOKENS.items()
        }
    )


@lru_cache(maxsize=KEPT_SETTINGS)
def _embeddings(settings: Settings) -> OpenRouterEmbeddings:
    return OpenRouterEmbeddings(settings=settings)
