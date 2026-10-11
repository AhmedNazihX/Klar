"""`search_ai_act` (aiact/retrieval/search.py) against the local Supabase Postgres.

The first tests load their own documents (`test-c6-*` doc_keys) inside the `db` fixture's
rolled-back transaction, with made-up words (zorblax, frobnic) the real corpus never uses and
3-dimensional vectors under a test model, so neither arm can reach the real corpus and the tests
run on an empty database (CI). The last tests read the loaded, embedded corpus and skip when it
isn't there; their query embeddings are recorded (tests/recordings/db/test_search_ai_act/).
"""

from dataclasses import replace
from datetime import date
from typing import Any

import psycopg
import pytest
from psycopg import sql

from aiact.corpus.build import AI_ACT_IN_FORCE, DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.embed import ARMS, vector_literal
from aiact.corpus.load import load_all
from aiact.llm.embeddings import OpenRouterEmbeddings
from aiact.retrieval import search as search_module
from aiact.retrieval.search import (
    CANDIDATES,
    ENGINE_TUNING,
    SearchResults,
    SearchTuning,
    prepare_search,
    search_ai_act,
)
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
        # Three levels; the middle one has no vector and no query word, so it is never a hit.
        ProvisionRow("art:3", None, None, "Article 3", "Plimbo rules: 1. (a) a plimbo point.",
                     AI_ACT_IN_FORCE),
        ProvisionRow("art:3:1", "art:3", AI_ACT_IN_FORCE, "Article 3", "1. (a) point.",
                     AI_ACT_IN_FORCE),
        ProvisionRow("art:3:1:a", "art:3:1", AI_ACT_IN_FORCE, "Article 3", "a plimbo point.",
                     AI_ACT_IN_FORCE),
        # Word statistics count units, not slices: snorfle is in 2 units, quibbet in 1 unit with
        # 2 slices. The snorfle rows come first, so a tie would rank them first.
        ProvisionRow("art:5", None, None, "Article 5", "Snorfle.", AI_ACT_IN_FORCE),
        ProvisionRow("art:6", None, None, "Article 6", "Snorfle.", AI_ACT_IN_FORCE),
        ProvisionRow("art:4", None, None, "Article 4", "Old quibbet.", AI_ACT_IN_FORCE,
                     OMNIBUS_IN_FORCE),
        ProvisionRow("art:4", None, None, "Article 4", "New quibbet.", OMNIBUS_IN_FORCE),
        # An annex with one point: the annex row holds the point's text (C1), and search ranks
        # the point, never the annex (X1b), unless the tuning lets it.
        ProvisionRow("annex:IX", None, None, "Annex IX", "Snorkwhip areas: 1. A snorkwhip point.",
                     AI_ACT_IN_FORCE),
        ProvisionRow("annex:IX:1", "annex:IX", AI_ACT_IN_FORCE, "Annex IX", "A snorkwhip point.",
                     AI_ACT_IN_FORCE),
    )),
    DocumentLoad(replace(AMENDED, language="de"), (
        ProvisionRow("art:1", None, None, "Artikel 1", "Pflichten für Quuxsysteme.",
                     AI_ACT_IN_FORCE),
    )),
    DocumentLoad(OMNIBUS, (
        ProvisionRow("art:1", None, None, None, "Omnibus zorblax amendment.", OMNIBUS_IN_FORCE),
        ProvisionRow("art:2", None, None, None, "Omnibus brastle.", OMNIBUS_IN_FORCE),
    )),
    DocumentLoad(GUIDE, (
        ProvisionRow("guide:test-c6-guide:para:1", None, None, None, "Guidance on zorblax.",
                     GUIDE_PUBLISHED),
        ProvisionRow("guide:test-c6-guide:ex:001", None, None, None, "Held-out zorblax example.",
                     GUIDE_PUBLISHED, source_example_id="hr-ex-001", is_held_out=True),
        ProvisionRow("guide:test-c6-guide:ex:002", None, None, None, "Visible zorblax example.",
                     GUIDE_PUBLISHED, source_example_id="hr-ex-002"),
        ProvisionRow("guide:test-c6-guide:para:2", None, None, None, "The zorbapp.",
                     GUIDE_PUBLISHED),
        ProvisionRow("guide:test-c6-guide:para:3", None, None, None, "Zorbapplications.",
                     GUIDE_PUBLISHED),
        # Word statistics: visible, glimmet is in 2 rows and brastle in 1; the held-out rows and
        # the Omnibus would make brastle the commoner word if they were counted.
        ProvisionRow("guide:test-c6-guide:para:4", None, None, None, "Glimmet.", GUIDE_PUBLISHED),
        ProvisionRow("guide:test-c6-guide:para:5", None, None, None, "The glimmet.",
                     GUIDE_PUBLISHED),
        ProvisionRow("guide:test-c6-guide:para:6", None, None, None, "Brastle.", GUIDE_PUBLISHED),
        *(
            ProvisionRow(f"guide:test-c6-guide:ex:10{n}", None, None, None, f"Brastle {n}.",
                         GUIDE_PUBLISHED, source_example_id=f"hr-ex-10{n}", is_held_out=True)
            for n in range(1, 4)
        ),
        ProvisionRow("guide:test-c6-guide:ex:104", None, None, None, "A voiceprintzz example.",
                     GUIDE_PUBLISHED, source_example_id="hr-ex-104", is_held_out=True),
    )),
    DocumentLoad(CODE, (
        ProvisionRow("guide:test-c6-code:para:1", None, None, None, "A code on zorblax.",
                     GUIDE_PUBLISHED),
        # Four words no other row has and no vector: a strong keyword-only match (C8), also in
        # an empty database (4 x ln(about 20 units) is above FIXTURE_MIN_KEYWORD_IDF).
        ProvisionRow("guide:test-c6-code:para:2", None, None, None,
                     "Quorvex klimbat drossel wuffling.", GUIDE_PUBLISHED),
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
    ("art:3", "Plimbo rules: 1. (a) a plimbo point."): [0.0, -0.9, -0.1],
    ("art:3:1:a", "a plimbo point."): [0.0, -1.0, 0.0],
    ("annex:IX", "Snorkwhip areas: 1. A snorkwhip point."): [-0.6, 0.0, 0.8],
    ("annex:IX:1", "A snorkwhip point."): [-0.8, 0.0, 0.6],
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
    """No cut-off unless a test asks for one, whatever SEARCH_MAX_DISTANCE is set to."""
    return search_ai_act(
        query,
        embedder=FixedEmbedder(vector),
        connection=connection,
        **{"limit": CANDIDATES, "max_distance": None, **kwargs},  # pyright: ignore[reportArgumentType]
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


def test_doc_keys_limits_both_arms_to_those_documents(corpus: psycopg.Connection):
    # Every row of the guideline, from either arm (para:1 by meaning and keyword, para:3 by
    # keyword only), and nothing of the Act or the code that the unfiltered search finds.
    everything = _found(_search(corpus, as_of=AFTER_OMNIBUS))
    assert {key for key, _ in everything} > {GUIDE.doc_key}
    found = _found(_search(corpus, as_of=AFTER_OMNIBUS, doc_keys={GUIDE.doc_key}))
    assert found
    assert {key for key, _ in found} == {GUIDE.doc_key}
    assert ("test-c6-guide", "guide:test-c6-guide:ex:001") not in found  # still held out


def test_doc_keys_keeps_the_held_out_opt_in_and_the_exclude_filter(corpus: psycopg.Connection):
    results = _search(
        corpus,
        as_of=AFTER_OMNIBUS,
        doc_keys={GUIDE.doc_key},
        include_held_out=True,
        exclude_source_example_ids=["hr-ex-002"],
    )
    found = _found(results)
    assert ("test-c6-guide", "guide:test-c6-guide:ex:001") in found
    assert ("test-c6-guide", "guide:test-c6-guide:ex:002") not in found


def test_a_german_query_matches_through_prefixes(corpus: psycopg.Connection):
    """German stems 'Quuxsystem' to quuxsyst but 'Quuxsysteme' to quuxsystem: the prefix query
    still matches. The vector points away from the row, so only the keywords can find it."""
    results = _search(corpus, "Quuxsystem", [0.0, 0.0, 1.0], language="de", as_of=AFTER_OMNIBUS)
    german = [h for h in results.hits if h.doc_key == AMENDED.doc_key]
    assert [(h.provision_id, h.language) for h in german] == [("art:1", Language.DE)]
    assert german[0].keyword_rank == 1
    assert all(h.language is Language.DE for h in results.hits)
    assert results.disclaimer == DISCLAIMER_DE


NO_WORDS = "qwxyz vlorp"
"""A query no row shares a word with, so only the meaning arm ranks."""


def test_the_better_ranked_of_parent_and_child_wins(corpus: psycopg.Connection):
    nearer_child = _found(_search(corpus, NO_WORDS, [0.1, 0.9, 0.0], as_of=AFTER_OMNIBUS))
    nearer_parent = _found(_search(corpus, NO_WORDS, [0.0, 1.0, 0.0], as_of=AFTER_OMNIBUS))
    assert nearer_child[0] == (AMENDED.doc_key, "art:2:a")
    assert (AMENDED.doc_key, "art:2") not in nearer_child
    assert nearer_parent[0] == (AMENDED.doc_key, "art:2")
    assert (AMENDED.doc_key, "art:2:a") not in nearer_parent


def test_a_parent_is_kept_when_its_child_is_beyond_the_limit(corpus: psycopg.Connection):
    found = _found(_search(corpus, NO_WORDS, [0.0, 1.0, 0.0], as_of=AFTER_OMNIBUS, limit=1))
    assert found == [(AMENDED.doc_key, "art:2")]


def test_a_grandparent_and_grandchild_overlap_without_the_middle_level(
    corpus: psycopg.Connection,
):
    found = _found(_search(corpus, NO_WORDS, [0.0, -1.0, 0.0], as_of=AFTER_OMNIBUS))
    plimbo = [pid for key, pid in found if key == AMENDED.doc_key and pid.startswith("art:3")]
    assert plimbo == ["art:3:1:a"]


def test_english_words_match_exactly_not_as_prefixes(corpus: psycopg.Connection):
    hits = _search(corpus, "zorbapp", [0.0, 0.0, 1.0], as_of=AFTER_OMNIBUS).hits
    keyword = {h.provision_id for h in hits if h.keyword_rank is not None}
    assert "guide:test-c6-guide:para:2" in keyword
    assert "guide:test-c6-guide:para:3" not in keyword


def test_word_statistics_ignore_held_out_rows_and_the_omnibus(corpus: psycopg.Connection):
    """The rarer visible word ranks first: brastle (1 visible row) over glimmet (2)."""
    hits = _search(corpus, "glimmet brastle", [0.0, 0.0, 1.0], as_of=AFTER_OMNIBUS).hits
    rank = {h.provision_id: h.keyword_rank for h in hits}
    brastle = rank["guide:test-c6-guide:para:6"]
    glimmet = rank.get("guide:test-c6-guide:para:4")
    assert brastle is not None
    assert glimmet is None or brastle < glimmet


def test_word_statistics_count_each_unit_once(corpus: psycopg.Connection):
    hits = _search(corpus, "quibbet snorfle", [0.0, 0.0, 1.0], as_of=AFTER_OMNIBUS).hits
    rank = {h.provision_id: h.keyword_rank for h in hits if h.doc_key == AMENDED.doc_key}
    quibbet = rank["art:4"]
    assert quibbet is not None
    assert all(r is not None and quibbet < r for r in (rank["art:5"], rank["art:6"]))


def test_a_word_only_held_out_rows_use_finds_them_only_when_opted_in(corpus: psycopg.Connection):
    """The statistics never count held-out rows, but such a word still gets a weight, so the gap
    run (V8) can find an example by its own words."""
    example = "guide:test-c6-guide:ex:104"
    default = _search(corpus, "voiceprintzz", [0.0, 0.0, 1.0], as_of=AFTER_OMNIBUS)
    assert example not in {h.provision_id for h in default.hits}
    assert all(h.keyword_rank is None for h in default.hits)
    opted_in = _search(corpus, "voiceprintzz", [0.0, 0.0, 1.0], as_of=AFTER_OMNIBUS,
                       include_held_out=True)  # fmt: skip
    keyword = [h.provision_id for h in opted_in.hits if h.keyword_rank is not None]
    assert keyword == [example]


TIE = replace(AMENDED, doc_key="test-c6-tie", title="Test AI Act (ties)", sha256="c" * 64)
TIE_WORDS = ("zorvikan", "blintozar", "quaffelix", "drumbleck", "snivvetor", "plorkanim",
             "gribbolux", "fenwhistal")  # fmt: skip
"""Made-up words; the nth is in `multiplier` * n + 1 filler rows, so each has its own IDF."""
TIED_IDS = ("art:7", "art:7:1")


def _tie_load(multiplier: int) -> DocumentLoad:
    """An article and its only paragraph with the same words, plus filler rows that give each
    word a different IDF."""
    text = " ".join(TIE_WORDS) + "."
    article = ProvisionRow("art:7", None, None, "Article 7", text, AI_ACT_IN_FORCE)
    paragraph = ProvisionRow("art:7:1", "art:7", AI_ACT_IN_FORCE, "Article 7", text,
                             AI_ACT_IN_FORCE)  # fmt: skip
    fillers = [
        (word, number) for n, word in enumerate(TIE_WORDS) for number in range(multiplier * n + 1)
    ]
    rows = [
        ProvisionRow(f"art:{30 + i}", None, None, f"Article {30 + i}", f"{word} filler {number}.",
                     AI_ACT_IN_FORCE)
        for i, (word, number) in enumerate(fillers)
    ]  # fmt: skip
    return DocumentLoad(TIE, (article, paragraph, *rows))


@pytest.mark.parametrize("multiplier", [1, 3, 5])
def test_a_keyword_tie_goes_to_the_lower_id(db: psycopg.Connection, multiplier: int):
    """Two rows with the same words have the same IDF sum, but a float sum's last bits depend on
    the order it adds the words in, so ranked on the exact float the paragraph can overtake its
    article (F11, between the local and hosted databases). Ranked on the rounded sum, the lower
    id (the article, loaded first) wins.

    Which IDFs flip an unrounded sum depends on the whole corpus's word statistics, so the three
    multipliers are measured, not arbitrary: without the rounding, multiplier 3 fails on the
    loaded local corpus (9,083 provisions) and 1 and 5 fail on an empty one (CI), the same on
    every run and under both a planner-chosen and a forced sorted-groups plan."""
    load_all(db, (_tie_load(multiplier),))
    hits = _search(db, " ".join(TIE_WORDS), [1.0, 0.0, 0.0], doc_keys=[TIE.doc_key]).hits
    tied = [(h.provision_id, h.keyword_rank) for h in hits if h.provision_id in TIED_IDS]
    assert tied == [("art:7", 1)]


def test_the_iterative_scan_setting_does_not_leak(db: psycopg.Connection):
    """Inside a caller's transaction the search runs in a savepoint; its setting must not
    outlive it."""
    db.execute("set local hnsw.iterative_scan = strict_order")
    search_ai_act(NO_WORDS, embedder=FixedEmbedder([1.0, 0.0, 0.0]), connection=db,
                  max_distance=None)  # fmt: skip
    row = db.execute("select current_setting('hnsw.iterative_scan')").fetchone()
    assert row == ("strict_order",)
    assert db.execute("select current_setting('enable_indexscan')").fetchone() == ("on",)


def test_the_search_ranks_by_an_exact_scan(db: psycopg.Connection, monkeypatch):
    """The approximate HNSW index can rank a parent and its paragraph differently as table
    statistics change, so the search runs with plain index scans off (exact, the same each run)."""
    seen: list[object] = []
    real_execute = psycopg.Cursor.execute

    def spy(self: psycopg.Cursor, query: Any, params: Any = None, **kwargs: Any) -> Any:
        if isinstance(query, sql.Composed) and "vector_hits" in query.as_string(db):
            row: Any = real_execute(
                self, "select current_setting('enable_indexscan') as v"
            ).fetchone()
            seen.append(row["v"])
        return real_execute(self, query, params, **kwargs)

    monkeypatch.setattr(psycopg.Cursor, "execute", spy)
    search_ai_act(NO_WORDS, embedder=FixedEmbedder([1.0, 0.0, 0.0]), connection=db,
                  max_distance=None)  # fmt: skip
    assert seen == ["off"]


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


# --- Relevance: similarity, keyword IDF, the cut-off and `found` (C8) -------------------------

OFF_TOPIC = [0.0, 0.0, -1.0]
"""Points away from every visible row: the nearest (art:3) is at cosine distance 0.89."""
CUT_OFF = 0.5
FIXTURE_MIN_KEYWORD_IDF = 9.0
"""A keyword bar the fixture's four rare words clear in an empty database (C8's first value)."""


def test_hits_carry_the_similarity_and_the_keyword_idf(corpus: psycopg.Connection):
    hits = _search(corpus, "new zorblax duty", as_of=AFTER_OMNIBUS).hits
    first = hits[0]
    assert first.similarity == pytest.approx(1.0)
    assert first.keyword_idf is not None and first.keyword_idf > 0
    code = next(h for h in hits if h.doc_key == "test-c6-code")
    assert (code.similarity, code.keyword_idf is not None) == (None, True)
    meaning_only = _search(corpus, NO_WORDS, [0.0, 0.0, 1.0], as_of=AFTER_OMNIBUS).hits
    assert meaning_only[0].similarity == pytest.approx(1.0)
    assert all(h.keyword_idf is None for h in meaning_only)


def test_the_cut_off_leaves_an_off_topic_query_with_nothing(corpus: psycopg.Connection):
    uncut = _search(corpus, NO_WORDS, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=None)
    assert uncut.hits and uncut.found  # without a cut-off every query gets hits
    cut = _search(corpus, NO_WORDS, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=CUT_OFF)
    assert [h for h in cut.hits if h.similarity is not None] == []
    assert (cut.found, cut.max_distance) == (False, CUT_OFF)


def test_a_matching_query_stays_found_under_the_cut_off(corpus: psycopg.Connection):
    results = _search(corpus, as_of=AFTER_OMNIBUS, max_distance=CUT_OFF)
    assert results.found
    assert results.hits[0].provision_id == "art:1"
    similarities = [h.similarity for h in results.hits if h.similarity is not None]
    assert similarities and min(similarities) >= 1 - CUT_OFF
    # The recital is at distance 1: the meaning arm drops it, the keywords still find it.
    recital = next(h for h in results.hits if h.provision_id == "recital:1")
    assert (recital.similarity, recital.vector_rank, recital.keyword_rank is not None) == (
        None,
        None,
        True,
    )


def test_a_strong_keyword_only_match_stays_found(
    corpus: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
):
    """The rule, not the calibrated value (X1b's 24, pinned in test_settings): in an empty
    database the four fixture words reach only about 4 x ln(20), so the bar is set below that."""
    bar = Settings(_env_file=None, search_min_keyword_idf=FIXTURE_MIN_KEYWORD_IDF)  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr(search_module, "get_settings", lambda: bar)
    results = _search(corpus, "quorvex klimbat drossel wuffling", OFF_TOPIC, as_of=AFTER_OMNIBUS,
                      max_distance=CUT_OFF)  # fmt: skip
    assert [h.provision_id for h in results.hits] == ["guide:test-c6-code:para:2"]
    idf = results.hits[0].keyword_idf
    assert idf is not None and idf >= FIXTURE_MIN_KEYWORD_IDF
    assert results.found


def test_the_c6_searches_ignore_a_set_cut_off(
    corpus: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
):
    """The C6 tests pass `max_distance=None`, so a SEARCH_MAX_DISTANCE in .env can't change
    them; an omitted `max_distance` still takes the setting."""
    tight = Settings(_env_file=None, search_max_distance=0.0)  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr(search_module, "get_settings", lambda: tight)
    uncut = _search(corpus, NO_WORDS, OFF_TOPIC, as_of=AFTER_OMNIBUS)
    assert uncut.max_distance is None
    assert [h for h in uncut.hits if h.similarity is not None]
    omitted = search_ai_act(NO_WORDS, as_of=AFTER_OMNIBUS, embedder=FixedEmbedder(OFF_TOPIC),
                            connection=corpus)  # fmt: skip
    assert (omitted.max_distance, omitted.found) == (0.0, False)


def test_the_cut_off_filters_inside_the_vector_arm_s_sql(db: psycopg.Connection):
    """The plan filters the materialized nearest rows by distance; no row reaches Python first."""
    params, statement = prepare_search(
        NO_WORDS, Language.EN, LawVersion.AMENDED, None, None, (), False, TOP,
        FixedEmbedder(OFF_TOPIC), max_distance=CUT_OFF,
    )  # fmt: skip
    plan = [row[0] for row in db.execute(sql.SQL("explain ") + statement, params)]
    scan = next(i for i, line in enumerate(plan) if "CTE Scan on vector_hits" in line)
    assert "distance <=" in plan[scan + 1], plan[scan : scan + 2]


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
    results = search_ai_act(query, as_of=AFTER_OMNIBUS, limit=TOP, embedder=qwen3, connection=db,
                            max_distance=None)  # fmt: skip
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
    results = search_ai_act(query, "de", as_of=AFTER_OMNIBUS, embedder=qwen3, connection=db,
                            max_distance=None)  # fmt: skip
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
        default = search_ai_act(text, embedder=embedder, connection=db, limit=50,
                                max_distance=None)  # fmt: skip
        assert not held_out & {h.provision_id for h in default.hits}, provision_id
    provision_id, text, embedding = examples[0]
    embedder = FixedEmbedder([float(x) for x in embedding.strip("[]").split(",")], QWEN3.model)
    opted_in = search_ai_act(text, embedder=embedder, connection=db, include_held_out=True,
                             max_distance=None)  # fmt: skip
    assert provision_id in [h.provision_id for h in opted_in.hits[:3]]


# --- X1b: annex points over the rows that hold them; exact references ----------------------

SNORK_AREA = [-0.6, 0.0, 0.8]
"""The annex row's own vector: the point (cosine 0.96) is the nearest row once it is skipped."""


def test_an_annex_point_ranks_and_the_annex_that_holds_it_does_not(corpus: psycopg.Connection):
    found = _found(_search(corpus, NO_WORDS, SNORK_AREA, as_of=AFTER_OMNIBUS))
    assert found[0] == (AMENDED.doc_key, "annex:IX:1")
    assert (AMENDED.doc_key, "annex:IX") not in found
    containers = SearchTuning(skips_annex_containers=False)
    with_containers = _found(_search(corpus, NO_WORDS, SNORK_AREA, as_of=AFTER_OMNIBUS,
                                     tuning=containers))  # fmt: skip
    assert with_containers[0] == (AMENDED.doc_key, "annex:IX")
    assert (AMENDED.doc_key, "annex:IX:1") not in with_containers  # inside the annex row


def test_the_keyword_arm_skips_the_annex_row_too(corpus: psycopg.Connection):
    """'areas' is only in the annex row, so with the meaning arm cut (`max_distance=0`) the
    keywords alone would rank the annex row first and hide its point; skipped, the point is the
    keyword arm's first row."""
    query = "snorkwhip areas"
    skipped = _search(corpus, query, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0)
    first = skipped.hits[0]
    assert (first.doc_key, first.provision_id, first.keyword_rank) == (
        AMENDED.doc_key,
        "annex:IX:1",
        1,
    )
    assert (AMENDED.doc_key, "annex:IX") not in _found(skipped)
    containers = SearchTuning(skips_annex_containers=False)
    kept = _search(corpus, query, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0,
                   tuning=containers)  # fmt: skip
    first = kept.hits[0]
    assert (first.provision_id, first.keyword_rank) == ("annex:IX", 1)
    assert (AMENDED.doc_key, "annex:IX:1") not in _found(kept)  # inside the annex row


def test_an_article_without_points_is_no_container(corpus: psycopg.Connection):
    """The rule is for annexes: an article with a paragraph under it still ranks (art:2)."""
    found = _found(_search(corpus, NO_WORDS, [0.0, 1.0, 0.0], as_of=AFTER_OMNIBUS))
    assert found[0] == (AMENDED.doc_key, "art:2")


def _named(results: SearchResults) -> list[tuple[str, int | None]]:
    """(provision_id, reference_rank) of the named test rows, best first."""
    return [
        (h.provision_id, h.reference_rank)
        for h in results.hits
        if h.doc_key.startswith("test-c6-") and h.reference_rank is not None
    ]


def test_a_named_provision_comes_first_and_is_found_past_any_cut_off(corpus: psycopg.Connection):
    results = _search(corpus, "What does Article 2 say?", OFF_TOPIC, as_of=AFTER_OMNIBUS,
                      max_distance=0.0)  # fmt: skip
    assert _named(results) == [("art:2", 1)]
    assert results.hits[0].reference_rank == 1
    named = next(h for h in results.hits if h.doc_key == AMENDED.doc_key)
    assert (named.provision_id, named.similarity) == ("art:2", None)
    assert results.found is True
    unnamed = _search(corpus, NO_WORDS, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0)
    assert unnamed.found is False


def test_named_provisions_keep_the_order_named(corpus: psycopg.Connection):
    results = _search(corpus, "Article 6 and Art. 5", OFF_TOPIC, as_of=AFTER_OMNIBUS)
    assert _named(results) == [("art:6", 1), ("art:5", 2)]
    assert results.hits[0].reference_rank == 1


def test_a_named_provision_is_read_from_the_version_and_date_asked(corpus: psycopg.Connection):
    after = _search(corpus, "Article 4", OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0)
    before = _search(corpus, "Article 4", OFF_TOPIC, as_of=BEFORE_OMNIBUS, max_distance=0.0)
    original = _search(corpus, "Article 4", OFF_TOPIC, law_version="original", max_distance=0.0)
    texts = [
        [h.text for h in r.hits if h.doc_key.startswith("test-c6-") and h.reference_rank]
        for r in (after, before, original)
    ]
    assert texts == [["New quibbet."], ["Old quibbet."], []]  # the original text has no art:4


def test_a_whole_annex_named_is_not_pinned(corpus: psycopg.Connection):
    results = _search(corpus, "Annex IX", OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0)
    assert all(h.reference_rank is None for h in results.hits)
    point = _search(corpus, "Annex IX point 1", OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0)
    assert _named(point) == [("annex:IX:1", 1)]


# Two example rows whose ids an exact reference can name: one held out (Pile B), one visible.
NAMED_EXAMPLES = DocumentLoad(
    replace(GUIDE, doc_key="test-c6-guide-named", title="Test guideline, named rows"),
    (
        ProvisionRow("art:90", None, None, None, "A held-out named example.", GUIDE_PUBLISHED,
                     source_example_id="hr-ex-190", is_held_out=True),
        ProvisionRow("annex:XX:1", None, None, None, "A visible named example.",
                     GUIDE_PUBLISHED, source_example_id="hr-ex-191"),
    ),
)  # fmt: skip


def test_a_named_held_out_row_is_returned_only_when_opted_in(corpus: psycopg.Connection):
    load_all(corpus, (NAMED_EXAMPLES,))
    query = "Article 90"
    default = _search(corpus, query, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0)
    assert _named(default) == []  # (the loaded corpus, if any, has its own art:90)
    opted_in = _search(corpus, query, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0,
                       include_held_out=True)  # fmt: skip
    assert _named(opted_in) == [("art:90", 1)]
    excluded = _search(corpus, query, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0,
                       include_held_out=True, exclude_source_example_ids=["hr-ex-190"])  # fmt: skip
    assert _named(excluded) == []


def test_a_named_row_is_left_out_by_the_exclude_filter(corpus: psycopg.Connection):
    load_all(corpus, (NAMED_EXAMPLES,))
    query = "Annex XX point 1"
    kept = _search(corpus, query, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0)
    assert _named(kept) == [("annex:XX:1", 1)]
    excluded = _search(corpus, query, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0,
                       exclude_source_example_ids=["hr-ex-191"])  # fmt: skip
    assert _named(excluded) == []


def test_another_acts_article_is_not_pinned(corpus: psycopg.Connection):
    for query in ("Article 2 GDPR", "Art. 2 DSGVO", "Article 2 of Regulation (EU) 2016/679"):
        results = _search(corpus, query, OFF_TOPIC, as_of=AFTER_OMNIBUS, max_distance=0.0)
        assert _named(results) == [], query


def test_the_engine_tuning_ranks_as_c6_did(corpus: psycopg.Connection):
    """The engine (`ENGINE_TUNING`) pins no named provision and ranks annex rows with points."""
    named = _search(corpus, "What does Article 2 say?", OFF_TOPIC, as_of=AFTER_OMNIBUS,
                    max_distance=0.0, tuning=ENGINE_TUNING)  # fmt: skip
    assert _named(named) == []
    annex = _found(_search(corpus, NO_WORDS, SNORK_AREA, as_of=AFTER_OMNIBUS,
                           tuning=ENGINE_TUNING))  # fmt: skip
    assert annex[0] == (AMENDED.doc_key, "annex:IX")
