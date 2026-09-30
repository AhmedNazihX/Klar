"""Benchmark isolation check (story B13; INIT > Benchmark isolation 5; decision 012).

Pile B examples are stored in `provisions`, tagged and held out, so this checks behaviour:
1. `eval/split.json` is in split mode, every Pile B id sits on a held-out row, no retrievable
   row carries one, and every example row holds the text B2 extracted for its id.
2. Every retrieval entry point hides held-out rows by default. `ENTRY_POINTS` lists them with a
   probe (`get_provision` by id; `search_ai_act` with each held-out row's own text and stored
   vector). Every other public callable of `aiact/retrieval/` must be in `NOT_ENTRY_POINTS` with
   a reason, or `test_every_retrieval_callable_is_registered_or_explained` fails.
3. No benchmark text (Pile B example or case description) is repeated in a retrievable row:
   by word 6-grams everywhere, and by embedding cosine where the corpus vectors exist. The two
   retellings decision 016 keeps (`eval/isolation/contaminated.json`) are recorded, not failed on.
The injection tests show each check fails on a planted leak, inside a rolled-back transaction.

The corpus checks read the loaded corpus. CI's isolation job loads it from the committed
`data/parsed/` and sets AIACT_REQUIRE_CORPUS, which turns a missing corpus (or a missing `eval/`,
as in a Corpus-lane worktree) into a failure instead of a skip. CI has no corpus vectors (no live
calls), so the embedding check runs only locally, after `aiact corpus embed`.
"""

import importlib
import inspect
import json
import os
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from types import ModuleType

import psycopg
import pytest

import aiact.retrieval
from aiact.corpus.build import DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.embed import ARMS, vector_literal
from aiact.corpus.load import load_all
from aiact.eval import isolation
from aiact.eval.isolation import BenchmarkText, ContaminatedList, EmbeddingCache, ExampleText
from aiact.eval.split import SPLIT_FILE, Split, SplitMode
from aiact.retrieval.provisions import ProvisionNotFoundError, get_provision
from aiact.retrieval.search import CANDIDATES as SEARCH_CANDIDATES
from aiact.retrieval.search import search_ai_act
from aiact.settings import BACKEND_DIR, get_settings
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


class StoredVectorEmbedder:
    """A query embedder for the probe: returns the held-out row's own stored vector, so the
    vector arm is asked for the row too. Without corpus vectors (CI) it returns a fixed unit
    vector and the keyword arm does the finding. No model is called."""

    def __init__(self, connection: psycopg.Connection, provision_id: str) -> None:
        self.model = ARMS["qwen3"].model
        self.dimensions = get_settings().embedding_dimensions
        row = connection.execute(
            STORED_VECTOR, (provision_id, self.model, self.dimensions)
        ).fetchone()
        self.vector: list[float] = (
            json.loads(row[0]) if row else [1.0] + [0.0] * (self.dimensions - 1)
        )

    def embed_query(self, text: str) -> list[float]:
        return self.vector


STORED_VECTOR = """
    select e.embedding::text from provision_embeddings e join provisions p
      on p.id = e.provision_row_id and p.content_sha256 = e.content_sha256
    where p.provision_id = %s and e.model = %s and e.dims = %s
    limit 1
"""


def _probe_search_ai_act(
    connection: psycopg.Connection, row: HeldOutRow, include_held_out: bool
) -> frozenset[str]:
    results = search_ai_act(
        row.text,
        as_of=AFTER_THE_GUIDELINES,
        include_held_out=include_held_out,
        limit=SEARCH_CANDIDATES,
        embedder=StoredVectorEmbedder(connection, row.provision_id),
        connection=connection,
    )
    return frozenset(hit.provision_id for hit in results.hits)


ENTRY_POINTS: dict[str, Probe] = {
    "aiact.retrieval.provisions.get_provision": _probe_get_provision,
    "aiact.retrieval.search.search_ai_act": _probe_search_ai_act,
}
"""The retrieval entry points, each with its probe."""
NOT_ENTRY_POINTS: dict[str, str] = {
    "aiact.retrieval.provisions.Provision": "the result type of get_provision",
    "aiact.retrieval.provisions.ProvisionNotFoundError": "an error type",
    "aiact.retrieval.search.QueryEmbedder": "the protocol a caller's embedder follows",
    "aiact.retrieval.search.QueryEmbedder.embed_query": "a protocol stub",
    "aiact.retrieval.search.SearchHit": "a result type of search_ai_act",
    "aiact.retrieval.search.SearchResults": "the result type of search_ai_act",
    "aiact.retrieval.search.prepare_search": "builds search_ai_act's statement; runs no query",
    "aiact.retrieval.search.distinct_units": "dedupes rows search_ai_act already fetched",
}
"""Public callables of `aiact.retrieval` that return no corpus rows by themselves, and why."""
OPT_IN_PARAMETER = "include_held_out"


def public_callables(package: ModuleType) -> dict[str, object]:
    """Every public callable a package defines, by dotted name: functions (decorated ones too),
    classes and their own public methods and properties, in the package's `__init__` and in every
    module and sub-package below it. Names imported from elsewhere are left out."""
    modules = [package] + [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(package.__path__, f"{package.__name__}.")
    ]
    found: dict[str, object] = {}
    for module in modules:
        for name, value in vars(module).items():
            if name.startswith("_") or getattr(value, "__module__", None) != module.__name__:
                continue
            if not callable(value):
                continue
            found[f"{module.__name__}.{name}"] = value
            if inspect.isclass(value):
                found |= _public_members(f"{module.__name__}.{name}", value)
    return found


def _public_members(prefix: str, cls: type) -> dict[str, object]:
    members: dict[str, object] = {}
    for name, member in vars(cls).items():
        if name.startswith("_"):
            continue
        if isinstance(member, staticmethod | classmethod | property) or callable(member):
            members[f"{prefix}.{name}"] = member
    return members


def test_every_retrieval_callable_is_registered_or_explained() -> None:
    found = set(public_callables(aiact.retrieval))
    unlisted = sorted(found - set(ENTRY_POINTS) - set(NOT_ENTRY_POINTS))
    assert unlisted == [], (
        "add each to ENTRY_POINTS with a probe (decision 012: every search entry point hides "
        "Pile B by default), or to NOT_ENTRY_POINTS with the reason it returns no rows"
    )
    assert sorted((set(ENTRY_POINTS) | set(NOT_ENTRY_POINTS)) - found) == []  # no stale entries


def test_the_discovery_finds_decorated_nested_and_class_callables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "b13_discovery_fixture"
    (package / "sub").mkdir(parents=True)
    (package / "__init__.py").write_text("def in_init(): ...\n")
    (package / "sub" / "__init__.py").write_text("")
    (package / "sub" / "nested.py").write_text(
        "import functools\nfrom os.path import join\n\n"
        "@functools.lru_cache\ndef cached(): ...\n\n"
        "def _private(): ...\n\n"
        "class Finder:\n"
        "    def find(self): ...\n"
        "    @staticmethod\n    def lookup(): ...\n"
        "    def _helper(self): ...\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    found = public_callables(importlib.import_module("b13_discovery_fixture"))
    assert set(found) == {
        "b13_discovery_fixture.in_init",
        "b13_discovery_fixture.sub.nested.cached",
        "b13_discovery_fixture.sub.nested.Finder",
        "b13_discovery_fixture.sub.nested.Finder.find",
        "b13_discovery_fixture.sub.nested.Finder.lookup",
    }


@pytest.mark.parametrize("name", sorted(ENTRY_POINTS))
def test_the_held_out_opt_in_is_off_by_default(name: str) -> None:
    entry_point = public_callables(aiact.retrieval)[name]
    assert callable(entry_point)
    parameter = inspect.signature(entry_point).parameters.get(OPT_IN_PARAMETER)
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
    # The probe reaches the rows: with the opt-in each comes back, so the check can fail.
    missed = [
        row.source_example_id
        for row in held_out
        if row.provision_id not in probe(corpus, row, True)
    ]
    assert missed == []


# --- 3. Near-duplicates ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def contaminated(split: Split) -> ContaminatedList:
    return isolation.load_contaminated()


def _known(contaminated: ContaminatedList) -> frozenset[tuple[str, str]]:
    """The (example, passage) pairs decision 016 keeps: recorded, not failed on."""
    return frozenset((e.example_id, e.passage) for e in contaminated.examples)


def test_no_benchmark_text_repeats_a_retrievable_row(
    corpus: psycopg.Connection,
    benchmark_texts: tuple[BenchmarkText, ...],
    contaminated: ContaminatedList,
) -> None:
    matches = isolation.closest_by_ngram(benchmark_texts, isolation.retrievable_rows(corpus))
    known = _known(contaminated)
    repeats = [m for m in matches if m.is_near_duplicate and (m.key, m.provision_id) not in known]
    assert repeats == [], matches[:5]


def test_the_contaminated_examples_are_pile_b(contaminated: ContaminatedList, split: Split) -> None:
    assert contaminated.decision == "docs/decisions/016-contaminated-pile-b-cases.md"
    assert (BACKEND_DIR.parent / contaminated.decision).is_file()
    ids = [e.example_id for e in contaminated.examples]
    assert sorted(ids) == ["hr-ex-031", "hr-ex-269"]
    assert set(ids) <= set(split.pile_b)


def test_the_contaminated_overlaps_are_as_recorded(
    corpus: psycopg.Connection,
    contaminated: ContaminatedList,
    pile_b_texts: tuple[BenchmarkText, ...],
) -> None:
    """The file documents the measured overlap; a corpus or normalisation change that moves it
    shows up here (and may need decision 016 revisited)."""
    texts = {t.key: t for t in pile_b_texts}
    rows = isolation.retrievable_rows(corpus)
    for known in contaminated.examples:
        passage = tuple(r for r in rows if r.provision_id == known.passage and r.language == "en")
        (match,) = isolation.closest_by_ngram((texts[known.example_id],), passage)
        assert (round(match.coverage, 3), match.longest_run) == (known.coverage, known.longest_run)


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
    corpus: psycopg.Connection, split: Split, contaminated: ContaminatedList
) -> None:
    cache = _embedding_cache()
    _require_corpus_vectors(corpus, cache)
    texts = isolation.embedded_texts()  # the texts `aiact evaluate isolation-embed` embeds
    missing = [t.key for t in texts if isolation.text_key(t.text) not in cache.vectors]
    assert missing == [], "run `aiact evaluate isolation-embed` for the new or changed texts"
    matches = isolation.nearest_by_embedding(corpus, texts, cache)
    known = _known(contaminated)
    close = [m for m in matches if m.is_near_duplicate and (m.key, m.provision_id) not in known]
    assert close == [], matches[:5]
    cosines = {(m.key, m.provision_id): m.cosine for m in matches}
    for example in contaminated.examples:
        pair = (example.example_id, example.passage)
        if pair in cosines:  # otherwise another row is nearer; the recorded value still holds
            assert round(cosines[pair], 3) == example.cosine


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
