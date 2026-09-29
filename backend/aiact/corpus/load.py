"""Load the corpus into Postgres: `aiact corpus load` writes `documents` and `provisions`.

The rows come from `aiact.corpus.build` (manifest + parsed JSONL). Each document is its own
transaction (decision 009):
- the document is upserted on `(doc_key, law_version, language)`; a row whose columns are all
  the same is left alone;
- when its `sha256` (the raw file) or `load_sha256` (the rows built from the parsed files) changed,
  all its provisions are deleted in one statement and inserted again, parents before children;
  their embeddings go with them (cascade). Both unchanged means the provisions are skipped, so a
  re-run changes nothing.

The corpus tables are server-only (RLS on, no Data API grants), so the loader writes over a
direct connection (`aiact.db.connect`). Two loaders running at once wait for each other per
document (a transaction-level advisory lock). Documents in the database that the manifest no
longer lists are reported, never deleted. Afterwards it counts the rows per document from the
database and writes them to `docs/corpus_stats.md`.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import psycopg

from aiact.corpus.build import DocumentLoad, LoadError
from aiact.corpus.files import write_if_changed
from aiact.settings import BACKEND_DIR

logger = logging.getLogger(__name__)

Outcome = Literal["inserted", "reloaded", "updated", "unchanged"]
"""`updated`: only the document's metadata (title, dates, URL) changed; provisions were kept."""

STATS_FILE = BACKEND_DIR.parent / "docs" / "corpus_stats.md"

SELECT_DOCUMENT = """
    select id, sha256, load_sha256 from documents
    where doc_key = %(doc_key)s and law_version is not distinct from %(law_version)s
      and language = %(language)s
"""
DOCUMENT_COLUMNS = (
    "title",
    "celex",
    "doc_type",
    "is_amending",
    "status",
    "published_on",
    "in_force_from",
    "source_url",
    "sha256",
    "load_sha256",
)
KEY_COLUMNS = ("doc_key", "law_version", "language")
# Updates only a row that differs, so an unchanged document returns no row and isn't rewritten.
UPSERT_DOCUMENT = f"""
    insert into documents ({", ".join((*KEY_COLUMNS, *DOCUMENT_COLUMNS))})
    values ({", ".join(f"%({c})s" for c in (*KEY_COLUMNS, *DOCUMENT_COLUMNS))})
    on conflict ({", ".join(KEY_COLUMNS)}) do update
    set {", ".join(f"{c} = excluded.{c}" for c in DOCUMENT_COLUMNS)}
    where ({", ".join(f"documents.{c}" for c in DOCUMENT_COLUMNS)})
      is distinct from ({", ".join(f"excluded.{c}" for c in DOCUMENT_COLUMNS)})
    returning id
"""
# The parent is the slice of the parent provision the builder named, inserted earlier in the batch.
INSERT_PROVISION = """
    insert into provisions (
      provision_id, document_id, language, parent_id, heading, text,
      valid_from, valid_to, source_example_id, is_held_out
    )
    values (
      %(provision_id)s, %(document_id)s, %(language)s,
      (select p.id from provisions p
       where p.document_id = %(document_id)s and p.language = %(language)s
         and p.provision_id = %(parent_id)s and p.valid_from = %(parent_valid_from)s),
      %(heading)s, %(text)s, %(valid_from)s, %(valid_to)s, %(source_example_id)s, %(is_held_out)s
    )
"""
# Serialises two loaders on the same document, so the second sees the first's row.
LOCK_DOCUMENT = "select pg_advisory_xact_lock(hashtextextended(%s, 0))"
DOCUMENT_KEYS = "select doc_key, law_version, language from documents order by 1, 2, 3"
COUNT_ROOTS = "select count(*) from provisions where document_id = %s and parent_id is null"
STATS_QUERY = """
    with ids as (
      select distinct d.id as document_id, d.doc_key, d.law_version, d.language, p.provision_id
      from documents d join provisions p on p.document_id = d.id
    ),
    linked as (
      select a.document_id, count(*) as linked
      from ids a join ids b
        on b.doc_key = a.doc_key and b.law_version is not distinct from a.law_version
       and b.language <> a.language and b.provision_id = a.provision_id
      group by a.document_id
    ),
    sliced as (
      select document_id, count(*) as sliced
      from (select document_id, provision_id from provisions
            group by document_id, provision_id having count(*) > 1) s
      group by document_id
    )
    select d.doc_key, d.language, d.law_version, d.status,
           count(p.id) as row_count,
           count(distinct p.provision_id) as provision_count,
           coalesce(max(s.sliced), 0) as sliced,
           count(p.id) filter (where p.source_example_id is not null) as examples,
           count(p.id) filter (where p.is_held_out) as held_out,
           coalesce(max(l.linked), 0) as linked
    from documents d
    left join provisions p on p.document_id = d.id
    left join sliced s on s.document_id = d.id
    left join linked l on l.document_id = d.id
    group by d.id
    order by d.doc_key, d.law_version nulls first, d.language
"""


def _document_params(load: DocumentLoad) -> dict[str, object]:
    d = load.document
    return {
        "doc_key": d.doc_key,
        "law_version": d.law_version,
        "language": d.language,
        "title": d.title,
        "celex": d.celex,
        "doc_type": d.doc_type,
        "is_amending": d.is_amending,
        "status": d.status,
        "published_on": d.published_on,
        "in_force_from": d.in_force_from,
        "source_url": d.source_url,
        "sha256": d.sha256,
        "load_sha256": load.load_sha256,
    }


def _insert_provisions(
    connection: psycopg.Connection, document_id: int, load: DocumentLoad
) -> None:
    params = [
        {
            "provision_id": p.provision_id,
            "document_id": document_id,
            "language": load.document.language,
            "parent_id": p.parent_id,
            "parent_valid_from": p.parent_valid_from,
            "heading": p.heading,
            "text": p.text,
            "valid_from": p.valid_from,
            "valid_to": p.valid_to,
            "source_example_id": p.source_example_id,
            "is_held_out": p.is_held_out,
        }
        for p in load.provisions
    ]
    with connection.cursor() as cursor:
        cursor.executemany(INSERT_PROVISION, params)
        roots = cursor.execute(COUNT_ROOTS, (document_id,)).fetchone()
    expected = sum(p.parent_id is None for p in load.provisions)
    if roots is None or roots[0] != expected:
        # Rolls the document's transaction back: a missing parent would silently orphan a unit.
        raise LoadError(f"{load.label}: {roots} rows without a parent, expected {expected}")


def load_document(connection: psycopg.Connection, load: DocumentLoad) -> Outcome:
    """Upsert one document and, if its text changed, replace its provisions; one transaction."""
    params = _document_params(load)
    lock_key = f"corpus:{load.label}:{load.document.law_version}"
    with connection.transaction():
        connection.execute(LOCK_DOCUMENT, (lock_key,))
        existing = connection.execute(SELECT_DOCUMENT, params).fetchone()
        written = connection.execute(UPSERT_DOCUMENT, params).fetchone()
        document_id = written[0] if written is not None else existing[0] if existing else None
        if document_id is None:
            raise LoadError(f"{load.label}: the upsert returned no document id")
        if existing is not None and tuple(existing[1:]) == (
            params["sha256"],
            params["load_sha256"],
        ):
            return "unchanged" if written is None else "updated"
        connection.execute("delete from provisions where document_id = %s", (document_id,))
        _insert_provisions(connection, document_id, load)
    return "inserted" if existing is None else "reloaded"


def load_all(
    connection: psycopg.Connection, loads: tuple[DocumentLoad, ...]
) -> tuple[tuple[str, Outcome], ...]:
    """Load every document; each label with what happened to it."""
    outcomes: list[tuple[str, Outcome]] = []
    for load in loads:
        outcome = load_document(connection, load)
        logger.info("%s: %s (%d provision rows)", load.label, outcome, len(load.provisions))
        outcomes.append((load.label, outcome))
    return tuple(outcomes)


def unlisted_documents(
    connection: psycopg.Connection, loads: tuple[DocumentLoad, ...]
) -> tuple[str, ...]:
    """`doc_key.lang (law_version)` of stored documents the loads don't include."""
    listed = {(d.document.doc_key, d.document.law_version, d.document.language) for d in loads}
    return tuple(
        f"{key}.{language} ({version or '-'})"
        for key, version, language in connection.execute(DOCUMENT_KEYS).fetchall()
        if (key, version, language) not in listed
    )


@dataclass(frozen=True)
class DocumentStats:
    """Row counts of one document, as stored."""

    doc_key: str
    language: str
    law_version: str | None
    status: str
    rows: int
    provisions: int
    sliced: int
    examples: int
    held_out: int
    linked: int


def corpus_stats(connection: psycopg.Connection) -> tuple[DocumentStats, ...]:
    """Row counts per document, read back from the database."""
    return tuple(DocumentStats(*row) for row in connection.execute(STATS_QUERY).fetchall())


STATS_HEADER = """# Corpus statistics

Generated by `aiact corpus load` from the database after loading; do not edit by hand.

- **Rows**: `provisions` rows (time slices). **Provisions**: distinct `provision_id`s.
- **Sliced**: provisions with more than one time slice: changed by the Digital Omnibus, or under
  a provision it changed (decision 014).
- **Examples**: Commission worked-example chunks (`source_example_id` set);
  **Held out**: of those, Pile B examples (`is_held_out`, excluded from search by default).
- **Linked**: provision ids the other language version of the same document also has
  (EN and DE are linked by `provision_id`).

"""


def render_stats(stats: tuple[DocumentStats, ...]) -> str:
    """The stats as a markdown table with a total row."""
    lines = [
        "| Document | Lang | Law version | Status | Rows | Provisions | Sliced | Examples"
        " | Held out | Linked |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in stats:
        lines.append(
            f"| {s.doc_key} | {s.language} | {s.law_version or '-'} | {s.status} | {s.rows}"
            f" | {s.provisions} | {s.sliced} | {s.examples} | {s.held_out} | {s.linked} |"
        )
    totals = [sum(getattr(s, f) for s in stats) for f in ("rows", "provisions", "sliced")]
    totals += [sum(getattr(s, f) for s in stats) for f in ("examples", "held_out", "linked")]
    lines.append(f"| **Total** | | | | {' | '.join(str(t) for t in totals)} |")
    return "\n".join(lines) + "\n"


def write_stats(stats: tuple[DocumentStats, ...], path: Path) -> bool:
    """Write `docs/corpus_stats.md`; True if its content changed."""
    return write_if_changed(path, STATS_HEADER + render_stats(stats))
