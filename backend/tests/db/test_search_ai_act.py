"""`search_ai_act` (aiact/retrieval/search.py) against the local Supabase Postgres.

The first tests load their own documents (`test-c6-*` doc_keys) inside the `db` fixture's
rolled-back transaction, with made-up words (zorblax, frobnic) the real corpus never uses and
3-dimensional vectors under a test model, so neither arm can reach the real corpus and the tests
run on an empty database (CI). The last tests read the loaded, embedded corpus and skip when it
isn't there; their query embeddings are recorded (tests/recordings/db/test_search_ai_act/).
"""

from dataclasses import replace
from datetime import date

import psycopg
import pytest
from psycopg import sql

from aiact.corpus.build import AI_ACT_IN_FORCE, DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.embed import ARMS, vector_literal
from aiact.corpus.load import load_all
from aiact.llm.embeddings import OpenRouterEmbeddings
from aiact.retrieval.search import SearchResults, prepare_search, search_ai_act
from aiact.schemas import DISCLAIMER_DE, DISCLAIMER_EN, Language, LawVersion
from aiact.settings import Settings

pytestmark = pytest.mark.db

TEST_MODEL = "test-c6/fake"
OMNIBUS_IN_FORCE = date(2026, 7, 27)
BEFORE_OMNIBUS = date(2025, 6, 1)
AFTER_OMNIBUS = date(2026, 9, 29)
GUIDE_PUBLISHED = date(2026, 5, 19)
HEADING = "Article 1 — Zorblax"


class FixedEmbedder:
    """Returns one given vector for any query, under the test model."""

    def __init__(self, vector: list[float], model: str = TEST_MODEL) -> None:
        self.vector = vector
        self.model = model
        self.dimensions = len(vector)

    def embed_query(self, text: str) -> list[float]:
        return self.vector


ORIGINAL = DocumentRow(
    doc_key="test-c6-act",
    title="Test AI Act (original)",
    celex=None,
    doc_type="law",
    is_amending=False,
    status="final",
    law_version="original",
    language="en",
    published_on=date(2024, 7, 12),
    in_force_from=AI_ACT_IN_FORCE,
    source_url="https://eur-lex.europa.eu/",
    sha256="a" * 64,
)
AMENDED = replace(
    ORIGINAL,
    doc_key="test-c6-act-consolidated",
    title="Test AI Act (consolidated)",
    status="consolidated",
    law_version="amended",
    published_on=OMNIBUS_IN_FORCE,
)
OMNIBUS = replace(AMENDED, doc_key="test-c6-omnibus", law_version=None, is_amending=True)
GUIDE = DocumentRow(
    doc_key="test-c6-guide",
    title="Test guideline",
    celex=None,
    doc_type="guideline",
    is_amending=False,
    status="draft",
    law_version=None,
    language="en",
    published_on=GUIDE_PUBLISHED,
    in_force_from=None,
    source_url="https://ec.europa.eu/",
    sha256="b" * 64,
)
CODE = replace(GUIDE, doc_key="test-c6-code", title="Test code", doc_type="code")

LOADS = (
    DocumentLoad(ORIGINAL, (
        ProvisionRow("art:1", None, None, HEADING, "Original zorblax duty.", AI_ACT_IN_FORCE),
        ProvisionRow("recital:1", None, None, None, "A recital on zorblax.", AI_ACT_IN_FORCE),
    )),
    DocumentLoad(AMENDED, (
        ProvisionRow("art:1", None, None, HEADING, "Old zorblax duty.", AI_ACT_IN_FORCE,
                     OMNIBUS_IN_FORCE),
        ProvisionRow("art:1", None, None, HEADING, "New zorblax duty.", OMNIBUS_IN_FORCE),
        ProvisionRow("art:2", None, None, "Article 2", "Frobnic rules: (a) a frobnic point.",
                     AI_ACT_IN_FORCE),
        ProvisionRow("art:2:a", "art:2", AI_ACT_IN_FORCE, "Article 2", "a frobnic point.",
                     AI_ACT_IN_FORCE),
    )),
    DocumentLoad(replace(AMENDED, language="de"), (
        ProvisionRow("art:1", None, None, "Artikel 1", "Pflichten für Quuxsysteme.",
                     AI_ACT_IN_FORCE),
    )),
    DocumentLoad(OMNIBUS, (
        ProvisionRow("art:1", None, None, None, "Omnibus zorblax amendment.", OMNIBUS_IN_FORCE),
    )),
    DocumentLoad(GUIDE, (
        ProvisionRow("guide:test-c6-guide:para:1", None, None, None, "Guidance on zorblax.",
                     GUIDE_PUBLISHED),
        ProvisionRow("guide:test-c6-guide:ex:001", None, None, None, "Held-out zorblax example.",
                     GUIDE_PUBLISHED, source_example_id="hr-ex-001", is_held_out=True),
        ProvisionRow("guide:test-c6-guide:ex:002", None, None, None, "Visible zorblax example.",
                     GUIDE_PUBLISHED, source_example_id="hr-ex-002"),
    )),
    DocumentLoad(CODE, (
        ProvisionRow("guide:test-c6-code:para:1", None, None, None, "A code on zorblax.",
                     GUIDE_PUBLISHED),
    )),
)  # fmt: skip

EMBED = """
    insert into provision_embeddings (provision_row_id, model, dims, embedding, content_sha256)
    select p.id, %(model)s, 3, %(vector)s::extensions.vector, p.content_sha256
    from provisions p join documents d on d.id = p.document_id
    where d.doc_key like 'test-c6-%%' and p.provision_id = %(provision_id)s
      and p.text = %(text)s
"""

ZORBLAX_NEW = [1.0, 0.0, 0.0]
HELD_OUT = [0.5, 0.5, 0.7]
VECTORS = {
    # (provision_id, text): vector. The code row has none, so only the keywords can find it.
    ("art:1", "Original zorblax duty."): [0.9, 0.1, 0.0],
    ("recital:1", "A recital on zorblax."): [0.0, 0.0, 1.0],
    ("art:1", "Old zorblax duty."): [0.9, 0.0, 0.1],
    ("art:1", "New zorblax duty."): ZORBLAX_NEW,
    ("art:2", "Frobnic rules: (a) a frobnic point."): [0.0, 1.0, 0.0],
    ("art:2:a", "a frobnic point."): [0.1, 0.9, 0.0],
    ("art:1", "Pflichten für Quuxsysteme."): [0.8, 0.2, 0.0],
    ("art:1", "Omnibus zorblax amendment."): ZORBLAX_NEW,
    ("guide:test-c6-guide:para:1", "Guidance on zorblax."): [0.7, 0.3, 0.0],
    ("guide:test-c6-guide:ex:001", "Held-out zorblax example."): HELD_OUT,
    ("guide:test-c6-guide:ex:002", "Visible zorblax example."): [0.6, 0.4, 0.0],
}


@pytest.fixture
def corpus(db: psycopg.Connection) -> psycopg.Connection:
    load_all(db, LOADS)
    for (provision_id, text), vector in VECTORS.items():
        params = {"model": TEST_MODEL, "vector": vector_literal(vector),
                  "provision_id": provision_id, "text": text}  # fmt: skip
        db.execute(EMBED, params)
    return db


def _search(
    connection: psycopg.Connection,
    query: str = "zorblax",
    vector: list[float] = ZORBLAX_NEW,
    **kwargs: object,
) -> SearchResults:
    return search_ai_act(
        query,
        embedder=FixedEmbedder(vector),
        connection=connection,
        **kwargs,  # pyright: ignore[reportArgumentType]
    )


def _found(results: SearchResults) -> list[tuple[str, str]]:
    """(doc_key, provision_id) of the test hits, best first."""
    return [(h.doc_key, h.provision_id) for h in results.hits if h.doc_key.startswith("test-c6-")]


def test_the_hybrid_ranking_fuses_both_arms(corpus: psycopg.Connection):
    results = _search(corpus, "new zorblax duty", as_of=AFTER_OMNIBUS)
    first = results.hits[0]
    assert (first.doc_key, first.provision_id, first.text) == (
        "test-c6-act-consolidated",
        "art:1",
        "New zorblax duty.",
    )
    assert first.vector_rank == 1
    assert first.keyword_rank is not None
    assert first.score == max(hit.score for hit in results.hits)
    code = next(h for h in results.hits if h.doc_key == "test-c6-code")
    assert (code.vector_rank, code.keyword_rank is not None) == (None, True)
    assert results.law_version is LawVersion.AMENDED
    assert results.as_of == AFTER_OMNIBUS
    assert results.disclaimer == DISCLAIMER_EN


def test_a_meaning_only_match_is_found_without_shared_words(corpus: psycopg.Connection):
    results = _search(corpus, "qwxyz vlorp", [0.0, 0.0, 1.0], as_of=AFTER_OMNIBUS)
    assert _found(results)[0] == ("test-c6-act", "recital:1")
    assert all(hit.keyword_rank is None for hit in results.hits)


def test_the_amended_text_and_guidance_by_default(corpus: psycopg.Connection):
    found = _found(_search(corpus, as_of=AFTER_OMNIBUS))
    assert ("test-c6-act-consolidated", "art:1") in found
    assert ("test-c6-guide", "guide:test-c6-guide:para:1") in found
    assert ("test-c6-act", "art:1") not in found
    assert ("test-c6-omnibus", "art:1") not in found


def test_recitals_come_from_the_original_text_under_either_version(corpus: psycopg.Connection):
    amended = _found(_search(corpus, as_of=AFTER_OMNIBUS))
    original = _found(_search(corpus, law_version="original"))
    assert ("test-c6-act", "recital:1") in amended
    assert ("test-c6-act", "recital:1") in original


def test_the_original_text_is_an_explicit_view(corpus: psycopg.Connection):
    results = _search(corpus, law_version=LawVersion.ORIGINAL)
    found = _found(results)
    assert ("test-c6-act", "art:1") in found
    assert ("test-c6-act-consolidated", "art:1") not in found
    assert ("test-c6-guide", "guide:test-c6-guide:para:1") in found
    assert ("test-c6-omnibus", "art:1") not in found
    assert (results.law_version, results.as_of) == (LawVersion.ORIGINAL, None)


def test_as_of_picks_the_slice_in_force(corpus: psycopg.Connection):
    def art_1_texts(on: date) -> list[str]:
        hits = _search(corpus, as_of=on).hits
        return [h.text for h in hits if (h.doc_key, h.provision_id) == (AMENDED.doc_key, "art:1")]

    assert art_1_texts(BEFORE_OMNIBUS) == ["Old zorblax duty."]
    assert art_1_texts(OMNIBUS_IN_FORCE) == ["New zorblax duty."]


def test_guidance_before_its_publication_is_not_found(corpus: psycopg.Connection):
    found = _found(_search(corpus, as_of=BEFORE_OMNIBUS))
    assert not [key for key, _ in found if key in {GUIDE.doc_key, CODE.doc_key}]


def test_a_held_out_example_is_never_returned_by_default(corpus: psycopg.Connection):
    """Decision 012: even a query copied from the example, with its exact vector, misses it."""
    held_out = ("test-c6-guide", "guide:test-c6-guide:ex:001")
    default = _search(corpus, "Held-out zorblax example.", HELD_OUT, as_of=AFTER_OMNIBUS)
    assert held_out not in _found(default)
    opted_in = _search(corpus, "Held-out zorblax example.", HELD_OUT, as_of=AFTER_OMNIBUS,
                       include_held_out=True)  # fmt: skip
    assert _found(opted_in)[0] == held_out


def test_the_exclude_filter_removes_the_ids_and_keeps_the_rest(corpus: psycopg.Connection):
    visible = ("test-c6-guide", "guide:test-c6-guide:ex:002")
    assert visible in _found(_search(corpus, as_of=AFTER_OMNIBUS))
    found = _found(_search(corpus, as_of=AFTER_OMNIBUS, exclude_source_example_ids=["hr-ex-002"]))
    assert visible not in found
    # Rows without a source example (law, guidance prose) are kept.
    assert ("test-c6-guide", "guide:test-c6-guide:para:1") in found
    assert ("test-c6-act-consolidated", "art:1") in found


def test_the_exclude_filter_also_applies_when_held_out_rows_are_opted_in(
    corpus: psycopg.Connection,
):
    found = _found(_search(corpus, as_of=AFTER_OMNIBUS, include_held_out=True,
                           exclude_source_example_ids=["hr-ex-001"]))  # fmt: skip
    assert ("test-c6-guide", "guide:test-c6-guide:ex:001") not in found
    assert ("test-c6-guide", "guide:test-c6-guide:ex:002") in found


def test_doc_types_filter(corpus: psycopg.Connection):
    found = _found(_search(corpus, as_of=AFTER_OMNIBUS, doc_types={"code"}))
    assert found == [("test-c6-code", "guide:test-c6-code:para:1")]


def test_a_german_query_matches_through_prefixes(corpus: psycopg.Connection):
    """German stems 'Quuxsystem' to quuxsyst but 'Quuxsysteme' to quuxsystem: the prefix query
    still matches. The vector points away from the row, so only the keywords can find it."""
    results = _search(corpus, "Quuxsystem", [0.0, 0.0, 1.0], language="de", as_of=AFTER_OMNIBUS)
    german = [h for h in results.hits if h.doc_key == AMENDED.doc_key]
    assert [(h.provision_id, h.language) for h in german] == [("art:1", Language.DE)]
    assert german[0].keyword_rank == 1
    assert all(h.language is Language.DE for h in results.hits)
    assert results.disclaimer == DISCLAIMER_DE


def test_a_parent_gives_way_to_its_child(corpus: psycopg.Connection):
    found = _found(_search(corpus, "frobnic point", [0.0, 1.0, 0.0], as_of=AFTER_OMNIBUS))
    assert found[0] == ("test-c6-act-consolidated", "art:2:a")
    assert ("test-c6-act-consolidated", "art:2") not in found


def test_a_stale_vector_is_never_ranked(corpus: psycopg.Connection):
    corpus.execute(
        """update provision_embeddings e set content_sha256 = %s from provisions p, documents d
           where e.provision_row_id = p.id and p.document_id = d.id and e.model = %s
             and d.doc_key = 'test-c6-guide' and p.provision_id = 'guide:test-c6-guide:para:1'""",
        ("0" * 64, TEST_MODEL),
    )
    guide = next(
        h
        for h in _search(corpus, as_of=AFTER_OMNIBUS).hits
        if h.provision_id == "guide:test-c6-guide:para:1"
    )
    assert (guide.vector_rank, guide.keyword_rank is not None) == (None, True)


def test_the_limit_caps_the_hits(corpus: psycopg.Connection):
    assert len(_search(corpus, as_of=AFTER_OMNIBUS, limit=2).hits) == 2


QWEN3 = ARMS["qwen3"]
DIMS = 1536
TOP = 5


def test_the_meaning_arm_can_use_the_partial_hnsw_index(db: psycopg.Connection):
    """The statement keeps the index's cast and predicate (decision 009). At about 9,000 rows the
    planner prefers an exact scan, so sorting is switched off to show the index path exists."""
    embedder = FixedEmbedder([1.0] + [0.0] * (DIMS - 1), QWEN3.model)
    params, statement = prepare_search(
        "credit score", Language.EN, LawVersion.AMENDED, None, None, (), False, TOP, embedder
    )
    with db.transaction():
        db.execute("set local enable_sort = off")
        plan = "\n".join(row[0] for row in db.execute(sql.SQL("explain ") + statement, params))
    assert "provision_embeddings_qwen3_1536_idx" in plan


# --- The loaded, embedded corpus (skipped when `aiact corpus embed` hasn't run) ---------------


def _require_embedded_corpus(db: psycopg.Connection) -> None:
    row = db.execute(
        "select count(*) from provision_embeddings where model = %s and dims = %s",
        (QWEN3.model, DIMS),
    ).fetchone()
    if row is None or row[0] < 1000:
        pytest.skip("the corpus isn't embedded; run `aiact corpus load` and `aiact corpus embed`")


@pytest.fixture
def qwen3(openrouter_settings: Settings) -> OpenRouterEmbeddings:
    return OpenRouterEmbeddings(
        model=QWEN3.model, provider=QWEN3.provider, dimensions=DIMS, settings=openrouter_settings
    )


def _top(results: SearchResults) -> list[str]:
    return [f"{h.doc_key} {h.provision_id}" for h in results.hits]


@pytest.mark.vcr
def test_a_softly_worded_tenant_query_finds_annex_iii_5b(
    db: psycopg.Connection, qwen3: OpenRouterEmbeddings
):
    _require_embedded_corpus(db)
    query = (
        "We run a small letting agency. Our app looks at a flat applicant's bank statements and "
        "payslips and tells the landlord how likely they are to keep paying the rent."
    )
    results = search_ai_act(query, as_of=AFTER_OMNIBUS, limit=TOP, embedder=qwen3, connection=db)
    assert "ai-act-consolidated annex:III:5:b" in _top(results), _top(results)


@pytest.mark.vcr
def test_a_german_query_finds_annex_iii_5b(db: psycopg.Connection, qwen3: OpenRouterEmbeddings):
    """None of the query's telling words (Miete, Kontoauszug) occur in the German corpus, so the
    meaning arm carries it (5(b) ranked 5th when recorded); the check allows the default 10."""
    _require_embedded_corpus(db)
    query = (
        "Unsere Software prüft anhand von Kontoauszügen, ob Mietinteressenten die Miete "
        "zuverlässig zahlen können, und gibt dem Vermieter eine Einschätzung."
    )
    results = search_ai_act(query, "de", as_of=AFTER_OMNIBUS, embedder=qwen3, connection=db)
    assert "ai-act-consolidated annex:III:5:b" in _top(results), _top(results)
    assert {h.language for h in results.hits} == {Language.DE}
    assert results.disclaimer == DISCLAIMER_DE


def test_a_default_search_never_returns_a_loaded_pile_b_row(db: psycopg.Connection):
    """Decision 012 on the real corpus: for every held-out example, a query copied from its text
    with its own stored vector returns no held-out row; opted in, the example is in the top 3."""
    _require_embedded_corpus(db)
    examples = db.execute(
        """select p.provision_id, p.text, e.embedding::text
           from provisions p join provision_embeddings e on e.provision_row_id = p.id
           where p.is_held_out and e.model = %s and e.dims = %s
             and e.content_sha256 = p.content_sha256
           order by p.provision_id""",
        (QWEN3.model, DIMS),
    ).fetchall()
    assert examples, "the loaded corpus has no embedded held-out rows"
    held_out = {
        row[0] for row in db.execute("select provision_id from provisions where is_held_out")
    }
    for provision_id, text, embedding in examples:
        embedder = FixedEmbedder([float(x) for x in embedding.strip("[]").split(",")], QWEN3.model)
        default = search_ai_act(text, embedder=embedder, connection=db, limit=50)
        assert not held_out & {h.provision_id for h in default.hits}, provision_id
    provision_id, text, embedding = examples[0]
    embedder = FixedEmbedder([float(x) for x in embedding.strip("[]").split(",")], QWEN3.model)
    opted_in = search_ai_act(text, embedder=embedder, connection=db, include_held_out=True)
    assert provision_id in [h.provision_id for h in opted_in.hits[:3]]
