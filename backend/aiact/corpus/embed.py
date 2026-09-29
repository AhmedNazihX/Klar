"""Embed the corpus: `aiact corpus embed` writes `provision_embeddings` (decision 009).

Every provision row gets one vector per embedding arm, keyed by `(provision_row_id, model, dims)`,
with the provision's `content_sha256` copied next to it. A row is skipped only when that key
exists and the hashes match; a missing or stale row is (re-)embedded and upserted.

Rows with the same text share one vector: the consolidated text's time slices that a split left
unchanged (decision 014) and the parts of the original and amended AI Act that match. The run
first copies vectors already stored for the same `content_sha256`, then embeds each remaining
distinct text once, in batches, and writes its vector to every row that has it. Each batch is
its own transaction, so an interrupted run resumes where it stopped. Tokens and cost are logged
per batch and summed in the report.

Parent rows include their children's text (C1), so every row, parent or leaf, has its own vector;
search (C6) dedupes hits by `parent_id`. The corpus tables are server-only, so this writes over
a direct connection (`aiact.db.connect`).
"""

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

import psycopg

from aiact.llm.embeddings import EmbeddingBatch, EmbeddingError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingArm:
    """One embedding model as OpenRouter serves it, pinned to one provider."""

    model: str
    provider: str
    max_input_chars: int
    """Longer texts are skipped and reported (about 3 characters per token of context)."""


ARMS = {
    # Decision 005: Nebius, 32,000-token context.
    "qwen3": EmbeddingArm("qwen/qwen3-embedding-8b", "nebius", 96_000),
    # Decision 005: the X1 comparison arm, ZDR via azure (no EU pin), 8,192-token context.
    "openai3l": EmbeddingArm("openai/text-embedding-3-large", "azure", 24_000),
}
DIMENSION_CHOICES = (1536, 1024)
DEFAULT_BATCH_SIZE = 32
MAX_BATCH_CHARS = 100_000
"""A batch closes before its texts pass this many characters (about 30,000 tokens a request)."""

ROWS = """
    from provisions p
    join documents d on d.id = p.document_id
    left join provision_embeddings e
      on e.provision_row_id = p.id and e.model = %(model)s and e.dims = %(dims)s
"""
STALE = """
    where (e.provision_row_id is null or e.content_sha256 <> p.content_sha256)
      and (%(doc_keys)s::text[] is null or d.doc_key = any(%(doc_keys)s::text[]))
"""
PENDING = f"select p.id, p.content_sha256, p.heading, p.text {ROWS} {STALE} order by p.id"
# A stored vector embeds the text its content_sha256 names, whichever row it belongs to now.
REUSE = f"""
    with source as (
      select distinct on (content_sha256) content_sha256, embedding
      from provision_embeddings where model = %(model)s and dims = %(dims)s
      order by content_sha256, created_at desc
    )
    insert into provision_embeddings (provision_row_id, model, dims, embedding, content_sha256)
    select p.id, %(model)s, %(dims)s, s.embedding, p.content_sha256
    {ROWS} join source s on s.content_sha256 = p.content_sha256 {STALE}
    on conflict (provision_row_id, model, dims) do update
    set embedding = excluded.embedding, content_sha256 = excluded.content_sha256, created_at = now()
"""
# Writes only rows whose text is still the one embedded, so a reload during the run can't
# attach a vector to a changed or deleted provision.
UPSERT = """
    insert into provision_embeddings (provision_row_id, model, dims, embedding, content_sha256)
    select p.id, %(model)s, %(dims)s, %(embedding)s::extensions.vector, p.content_sha256
    from provisions p
    where p.id = any(%(row_ids)s) and p.content_sha256 = %(content_sha256)s
    on conflict (provision_row_id, model, dims) do update
    set embedding = excluded.embedding, content_sha256 = excluded.content_sha256, created_at = now()
"""
DELETE_STALE = """
    delete from provision_embeddings e
    using provisions p
    where e.provision_row_id = p.id and e.provision_row_id = any(%(row_ids)s)
      and e.model = %(model)s and e.dims = %(dims)s and e.content_sha256 <> p.content_sha256
"""
ARM_INDEX = """
    select count(*) from pg_indexes
    where schemaname = 'public' and tablename = 'provision_embeddings'
      and indexdef like '%%' || %(model)s || '%%'
      and indexdef like '%%vector(' || %(dims)s || ')%%'
"""


class Embedder(Protocol):
    """What the run needs from an embeddings client (`aiact.llm.OpenRouterEmbeddings`)."""

    def embed_batch(self, texts: list[str]) -> EmbeddingBatch: ...


@dataclass(frozen=True)
class PendingText:
    """One distinct text to embed and the provision rows that have it."""

    content_sha256: str
    text: str
    row_ids: tuple[int, ...]


@dataclass(frozen=True)
class EmbedReport:
    """What one run did. `rows_*` count provision rows, `texts_*` distinct texts."""

    model: str
    dims: int
    rows_reused: int
    rows_embedded: int
    texts_embedded: int
    too_long: tuple[str, ...]
    """content_sha256 of texts over the arm's input limit: not embedded, older vectors removed."""
    batches: int
    tokens: int
    cost_usd: float


def input_text(heading: str | None, text: str) -> str:
    """The text sent to the model: the heading, a newline and the body, as `content_sha256` hashes
    them (without the newline when there is no heading)."""
    return f"{heading}\n{text}" if heading else text


def vector_literal(vector: Sequence[float]) -> str:
    """A pgvector text literal, `[x,y,…]`."""
    return "[" + ",".join(repr(x) for x in vector) + "]"


def group_by_text(rows: Sequence[tuple[int, str, str | None, str]]) -> tuple[PendingText, ...]:
    """Group `(row_id, content_sha256, heading, text)` rows by hash, first-seen order."""
    grouped: dict[str, tuple[str, list[int]]] = {}
    for row_id, content_sha256, heading, text in rows:
        grouped.setdefault(content_sha256, (input_text(heading, text), []))[1].append(row_id)
    return tuple(PendingText(sha, text, tuple(row_ids)) for sha, (text, row_ids) in grouped.items())


def batches(
    texts: Sequence[PendingText], batch_size: int, max_chars: int = MAX_BATCH_CHARS
) -> Iterator[tuple[PendingText, ...]]:
    """Split texts into batches of at most `batch_size` texts and about `max_chars` characters;
    a text longer than `max_chars` goes alone."""
    batch: list[PendingText] = []
    chars = 0
    for item in texts:
        if batch and (len(batch) == batch_size or chars + len(item.text) > max_chars):
            yield tuple(batch)
            batch, chars = [], 0
        batch.append(item)
        chars += len(item.text)
    if batch:
        yield tuple(batch)


def has_arm_index(connection: psycopg.Connection, model: str, dims: int) -> bool:
    """Whether a partial HNSW index exists for this (model, dims) arm (decision 009)."""
    row = connection.execute(ARM_INDEX, {"model": model, "dims": dims}).fetchone()
    return row is not None and row[0] > 0


def _write_batch(
    connection: psycopg.Connection,
    batch: tuple[PendingText, ...],
    result: EmbeddingBatch,
    params: dict[str, object],
) -> None:
    if len(result.vectors) != len(batch):
        raise EmbeddingError(f"expected {len(batch)} vectors, got {len(result.vectors)}")
    rows = [
        {
            **params,
            "embedding": vector_literal(vector),
            "row_ids": list(item.row_ids),
            "content_sha256": item.content_sha256,
        }
        for item, vector in zip(batch, result.vectors, strict=False)
    ]
    with connection.transaction(), connection.cursor() as cursor:
        cursor.executemany(UPSERT, rows)


def _drop_stale(
    connection: psycopg.Connection, texts: tuple[PendingText, ...], params: dict[str, object]
) -> None:
    """Delete this arm's vectors of rows that won't be embedded, so search can't rank them on
    an older text."""
    row_ids = [row_id for item in texts for row_id in item.row_ids]
    with connection.transaction():
        connection.execute(DELETE_STALE, {**params, "row_ids": row_ids})


def embed_corpus(
    connection: psycopg.Connection,
    embedder: Embedder,
    arm: EmbeddingArm,
    dims: int,
    *,
    doc_keys: Sequence[str] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EmbedReport:
    """Give every provision row (of `doc_keys`, or all) a current vector for this arm."""
    params: dict[str, object] = {
        "model": arm.model,
        "dims": dims,
        "doc_keys": list(doc_keys) if doc_keys else None,
    }
    with connection.transaction():
        rows_reused = connection.execute(REUSE, params).rowcount
    pending = group_by_text(connection.execute(PENDING, params).fetchall())
    too_long = tuple(t for t in pending if len(t.text) > arm.max_input_chars)
    if too_long:
        _drop_stale(connection, too_long, params)
    for item in too_long:
        logger.warning(
            "%s: text %s is over %d characters; not embedded, any older vector removed",
            arm.model,
            item.content_sha256,
            arm.max_input_chars,
        )
    to_embed = tuple(t for t in pending if len(t.text) <= arm.max_input_chars)
    results: list[EmbeddingBatch] = []
    for number, batch in enumerate(batches(to_embed, batch_size), start=1):
        result = embedder.embed_batch([item.text for item in batch])
        _write_batch(connection, batch, result, params)
        results.append(result)
        logger.info(
            "%s/%d batch %d: %d texts, %d tokens, $%.6f",
            arm.model,
            dims,
            number,
            len(batch),
            result.tokens,
            result.cost_usd,
        )
    return EmbedReport(
        model=arm.model,
        dims=dims,
        rows_reused=rows_reused,
        rows_embedded=sum(len(t.row_ids) for t in to_embed),
        texts_embedded=len(to_embed),
        too_long=tuple(t.content_sha256 for t in too_long),
        batches=len(results),
        tokens=sum(r.tokens for r in results),
        cost_usd=sum(r.cost_usd for r in results),
    )
