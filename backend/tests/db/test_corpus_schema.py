"""The corpus migration (supabase/migrations/*_corpus.sql) against the local Supabase Postgres.

The documents use `test-` keys: `aiact corpus load` fills the shared database with the real ones.
"""

import psycopg
import pytest

from aiact.settings import Settings

pytestmark = pytest.mark.db

CORPUS_TABLES = ("documents", "provisions", "provision_embeddings")
DEFAULT_MODEL = "qwen/qwen3-embedding-8b"
DEFAULT_DIMS = 1536
SHA256 = "a" * 64
AI_ACT_IN_FORCE = "2024-08-01"
DRAFT_DATES = ("2026-05-19", None)
OMNIBUS_DATE = "2026-12-02"

# The default arm's query shape: the same cast and predicate as its partial HNSW index.
DEFAULT_ARM_NEAREST = """
    select p.provision_id, e.embedding::vector(1536) <=> %(query)s::vector(1536) as distance
    from provision_embeddings e join provisions p on p.id = e.provision_row_id
    where e.model = 'qwen/qwen3-embedding-8b' and e.dims = 1536
      and p.document_id = %(document_id)s
    order by e.embedding::vector(1536) <=> %(query)s::vector(1536)
    limit 2
"""


def _vector(*weights: tuple[int, float], dims: int = DEFAULT_DIMS) -> str:
    """A pgvector text literal of `dims` zeros with the given (position, value) weights."""
    values = [0.0] * dims
    for position, value in weights:
        values[position] = value
    return "[" + ",".join(str(value) for value in values) + "]"


def _insert_document(
    db: psycopg.Connection,
    language: str,
    doc_key: str = "test-ai-act",
    doc_type: str = "law",
    law_version: str | None = "amended",
) -> int:
    row = db.execute(
        """
        insert into documents
          (doc_key, title, doc_type, status, law_version, language, source_url, sha256)
        values (%s, 'AI Act', %s, 'final', %s, %s, 'https://eur-lex.europa.eu/', %s)
        returning id
        """,
        (doc_key, doc_type, law_version, language, SHA256),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_provision(
    db: psycopg.Connection,
    document_id: int,
    language: str,
    provision_id: str,
    text: str,
    parent_id: int | None = None,
    valid: tuple[str, str | None] = ("2024-08-01", None),
) -> int:
    row = db.execute(
        """
        insert into provisions
          (provision_id, document_id, language, parent_id, heading, text, valid_from, valid_to)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (provision_id, document_id, language, parent_id, "Article 6", text, *valid),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_embedding(
    db: psycopg.Connection,
    provision_row_id: int,
    vector: str,
    model: str = DEFAULT_MODEL,
    dims: int = DEFAULT_DIMS,
) -> None:
    db.execute(
        """
        insert into provision_embeddings (provision_row_id, model, dims, embedding, content_sha256)
        select id, %s, %s, %s::vector, content_sha256 from provisions where id = %s
        """,
        (model, dims, vector, provision_row_id),
    )


def test_inserts_and_reads_a_provision(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en")
    parent = _insert_provision(db, document_id, "en", "art:6", "Classification rules.")
    child = _insert_provision(
        db, document_id, "en", "art:6:3", "An AI system shall not be high-risk.", parent
    )

    row = db.execute(
        """
        select p.provision_id, p.parent_id, p.text, p.source_example_id, d.law_version
        from provisions p join documents d on d.id = p.document_id
        where p.id = %s
        """,
        (child,),
    ).fetchone()

    assert row == ("art:6:3", parent, "An AI system shall not be high-risk.", None, "amended")


def test_keyword_query_uses_the_language_config(db: psycopg.Connection) -> None:
    english = _insert_document(db, "en")
    german = _insert_document(db, "de")
    _insert_provision(db, english, "en", "art:6:2", "Systems referred to in Annex III.")
    _insert_provision(db, german, "de", "art:6:2", "Die in Anhang III genannten Systeme.")
    _insert_provision(db, english, "en", "art:50:1", "Providers shall inform people.")

    def matches(config: str, query: str) -> list[tuple[str, str]]:
        return db.execute(
            """
            select provision_id, language from provisions
            where fts @@ websearch_to_tsquery(%s::regconfig, %s)
              and document_id = any(%s)
            order by ts_rank(fts, websearch_to_tsquery(%s::regconfig, %s)) desc
            """,
            (config, query, [english, german], config, query),
        ).fetchall()

    assert matches("english", "system annex") == [("art:6:2", "en")]
    assert matches("german", "genannte Anhang") == [("art:6:2", "de")]

    # Each row's tsvector was built with its own language's config (German drops "die" and "in").
    mismatched = db.execute(
        """
        select provision_id, language from provisions
        where document_id = any(%s)
          and fts <> to_tsvector(
            case language when 'de' then 'german' else 'english' end::regconfig,
            coalesce(heading, '') || ' ' || text)
        """,
        ([english, german],),
    ).fetchall()
    assert mismatched == []
    german_fts = db.execute(
        "select fts::text from provisions where document_id = %s", (german,)
    ).fetchone()
    assert german_fts is not None
    assert "'die'" not in german_fts[0]


def test_vector_query_returns_nearest_by_cosine(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en")
    near = _insert_provision(db, document_id, "en", "annex:III:4:a", "Recruitment systems.")
    far = _insert_provision(db, document_id, "en", "recital:53", "Narrow procedural tasks.")
    _insert_embedding(db, near, _vector((0, 1.0), (1, 0.2)))
    _insert_embedding(db, far, _vector((1, 1.0)))

    rows = db.execute(
        DEFAULT_ARM_NEAREST, {"query": _vector((0, 1.0)), "document_id": document_id}
    ).fetchall()

    assert [provision_id for provision_id, _ in rows] == ["annex:III:4:a", "recital:53"]
    assert rows[0][1] < rows[1][1]


def test_default_arm_query_can_use_its_partial_index(db: psycopg.Connection) -> None:
    db.execute("set local enable_seqscan = off")
    plan = db.execute(
        "explain " + DEFAULT_ARM_NEAREST, {"query": _vector((0, 1.0)), "document_id": 0}
    ).fetchall()
    assert "provision_embeddings_qwen3_1536_idx" in "\n".join(line for (line,) in plan)


def test_default_arm_index_matches_settings_dimensions(db: psycopg.Connection) -> None:
    row = db.execute(
        "select indexdef from pg_indexes where indexname = 'provision_embeddings_qwen3_1536_idx'"
    ).fetchone()
    assert row is not None
    dims = Settings.model_fields["embedding_dimensions"].default
    assert dims == DEFAULT_DIMS
    assert f"vector({dims})" in row[0]
    assert f"dims = {dims}" in row[0]


def test_embeddings_of_other_sizes_sit_beside_the_default(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en")
    provision = _insert_provision(db, document_id, "en", "art:3:1", "AI system means ...")
    _insert_embedding(db, provision, _vector((0, 1.0)))
    _insert_embedding(db, provision, _vector((0, 1.0), dims=1024), dims=1024)

    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        _insert_embedding(db, provision, _vector((0, 1.0), dims=1024), model="other", dims=1536)


def test_provision_language_must_match_its_document(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en")
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        _insert_provision(db, document_id, "de", "art:6:3", "Ein KI-System gilt nicht als ...")


def test_parent_must_be_in_the_same_document(db: psycopg.Connection) -> None:
    original = _insert_document(db, "en", law_version="original")
    amended = _insert_document(db, "en", law_version="amended")
    parent = _insert_provision(db, original, "en", "art:6", "Classification rules.")
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        _insert_provision(db, amended, "en", "art:6:3", "An AI system ...", parent)


def test_time_slices_may_follow_but_not_overlap(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en")
    _insert_provision(db, document_id, "en", "art:50:2", "Old.", valid=("2024-08-01", "2026-12-02"))
    _insert_provision(db, document_id, "en", "art:50:2", "New.", valid=("2026-12-02", None))

    with pytest.raises(psycopg.errors.ExclusionViolation), db.transaction():
        _insert_provision(db, document_id, "en", "art:50:2", "Clash.", valid=("2025-01-01", None))
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        _insert_provision(
            db, document_id, "en", "art:5:1", "Bad.", valid=("2025-01-01", "2025-01-01")
        )


def test_document_key_treats_null_law_versions_as_equal(db: psycopg.Connection) -> None:
    _insert_document(db, "en", doc_key="test-guide-art50", doc_type="guideline", law_version=None)
    _insert_document(db, "de", doc_key="test-guide-art50", doc_type="guideline", law_version=None)
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        _insert_document(
            db, "en", doc_key="test-guide-art50", doc_type="guideline", law_version=None
        )


def test_only_amending_acts_may_be_laws_without_a_version(db: psycopg.Connection) -> None:
    omnibus = db.execute(
        """
        insert into documents
          (doc_key, title, doc_type, is_amending, status, language, source_url, sha256)
        values ('test-omnibus', 'Digital Omnibus', 'law', true, 'final', 'en', 'https://x', %s)
        returning law_version
        """,
        (SHA256,),
    ).fetchone()
    assert omnibus == (None,)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        _insert_document(db, "en", doc_key="test-ai-act", law_version=None)


def test_reload_replaces_a_documents_provisions_in_one_transaction(
    db: psycopg.Connection,
) -> None:
    document_id = _insert_document(db, "en", doc_key="test-guide-art50", doc_type="guideline")
    parent = _insert_provision(db, document_id, "en", "guide:art50", "Draft.", valid=DRAFT_DATES)
    child = _insert_provision(
        db, document_id, "en", "guide:art50:1", "Draft point.", parent, valid=DRAFT_DATES
    )
    _insert_embedding(db, child, _vector((0, 1.0)))

    # C3's reload after a sha256 change: delete everything, insert the final text with new dates.
    with db.transaction():
        db.execute("delete from provisions where document_id = %s", (document_id,))
        parent = _insert_provision(db, document_id, "en", "guide:art50", "Final.")
        _insert_provision(db, document_id, "en", "guide:art50:1", "Final point.", parent)

    counts = db.execute(
        """
        select (select count(*) from provisions where document_id = %s),
               (select count(*) from provision_embeddings where provision_row_id = %s)
        """,
        (document_id, child),
    ).fetchone()
    assert counts == (2, 0)


def test_deleting_a_single_parent_fails(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en")
    parent = _insert_provision(db, document_id, "en", "art:6", "Classification rules.")
    _insert_provision(db, document_id, "en", "art:6:3", "An AI system ...", parent)
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        db.execute("delete from provisions where id = %s", (parent,))


def test_text_change_makes_the_stored_embedding_stale(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en")
    provision = _insert_provision(db, document_id, "en", "art:3:1", "AI system means ...")
    _insert_embedding(db, provision, _vector((0, 1.0)))

    def is_fresh() -> bool:
        row = db.execute(
            """
            select p.content_sha256 = e.content_sha256
            from provisions p join provision_embeddings e on e.provision_row_id = p.id
            where p.id = %s
            """,
            (provision,),
        ).fetchone()
        assert row is not None
        return row[0]

    assert is_fresh()
    db.execute(
        "update provisions set text = 'AI system means a machine-based system' where id = %s",
        (provision,),
    )
    assert not is_fresh()


def test_as_of_picks_the_slice_in_force(db: psycopg.Connection) -> None:
    amended = _insert_document(db, "en")
    _insert_provision(
        db, amended, "en", "art:50:2", "Before.", valid=(AI_ACT_IN_FORCE, OMNIBUS_DATE)
    )
    _insert_provision(db, amended, "en", "art:50:2", "After.", valid=(OMNIBUS_DATE, None))

    def text_as_of(as_of: str) -> str:
        row = db.execute(
            """
            select p.text from provisions p join documents d on d.id = p.document_id
            where p.provision_id = 'art:50:2' and p.language = 'en' and d.id = %s
              and d.law_version = 'amended' and not d.is_amending
              and daterange(p.valid_from, p.valid_to) @> %s::date
            """,
            (amended, as_of),
        ).fetchone()
        assert row is not None
        return row[0]

    assert text_as_of("2026-12-01") == "Before."
    assert text_as_of(OMNIBUS_DATE) == "After."


def test_data_api_roles_get_no_sequences_or_functions(db: psycopg.Connection) -> None:
    for role in ("anon", "authenticated"):
        row = db.execute(
            """
            select
              has_sequence_privilege(%(role)s, 'public.documents_id_seq', 'usage,select,update'),
              has_sequence_privilege(%(role)s, 'public.provisions_id_seq', 'usage,select,update'),
              has_function_privilege(
                %(role)s, 'public.provision_content_sha256(text, text)', 'execute')
            """,
            {"role": role},
        ).fetchone()
        assert row == (False, False, False), role


def test_corpus_tables_have_rls_and_no_data_api_grants(db: psycopg.Connection) -> None:
    for table in CORPUS_TABLES:
        row = db.execute(
            """
            select c.relrowsecurity,
                   has_table_privilege('anon', c.oid, 'select'),
                   has_table_privilege('authenticated', c.oid, 'select')
            from pg_class c where c.oid = %s::regclass
            """,
            (f"public.{table}",),
        ).fetchone()
        assert row == (True, False, False), table
