"""Benchmark isolation check (story B13; INIT > Benchmark isolation 5; decision 012).

Pile B examples are stored in `provisions`, tagged and held out, so this checks behaviour:
1. `eval/split.json` is in split mode, every Pile B id sits on a held-out row, no retrievable
   row carries one, and every example row holds the text B2 extracted for its id.
2. Every retrieval entry point hides held-out rows by default. `ENTRY_POINTS` lists them with a
   probe; a public function added to `aiact/retrieval/` fails
   `test_every_retrieval_function_is_registered` until it is listed (C6's `search_ai_act`
   plugs in there, with a probe that searches with each Pile B example's own text).
3. No benchmark text (Pile B example or case description) is repeated in a retrievable row:
   by word 6-grams everywhere, and by embedding cosine where the corpus vectors exist.
The injection tests show each check fails on a planted leak, inside a rolled-back transaction.

The corpus checks read the loaded corpus. CI's isolation job loads it from the committed
`data/parsed/` and sets AIACT_REQUIRE_CORPUS, which turns a missing corpus (or a missing `eval/`,
as in a Corpus-lane worktree) into a failure instead of a skip. CI has no corpus vectors (no live
calls), so the embedding check runs only locally, after `aiact corpus embed`.
"""

import importlib
import inspect
import os
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

import psycopg
import pytest

import aiact.retrieval
from aiact.corpus.build import DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.embed import ARMS, vector_literal
from aiact.corpus.load import load_all
from aiact.eval import isolation
from aiact.eval.isolation import BenchmarkText, EmbeddingCache, ExampleText
from aiact.eval.split import SPLIT_FILE, Split, SplitMode
from aiact.retrieval.provisions import ProvisionNotFoundError, get_provision
from aiact.settings import get_settings
from tests.db.conftest import db, db_connection  # noqa: F401  (fixtures)

pytestmark = pytest.mark.db

REQUIRE_CORPUS_ENV = "AIACT_REQUIRE_CORPUS"
AFTER_THE_GUIDELINES = date(2026, 9, 30)
INJECTED_DOC = "test-b13-guide"
FOOTNOTE_NUMBER = " 114"
"""Inserted into planted copies: footnote numbers can stay in corpus text (decision 001 rule 7)."""


def _require(is_met: bool, reason: str) -> None:
    """Skip when a precondition is missing, or fail in CI's isolation job."""
    if is_met:
        return
    if os.environ.get(REQUIRE_CORPUS_ENV):
        pytest.fail(reason, pytrace=False)
    pytest.skip(reason)


# --- Benchmark inputs -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def split() -> Split:
    _require(SPLIT_FILE.is_file(), f"{SPLIT_FILE} is missing (a Corpus-lane worktree has no eval/)")
    return isolation.load_split()


@pytest.fixture(scope="module")
def examples(split: Split) -> tuple[ExampleText, ...]:
    """B2's example rows; needs `split` so a worktree without eval/ skips here too."""
    return isolation.load_example_texts()


@pytest.fixture(scope="module")
def pile_b_texts(split: Split, examples: tuple[ExampleText, ...]) -> tuple[BenchmarkText, ...]:
    return isolation.pile_b_texts(examples, split.pile_b)


@pytest.fixture(scope="module")
def benchmark_texts(pile_b_texts: tuple[BenchmarkText, ...]) -> tuple[BenchmarkText, ...]:
    """Pile B and every case description, the appliedAI extraction too when it is present."""
    return pile_b_texts + isolation.case_texts()


@pytest.fixture
def corpus(db: psycopg.Connection) -> psycopg.Connection:  # noqa: F811
    """The loaded corpus, inside the rolled-back test transaction."""
    row = db.execute(
        "select count(*) from provisions where source_example_id is not null"
    ).fetchone()
    _require(bool(row and row[0]), "the corpus isn't loaded; run `aiact corpus load`")
    return db


# --- 1. Tags --------------------------------------------------------------------------------


def test_the_split_holds_pile_b_out(split: Split) -> None:
    """Leave-one-out would need the per-case filter instead; decision 011 fixed a split."""
    assert split.mode is SplitMode.SPLIT
    assert len(split.pile_b) == 153


def test_every_pile_b_example_is_tagged_and_held_out(
    corpus: psycopg.Connection, split: Split
) -> None:
    gaps = isolation.tag_gaps(corpus, split.pile_b)
    assert gaps.is_empty, gaps


def test_every_example_row_holds_the_text_b2_extracted(
    corpus: psycopg.Connection, examples: tuple[ExampleText, ...]
) -> None:
    """C2 numbers the examples from the PDFs alone; B2's extraction (decision 001's anchor
    table) must agree, or a tag would sit on the wrong text."""
    assert len(examples) == 307
    assert isolation.derivation_mismatches(corpus, examples) == ()


# --- 2. Entry points ------------------------------------------------------------------------


@dataclass(frozen=True)
class HeldOutRow:
    provision_id: str
    source_example_id: str
    text: str


Probe = Callable[[psycopg.Connection, HeldOutRow, bool], frozenset[str]]
"""Ask an entry point for a held-out row, the way a caller would (by id for a lookup, by the
example's own text for a search), and return the provision_ids it gave back. The flag is the
entry point's opt-in (`include_held_out`)."""


def _probe_get_provision(
    connection: psycopg.Connection, row: HeldOutRow, include_held_out: bool
) -> frozenset[str]:
    try:
        found = get_provision(
            row.provision_id,
            as_of=AFTER_THE_GUIDELINES,
            include_held_out=include_held_out,
            connection=connection,
        )
    except ProvisionNotFoundError:
        return frozenset()
    return frozenset({found.provision_id})


ENTRY_POINTS: dict[str, Probe] = {
    "aiact.retrieval.provisions.get_provision": _probe_get_provision,
}
"""Every public function of `aiact.retrieval`, with its probe."""
OPT_IN_PARAMETER = "include_held_out"


def _retrieval_functions() -> dict[str, Callable[..., object]]:
    functions: dict[str, Callable[..., object]] = {}
    for info in pkgutil.iter_modules(aiact.retrieval.__path__, "aiact.retrieval."):
        module = importlib.import_module(info.name)
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("_") and function.__module__ == module.__name__:
                functions[f"{module.__name__}.{name}"] = function
    return functions


def test_every_retrieval_function_is_registered() -> None:
    assert set(_retrieval_functions()) == set(ENTRY_POINTS), (
        "add each new retrieval function to ENTRY_POINTS with a probe (decision 012: every "
        "search entry point hides Pile B by default)"
    )


@pytest.mark.parametrize("name", sorted(ENTRY_POINTS))
def test_the_held_out_opt_in_is_off_by_default(name: str) -> None:
    parameter = inspect.signature(_retrieval_functions()[name]).parameters.get(OPT_IN_PARAMETER)
    assert parameter is not None, f"{name} has no `{OPT_IN_PARAMETER}` opt-in"
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is False


def _held_out_rows(connection: psycopg.Connection) -> tuple[HeldOutRow, ...]:
    rows = connection.execute(
        "select provision_id, source_example_id, text from provisions where is_held_out"
    ).fetchall()
    return tuple(HeldOutRow(*row) for row in rows)


@pytest.mark.parametrize("name", sorted(ENTRY_POINTS))
def test_a_default_call_never_returns_a_pile_b_row(name: str, corpus: psycopg.Connection) -> None:
    probe = ENTRY_POINTS[name]
    held_out = _held_out_rows(corpus)
    held_out_ids = frozenset(row.provision_id for row in held_out)
    assert len(held_out) == 153
    leaked = {row.source_example_id: probe(corpus, row, False) & held_out_ids for row in held_out}
    assert {k: v for k, v in leaked.items() if v} == {}
    # The probe reaches the rows: with the opt-in they come back, so the check can fail.
    assert all(probe(corpus, row, True) for row in held_out)


# --- 3. Near-duplicates ---------------------------------------------------------------------


def test_no_benchmark_text_repeats_a_retrievable_row(
    corpus: psycopg.Connection, benchmark_texts: tuple[BenchmarkText, ...]
) -> None:
    matches = isolation.closest_by_ngram(benchmark_texts, isolation.retrievable_rows(corpus))
    assert [m for m in matches if m.is_near_duplicate] == [], matches[:5]


def _embedding_cache() -> EmbeddingCache:
    arm = ARMS["qwen3"]
    return isolation.load_cache(
        isolation.EMBEDDINGS_FILE, arm.model, get_settings().embedding_dimensions
    )


def _require_corpus_vectors(connection: psycopg.Connection, cache: EmbeddingCache) -> None:
    if not isolation.embedded_row_count(connection, cache.model, cache.dims):
        pytest.skip(
            f"no {cache.model}/{cache.dims} corpus vectors (CI has none); run `aiact corpus embed`"
        )


def test_no_benchmark_text_is_a_close_paraphrase_of_a_retrievable_row(
    corpus: psycopg.Connection, benchmark_texts: tuple[BenchmarkText, ...]
) -> None:
    cache = _embedding_cache()
    _require_corpus_vectors(corpus, cache)
    # The appliedAI extraction is left out of the committed vectors (its licence is unclear).
    texts = tuple(t for t in benchmark_texts if not t.key.startswith("appliedai"))
    missing = [t.key for t in texts if isolation.text_key(t.text) not in cache.vectors]
    assert missing == [], "run `aiact evaluate isolation-embed` for the new or changed texts"
    matches = isolation.nearest_by_embedding(corpus, texts, cache)
    assert [m for m in matches if m.is_near_duplicate] == [], matches[:5]


# --- Planted leaks: each check fails on one (rolled back) -------------------------------------


INJECTED_DOCUMENT = DocumentRow(
    doc_key=INJECTED_DOC,
    title="Test guideline with planted leaks",
    celex=None,
    doc_type="guideline",
    is_amending=False,
    status="draft",
    law_version=None,
    language="en",
    published_on=date(2026, 5, 19),
    in_force_from=None,
    source_url="https://ec.europa.eu/",
    sha256="c" * 64,
)


def _planted_copy(text: str) -> str:
    """A Pile B text as a guideline might repeat it: mid-paragraph, with a footnote number."""
    first, _, rest = text.partition(" ")
    return f"(7) Consider the following. {first}{FOOTNOTE_NUMBER} {rest} The same applies here."


def _plant(connection: psycopg.Connection, rows: tuple[ProvisionRow, ...]) -> None:
    load_all(connection, (DocumentLoad(INJECTED_DOCUMENT, rows),))


def _row(number: int, text: str, **tags: object) -> ProvisionRow:
    published = INJECTED_DOCUMENT.published_on or AFTER_THE_GUIDELINES
    row = ProvisionRow(f"guide:{INJECTED_DOC}:para:{number}", None, None, None, text, published)
    return replace(row, **tags)


@pytest.fixture
def planted_text(pile_b_texts: tuple[BenchmarkText, ...]) -> BenchmarkText:
    return pile_b_texts[0]


def test_an_untagged_copy_of_a_pile_b_example_is_caught(
    db: psycopg.Connection,  # noqa: F811
    planted_text: BenchmarkText,
) -> None:
    _plant(db, (_row(7, _planted_copy(planted_text.text)),))
    matches = isolation.closest_by_ngram((planted_text,), isolation.retrievable_rows(db))
    caught = [m for m in matches if m.is_near_duplicate]
    assert [m.provision_id for m in caught] == [f"guide:{INJECTED_DOC}:para:7"]
    assert caught[0].coverage == 1.0


def test_a_pile_b_row_that_is_not_held_out_is_caught(
    db: psycopg.Connection,  # noqa: F811
    planted_text: BenchmarkText,
    split: Split,
) -> None:
    _plant(db, (_row(1, planted_text.text, source_example_id=planted_text.key),))
    assert planted_text.key in isolation.tag_gaps(db, split.pile_b).retrievable


def test_a_held_out_row_is_hidden_and_an_untagged_copy_is_not(
    db: psycopg.Connection,  # noqa: F811
    planted_text: BenchmarkText,
) -> None:
    """The probe tells a hidden row from a leaked one, so the entry-point check can fail."""
    held = _row(1, planted_text.text, source_example_id=planted_text.key, is_held_out=True)
    _plant(db, (held, _row(2, _planted_copy(planted_text.text))))
    held_out = HeldOutRow(held.provision_id, planted_text.key, planted_text.text)
    copy = replace(held_out, provision_id=f"guide:{INJECTED_DOC}:para:2")
    assert _probe_get_provision(db, held_out, False) == frozenset()
    assert _probe_get_provision(db, copy, False) == {copy.provision_id}


def test_a_paraphrase_with_a_close_vector_is_caught(
    db: psycopg.Connection,  # noqa: F811
    planted_text: BenchmarkText,
) -> None:
    """A planted row given the Pile B text's own vector: the nearest-row query finds it."""
    cache = _embedding_cache()
    _plant(db, (_row(3, "A paraphrase that shares no wording with the example."),))
    db.execute(
        """
        insert into provision_embeddings (provision_row_id, model, dims, embedding, content_sha256)
        select p.id, %(model)s, %(dims)s, %(vector)s::extensions.vector, p.content_sha256
        from provisions p join documents d on d.id = p.document_id
        where d.doc_key = %(doc_key)s
        """,
        {
            "model": cache.model,
            "dims": cache.dims,
            "vector": vector_literal(
                isolation.decode_vector(cache.vectors[isolation.text_key(planted_text.text)])
            ),
            "doc_key": INJECTED_DOC,
        },
    )
    matches = isolation.nearest_by_embedding(db, (planted_text,), cache)
    caught = [m for m in matches if m.is_near_duplicate]
    assert [m.provision_id for m in caught] == [f"guide:{INJECTED_DOC}:para:3"]
    assert caught[0].cosine > 0.999
