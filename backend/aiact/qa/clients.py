"""The Q&A's model and its corpus search, as the API and V6 run them (P7).

The answer comes from the engine model, pinned to `ENGINE_PROVIDER` with fallbacks off
(decision 005), so a question (which may quote the user's own tool) stays in the EU. It makes one
attempt per question (`max_retries=0`): the user can ask again, and no retry is ever billed
unseen. Like the engine's models (E15), it is built once per settings and shared, so a question
builds no HTTP client of its own; a caller that meters it takes a copy with its callback. The
API searches with the engine's shared query embedder (`aiact.engine.clients.engine_embeddings`).
"""

import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date
from functools import lru_cache

import psycopg
from langchain_core.language_models import BaseChatModel

from aiact.llm import engine_chat_model
from aiact.llm.structured import ChatRoute
from aiact.qa.answer import QA_TOP_K, Searcher
from aiact.retrieval.search import QueryEmbedder, SearchResults, search_ai_act
from aiact.schemas import Language, LawVersion
from aiact.settings import Settings

QA_MAX_TOKENS = 3000
"""Bounds a runaway answer: about 200 words of answer, the rest for the engine model's reasoning
(decision 005; the engine's own nodes cap theirs at 3,000 to 6,000)."""
QA_MAX_RETRIES = 0
"""One attempt per question (`chat_model`: 0 gives a client that never retries)."""
KEPT_SETTINGS = 4

ConnectionFactory = Callable[[], AbstractContextManager[psycopg.Connection]]

_BUILDING = threading.Lock()


def qa_chat(settings: Settings) -> BaseChatModel:
    """The engine model with the Q&A's output cap and one attempt, built on the first call with
    these settings and shared after. Raises `LLMConfigError` when `ENGINE_MODEL`,
    `ENGINE_PROVIDER` or the API key is not set."""
    with _BUILDING:
        return _chat(settings)  # pyright: ignore[reportArgumentType]: frozen, so hashable


@lru_cache(maxsize=KEPT_SETTINGS)
def _chat(settings: Settings) -> BaseChatModel:
    return engine_chat_model(
        max_tokens=QA_MAX_TOKENS, max_retries=QA_MAX_RETRIES, settings=settings
    )


def qa_route(settings: Settings) -> ChatRoute:
    """The Q&A's model as a route with no second model: a refused question fails at once."""
    return ChatRoute(qa_chat(settings))


def corpus_searcher(connect: ConnectionFactory, embedder: QueryEmbedder) -> Searcher:
    """Searches the corpus as Q&A does: the top `QA_TOP_K` hits under the `SEARCH_MAX_DISTANCE`
    cut-off, each search on its own connection (never `include_held_out`, decision 012)."""

    def search(
        question: str, language: Language, law_version: LawVersion, as_of: date | None
    ) -> SearchResults:
        with connect() as connection:
            return search_ai_act(
                question,
                language,
                law_version,
                as_of,
                limit=QA_TOP_K,
                embedder=embedder,
                connection=connection,
            )

    return search
