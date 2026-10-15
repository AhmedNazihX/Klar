"""Benchmark isolation check (story B13; INIT > Benchmark isolation 5; decision 012).

Pile B examples are stored in `provisions`, tagged and held out, so this checks behaviour:
1. `eval/split.json` is in split mode, every Pile B id sits on a held-out row, no retrievable
   row carries one, and every example row holds the text B2 extracted for its id.
2. Every retrieval entry point hides held-out rows by default. `ENTRY_POINTS` lists them with a
   probe (`get_provision` by id; `search_ai_act` with each held-out row's own text and stored
   vector). Every other public callable of `aiact/retrieval/` must be in `NOT_ENTRY_POINTS` with
   a reason, or `test_every_retrieval_callable_is_registered_or_explained` fails.
3. No benchmark text (Pile B example or case description) is repeated in a retrievable row:
   by word 6-grams everywhere (the judge validation's invented texts too), and by embedding
   cosine where the corpus vectors exist. The two retellings decision 016 keeps sit below every
   limit, so the checks pass with them, not by exempting them. Their overlap is recorded in
   `eval/isolation/contaminated.json` and pinned by
   `test_the_contaminated_overlaps_are_as_recorded` (and the local cosine re-check).
4. No tracked file outside the folders the Engine lane denies names a Pile B case (V11), except
   the ids `NAMES_PILE_B_CASES` pins for two files, each with a reason: any other id fails.
The injection tests show each check fails on a planted leak, inside a rolled-back transaction.

The corpus checks read the loaded corpus. CI's isolation job loads it from the committed
`data/parsed/` and sets AIACT_REQUIRE_CORPUS, which turns a missing corpus (or a missing `eval/`,
as in a Corpus-lane worktree) into a failure instead of a skip. CI has no corpus vectors (no live
calls), so the embedding check runs only locally, after `aiact corpus embed`.
"""

import ast
import importlib
import inspect
import json
import os
import pkgutil
import re
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields, replace
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, get_type_hints

import anyio
import psycopg
import pytest
import yaml
from pydantic import BaseModel

import aiact.retrieval
from aiact.api import classify as api_classify
from aiact.api import qa as api_qa
from aiact.corpus.build import DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.embed import ARMS, vector_literal
from aiact.corpus.load import load_all
from aiact.engine import (
    ClassifyRequest,
    classify_system,
    run_classification,
    stream_classification,
)
from aiact.engine.classify import Retrieval
from aiact.engine.nodes.common import Lookup
from aiact.eval import isolation, judge_validation, label_filter
from aiact.eval.cases import CASES_DIR, QA_DIR_NAME, CaseSet
from aiact.eval.isolation import BenchmarkText, ContaminatedList, EmbeddingCache, ExampleText
from aiact.eval.runner import ClassifierInput
from aiact.eval.split import SPLIT_FILE, Split, SplitMode
from aiact.mcp.server import build_server
from aiact.retrieval import search as search_module
from aiact.retrieval.provisions import ProvisionNotFoundError, get_provision
from aiact.retrieval.search import CANDIDATES as SEARCH_CANDIDATES
from aiact.retrieval.search import search_ai_act
from aiact.settings import BACKEND_DIR, Settings, get_settings
from tests.db.conftest import (  # noqa: F401  (fixtures)
    REQUIRE_CORPUS_ENV,
    db,
    db_connection,
)
from tests.mcp.test_server import HIDDEN_ARGUMENTS, property_names

pytestmark = pytest.mark.db

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


@pytest.fixture(scope="module")
def judge_validation_texts(split: Split) -> tuple[BenchmarkText, ...]:
    """The judge validation cases that quote no provision (V4): their descriptions, facts and
    documents are invented. The others quote the Act word for word, and their claims restate
    it, by design."""
    return tuple(
        BenchmarkText(f"{case.id}:{part}", text)
        for case in judge_validation.load_cases()
        if not case.provisions
        for part, text in (("claim", case.claim), ("source", case.source))
    )


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


def test_the_case_texts_hold_every_yaml_case(split: Split) -> None:
    """Counted apart from the loader: a loader that dropped cases would thin every check below."""
    folders = [s.value for s in CaseSet if s is not CaseSet.APPLIEDAI] + [QA_DIR_NAME]
    files = (path for folder in folders for path in (CASES_DIR / folder).rglob("*.yaml"))
    documents = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in files]
    count = sum(len(d) if isinstance(d, list) else 1 for d in documents)
    assert len(isolation.case_texts(appliedai_file=None)) == count > 0


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
        max_distance=None,  # a cut-off (C8) would hide a meaning-arm leak
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
    "aiact.retrieval.provisions.document_for": "maps a provision id to its document; no query",
    "aiact.retrieval.provisions.get_omnibus_provision": "reads only the amending act (the "
    "Omnibus), which holds no guideline example; its query also drops held-out rows",
    "aiact.retrieval.search.QueryEmbedder": "the protocol a caller's embedder follows",
    "aiact.retrieval.search.QueryEmbedder.embed_query": "a protocol stub",
    "aiact.retrieval.search.SearchHit": "a result type of search_ai_act",
    "aiact.retrieval.search.SearchResults": "the result type of search_ai_act",
    "aiact.retrieval.search.prepare_search": "builds search_ai_act's statement; runs no query",
    "aiact.retrieval.search.distinct_units": "dedupes rows search_ai_act already fetched",
    "aiact.retrieval.search.hit_metadata": "a search's trace metadata from rows it already "
    "returned (their ids); runs no query",
    "aiact.retrieval.search.SearchTuning": "search_ai_act's ranking constants; runs no query",
    "aiact.retrieval.references.exact_references": "reads provision ids from a query's text; "
    "runs no query (search_ai_act looks them up under its own filters)",
    "aiact.retrieval.documents.list_documents": "reads only the documents table (titles and "
    "dates), never a provision row",
    "aiact.retrieval.documents.DocumentInfo": "a result type of list_documents",
    "aiact.retrieval.documents.DocumentList": "the result type of list_documents",
    "aiact.retrieval.tracing.traced_lookup": "traces a lookup it wraps; runs no query itself",
    "aiact.retrieval.tracing.provision_metadata": "a lookup's trace metadata; runs no query",
    "aiact.retrieval.tracing.search_metadata": "a search's trace metadata; runs no query",
    "aiact.retrieval.tracing.benchmark_run": "marks lookups as a benchmark run's; runs no query",
    "aiact.retrieval.tracing.is_benchmark_run": "reads that mark; runs no query",
}
"""Public callables of `aiact.retrieval` that return no corpus rows by themselves, or no
guideline rows (so never a held-out example), and why."""
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


ENGINE_OPT_INS: dict[str, Callable[..., object]] = {
    "aiact.engine.classify_system": classify_system,
    "aiact.engine.run_classification": run_classification,
    "aiact.engine.stream_classification": stream_classification,
}
"""The engine's entry points that carry the gap run's opt-in (E10) to every retrieval call of a
run (`tests/engine/test_held_out.py`, `tests/engine/test_engine_nodes.py`). Only V8's gap run
sets it; the API (P1) and the MCP tools (P2b) never expose it."""
OPT_IN_FIELDS: dict[str, type] = {
    "aiact.engine.classify.Retrieval": Retrieval,
    "aiact.engine.nodes.common.Lookup": Lookup,
    "aiact.eval.runner.ClassifierInput": ClassifierInput,
}
"""The dataclasses that carry the opt-in: a run's retrieval options and its lookup, and the
runner's per-case input (set only by `--exclude-mode all`, the gap run)."""
REQUEST_MODELS: dict[str, type[BaseModel]] = {
    "aiact.engine.ClassifyRequest": ClassifyRequest,
    "aiact.api POST /classify body": get_type_hints(api_classify.started_run)["body"],
    "aiact.api POST /qa body": get_type_hints(api_qa.ask_question)["body"],
}
"""Every public request model (the bodies P1 and P2b accept): none may carry the opt-in. The MCP
`classify_system` tool builds a `ClassifyRequest` from its arguments, whose model the SDK makes
from the tool's signature: `test_no_mcp_tool_takes_the_opt_in` checks every tool's arguments.
The API's query parameters are checked in tests/api/test_app.py (no parameter or schema property
in its OpenAPI document is an opt-in)."""


def test_no_mcp_tool_takes_the_opt_in() -> None:
    """P2b: the four MCP tools, classify_system among them, as an outside agent sees them,
    nested arguments and `$defs` included (the hidden names are tests/mcp/test_server.py's)."""
    assert {OPT_IN_PARAMETER, "exclude_source_example_ids"} <= HIDDEN_ARGUMENTS
    tools = anyio.run(build_server().list_tools)
    assert "classify_system" in {tool.name for tool in tools}
    for tool in tools:
        assert property_names(tool.input_schema).isdisjoint(HIDDEN_ARGUMENTS), tool.name


@pytest.mark.parametrize("name", sorted(ENGINE_OPT_INS))
def test_the_engines_held_out_opt_in_is_off_by_default(name: str) -> None:
    parameter = inspect.signature(ENGINE_OPT_INS[name]).parameters.get(OPT_IN_PARAMETER)
    assert parameter is not None, f"{name} has no `{OPT_IN_PARAMETER}` opt-in"
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is False


@pytest.mark.parametrize("name", sorted(OPT_IN_FIELDS))
def test_the_opt_in_fields_are_keyword_only_and_off_by_default(name: str) -> None:
    [found] = [f for f in fields(OPT_IN_FIELDS[name]) if f.name == OPT_IN_PARAMETER]
    assert found.kw_only is True
    assert found.default is False


@pytest.mark.parametrize("name", sorted(REQUEST_MODELS))
def test_no_public_request_model_has_the_opt_in(name: str) -> None:
    assert OPT_IN_PARAMETER not in REQUEST_MODELS[name].model_fields


def opt_in_set_true(source: str) -> list[int]:
    """The lines where `source` sets the opt-in to a literal True: as a keyword argument
    (`include_held_out=True`) or a dict entry (`"include_held_out": True`)."""
    values: list[ast.expr] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.keyword) and node.arg == OPT_IN_PARAMETER:
            values.append(node.value)
        elif isinstance(node, ast.Dict):
            values.extend(
                value
                for key, value in zip(node.keys, node.values, strict=True)
                if isinstance(key, ast.Constant) and key.value == OPT_IN_PARAMETER
            )
    return [v.lineno for v in values if isinstance(v, ast.Constant) and v.value is True]


def test_the_literal_true_finder_catches_both_forms() -> None:
    source = (
        f"f({OPT_IN_PARAMETER}=True)\n"
        f"g({{'{OPT_IN_PARAMETER}': True}})\n"
        f"h({OPT_IN_PARAMETER}=flag, other=True)\n"
    )
    assert opt_in_set_true(source) == [1, 2]


def test_no_package_code_turns_the_opt_in_on() -> None:
    """Held-out rows stay hidden in the app: no module sets the opt-in to a literal True (V8's
    gap run passes it from the runner's exclude mode)."""
    package = BACKEND_DIR / "aiact"
    found = [
        f"{path.relative_to(BACKEND_DIR)}:{line}"
        for path in sorted(package.rglob("*.py"))
        for line in opt_in_set_true(path.read_text(encoding="utf-8"))
    ]
    assert found == []


def _held_out_rows(connection: psycopg.Connection) -> tuple[HeldOutRow, ...]:
    rows = connection.execute(
        "select provision_id, source_example_id, text from provisions where is_held_out"
    ).fetchall()
    return tuple(HeldOutRow(*row) for row in rows)


def test_the_search_probe_ignores_a_set_cut_off(
    db: psycopg.Connection,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With SEARCH_MAX_DISTANCE set, the probe still searches the meaning arm without a cut-off,
    so a held-out row near the query can't hide behind it. Needs no corpus or eval/."""
    tight = Settings(_env_file=None, search_max_distance=0.0)  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr(search_module, "get_settings", lambda: tight)
    cut_offs: list[object] = []
    real_run = search_module._run  # pyright: ignore[reportPrivateUsage]

    def recording_run(connection: psycopg.Connection, statement: Any, params: dict[str, Any]):
        cut_offs.append(params["max_distance"])
        return real_run(connection, statement, params)

    monkeypatch.setattr(search_module, "_run", recording_run)
    _probe_search_ai_act(db, HeldOutRow("art:1", "hr-ex-000", "credit scoring"), False)
    assert cut_offs == [None]


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


def test_no_benchmark_text_repeats_a_retrievable_row(
    corpus: psycopg.Connection,
    benchmark_texts: tuple[BenchmarkText, ...],
    judge_validation_texts: tuple[BenchmarkText, ...],
) -> None:
    assert len(judge_validation_texts) == 48  # 24 invented cases, claim and source each
    texts = benchmark_texts + judge_validation_texts
    matches = isolation.closest_by_ngram(texts, isolation.retrievable_rows(corpus))
    assert [m for m in matches if m.is_near_duplicate] == [], matches[:5]


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
    assert [m for m in matches if m.is_near_duplicate] == [], matches[:5]
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


def test_the_engine_lane_never_sees_pile_b_label_filter_output() -> None:
    """Pile B's label-filter answers and disagreements hold its labels and the second model's
    reasons, so their folder is in the Engine lane's deny list (B9, option A, 2026-10-10)."""
    repo = BACKEND_DIR.parent
    config = json.loads((repo / ".claude" / "foreman.json").read_text())
    folder = label_filter.reports_folder(CaseSet.COMMISSION_B).relative_to(repo).as_posix()
    assert folder in config["lanes"]["Engine"]["deny"]
    assert label_filter.reports_folder(CaseSet.OWN) != label_filter.reports_folder(
        CaseSet.COMMISSION_B
    )


# --- Pile B case ids in tracked files (V11) -------------------------------------------------

PILE_B_CASE_ID = re.compile(r"(?<![A-Za-z0-9])cb-(\d{3})(?!\d)", re.IGNORECASE)
"""A Pile B case id, `cb-NNN-<slug>`, or its short form `cb-NNN`, in any case; the group is its
number. Tests use made-up ids that don't match (`cb-test-…`)."""
PILE_B_PLACES = (
    "eval/commission_examples",
    "eval/cases/commission_b",
    "eval/split.json",
    "eval/reports/pile_b",
)
"""Where Pile B's ids and labels belong: exactly the paths the Engine lane denies."""


@dataclass(frozen=True)
class KnownPileBNames:
    """A tracked file outside `PILE_B_PLACES` that already names Pile B cases, and why."""

    reason: str
    numbers: frozenset[str]
    """The case numbers (`cb-NNN`) it names today; any other one is a leak. Numbers only, so
    this file names no case itself."""


NAMES_PILE_B_CASES: dict[str, KnownPileBNames] = {
    "eval/LABEL_CHANGES.md": KnownPileBNames(
        "the label-change log names each changed case and its labels, and the label-freeze "
        "check (B10a) matches its rows by case id",
        frozenset(["030", "097", "098", "222", "269", "304"]),
    ),
    "docs/BACKLOG.md": KnownPileBNames(
        "the orchestrator's hand-over notes on the Pile B stories (B4, B9, B10b, X0b); only the "
        "orchestrator edits it",
        frozenset(
            [
                "030",
                "041",
                "042",
                "098",
                "108",
                "123",
                "173",
                "222",
                "240",
                "269",
                "293",
                "304",
                "307",
            ]
        ),
    ),
}
"""The pinned baseline: tracked files allowed to name these Pile B cases outside
`PILE_B_PLACES`, each with its reason (V11)."""


def _is_pile_b_place(name: str) -> bool:
    return any(name == place or name.startswith(f"{place}/") for place in PILE_B_PLACES)


def pile_b_id_leaks(repo: Path, names: Iterable[str]) -> dict[str, list[str]]:
    """Each file of `names` (paths from `repo`) outside the allowed places that names a Pile B
    case its baseline doesn't hold, with those ids. A file this worktree leaves out (a lane's
    sparse checkout) is skipped; one that isn't UTF-8 is read with its bad bytes replaced."""
    leaks: dict[str, list[str]] = {}
    for name in names:
        path = repo / name
        if _is_pile_b_place(name) or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        known = NAMES_PILE_B_CASES.get(name)
        allowed = known.numbers if known else frozenset()
        if found := sorted({number for number in PILE_B_CASE_ID.findall(text)} - allowed):
            leaks[name] = [f"cb-{number}" for number in found]
    return leaks


def tracked_files(repo: Path) -> list[str]:
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True
    ).stdout
    return [name for name in listed.decode().split("\0") if name]


def test_no_tracked_file_outside_the_pile_b_places_names_a_pile_b_case() -> None:
    repo = BACKEND_DIR.parent
    names = tracked_files(repo)
    assert "backend/tests/test_isolation.py" in names
    assert pile_b_id_leaks(repo, names) == {}
    assert set(NAMES_PILE_B_CASES) <= set(names)


def test_the_pile_b_places_are_the_engine_lanes_deny_list() -> None:
    config = json.loads((BACKEND_DIR.parent / ".claude" / "foreman.json").read_text())
    assert sorted(PILE_B_PLACES) == sorted(config["lanes"]["Engine"]["deny"])


def test_the_files_allowed_to_name_pile_b_cases_are_pinned() -> None:
    assert set(NAMES_PILE_B_CASES) == {"eval/LABEL_CHANGES.md", "docs/BACKLOG.md"}
    assert all(known.reason and known.numbers for known in NAMES_PILE_B_CASES.values())


NEW = "999"
"""A case number no baseline holds, for planted ids."""


def test_a_planted_pile_b_id_is_caught_outside_the_allowed_places(tmp_path: Path) -> None:
    assert all(NEW not in known.numbers for known in NAMES_PILE_B_CASES.values())
    old = min(NAMES_PILE_B_CASES["eval/LABEL_CHANGES.md"].numbers)
    planted = f"- **scope** (1): {'cb-'}{NEW}-made-up-system (expected high_risk)\n"
    names = (
        "eval/reports/run-2099-01-01.md",
        "eval/reports/pile_b/run-2099-01-01.md",
        "eval/commission_examples/made-up.md",
        "eval/split.json.bak",
        "eval/LABEL_CHANGES.md",
        "docs/BACKLOG.md",
        "docs/notes.md",
        ".claude/skills/eval/notes.md",
        "backend/notes.md",
    )
    for name in names:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(planted, encoding="utf-8")
    (tmp_path / "known.md").write_text(f"see {'cb-'}{old}\n", encoding="utf-8")
    (tmp_path / "short.md").write_text(f"see CB-{NEW}, x_{'cb-'}{NEW}, cb-12, scb-1234, cb-1234\n")
    (tmp_path / "binary.bin").write_bytes(b"\xff\xfe" + planted.encode())
    leaks = pile_b_id_leaks(tmp_path, (*names, "known.md", "short.md", "binary.bin", "missing.md"))
    expected = [f"{'cb-'}{NEW}"]
    assert leaks == {
        "eval/reports/run-2099-01-01.md": expected,
        "eval/split.json.bak": expected,
        "eval/LABEL_CHANGES.md": expected,
        "docs/BACKLOG.md": expected,
        "docs/notes.md": expected,
        ".claude/skills/eval/notes.md": expected,
        "backend/notes.md": expected,
        "known.md": [f"{'cb-'}{old}"],
        "short.md": expected,
        "binary.bin": expected,
    }


def test_an_allowed_file_may_keep_the_pile_b_cases_it_names_today(tmp_path: Path) -> None:
    for name, known in NAMES_PILE_B_CASES.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        ids = ", ".join(f"{'cb-'}{number}-x" for number in sorted(known.numbers))
        (tmp_path / name).write_text(ids, encoding="utf-8")
    assert pile_b_id_leaks(tmp_path, NAMES_PILE_B_CASES) == {}
