"""The corpus side of the transparency node (E6): what it looks up and searches before the model
answers. No model is involved here.

- **Art. 50 by lookup.** The whole article is always fetched (`get_provision`) in the case's
  language, law version and date, so the model reads every duty and every exception.
- **Guidance by search.** The Commission's guidelines on the Art. 50 transparency obligations are
  searched with the description (`search_ai_act` limited to `guide-art50` inside the SQL, no
  distance cut-off: C8), with the caller's `exclude_source_example_ids`; held-out examples are
  never retrievable (decision 012). The guidelines are English only, so a German search that
  finds nothing is repeated in English.
"""

from dataclasses import dataclass
from typing import Protocol

import psycopg

from aiact.engine.nodes.common import Lookup, lookup_for
from aiact.engine.state import EngineState
from aiact.retrieval.provisions import Provision, get_provision
from aiact.retrieval.search import QueryEmbedder, SearchHit, search_ai_act
from aiact.schemas import Language

ARTICLE_50 = "art:50"
GUIDANCE_DOC_KEYS = frozenset({"guide-art50"})
"""The manifest key of the Commission's guidelines on the Art. 50 transparency obligations."""
GUIDANCE_PASSAGES = 8
"""How many guideline passages the model reads: Art. 50 has four duties, each with exceptions."""


class TransparencyLibrary(Protocol):
    """Where the node reads the law and the guidance from (`TransparencyCorpus`, or a replay)."""

    def provision(self, provision_id: str, lookup: Lookup) -> Provision: ...

    def guidance(self, query: str, lookup: Lookup, *, language: Language) -> tuple[SearchHit, ...]:
        """The best `guide-art50` passages in `language`."""
        ...


class TransparencyCorpus:
    """The corpus through `get_provision` and `search_ai_act`, over one connection and one
    embedder (`TransparencyCheck` opens a short connection per use)."""

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
    """Art. 50 as the law version and date read have it, and the guidance for the description."""

    article: Provision
    guidance: tuple[SearchHit, ...]


def retrieve(state: EngineState, library: TransparencyLibrary) -> Retrieved:
    """Art. 50 by lookup, then the guideline passages closest to the description (in the case's
    language, else in English). Raises `ProvisionNotFoundError` when the corpus lacks Art. 50."""
    lookup = lookup_for(state)
    article = library.provision(ARTICLE_50, lookup)
    guidance: tuple[SearchHit, ...] = ()
    for language in dict.fromkeys((lookup.language, Language.EN)):
        guidance = library.guidance(state["description"], lookup, language=language)
        if guidance:
            break
    return Retrieved(article=article, guidance=guidance)
