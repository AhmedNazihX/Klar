"""Benchmark isolation measurements (story B13; INIT > Benchmark isolation 5; decision 012).

Pile B rows are stored in `provisions`, tagged, and hidden by default (decision 012), so the
check is about behaviour, not absence. This module holds the measurements; the assertions are in
`tests/test_isolation.py`, which CI runs against the committed corpus.
- **Tags.** Every Pile B id of `eval/split.json` must sit on a held-out row, no retrievable row
  may carry a Pile B id, and each example row must hold the text B2 extracted for its id.
- **Word n-grams.** For every benchmark text, the share of its 6-word runs found in one
  retrievable row (`coverage`) and the longest shared verbatim run. Text is compared lower-case,
  letters only: digits go, so footnote numbers left in the corpus (decision 001 rule 7) don't
  hide a match, and hyphens inside words are joined ("real-time" = "realtime").
- **Embeddings.** The cosine between each benchmark text and its nearest retrievable row, with
  the corpus arm's model. The benchmark vectors live in `EMBEDDINGS_FILE` under `eval/`, never
  in the corpus tables; `aiact evaluate isolation-embed` fills it (a small paid call).

The benchmark texts are the Pile B examples' own `text` (the `lead_in` is left out: it is the
paragraph or bullet that introduces the list, prose that stays retrievable, or is shared with
the Pile A examples of the same bullet) and every case description. The academic cases' `Domain:`
line is left out: it quotes an Annex III heading verbatim (B12's audit), statutory wording that is
in the corpus by design.
"""

import base64
import hashlib
import json
import re
import struct
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import psycopg
from pydantic import BaseModel, ConfigDict, Field

from aiact.corpus.embed import vector_literal
from aiact.eval.cases import APPLIEDAI_FILE, CASES_DIR, EVAL_DIR, CaseSet, load_cases, load_jsonl
from aiact.eval.split import EXAMPLES_FILE, SPLIT_FILE, Split
from aiact.llm.embeddings import EmbeddingBatch

EMBEDDINGS_FILE = EVAL_DIR / "isolation" / "embeddings.json"
NGRAM_WORDS = 6
PROSE_COVERAGE_LIMIT = 0.5
"""A benchmark text with half its 6-word runs in one guideline or law row repeats that row."""
EXAMPLE_COVERAGE_LIMIT = 0.8
"""Against a Pile A example row the limit is higher: examples of one list share their reasoning
sentence ("It therefore falls outside the use case of point 4(a)"), and the split keeps such
siblings on both sides by design (decisions 001 and 011). The highest measured is 0.65."""
DERIVATION_COVERAGE_MIN = 0.9
"""An example row must hold at least this share of the 6-word runs of B2's text for its id."""
EMBEDDING_COSINE_LIMIT = 0.9
"""A cosine at or above this against a retrievable row counts as a close restatement of it.

A coarse backstop, measured with Qwen3/1536 on 2026-09-30: a Pile B text scores a median 0.918
against its own stored row (heading and lead-in added), but topical prose on the same Annex III
point already reaches 0.894 (hr-ex-284 vs annex-iii para:417), and hr-ex-064's word-for-word
repeat inside para:183 only 0.904. So the cosine can't tell a paraphrase inside a long
paragraph from a paragraph on the same topic; the 6-gram check is the main detector."""
DOMAIN_LINE_PREFIX = "Domain:"

WORD_RE = re.compile(r"[^\W\d_]+")
INNER_HYPHEN_RE = re.compile("(?<=[^\\W\\d_])[-‐‑](?=[^\\W\\d_])")  # noqa: RUF001
"""A hyphen, Unicode hyphen or non-breaking hyphen between two letters."""
APOSTROPHE_RE = re.compile("['’]")  # noqa: RUF001

type Ngram = tuple[str, ...]


def normalised_words(text: str) -> tuple[str, ...]:
    """Lower-case letter runs, with apostrophes dropped, inner hyphens joined and digits gone."""
    joined = INNER_HYPHEN_RE.sub("", APOSTROPHE_RE.sub("", text.lower()))
    return tuple(WORD_RE.findall(joined))


def ngrams(words: Sequence[str], size: int = NGRAM_WORDS) -> frozenset[Ngram]:
    return frozenset(tuple(words[i : i + size]) for i in range(len(words) - size + 1))


def longest_shared_run(first: Sequence[str], second: Sequence[str]) -> int:
    """The length in words of the longest run that both word sequences contain."""
    best = 0
    previous = [0] * (len(second) + 1)
    for word in first:
        current = [0] * (len(second) + 1)
        for j, other in enumerate(second, start=1):
            if word == other:
                current[j] = previous[j - 1] + 1
                best = max(best, current[j])
        previous = current
    return best


# --- The benchmark side ---------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkText:
    """One text the corpus must not repeat: a Pile B example or a case description."""

    key: str
    """The example id (`hr-ex-NNN`) or the case id."""
    text: str


class ExampleText(BaseModel):
    """The fields of a B2 example row this check needs."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    example_id: str = Field(pattern=r"^hr-ex-[0-9]{3}$")
    source: str
    text: str = Field(min_length=1)


def load_split(path: Path = SPLIT_FILE) -> Split:
    return Split.model_validate_json(path.read_text(encoding="utf-8"))


def load_example_texts(path: Path = EXAMPLES_FILE) -> tuple[ExampleText, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return tuple(ExampleText.model_validate(json.loads(line)) for line in lines if line.strip())


def pile_b_texts(
    examples: Iterable[ExampleText], pile_b: Iterable[str]
) -> tuple[BenchmarkText, ...]:
    held_out = frozenset(pile_b)
    return tuple(BenchmarkText(e.example_id, e.text) for e in examples if e.example_id in held_out)


def checked_description(case_set: CaseSet, description: str) -> str:
    """The description without the academic `Domain:` line (see the module docstring)."""
    if case_set is not CaseSet.ACADEMIC:
        return description
    lines = description.splitlines()
    return "\n".join(line for line in lines if not line.startswith(DOMAIN_LINE_PREFIX))


def case_texts(
    cases_dir: Path = CASES_DIR, appliedai_file: Path | None = APPLIEDAI_FILE
) -> tuple[BenchmarkText, ...]:
    """Every case description of the YAML sets that exist, plus the appliedAI extraction when
    `appliedai_file` is given and present (it is gitignored and may be absent)."""
    texts: list[BenchmarkText] = []
    for case_set in CaseSet:
        if case_set is CaseSet.APPLIEDAI:
            continue
        if not (cases_dir / case_set.value).is_dir():
            continue
        cases = load_cases(case_set, cases_dir)
        texts.extend(
            BenchmarkText(c.id, checked_description(case_set, c.description)) for c in cases
        )
    if appliedai_file is not None and appliedai_file.is_file():
        texts.extend(BenchmarkText(c.id, c.description) for c in load_jsonl(appliedai_file))
    return tuple(texts)


# --- The corpus side ------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusRow:
    """A provision row a default search can return."""

    provision_id: str
    language: str
    source_example_id: str | None
    text: str


RETRIEVABLE_ROWS = """
    select provision_id, language, source_example_id, text
    from provisions where not is_held_out order by id
"""


def retrievable_rows(connection: psycopg.Connection) -> tuple[CorpusRow, ...]:
    """Every row not held out: what search may return once C6's default filter is applied."""
    return tuple(CorpusRow(*row) for row in connection.execute(RETRIEVABLE_ROWS).fetchall())


@dataclass(frozen=True)
class TagGaps:
    """How the held-out flags in `provisions` differ from `pile_b`; empty means they agree."""

    untagged: tuple[str, ...]
    """Pile B ids with no held-out row."""
    retrievable: tuple[str, ...]
    """Pile B ids on a row that is not held out."""
    unexpected: tuple[str, ...]
    """Held-out rows whose id is not in Pile B."""

    @property
    def is_empty(self) -> bool:
        return not (self.untagged or self.retrievable or self.unexpected)


TAGGED_ROWS = """
    select source_example_id, is_held_out from provisions where source_example_id is not null
"""


def tag_gaps(connection: psycopg.Connection, pile_b: Iterable[str]) -> TagGaps:
    held_out_ids = frozenset(pile_b)
    rows = connection.execute(TAGGED_ROWS).fetchall()
    held = {example_id for example_id, is_held_out in rows if is_held_out}
    open_ = {example_id for example_id, is_held_out in rows if not is_held_out}
    return TagGaps(
        untagged=tuple(sorted(held_out_ids - held)),
        retrievable=tuple(sorted(held_out_ids & open_)),
        unexpected=tuple(sorted(held - held_out_ids)),
    )


EXAMPLE_ROWS = """
    select p.source_example_id, d.doc_key, p.text
    from provisions p join documents d on d.id = p.document_id and d.language = p.language
    where p.source_example_id is not null and p.language = 'en'
"""


def derivation_mismatches(
    connection: psycopg.Connection, examples: Iterable[ExampleText]
) -> tuple[str, ...]:
    """Example ids whose tagged row is missing, sits in another document, or doesn't hold B2's
    text: C2 derives the ids from the PDFs alone, so this checks it against decision 001."""
    rows = {example_id: (doc_key, text) for example_id, doc_key, text in connection.execute(
        EXAMPLE_ROWS
    ).fetchall()}  # fmt: skip
    mismatched: list[str] = []
    for example in examples:
        row = rows.get(example.example_id)
        if row is None or row[0] != example.source:
            mismatched.append(example.example_id)
            continue
        expected = ngrams(normalised_words(example.text))
        found = ngrams(normalised_words(row[1]))
        if expected and len(expected & found) / len(expected) < DERIVATION_COVERAGE_MIN:
            mismatched.append(example.example_id)
    return tuple(mismatched)


# --- Word n-gram closeness ------------------------------------------------------------------


@dataclass(frozen=True)
class NgramMatch:
    """A benchmark text's closest retrievable row of one kind (prose or example)."""

    key: str
    provision_id: str
    is_example_row: bool
    coverage: float
    """The share of the text's 6-word runs that the row contains."""
    longest_run: int
    """The longest verbatim run, in words, that the text and the row share."""

    @property
    def is_near_duplicate(self) -> bool:
        limit = EXAMPLE_COVERAGE_LIMIT if self.is_example_row else PROSE_COVERAGE_LIMIT
        return self.coverage >= limit


@dataclass
class NgramIndex:
    """Which retrievable rows contain each 6-word run."""

    rows: Sequence[CorpusRow]
    _words: list[tuple[str, ...]] = field(init=False)
    _index: dict[Ngram, list[int]] = field(init=False)

    def __post_init__(self) -> None:
        self._words = [normalised_words(row.text) for row in self.rows]
        index: defaultdict[Ngram, list[int]] = defaultdict(list)
        for position, words in enumerate(self._words):
            for gram in ngrams(words):
                index[gram].append(position)
        self._index = dict(index)

    def closest(self, text: BenchmarkText) -> tuple[NgramMatch, ...]:
        """The best prose row and the best example row, each only when one shares a run."""
        words = normalised_words(text.text)
        grams = ngrams(words)
        hits = Counter(position for gram in grams for position in self._index.get(gram, ()))
        best: dict[bool, tuple[int, int]] = {}
        for position, count in hits.items():
            kind = self.rows[position].source_example_id is not None
            if kind not in best or count > best[kind][1]:
                best[kind] = (position, count)
        return tuple(
            NgramMatch(
                key=text.key,
                provision_id=self.rows[position].provision_id,
                is_example_row=kind,
                coverage=count / len(grams),
                longest_run=longest_shared_run(words, self._words[position]),
            )
            for kind, (position, count) in sorted(best.items())
        )


def closest_by_ngram(
    texts: Iterable[BenchmarkText], rows: Sequence[CorpusRow]
) -> tuple[NgramMatch, ...]:
    """Every text's closest rows, highest coverage first."""
    index = NgramIndex(rows)
    matches = (match for text in texts for match in index.closest(text))
    return tuple(sorted(matches, key=lambda m: (-m.coverage, m.key)))


# --- Embeddings -----------------------------------------------------------------------------


class Embedder(Protocol):
    def embed_batch(self, texts: list[str]) -> EmbeddingBatch: ...


class EmbeddingCache(BaseModel):
    """The benchmark texts' vectors, keyed by the sha256 of the text, stored as base64 float16
    (enough for a cosine to three decimals, a quarter of the size of JSON floats)."""

    model_config = ConfigDict(frozen=True)

    model: str
    dims: int
    vectors: dict[str, str] = {}


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def encode_vector(vector: Sequence[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vector)}e", *vector)).decode("ascii")


def decode_vector(encoded: str) -> tuple[float, ...]:
    raw = base64.b64decode(encoded)
    return struct.unpack(f"<{len(raw) // 2}e", raw)


def load_cache(path: Path, model: str, dims: int) -> EmbeddingCache:
    """The cache at `path`, or an empty one; a cache for another model or size starts over."""
    if not path.is_file():
        return EmbeddingCache(model=model, dims=dims)
    cache = EmbeddingCache.model_validate_json(path.read_text(encoding="utf-8"))
    return cache if (cache.model, cache.dims) == (model, dims) else EmbeddingCache(
        model=model, dims=dims
    )  # fmt: skip


def write_cache(cache: EmbeddingCache, path: Path) -> None:
    """One vector per line, sorted, so a new case adds lines instead of rewriting the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ",\n".join(
        f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in sorted(cache.vectors.items())
    )
    header = f'{{"model": {json.dumps(cache.model)}, "dims": {cache.dims}, "vectors": {{\n'
    path.write_text(f"{header}{lines}\n}}}}\n", encoding="utf-8")


@dataclass(frozen=True)
class EmbedOutcome:
    cache: EmbeddingCache
    embedded: int
    removed: int
    tokens: int
    cost_usd: float


def refresh_cache(
    cache: EmbeddingCache,
    texts: Iterable[BenchmarkText],
    embedder: Embedder,
    batch_size: int = 64,
) -> EmbedOutcome:
    """A new cache holding a vector for every text: missing ones are embedded (as documents, no
    query instruction), those of texts no longer in the benchmark are dropped."""
    wanted = {text_key(t.text): t.text for t in texts}
    kept = {k: v for k, v in cache.vectors.items() if k in wanted}
    missing = [(k, v) for k, v in wanted.items() if k not in kept]
    added: dict[str, str] = {}
    tokens, cost = 0, 0.0
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        result = embedder.embed_batch([text for _, text in batch])
        added |= {k: encode_vector(v) for (k, _), v in zip(batch, result.vectors, strict=True)}
        tokens, cost = tokens + result.tokens, cost + result.cost_usd
    return EmbedOutcome(
        cache=cache.model_copy(update={"vectors": kept | added}),
        embedded=len(added),
        removed=len(cache.vectors) - len(kept),
        tokens=tokens,
        cost_usd=cost,
    )


@dataclass(frozen=True)
class EmbeddingMatch:
    """A benchmark text's nearest retrievable row of one kind (prose or example)."""

    key: str
    provision_id: str
    is_example_row: bool
    cosine: float

    @property
    def is_near_duplicate(self) -> bool:
        return self.cosine >= EMBEDDING_COSINE_LIMIT


# The exact nearest row of each kind (prose, example) for one vector: a sequential scan of the
# arm, since the query doesn't use the HNSW index's cast. The stale-vector guard and the held-out
# filter are inside the SQL, as C4's audit asks of every vector query.
NEAREST_ROWS = """
    select distinct on (p.source_example_id is not null)
           p.provision_id, p.source_example_id is not null,
           1 - (e.embedding operator(extensions.<=>) %(vector)s::extensions.vector)
    from provision_embeddings e
    join provisions p on p.id = e.provision_row_id and p.content_sha256 = e.content_sha256
    where e.model = %(model)s and e.dims = %(dims)s and not p.is_held_out
    order by p.source_example_id is not null,
             e.embedding operator(extensions.<=>) %(vector)s::extensions.vector
"""
COUNT_ARM = "select count(*) from provision_embeddings where model = %(model)s and dims = %(dims)s"


def embedded_row_count(connection: psycopg.Connection, model: str, dims: int) -> int:
    row = connection.execute(COUNT_ARM, {"model": model, "dims": dims}).fetchone()
    return row[0] if row else 0


def nearest_by_embedding(
    connection: psycopg.Connection, texts: Iterable[BenchmarkText], cache: EmbeddingCache
) -> tuple[EmbeddingMatch, ...]:
    """Every text's nearest prose row and example row, highest cosine first. A text missing
    from the cache raises KeyError: run `aiact evaluate isolation-embed`."""
    matches: list[EmbeddingMatch] = []
    for text in texts:
        params = {
            "vector": vector_literal(decode_vector(cache.vectors[text_key(text.text)])),
            "model": cache.model,
            "dims": cache.dims,
        }
        rows = connection.execute(NEAREST_ROWS, params).fetchall()
        matches.extend(EmbeddingMatch(text.key, pid, kind, float(cos)) for pid, kind, cos in rows)
    return tuple(sorted(matches, key=lambda m: (-m.cosine, m.key)))
