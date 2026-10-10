"""The corpus as the checks read it (E15, folding the copies E3 to E6 each had): one reader over
`get_provision` and `search_ai_act`, and the short connection each step reads it over.

- **`CorpusReader`**: one provision by its id, or the passages a search finds, on the run's
  `Lookup`, over one connection and one query embedder. Every call passes the run's
  `include_held_out` (False except in V8's gap run, decision 012), and every search the caller's
  `exclude_source_example_ids`, no distance cut-off (C8) and C6's ranking (`ENGINE_TUNING`,
  decision 003). Each check's library (scope's, the guideline checks', high-risk's) adds only
  what it searches for.
- **`CorpusReading`**: how a check reaches its library: the one it was given (a replay or a
  test), or the live corpus over a fresh connection for each use, closed before the use
  returns, so no connection stays open while the model answers. The live corpus embeds its
  queries with the run's shared embedder (`engine_nodes`), or with one built from the check's
  settings.
"""

from collections.abc import Callable, Collection

import psycopg

from aiact.db import connect
from aiact.engine.nodes.common import Lookup
from aiact.llm import OpenRouterEmbeddings
from aiact.retrieval.provisions import Provision, get_provision
from aiact.retrieval.search import ENGINE_TUNING, QueryEmbedder, SearchHit, search_ai_act
from aiact.schemas import Language
from aiact.settings import Settings


class CorpusReader:
    """The corpus through `get_provision` and `search_ai_act`, over one connection and one
    embedder."""

    def __init__(self, connection: psycopg.Connection, embedder: QueryEmbedder) -> None:
        self._connection = connection
        self._embedder = embedder

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        """Raises `ProvisionNotFoundError` when the corpus has no text for it."""
        return get_provision(
            provision_id,
            lookup.language,
            lookup.law_version,
            lookup.as_of,
            include_held_out=lookup.include_held_out,
            connection=self._connection,
        )

    def passages(
        self,
        query: str,
        lookup: Lookup,
        *,
        language: Language,
        limit: int,
        doc_keys: Collection[str] | None = None,
        doc_types: Collection[str] | None = None,
    ) -> tuple[SearchHit, ...]:
        """The `limit` passages closest to `query` in `language`, from the documents `doc_keys`
        names, or of the types `doc_types` names (None: any)."""
        results = search_ai_act(
            query,
            language,
            lookup.law_version,
            lookup.as_of,
            doc_keys=doc_keys,
            doc_types=doc_types,
            exclude_source_example_ids=lookup.exclude_source_example_ids,
            include_held_out=lookup.include_held_out,
            max_distance=None,
            limit=limit,
            embedder=self._embedder,
            connection=self._connection,
            tuning=ENGINE_TUNING,
        )
        return results.hits


class CorpusReading[L]:
    """A check's way to its corpus library: `library` when one is given, else the one `live`
    builds over a short connection for each use."""

    def __init__(
        self,
        library: L | None,
        live: Callable[[psycopg.Connection, QueryEmbedder], L],
        *,
        embedder: QueryEmbedder | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Without `library`, the live corpus embeds with `embedder`, or with one built here from
        `settings`: raises `LLMConfigError` then when `EMBEDDING_MODEL`, `EMBEDDING_PROVIDER` or
        the API key is not set."""
        self._library = library
        self._live = live
        self._embedder = (
            None if library is not None else embedder or OpenRouterEmbeddings(settings=settings)
        )

    def __call__[T](self, use: Callable[[L], T]) -> T:
        """`use` applied to the library: the given one, or one over a fresh connection that is
        closed before this returns."""
        if self._library is not None:
            return use(self._library)
        assert self._embedder is not None  # built whenever no library is given
        with connect() as connection:
            return use(self._live(connection, self._embedder))
