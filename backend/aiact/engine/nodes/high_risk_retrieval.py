"""The corpus side of the high-risk node (E5): what it looks up and searches before the model
answers. No model is involved here.

- **Annex III and Annex I by lookup.** Both lists are short and the law says where to look, so
  every Annex III point (the 25 leaves) and every Annex I point is fetched (`get_provision`) in
  the case's language and law version and shown as one line with its id: the model can only pick
  an id the text has, and a softly worded use can't miss its point because a search ranked it
  low (user, 2026-09-30).
- **Analogy.** The guidelines are searched with the description (`search_ai_act`, no distance
  cut-off: C8); their worked examples (Pile A only: held-out examples are never retrievable,
  decision 012) are shown for reasoning by analogy. The caller's `exclude_source_example_ids` go
  into every search, so a leave-one-out run drops the example a case was written from. Guidance
  is mostly English only, so a German search that finds none is repeated in English.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import psycopg

from aiact.engine.nodes.common import Lookup, lookup_for
from aiact.engine.state import EngineState
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError, get_provision
from aiact.retrieval.search import QueryEmbedder, SearchHit, search_ai_act
from aiact.schemas import Language

GUIDANCE_SEARCH_LIMIT = 8

ANNEX_I_CANDIDATES: tuple[str, ...] = (
    *(f"annex:I:A:{number}" for number in range(1, 13)),
    *(f"annex:I:B:{number}" for number in range(13, 22)),
)
"""Every Annex I point id either text may have: A.1-12 and B.13-21."""
ANNEX_III_POINTS: tuple[str, ...] = tuple(
    f"annex:III:{point}"
    for point in (
        *("1:a", "1:b", "1:c", "2", "3:a", "3:b", "3:c", "3:d", "4:a", "4:b"),
        *("5:a", "5:b", "5:c", "5:d", "6:a", "6:b", "6:c", "6:d", "6:e"),
        *("7:a", "7:b", "7:c", "7:d", "8:a", "8:b"),
    )
)
"""Every Annex III point a use can fall under (the leaves of the annex), in annex order."""


class HighRiskLibrary(Protocol):
    """Where the node reads the law and the guidance from (`HighRiskCorpus`, or a replay)."""

    def provision(self, provision_id: str, lookup: Lookup) -> Provision: ...

    def search(
        self, query: str, lookup: Lookup, *, language: Language, doc_type: str, limit: int
    ) -> tuple[SearchHit, ...]: ...


class HighRiskCorpus:
    """The corpus through `get_provision` and `search_ai_act`, over one connection and one
    embedder (`HighRiskCheck` opens the connection once per step). Every search carries the
    caller's exclusions and no distance cut-off (C8)."""

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

    def search(
        self, query: str, lookup: Lookup, *, language: Language, doc_type: str, limit: int
    ) -> tuple[SearchHit, ...]:
        results = search_ai_act(
            query,
            language,
            lookup.law_version,
            lookup.as_of,
            doc_types={doc_type},
            exclude_source_example_ids=lookup.exclude_source_example_ids,
            max_distance=None,
            limit=limit,
            embedder=self._embedder,
            connection=self._connection,
        )
        return results.hits


@dataclass(frozen=True)
class Retrieved:
    """What the lookups and the guidance search found for one description."""

    annex_i: tuple[Provision, ...]
    """Every Annex I point the text of this law version has, in order."""
    annex_iii: tuple[Provision, ...]
    """Every Annex III point (leaf) the text of this law version has, in annex order."""
    guidance: tuple[SearchHit, ...]


def _fetched(library: HighRiskLibrary, ids: Sequence[str], lookup: Lookup) -> tuple[Provision, ...]:
    """The provisions at `ids` that the text of this law version has, in order."""
    found: list[Provision] = []
    for provision_id in ids:
        try:
            found.append(library.provision(provision_id, lookup))
        except ProvisionNotFoundError:
            continue
    return tuple(found)


def annex_i_points(library: HighRiskLibrary, lookup: Lookup) -> tuple[Provision, ...]:
    """The Annex I points of the law version read, one lookup each. The candidates cover both
    numberings (the Omnibus moved machinery from A.1 to B.21), and a point the text lacks is
    skipped, so the model is only shown ids that exist."""
    return _fetched(library, ANNEX_I_CANDIDATES, lookup)


def annex_iii_points(library: HighRiskLibrary, lookup: Lookup) -> tuple[Provision, ...]:
    """Every Annex III leaf of the law version read, one lookup each, in annex order."""
    return _fetched(library, ANNEX_III_POINTS, lookup)


def retrieve(state: EngineState, library: HighRiskLibrary) -> Retrieved:
    """Both annexes' points, and the guidance for the description."""
    lookup = lookup_for(state)

    def guidance_in(language: Language) -> tuple[SearchHit, ...]:
        return library.search(
            state["description"],
            lookup,
            language=language,
            doc_type="guideline",
            limit=GUIDANCE_SEARCH_LIMIT,
        )

    guidance = guidance_in(lookup.language)
    if not guidance and lookup.language is not Language.EN:
        guidance = guidance_in(Language.EN)
    return Retrieved(
        annex_i=annex_i_points(library, lookup),
        annex_iii=annex_iii_points(library, lookup),
        guidance=guidance,
    )
