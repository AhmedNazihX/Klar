"""The corpus side of the prohibited node (E4): what it looks up and searches before the model
answers. No model is involved here.

- **Art. 5 by lookup.** The law says where to look, so the whole of Art. 5 is always fetched
  (`get_provision`) in the case's language, law version and date: the model reads every practice
  and every condition, and never relies on a search ranking to find one.
- **Guidance by search.** The Commission's guidelines on prohibited practices are searched with
  the description (`search_ai_act` limited to `guide-prohibited` inside the SQL, no distance
  cut-off: C8), with the caller's `exclude_source_example_ids`; held-out examples are never
  retrievable (decision 012). A German search that finds nothing is repeated in English.
"""

from dataclasses import dataclass
from typing import Protocol

import psycopg

from aiact.engine.nodes.common import Lookup, lookup_for
from aiact.engine.state import EngineState
from aiact.retrieval.provisions import Provision, get_provision
from aiact.retrieval.search import QueryEmbedder, SearchHit, search_ai_act
from aiact.schemas import Language

ARTICLE_5 = "art:5"
GUIDANCE_DOC_KEYS = frozenset({"guide-prohibited"})
"""The manifest key of the Commission's guidelines on prohibited AI practices."""
GUIDANCE_PASSAGES = 6
"""How many guideline passages the model reads."""


class ProhibitedLibrary(Protocol):
    """Where the node reads the law and the guidance from (`ProhibitedCorpus`, or a replay)."""

    def provision(self, provision_id: str, lookup: Lookup) -> Provision: ...

    def guidance(self, query: str, lookup: Lookup, *, language: Language) -> tuple[SearchHit, ...]:
        """The best `guide-prohibited` passages in `language`."""
        ...


class ProhibitedCorpus:
    """The corpus through `get_provision` and `search_ai_act`, over one connection and one
    embedder (`ProhibitedCheck` opens a short connection per use)."""

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
            connection=self._connection,
        )

    def guidance(self, query: str, lookup: Lookup, *, language: Language) -> tuple[SearchHit, ...]:
        results = search_ai_act(
            query,
            language,
            lookup.law_version,
            lookup.as_of,
            doc_keys=GUIDANCE_DOC_KEYS,
            exclude_source_example_ids=lookup.exclude_source_example_ids,
            max_distance=None,
            limit=GUIDANCE_PASSAGES,
            embedder=self._embedder,
            connection=self._connection,
        )
        return results.hits


@dataclass(frozen=True)
class Retrieved:
    """Art. 5 as the law version and date read have it, and the guidance for the description."""

    article: Provision
    guidance: tuple[SearchHit, ...]


def retrieve(state: EngineState, library: ProhibitedLibrary) -> Retrieved:
    """Art. 5 by lookup, then the guideline passages closest to the description (in the case's
    language, else in English). Raises `ProvisionNotFoundError` when the corpus lacks Art. 5."""
    lookup = lookup_for(state)
    article = library.provision(ARTICLE_5, lookup)
    guidance: tuple[SearchHit, ...] = ()
    for language in dict.fromkeys((lookup.language, Language.EN)):
        guidance = library.guidance(state["description"], lookup, language=language)
        if guidance:
            break
    return Retrieved(article=article, guidance=guidance)
