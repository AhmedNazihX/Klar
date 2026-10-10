"""`search_ai_act`: hybrid search over the corpus, meaning and keywords fused with RRF (story C6;
INIT > MCP tools, Tech stack).

No model is involved apart from the query embedding.
- **Two arms.** The meaning arm ranks provisions by cosine distance between their stored vector
  and the query vector (`embed_query`, so the task instruction goes on the query only). The
  keyword arm matches the `fts` column against each of the query's lexemes, as a prefix in German
  (`PREFIX_LANGUAGES`), whose stemmer is uneven: `syst:*` matches System and Systeme. A row
  scores the summed IDF (`ln(rows / rows with the word)`) of the words it has; words in more than
  `MAX_TERM_SHARE` (and `MIN_COMMON_ROWS`) of the rows are dropped, since a soft description is
  mostly such words and they would flood the arm with noise. The counts cover each unit of the
  searched language and law version once, never held-out rows or the Omnibus
  (`STATISTICS_SCOPE`); a word they don't contain gets the highest weight.
- **Fusion.** Each arm keeps its best `CANDIDATES` rows; weighted Reciprocal Rank Fusion adds
  `weight / (RRF_K + rank)` per arm. The keyword arm weighs `KEYWORD_WEIGHT`, little: X1b found
  it only lowered recall, so it breaks ties (decision 003). The constants travel as one
  `SearchTuning`, so the experiments can vary them.
- **Annex points.** An annex row with points under it (the whole annex, an Annex III area, an
  Annex I section) is left out of both ranked arms, so its points compete on their own (X1b).
- **Exact references.** The provisions a query names by number ("Article 50", "Anhang III Nr. 4";
  `aiact.retrieval.references`) are looked up by id under the same filters and come first, in
  the order named; such a hit is always relevant.
- **Vector index.** The meaning arm keeps the partial HNSW index's model and dims predicate and
  cast (decision 009), sets `hnsw.iterative_scan = relaxed_order` so filtered queries aren't
  short, and re-sorts a materialized CTE by distance, as pgvector advises. At about 9,000 rows the
  planner prefers an exact scan (about 15 ms), which is also exact; the index takes over when
  that gets dearer. A vector only counts while its `content_sha256` matches the provision's, so
  a stale vector is never ranked.
- **Filters.** Every filter sits inside the SQL of both arms, never in Python afterwards:
  - law version (default `amended`) by the decision-009 rule, so guidance (null version) stays
    searchable and the Omnibus never shows; recitals always come from the original text, the only
    one that has them (decision 014);
  - `as_of` (default today) against the amended text and the guidance slices; the original text
    is one open slice per unit, so `original` with `as_of` is an error, as in `get_provision`;
  - language (`fts` is built per row language, so the query is parsed in the same language);
  - `doc_types` (`law`, `guideline`, `code`), and `doc_keys` (manifest keys, for example
    `guide-definition`, so a step can search one guideline without the others crowding it out);
  - held-out (Pile B) examples are excluded by default (decision 012); only the gap run (V8) may
    set `include_held_out`. `exclude_source_example_ids` removes further examples by id.
- **Relevance (C8).** RRF is rank-based and says nothing absolute, so each hit also carries its
  meaning-arm `similarity` (1 - cosine distance) and its keyword-arm `keyword_idf` (the summed
  IDF above). `max_distance` cuts the meaning arm inside its SQL, after the nearest candidates are
  materialized, as pgvector advises for distance filters (a filter on the index scan itself
  would make an iterative scan walk the whole index for an off-topic query). It defaults to the
  `SEARCH_MAX_DISTANCE` setting; None is no cut-off. `SearchResults.found` tells "nothing
  relevant" from a match: a named provision, a hit within the cut-off, or a keyword hit on rare
  enough words (`SEARCH_MIN_KEYWORD_IDF`), so a match on the law's own rare terms counts. The
  engine searches without a cut-off (a signal, not a filter: a softly worded description must
  still reach its Annex point); Q&A and MCP use it. X1b calibrated both values (decision 003):
  Qwen3 cosines are compressed.
- **Parents.** A parent row includes all its descendants' text (C1), so a row that is an
  ancestor or a descendant of a better-ranked hit is skipped (`distinct_units`).
- **Tracing (V7).** Inside a traced engine run, a search is a LangSmith run of its own, with the
  documents and types it was limited to as metadata, never the query (`aiact.retrieval.tracing`).
"""

from collections.abc import Collection, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from math import isfinite
from typing import Any, LiteralString, Protocol

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from aiact.corpus.embed import vector_literal
from aiact.db import connect
from aiact.llm.embeddings import OpenRouterEmbeddings
from aiact.retrieval.references import exact_references
from aiact.retrieval.tracing import search_metadata, traced_lookup
from aiact.schemas import DISCLAIMER, DocumentStatus, Language, LawVersion
from aiact.schemas.base import ContractModel
from aiact.settings import get_settings

CANDIDATES = 50
"""Rows each arm hands to the fusion; also the largest `limit` a caller may ask for (X1b: 20 or
100 rank the same)."""

DEFAULT_LIMIT = 10
RRF_K = 10
"""The RRF constant (X1b; 60, the usual value, before): damps the gap between the first few
ranks of each arm. With the small keyword weight below, 2 to 20 rank alike."""

KEYWORD_WEIGHT = 0.1
"""The keyword arm's RRF weight (the meaning arm's is 1). X1b measured every weight from 0 to 1:
the keyword arm only ever lowered recall on both sets (0.5 with RRF_K 60, C6's guess, cost 0.1
of Q&A recall), so it now breaks ties between close meaning-arm ranks and no more. It still
finds the rows its rare words name, and gives `found` its `keyword_idf`."""

MAX_TERM_SHARE = 0.05
"""A query word found in more than this share of the rows in its language is left out of the
keyword arm: it says little and would flood the arm (soft descriptions are full of such words).
X1b: 0.01 to 0.1 rank the same at the keyword weight above."""

MIN_COMMON_ROWS = 50
"""A word is only too common when it is also in more than this many rows, so a small corpus
(tests, a partial load) doesn't lose all its words to the share rule."""

MAX_COSINE_DISTANCE = 2.0
"""The largest cosine distance there is (opposite vectors)."""


@dataclass(frozen=True)
class SearchTuning:
    """The ranking constants, as one value so X1b's experiments can vary them
    (`aiact evaluate embeddings --keyword-weight …`); the defaults are the chosen values."""

    keyword_weight: float = KEYWORD_WEIGHT
    rrf_k: int = RRF_K
    max_term_share: float = MAX_TERM_SHARE
    skips_annex_containers: bool = True
    """Rank an annex's points, never the annex, area or section row above them (X1b: with the
    rows that hold them in the running, a point's area outranked it in 15 of 48 Annex
    descriptions)."""

    def __post_init__(self) -> None:
        if not (isfinite(self.keyword_weight) and self.keyword_weight >= 0):
            raise ValueError(f"keyword_weight must be 0 or more, got {self.keyword_weight}")
        if self.rrf_k < 1:
            raise ValueError(f"rrf_k must be at least 1, got {self.rrf_k}")
        if not 0 < self.max_term_share <= 1:
            raise ValueError(f"max_term_share must be in (0, 1], got {self.max_term_share}")


DEFAULT_TUNING = SearchTuning()


class _FromSettings(Enum):
    TOKEN = "from settings"


FROM_SETTINGS = _FromSettings.TOKEN
"""The default of `max_distance`: take the `SEARCH_MAX_DISTANCE` setting."""

DOC_TYPES = frozenset({"law", "guideline", "code"})
FTS_CONFIGS = {Language.EN: "english", Language.DE: "german"}
"""The text search configuration per language, as the `provisions.fts` column uses it."""

PREFIX_LANGUAGES = frozenset({Language.DE})
"""Languages whose query words match as prefixes. The German stemmer is uneven (System -> syst,
Systeme -> system); the English one isn't, and there a prefix only adds noise (`app:*` matches
every `applic…`)."""

SCOPE: LiteralString = """
    not d.is_amending
    and p.language = %(language)s
    and (
      (d.law_version is null and daterange(p.valid_from, p.valid_to) @> %(on)s::date)
      or (d.law_version = %(law_version)s
          and (%(law_version)s = 'original' or daterange(p.valid_from, p.valid_to) @> %(on)s::date))
      or (d.law_version = 'original' and p.provision_id like 'recital:%%')
    )
    and (%(doc_types)s::text[] is null or d.doc_type = any(%(doc_types)s::text[]))
    and (%(doc_keys)s::text[] is null or d.doc_key = any(%(doc_keys)s::text[]))
    and (%(include_held_out)s or not p.is_held_out)
    and (p.source_example_id is null
         or not (p.source_example_id = any(%(exclude_source_example_ids)s::text[])))
"""
"""The filters every arm applies; `p` is the provision, `d` its document in the same language."""

ANNEX_CONTAINERS: LiteralString = """
    and not (%(skips_annex_containers)s and p.provision_id like 'annex:%%'
             and exists (select 1 from provisions c where c.parent_id = p.id))
"""
"""The meaning and keyword arms skip an annex row that has points under it (the whole annex, an
Annex III area, an Annex I section), so its points compete on their own (X1b)."""

STATISTICS_SCOPE: LiteralString = """
    not d.is_amending
    and not p.is_held_out
    and p.language = %(language)s
    and (d.law_version is null
         or d.law_version = %(law_version)s
         or (d.law_version = 'original' and p.provision_id like 'recital:%%'))
"""
"""The rows the keyword arm's word statistics count: the searched language and law version,
without held-out examples or the Omnibus, so neither can sway a ranking (decision 012), also not
when `include_held_out` is set. Each unit (document, provision id) counts once, however many
time slices it has; no date filter, since the statistics describe the text, not one day of it.
A word no counted unit has (for instance one only held-out examples use) gets the highest
weight, as if it were in one unit: it can only match a held-out row, and only when those are
opted in, so the gap run (V8) can still find an example by its own words."""

HYBRID_SEARCH: LiteralString = """
    with recursive vector_hits as materialized (
      select p.id,
             e.embedding::extensions.vector({dims})
               <=> %(query_vector)s::extensions.vector({dims}) as distance
      from provision_embeddings e
      join provisions p on p.id = e.provision_row_id and p.content_sha256 = e.content_sha256
      join documents d on d.id = p.document_id and d.language = p.language
      where e.model = {model} and e.dims = {dims} and {scope} {annex_containers}
      order by distance
      limit %(candidates)s
    ),
    -- The cut-off sits outside the materialized nearest rows, as pgvector advises.
    vector_ranked as (
      select id, distance, row_number() over (order by distance + 0, id) as rank
      from vector_hits
      where %(max_distance)s::float8 is null or distance <= %(max_distance)s::float8
    ),
    query_terms as materialized (
      select format(case when %(prefix_terms)s then '%%L:*' else '%%L' end, lexeme)::tsquery
             as term
      from unnest(to_tsvector(%(fts_config)s::regconfig, %(query)s))
      where position(E'\\\\' in lexeme) = 0
    ),
    statistics_total as materialized (
      select greatest(count(distinct (p.document_id, p.provision_id)), 1) as total
      from provisions p
      join documents d on d.id = p.document_id and d.language = p.language
      where {statistics_scope}
    ),
    -- One count per query word, straight on provisions so provisions_fts_idx serves it. The
    -- distinct count costs about 1-2 ms a word (about 60 ms for a 40-word description).
    term_weights as materialized (
      select t.term, ln(n.total::float8 / greatest(f.frequency, 1)) as idf
      from query_terms t
      cross join statistics_total n
      cross join lateral (
        select count(distinct (p.document_id, p.provision_id)) as frequency
        from provisions p
        join documents d on d.id = p.document_id and d.language = p.language
        where p.fts @@ t.term and {statistics_scope}
      ) f
      where f.frequency <= greatest(n.total * %(max_term_share)s, %(min_common_rows)s)
    ),
    keyword_ranked as (
      select p.id, sum(w.idf) as idf, row_number() over (order by sum(w.idf) desc, p.id) as rank
      from provisions p
      join documents d on d.id = p.document_id and d.language = p.language
      join term_weights w on p.fts @@ w.term
      where {scope} {annex_containers}
      group by p.id
      order by rank
      limit %(candidates)s
    ),
    -- The provisions the query names (`exact_references`), by id, in the order named.
    reference_ranked as (
      select p.id, array_position(%(reference_ids)s::text[], p.provision_id) as rank
      from provisions p
      join documents d on d.id = p.document_id and d.language = p.language
      where p.provision_id = any(%(reference_ids)s::text[]) and {scope}
    ),
    fused as (
      select id,
             sum(weight / (%(rrf_k)s + rank)) as score,
             min(rank) filter (where arm = 'vector') as vector_rank,
             min(rank) filter (where arm = 'keyword') as keyword_rank,
             min(rank) filter (where arm = 'reference') as reference_rank,
             min(measure) filter (where arm = 'vector') as distance,
             min(measure) filter (where arm = 'keyword') as keyword_idf
      from (
        select id, rank, 'vector' as arm, 1.0 as weight, distance as measure from vector_ranked
        union all
        select id, rank, 'keyword' as arm, %(keyword_weight)s as weight, idf as measure
        from keyword_ranked
        union all
        select id, rank, 'reference' as arm, 0.0 as weight, null as measure
        from reference_ranked
      ) ranked
      group by id
    ),
    lineage as (
      select f.id, p.parent_id as ancestor
      from fused f join provisions p on p.id = f.id
      where p.parent_id is not null
      union all
      select l.id, p.parent_id
      from lineage l join provisions p on p.id = l.ancestor
      where p.parent_id is not null
    )
    select f.id, f.score, f.vector_rank, f.keyword_rank, f.reference_rank, f.distance,
           f.keyword_idf,
           p.provision_id,
           array(select l.ancestor from lineage l where l.id = f.id) as ancestors,
           d.doc_key, d.title, d.doc_type, d.status, d.law_version, p.language,
           p.heading, p.text, p.valid_from, p.valid_to
    from fused f
    join provisions p on p.id = f.id
    join documents d on d.id = p.document_id and d.language = p.language
    order by f.reference_rank nulls last, f.score desc, f.id
"""


class QueryEmbedder(Protocol):
    """What search needs from an embeddings client (`aiact.llm.OpenRouterEmbeddings`): the arm
    it embeds with, and query embedding with the task instruction applied."""

    model: str
    dimensions: int

    def embed_query(self, text: str) -> list[float]: ...


class SearchHit(ContractModel):
    """One provision found, with where it comes from and how it ranked."""

    provision_id: str
    doc_key: str
    document_title: str
    doc_type: str
    law_version: LawVersion | None
    """The AI Act text the row belongs to; None for guidance."""
    status: DocumentStatus
    language: Language
    heading: str | None
    text: str
    valid_from: date
    valid_to: date | None
    score: float
    """The weighted RRF score: the sum of `weight / (RRF_K + rank)` over the arms that found it."""
    vector_rank: int | None
    """The rank in the meaning arm (1 is best); None when only the keywords found it."""
    keyword_rank: int | None
    """The rank in the keyword arm; None when only the meaning arm found it."""
    similarity: float | None
    """1 - the cosine distance to the query in the meaning arm; None when only the keywords found
    it (or the meaning arm's cut-off dropped it)."""
    keyword_idf: float | None
    """The summed IDF of the query words the row has; None when only the meaning arm found it."""
    reference_rank: int | None = None
    """Its place among the provisions the query names ("Article 50" names `art:50`), which come
    first; None when the query doesn't name it."""


class SearchResults(ContractModel):
    """The hits for one query, best first, with the version and date searched and the notice."""

    query: str
    language: Language
    law_version: LawVersion
    as_of: date | None
    """The date searched; None for the original text, which has one slice per unit."""
    hits: tuple[SearchHit, ...]
    max_distance: float | None
    """The meaning arm's cut-off applied; None for none."""
    found: bool
    """True when the query names a provision the corpus has, or a hit is within the cut-off (any
    meaning-arm hit, without one) or matches rare enough words (`SEARCH_MIN_KEYWORD_IDF`); False
    means nothing relevant was found."""
    disclaimer: str


@traced_lookup(search_metadata)
def search_ai_act(
    query: str,
    language: Language | str = Language.EN,
    law_version: LawVersion | str | None = None,
    as_of: date | None = None,
    *,
    doc_types: Collection[str] | None = None,
    doc_keys: Collection[str] | None = None,
    exclude_source_example_ids: Sequence[str] = (),
    include_held_out: bool = False,
    max_distance: float | _FromSettings | None = FROM_SETTINGS,
    limit: int = DEFAULT_LIMIT,
    embedder: QueryEmbedder | None = None,
    connection: psycopg.Connection | None = None,
    tuning: SearchTuning = DEFAULT_TUNING,
) -> SearchResults:
    """The provisions in `language` that best match `query`, from the law version and date asked.

    `law_version` defaults to `amended` and `as_of` to today. Held-out (Pile B) examples are never
    returned unless `include_held_out` is set, which only the gap run may do (decision 012).
    `max_distance` is the meaning arm's cosine-distance cut-off; it defaults to the
    `SEARCH_MAX_DISTANCE` setting, and None searches without one (as the engine does).
    `doc_keys` limits the search to those documents (manifest keys) inside both arms' SQL.
    The provisions the query names by number ("Article 50", "Anhang III Nr. 4") come first, in
    the order named (`exact_references`). `tuning` is for experiments only.
    Raises ValueError for an empty query, an unknown doc type, empty `doc_keys`, a `limit` outside
    1..CANDIDATES, a `max_distance` outside 0..2, or `original` together with `as_of`. Without
    an `embedder`, one is built from the settings; without a `connection`, one is opened from
    DATABASE_URL.
    """
    settings = get_settings()
    params, statement = prepare_search(
        query,
        Language(language),
        LawVersion(law_version) if law_version is not None else LawVersion.AMENDED,
        as_of,
        doc_types,
        exclude_source_example_ids,
        include_held_out,
        limit,
        embedder,
        max_distance=settings.search_max_distance
        if max_distance is FROM_SETTINGS
        else max_distance,
        doc_keys=doc_keys,
        tuning=tuning,
    )
    if connection is None:
        with connect() as own_connection:
            rows = _run(own_connection, statement, params)
    else:
        rows = _run(connection, statement, params)
    version = LawVersion(params["law_version"])
    hits = tuple(_hit(row) for row in distinct_units(rows, limit))
    return SearchResults(
        query=query,
        language=params["language"],
        law_version=version,
        as_of=None if version is LawVersion.ORIGINAL else params["on"],
        hits=hits,
        max_distance=params["max_distance"],
        found=any(_is_relevant(hit, settings.search_min_keyword_idf) for hit in hits),
        disclaimer=DISCLAIMER[Language(params["language"])],
    )


def _is_relevant(hit: SearchHit, min_keyword_idf: float) -> bool:
    """The query names it, the meaning arm kept it (so it is within any cut-off), or it matches
    rare enough words."""
    return (
        hit.reference_rank is not None
        or hit.similarity is not None
        or (hit.keyword_idf or 0.0) >= min_keyword_idf
    )


def prepare_search(
    query: str,
    language: Language,
    version: LawVersion,
    as_of: date | None,
    doc_types: Collection[str] | None,
    exclude_source_example_ids: Sequence[str],
    include_held_out: bool,
    limit: int,
    embedder: QueryEmbedder | None,
    *,
    max_distance: float | None = None,
    doc_keys: Collection[str] | None = None,
    tuning: SearchTuning = DEFAULT_TUNING,
) -> tuple[dict[str, Any], sql.Composed]:
    """Check the arguments, embed the query, and build the statement and its parameters (public so
    tests can EXPLAIN the statement). `max_distance` is taken as given: None is no cut-off.
    `doc_keys` None searches every document; an empty collection is rejected (it would find
    nothing)."""
    if not query.strip():
        raise ValueError("the search query is empty")
    if not 1 <= limit <= CANDIDATES:
        raise ValueError(f"limit must be between 1 and {CANDIDATES}, got {limit}")
    if doc_types is not None and not set(doc_types) <= DOC_TYPES:
        raise ValueError(f"unknown doc types {sorted(set(doc_types) - DOC_TYPES)}")
    if doc_keys is not None and not doc_keys:
        raise ValueError("doc_keys is empty; pass None to search every document")
    if version is LawVersion.ORIGINAL and as_of is not None:
        raise ValueError("as_of resolves only against the amended text; drop it for 'original'")
    if max_distance is not None and not (
        isfinite(max_distance) and 0.0 <= max_distance <= MAX_COSINE_DISTANCE
    ):
        raise ValueError(
            f"max_distance must be between 0 and {MAX_COSINE_DISTANCE}, got {max_distance}"
        )
    embedder = embedder or OpenRouterEmbeddings()
    vector = embedder.embed_query(query)
    params: dict[str, Any] = {
        "query": query,
        "query_vector": vector_literal(vector),
        "fts_config": FTS_CONFIGS[language],
        "prefix_terms": language in PREFIX_LANGUAGES,
        "language": language.value,
        "law_version": version.value,
        "on": as_of or date.today(),
        "doc_types": sorted(doc_types) if doc_types is not None else None,
        "doc_keys": sorted(doc_keys) if doc_keys is not None else None,
        "include_held_out": include_held_out,
        "max_distance": max_distance,
        "exclude_source_example_ids": list(exclude_source_example_ids),
        "reference_ids": list(exact_references(query)),
        "candidates": CANDIDATES,
        "min_common_rows": MIN_COMMON_ROWS,
        **asdict(tuning),
    }
    return params, _statement(embedder.model, embedder.dimensions)


def _statement(model: str, dims: int) -> sql.Composed:
    """The hybrid query with the arm's model and dims inlined as literals, so the planner can
    match the partial HNSW index's predicate and cast."""
    if isinstance(dims, bool) or not isinstance(dims, int) or dims <= 0:
        raise ValueError(f"embedding dimensions must be a positive integer, got {dims!r}")
    return sql.SQL(HYBRID_SEARCH).format(
        dims=sql.Literal(dims),
        model=sql.Literal(model),
        scope=sql.SQL(SCOPE),
        annex_containers=sql.SQL(ANNEX_CONTAINERS),
        statistics_scope=sql.SQL(STATISTICS_SCOPE),
    )


ITERATIVE_SCAN = "hnsw.iterative_scan"
SET_ITERATIVE_SCAN = "select set_config(%s, %s, true)"
PREVIOUS_ITERATIVE_SCAN = "select coalesce(current_setting(%s, true), '')"


def _run(
    connection: psycopg.Connection, statement: sql.Composed, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Run the search with `hnsw.iterative_scan = relaxed_order`, then put the setting back.

    Inside a caller's open transaction, `transaction()` is a savepoint and a local setting would
    outlive it, so the previous value is restored after the query. If the query fails, rolling
    back the savepoint (or transaction) undoes the setting anyway.
    """
    with connection.transaction(), connection.cursor(row_factory=dict_row) as cursor:
        previous = cursor.execute(PREVIOUS_ITERATIVE_SCAN, (ITERATIVE_SCAN,)).fetchone()
        cursor.execute(SET_ITERATIVE_SCAN, (ITERATIVE_SCAN, "relaxed_order"))
        rows = cursor.execute(statement, params).fetchall()
        restore = next(iter(previous.values())) if previous else ""
        cursor.execute(SET_ITERATIVE_SCAN, (ITERATIVE_SCAN, restore or "off"))
        return rows


def distinct_units(rows: Sequence[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """The first `limit` rows, in fused order, that don't overlap a row already taken.

    A parent's text includes all its descendants' (C1), so a row overlaps a taken row when one
    is an ancestor of the other (`ancestors` holds a row's full chain of parent ids). The
    better-ranked of the two wins, whether that is the parent or the child: only rows that
    compete for the returned slots are compared, so a parent is never dropped for a child
    ranked far below it.
    """
    taken: list[dict[str, Any]] = []
    taken_ids: set[int] = set()
    covered: set[int] = set()
    """The taken rows' ids and all their ancestors' ids."""
    for row in rows:
        if len(taken) == limit:
            break
        ancestors = set(row["ancestors"])
        if row["id"] in covered or ancestors & taken_ids:
            continue
        taken.append(row)
        taken_ids.add(row["id"])
        covered |= ancestors | {row["id"]}
    return taken


def _hit(row: dict[str, Any]) -> SearchHit:
    return SearchHit(
        provision_id=row["provision_id"],
        doc_key=row["doc_key"],
        document_title=row["title"],
        doc_type=row["doc_type"],
        law_version=row["law_version"],
        status=row["status"],
        language=row["language"],
        heading=row["heading"],
        text=row["text"],
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
        score=float(row["score"]),
        vector_rank=row["vector_rank"],
        keyword_rank=row["keyword_rank"],
        similarity=None if row["distance"] is None else 1.0 - float(row["distance"]),
        keyword_idf=None if row["keyword_idf"] is None else float(row["keyword_idf"]),
        reference_rank=row["reference_rank"],
    )
