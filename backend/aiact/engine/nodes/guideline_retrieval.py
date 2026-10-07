"""The corpus side of a check that reads one article and one set of guidelines (E4, E6): what it
looks up and searches before the model answers. No model is involved here.

- **The article by lookup.** The law says where to look, so the whole article (Art. 5 for the
  prohibited check, Art. 50 for transparency) is always fetched (`get_provision`) in the case's
  language, law version and date: the model reads every point and every condition, and never
  relies on a search ranking to find one.
- **Guidance by search.** The check's Commission guidelines are searched with the description
  (`search_ai_act` limited to their manifest keys inside the SQL, no distance cut-off: C8), with
  the caller's `exclude_source_example_ids`; held-out examples are hidden unless V8's gap run
  sets `include_held_out`, which every lookup and search passes through (decision 012). A German
  search that finds nothing is repeated in English.
"""

from dataclasses import dataclass
from typing import Protocol

import psycopg

from aiact.engine.nodes.common import Lookup, lookup_for
from aiact.engine.nodes.corpus import CorpusReader
from aiact.engine.state import EngineState
from aiact.retrieval.provisions import Provision
from aiact.retrieval.search import QueryEmbedder, SearchHit
from aiact.schemas import Language


@dataclass(frozen=True)
class GuidelineSource:
    """What a check reads: its article, its guidelines' manifest keys, and how many passages."""

    article: str
    doc_keys: frozenset[str]
    passages: int


class GuidelineLibrary(Protocol):
    """Where a check reads the law and the guidance from (`GuidelineCorpus`, or a replay)."""

    def provision(self, provision_id: str, lookup: Lookup) -> Provision: ...

    def guidance(self, query: str, lookup: Lookup, *, language: Language) -> tuple[SearchHit, ...]:
        """The best passages of the check's guidelines in `language`."""
        ...


class GuidelineCorpus(CorpusReader):
    """The corpus over one connection and one embedder, its searches limited to `source`'s
    guidelines (the check opens a short connection per use)."""

    def __init__(
        self, connection: psycopg.Connection, embedder: QueryEmbedder, source: GuidelineSource
    ) -> None:
        super().__init__(connection, embedder)
        self._source = source

    def guidance(self, query: str, lookup: Lookup, *, language: Language) -> tuple[SearchHit, ...]:
        source = self._source
        return self.passages(
            query, lookup, language=language, doc_keys=source.doc_keys, limit=source.passages
        )


@dataclass(frozen=True)
class Retrieved:
    """The article as the law version and date read have it, and the guidance for the
    description."""

    article: Provision
    guidance: tuple[SearchHit, ...]


def retrieve(state: EngineState, library: GuidelineLibrary, article: str) -> Retrieved:
    """`article` by lookup, then the guideline passages closest to the description (in the case's
    language, else in English). Raises `ProvisionNotFoundError` when the corpus lacks it."""
    lookup = lookup_for(state)
    found = library.provision(article, lookup)
    guidance: tuple[SearchHit, ...] = ()
    for language in dict.fromkeys((lookup.language, Language.EN)):
        guidance = library.guidance(state["description"], lookup, language=language)
        if guidance:
            break
    return Retrieved(article=found, guidance=guidance)
