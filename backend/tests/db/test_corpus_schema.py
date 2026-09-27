"""The corpus migration (supabase/migrations/*_corpus.sql) against the local Supabase Postgres."""

import psycopg
import pytest

from aiact.settings import Settings

pytestmark = pytest.mark.db

CORPUS_TABLES = ("documents", "provisions", "provision_embeddings")
EMBEDDING_DIMS = 1536
TEST_MODEL = "test-model"


def _vector(*weights: tuple[int, float]) -> str:
    """A pgvector text literal of EMBEDDING_DIMS zeros with the given (position, value) weights."""
    values = [0.0] * EMBEDDING_DIMS
    for position, value in weights:
        values[position] = value
    return "[" + ",".join(str(value) for value in values) + "]"


def _insert_document(db: psycopg.Connection, language: str, sha_char: str) -> int:
    row = db.execute(
        """
        insert into documents
          (title, celex, doc_type, status, law_version, language, published_on, source_url, sha256)
        values ('AI Act', '32024R1689', 'law', 'final', 'oj-2024-1689', %s, '2024-07-12',
                'https://eur-lex.europa.eu/eli/reg/2024/1689/oj', %s)
        returning id
        """,
        (language, sha_char * 64),
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
) -> int:
    row = db.execute(
        """
        insert into provisions (provision_id, document_id, language, parent_id, heading, text)
        values (%s, %s, %s, %s, %s, %s)
        returning id
        """,
        (provision_id, document_id, language, parent_id, "Article 6", text),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_embedding(db: psycopg.Connection, provision_row_id: int, vector: str) -> None:
    db.execute(
        """
        insert into provision_embeddings (provision_row_id, model, dims, embedding)
        values (%s, %s, %s, %s::vector)
        """,
        (provision_row_id, TEST_MODEL, EMBEDDING_DIMS, vector),
    )


def test_inserts_and_reads_a_provision(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en", "a")
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

    assert row == ("art:6:3", parent, "An AI system shall not be high-risk.", None, "oj-2024-1689")


def test_keyword_query_uses_the_language_config(db: psycopg.Connection) -> None:
    english = _insert_document(db, "en", "b")
    german = _insert_document(db, "de", "c")
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
    document_id = _insert_document(db, "en", "d")
    near = _insert_provision(db, document_id, "en", "annex:III:4:a", "Recruitment systems.")
    far = _insert_provision(db, document_id, "en", "recital:53", "Narrow procedural tasks.")
    _insert_embedding(db, near, _vector((0, 1.0), (1, 0.2)))
    _insert_embedding(db, far, _vector((1, 1.0)))

    rows = db.execute(
        """
        select p.provision_id, e.embedding <=> %s::vector as distance
        from provision_embeddings e join provisions p on p.id = e.provision_row_id
        where e.model = %s and p.document_id = %s
        order by e.embedding <=> %s::vector
        limit 2
        """,
        (_vector((0, 1.0)), TEST_MODEL, document_id, _vector((0, 1.0))),
    ).fetchall()

    assert [provision_id for provision_id, _ in rows] == ["annex:III:4:a", "recital:53"]
    assert rows[0][1] < rows[1][1]


def test_embedding_column_matches_settings_dimensions(db: psycopg.Connection) -> None:
    row = db.execute(
        """
        select atttypmod from pg_attribute
        where attrelid = 'public.provision_embeddings'::regclass and attname = 'embedding'
        """
    ).fetchone()
    assert row is not None
    assert row[0] == Settings.model_fields["embedding_dimensions"].default == EMBEDDING_DIMS


def test_provision_language_must_match_its_document(db: psycopg.Connection) -> None:
    document_id = _insert_document(db, "en", "e")
    with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        _insert_provision(db, document_id, "de", "art:6:3", "Ein KI-System gilt nicht als ...")


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
