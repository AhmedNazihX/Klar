"""The corpus side of the high-risk node (E5): what it searches and looks up before the model
answers. No model is involved here.

- **Annex III by search.** The description is searched in the law (`search_ai_act`, no distance
  cut-off, so a softly worded use still reaches its point: C8), and the Annex III rows among the
  hits are the candidate points. An area row (`annex:III:4`) stands for its leaf points, which
  are fetched, since the answer must name a leaf; the annex's own row is dropped.
- **Analogy.** The guidelines are searched the same way; their worked examples (Pile A only: held-
  out examples are never retrievable, decision 012) are shown for reasoning by analogy. The
  caller's `exclude_source_example_ids` go into every search, so a leave-one-out run drops the
  example a case was written from. Guidance is mostly English only, so a German search that finds
  none is repeated in English.
- **Annex I by lookup.** The Annex I list is short and the law says where to look, so each of its
  points is fetched (`get_provision`) and shown as one line with its id and short title: the
  model can only pick an id the text of this law version has.
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

LAW_SEARCH_LIMIT = 50
"""Hits asked of the law search; the Annex III rows among them are the candidates."""
MAX_ANNEX_CANDIDATES = 8
GUIDANCE_SEARCH_LIMIT = 8

ANNEX_I_CANDIDATES: tuple[str, ...] = (
    *(f"annex:I:A:{number}" for number in range(1, 13)),
    *(f"annex:I:B:{number}" for number in range(13, 22)),
)
"""Every Annex I point id either text may have: A.1-12 and B.13-21."""
ANNEX_III_PREFIX = "annex:III"
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


Passage = SearchHit | Provision
"""A retrieved text shown to the model: a search hit, or a provision fetched by id."""


@dataclass(frozen=True)
class Retrieved:
    """What the searches and the lookup found for one description."""

    annex_i: tuple[Provision, ...]
    """Every Annex I point the text of this law version has, in order."""
    annex_iii: tuple[Passage, ...]
    """The candidate Annex III points: leaves only, so every id shown can be answered."""
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


def _leaves(provision_id: str) -> tuple[str, ...]:
    """The Annex III points a law hit stands for: a leaf itself, an area row (`annex:III:4`) its
    leaves; the annex's own row and any other provision none."""
    if provision_id in ANNEX_III_POINTS:
        return (provision_id,)
    if not provision_id.startswith(f"{ANNEX_III_PREFIX}:"):
        return ()
    return tuple(point for point in ANNEX_III_POINTS if point.startswith(f"{provision_id}:"))


def annex_iii_candidates(
    law: Sequence[SearchHit], library: HighRiskLibrary, lookup: Lookup
) -> tuple[Passage, ...]:
    """The Annex III points among the law hits, in rank order. The answer must name a leaf, so
    an area row is replaced by its leaves (fetched unless found themselves)."""
    hits = {hit.provision_id: hit for hit in law}
    ids = tuple(dict.fromkeys(leaf for hit in law for leaf in _leaves(hit.provision_id)))
    chosen = ids[:MAX_ANNEX_CANDIDATES]
    missing = [point for point in chosen if point not in hits]
    fetched = {p.provision_id: p for p in _fetched(library, missing, lookup)}
    found: dict[str, Passage] = {**fetched, **hits}
    return tuple(found[point] for point in chosen if point in found)


def retrieve(state: EngineState, library: HighRiskLibrary) -> Retrieved:
    """The Annex III candidates, the guidance and the Annex I list for the description."""
    lookup = lookup_for(state)
    description = state["description"]

    def run(doc_type: str, language: Language, limit: int) -> tuple[SearchHit, ...]:
        return library.search(
            description, lookup, language=language, doc_type=doc_type, limit=limit
        )

    law = run("law", lookup.language, LAW_SEARCH_LIMIT)
    guidance = run("guideline", lookup.language, GUIDANCE_SEARCH_LIMIT)
    if not guidance and lookup.language is not Language.EN:
        guidance = run("guideline", Language.EN, GUIDANCE_SEARCH_LIMIT)
    return Retrieved(
        annex_i=annex_i_points(library, lookup),
        annex_iii=annex_iii_candidates(law, library, lookup),
        guidance=guidance,
    )
