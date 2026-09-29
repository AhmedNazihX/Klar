"""The corpus loader (aiact/corpus/load.py) against the local Supabase Postgres.

Every test runs in the `db` fixture's rolled-back transaction, and uses its own `doc_key`s, so
the loaded corpus in the shared database is never touched.
"""

from dataclasses import replace
from datetime import date

import psycopg
import pytest

from aiact.corpus.build import AI_ACT_IN_FORCE, DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.load import corpus_stats, load_all, load_document

pytestmark = pytest.mark.db

OMNIBUS_IN_FORCE = date(2026, 7, 27)
LAW = DocumentRow(
    doc_key="test-c3-law",
    title="Test law",
    celex=None,
    doc_type="law",
    is_amending=False,
    status="consolidated",
    law_version="amended",
    language="en",
    published_on=OMNIBUS_IN_FORCE,
    in_force_from=AI_ACT_IN_FORCE,
    source_url="https://eur-lex.europa.eu/",
    sha256="a" * 64,
)
PROVISIONS = (
    ProvisionRow("art:5", None, None, "Article 5", "1. old", AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE),
    ProvisionRow("art:5", None, None, "Article 5", "1. new 1a. ba", OMNIBUS_IN_FORCE),
    ProvisionRow("art:5:1", "art:5", AI_ACT_IN_FORCE, "Article 5", "old", AI_ACT_IN_FORCE,
                 OMNIBUS_IN_FORCE),
    ProvisionRow("art:5:1", "art:5", OMNIBUS_IN_FORCE, "Article 5", "new", OMNIBUS_IN_FORCE),
    ProvisionRow("art:5:1a", "art:5", OMNIBUS_IN_FORCE, "Article 5", "ba", OMNIBUS_IN_FORCE),
)  # fmt: skip
GUIDE = DocumentLoad(
    DocumentRow(
        doc_key="test-c3-guide",
        title="Test guideline",
        celex=None,
        doc_type="guideline",
        is_amending=False,
        status="draft",
        law_version=None,
        language="en",
        published_on=date(2026, 5, 19),
        in_force_from=None,
        source_url="https://ec.europa.eu/",
        sha256="b" * 64,
    ),
    (
        ProvisionRow("guide:test-c3-guide:para:1", None, None, None, "(1) a", date(2026, 5, 19)),
        ProvisionRow(
            "guide:test-c3-guide:ex:001",
            None,
            None,
            None,
            "example",
            date(2026, 5, 19),
            source_example_id="hr-ex-001",
            is_held_out=True,
        ),
    ),
)
AS_OF = """
    select p.provision_id, p.text, parent.provision_id, parent.valid_from
    from provisions p join documents d on d.id = p.document_id
    left join provisions parent on parent.id = p.parent_id
    where d.doc_key = %s and daterange(p.valid_from, p.valid_to) @> %s::date
    order by p.provision_id
"""


def _rows(db: psycopg.Connection, doc_key: str) -> list[tuple[object, ...]]:
    return db.execute(
        "select p.id, p.provision_id, p.valid_from, p.text, p.is_held_out from provisions p"
        " join documents d on d.id = p.document_id where d.doc_key = %s order by p.id",
        (doc_key,),
    ).fetchall()


def test_rerunning_changes_nothing(db: psycopg.Connection):
    loads = (DocumentLoad(LAW, PROVISIONS), GUIDE)
    assert [o for _, o in load_all(db, loads)] == ["inserted", "inserted"]
    before = _rows(db, "test-c3-law"), _rows(db, "test-c3-guide")
    document = db.execute("select xmin::text from documents where doc_key = 'test-c3-law'")
    xmin = document.fetchone()
    assert [o for _, o in load_all(db, loads)] == ["unchanged", "unchanged"]
    assert (_rows(db, "test-c3-law"), _rows(db, "test-c3-guide")) == before
    after = db.execute("select xmin::text from documents where doc_key = 'test-c3-law'")
    assert after.fetchone() == xmin


def test_parents_resolve_to_the_slice_of_the_same_dates(db: psycopg.Connection):
    load_document(db, DocumentLoad(LAW, PROVISIONS))
    assert db.execute(AS_OF, ("test-c3-law", "2025-01-01")).fetchall() == [
        ("art:5", "1. old", None, None),
        ("art:5:1", "old", "art:5", AI_ACT_IN_FORCE),
    ]
    assert db.execute(AS_OF, ("test-c3-law", "2026-09-01")).fetchall() == [
        ("art:5", "1. new 1a. ba", None, None),
        ("art:5:1", "new", "art:5", OMNIBUS_IN_FORCE),
        ("art:5:1a", "ba", "art:5", OMNIBUS_IN_FORCE),
    ]


def test_a_changed_text_replaces_the_provisions(db: psycopg.Connection):
    load_document(db, DocumentLoad(LAW, PROVISIONS))
    old_ids = {row[0] for row in _rows(db, "test-c3-law")}
    changed = (*PROVISIONS[:-1], replace(PROVISIONS[-1], text="ba, corrected"))
    assert load_document(db, DocumentLoad(LAW, changed)) == "reloaded"
    rows = _rows(db, "test-c3-law")
    assert len(rows) == len(PROVISIONS)
    assert old_ids.isdisjoint(row[0] for row in rows)
    assert rows[-1][3] == "ba, corrected"


def test_a_new_raw_file_reloads_even_with_the_same_rows(db: psycopg.Connection):
    load_document(db, DocumentLoad(LAW, PROVISIONS))
    renewed = DocumentLoad(replace(LAW, sha256="c" * 64), PROVISIONS)
    assert load_document(db, renewed) == "reloaded"


def test_a_metadata_change_keeps_the_provisions(db: psycopg.Connection):
    load_document(db, DocumentLoad(LAW, PROVISIONS))
    before = _rows(db, "test-c3-law")
    assert load_document(db, DocumentLoad(replace(LAW, title="Renamed"), PROVISIONS)) == "updated"
    assert _rows(db, "test-c3-law") == before
    title = db.execute("select title from documents where doc_key = 'test-c3-law'").fetchone()
    assert title == ("Renamed",)


def test_the_held_out_flag_is_stored(db: psycopg.Connection):
    load_document(db, GUIDE)
    assert [(row[1], row[4]) for row in _rows(db, "test-c3-guide")] == [
        ("guide:test-c3-guide:para:1", False),
        ("guide:test-c3-guide:ex:001", True),
    ]


def test_a_held_out_row_must_be_an_example(db: psycopg.Connection):
    bad = DocumentLoad(GUIDE.document, (replace(GUIDE.provisions[0], is_held_out=True),))
    with pytest.raises(psycopg.errors.CheckViolation):
        load_document(db, bad)


def test_stats_count_rows_slices_and_links(db: psycopg.Connection):
    de = replace(LAW, language="de")
    load_all(db, (DocumentLoad(LAW, PROVISIONS), DocumentLoad(de, PROVISIONS[:2]), GUIDE))
    stats = {(s.doc_key, s.language): s for s in corpus_stats(db)}
    law = stats[("test-c3-law", "en")]
    assert (law.rows, law.provisions, law.sliced, law.linked) == (5, 3, 2, 1)
    guide = stats[("test-c3-guide", "en")]
    assert (guide.examples, guide.held_out, guide.linked) == (1, 1, 0)
