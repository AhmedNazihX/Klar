"""The gap run's opt-in at the corpus (E10, decision 012): every corpus call an engine node or the
citation validator makes passes the run's `include_held_out` to `get_provision` and
`search_ai_act`, so it is False unless V8's gap run sets it. `test_classify.py` shows the flag
reaching each node's lookup; this shows each lookup's flag reaching the retrieval call. The
retrieval functions are replaced by recorders: no database is used."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date
from types import ModuleType
from typing import cast

import psycopg
import pytest

from aiact.engine import citations
from aiact.engine.citations import CorpusCitations, resolve
from aiact.engine.nodes import corpus, prohibited, scope
from aiact.engine.nodes.common import Lookup
from aiact.engine.nodes.guideline_retrieval import GuidelineCorpus
from aiact.engine.nodes.high_risk_retrieval import HighRiskCorpus
from aiact.retrieval.provisions import ProvisionNotFoundError
from aiact.retrieval.search import QueryEmbedder
from aiact.schemas import Citation, Language, LawVersion

LOOKUP = Lookup(Language.EN, LawVersion.AMENDED, date(2026, 10, 6), ("hr-ex-001",))
NO_CONNECTION = cast(psycopg.Connection, None)
"""The recorders never touch the connection."""


class Embedder:
    model = "qwen/qwen3-embedding-8b"
    dimensions = 2

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


EMBEDDER: QueryEmbedder = Embedder()


@dataclass
class Recorder:
    """Stands in for `get_provision` and `search_ai_act`, noting each call's opt-in."""

    flags: list[tuple[str, bool]] = field(default_factory=list)

    def get_provision(self, *args: object, include_held_out: bool = False, **kw: object) -> None:
        self.flags.append(("get_provision", include_held_out))
        raise ProvisionNotFoundError("recorded")

    def search_ai_act(self, *args: object, include_held_out: bool = False, **kw: object) -> object:
        self.flags.append(("search_ai_act", include_held_out))
        return _NoHits()


class _NoHits:
    hits = ()


def _provision(call: Callable[[], object]) -> None:
    with pytest.raises(ProvisionNotFoundError):
        call()


def scope_calls(lookup: Lookup) -> None:
    library = scope.CorpusLibrary(NO_CONNECTION, EMBEDDER)
    _provision(lambda: library.provision("art:3:1", lookup))
    library.definition_guidance("a tool", lookup)


def guideline_calls(lookup: Lookup) -> None:
    library = GuidelineCorpus(NO_CONNECTION, EMBEDDER, prohibited.SOURCE)
    _provision(lambda: library.provision("art:5", lookup))
    library.guidance("a tool", lookup, language=Language.EN)


def high_risk_calls(lookup: Lookup) -> None:
    library = HighRiskCorpus(NO_CONNECTION, EMBEDDER)
    _provision(lambda: library.provision("annex:III:4:a", lookup))
    library.search("a tool", lookup, language=Language.EN, doc_type="guideline", limit=8)


def citation_calls(lookup: Lookup) -> None:
    citation = Citation(
        provision_id="art:6:3",
        document_id="ai-act-consolidated",
        law_version=LawVersion.AMENDED,
        language=Language.EN,
        quote="As quoted.",
    )
    assert resolve(citation, lookup, CorpusCitations(NO_CONNECTION)) is None


CALLERS: dict[str, tuple[ModuleType, Callable[[Lookup], None], set[str]]] = {
    "scope": (corpus, scope_calls, {"get_provision", "search_ai_act"}),
    "prohibited and transparency": (corpus, guideline_calls, {"get_provision", "search_ai_act"}),
    "high_risk": (corpus, high_risk_calls, {"get_provision", "search_ai_act"}),
    "citation validator": (citations, citation_calls, {"get_provision"}),
}
"""Every corpus library the engine reads through, the module that calls the retrieval functions
for it (the checks' libraries share `aiact.engine.nodes.corpus`), and which functions it calls.
(The facts and role checks call none: role quotes the parsed Act and the validator re-quotes
it.)"""


@pytest.mark.parametrize("name", sorted(CALLERS))
@pytest.mark.parametrize("include_held_out", [True, False])
def test_every_engine_corpus_call_passes_the_runs_opt_in(
    name: str, include_held_out: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, drive, expected = CALLERS[name]
    recorder = Recorder()
    for function in expected:
        monkeypatch.setattr(module, function, getattr(recorder, function))
    drive(replace(LOOKUP, include_held_out=include_held_out))
    assert {called for called, _ in recorder.flags} == expected
    assert all(flag is include_held_out for _, flag in recorder.flags)


def test_a_lookup_hides_held_out_examples_unless_told_otherwise() -> None:
    assert LOOKUP.include_held_out is False
