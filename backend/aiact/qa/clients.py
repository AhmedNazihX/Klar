"""The Q&A's models, its corpus search and its corpus quotes, as the API and V6 run them (P7).

The answer comes from the engine model, pinned to `ENGINE_PROVIDER` with fallbacks off
(decision 005), so a question (which may quote the user's own tool) stays in the EU. A question
its provider's content filter refuses goes once to the refusal model (`REFUSAL_MODEL` on
`REFUSAL_PROVIDER`, fallbacks off), as the engine's nodes do (decision 033). Each makes one
attempt per question (`max_retries=0`): the user can ask again, and no retry is ever billed
unseen. Like the engine's models (E15), they are built once per settings and shared, so a
question builds no HTTP client of its own; a caller that meters them takes copies with its
callback. The API searches with the engine's shared query embedder
(`aiact.engine.clients.engine_embeddings`), and quotes a posted result's citations again from the
corpus as the engine's citation validator resolves them (`resolve`, decision 031).
"""

import threading
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import date
from functools import lru_cache
from pathlib import Path

import psycopg
from langchain_core.language_models import BaseChatModel
from pydantic import ValidationError

from aiact.corpus.build import LoadError
from aiact.engine.citations import (
    CorpusCitations,
    OmnibusChanges,
    load_omnibus_changes,
    resolve,
)
from aiact.engine.nodes.common import Lookup, provision_citation
from aiact.llm import engine_chat_model, refusal_chat_model
from aiact.llm.structured import ChatRoute
from aiact.qa.answer import QA_TOP_K, ResultQuotes, Searcher
from aiact.retrieval.search import QueryEmbedder, SearchResults, search_ai_act
from aiact.schemas import Citation, Language, LawVersion
from aiact.settings import Settings

QA_MAX_TOKENS = 3000
"""Bounds a runaway answer: about 200 words of answer, the rest for the engine model's reasoning
(decision 005; the engine's own nodes cap theirs at 3,000 to 6,000)."""
QA_MAX_RETRIES = 0
"""One attempt per question (`chat_model`: 0 gives a client that never retries)."""
KEPT_SETTINGS = 4

ConnectionFactory = Callable[[], AbstractContextManager[psycopg.Connection]]
ChatBuilder = Callable[..., BaseChatModel]
"""`engine_chat_model` or `refusal_chat_model`."""

_BUILDING = threading.Lock()


def qa_chat(settings: Settings) -> BaseChatModel:
    """The engine model with the Q&A's output cap and one attempt, built on the first call with
    these settings and shared after. Raises `LLMConfigError` when `ENGINE_MODEL`,
    `ENGINE_PROVIDER` or the API key is not set."""
    with _BUILDING:
        return _chat(settings, engine_chat_model)  # pyright: ignore[reportArgumentType]: frozen, so hashable


def qa_refusal_chat(settings: Settings) -> BaseChatModel:
    """The refusal model with the Q&A's output cap and one attempt, built once per settings like
    `qa_chat`. Raises `LLMConfigError` when `REFUSAL_MODEL`, `REFUSAL_PROVIDER` or the API key is
    not set."""
    with _BUILDING:
        return _chat(settings, refusal_chat_model)  # pyright: ignore[reportArgumentType]: frozen, so hashable


@lru_cache(maxsize=2 * KEPT_SETTINGS)
def _chat(settings: Settings, build: ChatBuilder) -> BaseChatModel:
    return build(max_tokens=QA_MAX_TOKENS, max_retries=QA_MAX_RETRIES, settings=settings)


def qa_route(settings: Settings) -> ChatRoute:
    """The Q&A's model and the second model its refused questions go to (decision 033)."""
    return ChatRoute(qa_chat(settings), qa_refusal_chat(settings))


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


def corpus_quotes(connect: ConnectionFactory, data_dir: Path) -> ResultQuotes:
    """Quotes a posted result's citations again from the corpus, all over one connection, as the
    engine's citation validator resolves them (`resolve`: by document, provision, law version and
    language on the date, held-out examples hidden), each rebuilt from the row found with the
    Omnibus marker; one that doesn't resolve is dropped. No connection opens for a result citing
    nothing. The `Lookup`'s language and law version go unread: `resolve` takes the citation's.
    Raises `OmnibusUnavailableError` when the parsed Omnibus can't be read."""

    def quotes(
        citations: Sequence[Citation], law_version: LawVersion, as_of: date | None
    ) -> tuple[Citation, ...]:
        if not citations:
            return ()
        lookup = Lookup(
            language=citations[0].language,
            law_version=law_version,
            as_of=as_of,
            exclude_source_example_ids=(),
        )
        omnibus = _omnibus_changes(data_dir)
        with connect() as connection:
            source = CorpusCitations(connection)
            found = [resolve(citation, lookup, source) for citation in citations]
        return tuple(
            provision_citation(provision).model_copy(
                update={"changed_by_omnibus": omnibus.marks(provision)}
            )
            for provision in found
            if provision is not None
        )

    return quotes


class OmnibusUnavailableError(RuntimeError):
    """The parsed Omnibus, which marks the citations it changed, can't be read. It carries the
    failure's type only."""


def _omnibus_changes(data_dir: Path) -> OmnibusChanges:
    """The Omnibus's amendment records, read once per `data_dir` (`load_omnibus_changes` caches
    them, as for the engine); a file that can't be read or loaded is retried on the next
    question."""
    try:
        return load_omnibus_changes(data_dir)
    except (OSError, LoadError, ValidationError) as exc:
        raise OmnibusUnavailableError(type(exc).__name__) from None
