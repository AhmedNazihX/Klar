"""The corpus embedder (aiact/corpus/embed.py) against the local Supabase Postgres.

Every test runs in the `db` fixture's rolled-back transaction, loads its own `test-c4-*`
documents and embeds only those, under a test model name, with a fake embedder: the stored
corpus and its real vectors are never touched.
"""

import hashlib
import math
from dataclasses import dataclass, field, replace
from datetime import date

import psycopg
import pytest

from aiact.corpus.build import AI_ACT_IN_FORCE, DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.embed import ARMS, EmbeddingArm, embed_corpus, has_arm_index
from aiact.corpus.load import load_document
from aiact.llm.embeddings import EmbeddingBatch, EmbeddingError

pytestmark = pytest.mark.db

DIMS = 4
ARM = EmbeddingArm("test/c4-model", "test", max_input_chars=1_000)
OMNIBUS_IN_FORCE = date(2026, 7, 27)
LAW = DocumentRow(
    doc_key="test-c4-law",
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
# art:5:2 has two slices with the same text (split with its parent, decision 014).
PROVISIONS = (
    ProvisionRow("art:5", None, None, "Article 5", "1. old 2. same", AI_ACT_IN_FORCE,
                 OMNIBUS_IN_FORCE),
    ProvisionRow("art:5", None, None, "Article 5", "1. new 2. same", OMNIBUS_IN_FORCE),
    ProvisionRow("art:5:1", "art:5", AI_ACT_IN_FORCE, "Article 5", "old", AI_ACT_IN_FORCE,
                 OMNIBUS_IN_FORCE),
    ProvisionRow("art:5:1", "art:5", OMNIBUS_IN_FORCE, "Article 5", "new", OMNIBUS_IN_FORCE),
    ProvisionRow("art:5:2", "art:5", AI_ACT_IN_FORCE, "Article 5", "same", AI_ACT_IN_FORCE,
                 OMNIBUS_IN_FORCE),
    ProvisionRow("art:5:2", "art:5", OMNIBUS_IN_FORCE, "Article 5", "same", OMNIBUS_IN_FORCE),
)  # fmt: skip
DISTINCT_TEXTS = 5
STORED = """
    select p.provision_id, p.valid_from, e.model, e.dims, e.content_sha256 = p.content_sha256,
           extensions.vector_norm(e.embedding)
    from provisions p join documents d on d.id = p.document_id
    left join provision_embeddings e on e.provision_row_id = p.id and e.model = %s
    where d.doc_key = any(%s) order by p.id
"""


def _unit_vector(text: str) -> list[float]:
    raw = [b + 1.0 for b in hashlib.sha256(text.encode()).digest()[:DIMS]]
    norm = math.sqrt(math.fsum(x * x for x in raw))
    return [x / norm for x in raw]


@dataclass
class FakeEmbedder:
    """Returns a vector derived from each text and records what it was sent."""

    calls: list[list[str]] = field(default_factory=list)

    def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        self.calls.append(texts)
        return EmbeddingBatch([_unit_vector(t) for t in texts], 10 * len(texts), 1e-6 * len(texts))

    @property
    def texts(self) -> list[str]:
        return [t for call in self.calls for t in call]


def _load(db: psycopg.Connection, document: DocumentRow = LAW, rows=PROVISIONS) -> None:
    load_document(db, DocumentLoad(document, rows))


def _embed(db: psycopg.Connection, embedder: FakeEmbedder, *doc_keys: str, **kwargs):
    return embed_corpus(db, embedder, ARM, DIMS, doc_keys=doc_keys or ("test-c4-law",), **kwargs)


def _stored(db: psycopg.Connection, *doc_keys: str) -> list[tuple[object, ...]]:
    return db.execute(STORED, (ARM.model, list(doc_keys or ("test-c4-law",)))).fetchall()


def test_every_row_gets_a_current_unit_vector_and_each_text_is_embedded_once(
    db: psycopg.Connection,
):
    _load(db)
    embedder = FakeEmbedder()
    report = _embed(db, embedder, batch_size=2)
    assert sorted(embedder.texts) == sorted({f"Article 5\n{p.text}" for p in PROVISIONS})
    assert [len(call) for call in embedder.calls] == [2, 2, 1]
    stored = _stored(db)
    assert len(stored) == len(PROVISIONS)
    for _, _, model, dims, is_current, norm in stored:
        assert (model, dims, is_current) == (ARM.model, DIMS, True)
        assert norm == pytest.approx(1.0, abs=1e-6)
    assert (report.texts_embedded, report.rows_embedded, report.rows_reused) == (
        DISTINCT_TEXTS,
        len(PROVISIONS),
        0,
    )
    assert (report.batches, report.tokens) == (3, 10 * DISTINCT_TEXTS)
    assert report.cost_usd == pytest.approx(1e-6 * DISTINCT_TEXTS)


def test_rerunning_embeds_nothing_and_changes_nothing(db: psycopg.Connection):
    _load(db)
    _embed(db, FakeEmbedder())
    before = db.execute("select xmin::text, * from provision_embeddings where model = %s",
                        (ARM.model,)).fetchall()  # fmt: skip
    embedder = FakeEmbedder()
    report = _embed(db, embedder)
    assert embedder.calls == []
    assert (report.rows_reused, report.texts_embedded, report.cost_usd) == (0, 0, 0.0)
    after = db.execute("select xmin::text, * from provision_embeddings where model = %s",
                       (ARM.model,)).fetchall()  # fmt: skip
    assert after == before


def test_a_changed_text_is_embedded_again(db: psycopg.Connection):
    _load(db)
    _embed(db, FakeEmbedder())
    db.execute(
        "update provisions p set text = 'new, corrected' from documents d"
        " where d.id = p.document_id and d.doc_key = 'test-c4-law' and p.text = 'new'"
    )
    assert [row[4] for row in _stored(db)].count(False) == 1
    embedder = FakeEmbedder()
    report = _embed(db, embedder)
    assert embedder.texts == ["Article 5\nnew, corrected"]
    assert report.rows_embedded == 1
    assert all(row[4] for row in _stored(db))


def test_a_stored_vector_is_reused_for_the_same_text_in_another_document(
    db: psycopg.Connection,
):
    _load(db)
    _embed(db, FakeEmbedder())
    original = replace(LAW, doc_key="test-c4-original", law_version="original")
    _load(db, original, tuple(replace(p, valid_to=None) for p in PROVISIONS[::2]))
    embedder = FakeEmbedder()
    report = _embed(db, embedder, "test-c4-original")
    assert embedder.calls == []
    assert report.rows_reused == 3
    assert all(row[4] for row in _stored(db, "test-c4-original"))


def test_a_text_over_the_arms_limit_is_skipped_and_reported(db: psycopg.Connection):
    long_row = ProvisionRow("art:6", None, None, None, "x" * 1_001, AI_ACT_IN_FORCE)
    _load(db, rows=(*PROVISIONS, long_row))
    embedder = FakeEmbedder()
    report = _embed(db, embedder)
    assert len(report.too_long) == 1
    assert "x" * 1_001 not in embedder.texts
    assert [row[2] for row in _stored(db)].count(None) == 1


def test_a_short_answer_from_the_embedder_writes_nothing(db: psycopg.Connection):
    _load(db)

    class ShortEmbedder(FakeEmbedder):
        def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
            return EmbeddingBatch([_unit_vector(texts[0])], 0, 0.0)

    with pytest.raises(EmbeddingError, match="expected 2 vectors, got 1"):
        _embed(db, ShortEmbedder(), batch_size=2)
    assert all(row[2] is None for row in _stored(db))


def test_only_the_default_arm_has_an_hnsw_index(db: psycopg.Connection):
    assert has_arm_index(db, ARMS["qwen3"].model, 1536)
    assert not has_arm_index(db, ARMS["qwen3"].model, 1024)
    assert not has_arm_index(db, ARMS["openai3l"].model, 1536)
