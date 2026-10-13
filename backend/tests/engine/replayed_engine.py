"""The engine as INIT's worked example was recorded (E10), for every replay of a whole run: the
worked example's own test, the runs the end-to-end tests record (`tests/e2e/test_e2e_runs.py`) and
the API those tests run against (`tests/e2e/replay_server.py`). One place, so a run is recorded
under the settings it is replayed with.

- `luna_settings`: the engine on Luna, and no LangSmith key.
- `recorded_libraries`: every check's corpus calls over one `CorpusRecording` (`live_corpus` answers
  them while recording).
- `replayed_nodes`: the engine's own nodes over those libraries, citations checked against the
  corpus built from `data/parsed/` (E9).
"""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial

from aiact.db import connect
from aiact.engine.classify import CorpusLibraries, NodeBuilder, engine_nodes
from aiact.engine.nodes import prohibited, transparency
from aiact.engine.nodes.common import Lookup
from aiact.engine.nodes.guideline_retrieval import GuidelineCorpus
from aiact.engine.nodes.high_risk_retrieval import HighRiskCorpus
from aiact.engine.nodes.scope import CorpusLibrary
from aiact.llm import OpenRouterEmbeddings
from aiact.retrieval.provisions import Provision
from aiact.retrieval.search import SearchHit
from aiact.schemas import Language, StepName
from aiact.settings import Settings
from tests.engine.built_corpus import built_validator
from tests.engine.nodes.corpus_recording import CorpusRecording, lookup_call

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"


def luna_settings(settings: Settings) -> Settings:
    """`settings` with the engine on Luna, and no LangSmith key: a recording run sends no trace
    (the run then switches tracing off, so none reaches the cassette)."""
    return settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER, "langsmith_api_key": None}
    )


@dataclass(frozen=True)
class LiveCorpus:
    """The live corpus libraries of every check, over one connection (recording only)."""

    scope: CorpusLibrary
    prohibited: GuidelineCorpus
    high_risk: HighRiskCorpus
    transparency: GuidelineCorpus


@contextmanager
def live_corpus(settings: Settings) -> Iterator[LiveCorpus]:
    """The corpus in the database `aiact.db.connect` reaches, with `settings`' embeddings."""
    embedder = OpenRouterEmbeddings(settings=settings)
    with connect() as connection:
        yield LiveCorpus(
            scope=CorpusLibrary(connection, embedder),
            prohibited=GuidelineCorpus(connection, embedder, prohibited.SOURCE),
            high_risk=HighRiskCorpus(connection, embedder),
            transparency=GuidelineCorpus(connection, embedder, transparency.SOURCE),
        )


class Recorded:
    """One check's corpus calls over the run's `CorpusRecording`. A lookup gives the same row
    whichever check asks; a search is keyed by its check too."""

    def __init__(self, recording: CorpusRecording[LiveCorpus], node: StepName) -> None:
        self._recording = recording
        self._node = node

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        return self._recording.provision(
            provision_id, lookup, lambda live: live.scope.provision(provision_id, lookup)
        )

    def _hits(
        self,
        call: Mapping[str, object],
        lookup: Lookup,
        ask: Callable[[LiveCorpus], tuple[SearchHit, ...]],
    ) -> tuple[SearchHit, ...]:
        return self._recording.hits({"node": self._node.value, **call, **lookup_call(lookup)}, ask)


class RecordedScope(Recorded):
    def definition_guidance(self, query: str, lookup: Lookup) -> tuple[SearchHit, ...]:
        return self._hits(
            {"definition_guidance": query},
            lookup,
            lambda live: live.scope.definition_guidance(query, lookup),
        )


class RecordedGuidance(Recorded):
    def guidance(self, query: str, lookup: Lookup, *, language: Language) -> tuple[SearchHit, ...]:
        def ask(live: LiveCorpus) -> tuple[SearchHit, ...]:
            library = live.prohibited if self._node is StepName.PROHIBITED else live.transparency
            return library.guidance(query, lookup, language=language)

        return self._hits({"guidance": query, "language": language}, lookup, ask)


class RecordedHighRisk(Recorded):
    def search(
        self, query: str, lookup: Lookup, *, language: Language, doc_type: str, limit: int
    ) -> tuple[SearchHit, ...]:
        call = {"search": query, "language": language, "doc_type": doc_type, "limit": limit}

        def ask(live: LiveCorpus) -> tuple[SearchHit, ...]:
            return live.high_risk.search(
                query, lookup, language=language, doc_type=doc_type, limit=limit
            )

        return self._hits(call, lookup, ask)


def recorded_libraries(recording: CorpusRecording[LiveCorpus]) -> CorpusLibraries:
    return CorpusLibraries(
        scope=RecordedScope(recording, StepName.SCOPE),
        prohibited=RecordedGuidance(recording, StepName.PROHIBITED),
        high_risk=RecordedHighRisk(recording, StepName.HIGH_RISK),
        transparency=RecordedGuidance(recording, StepName.TRANSPARENCY),
    )


def replayed_nodes(recording: CorpusRecording[LiveCorpus]) -> NodeBuilder:
    """The engine's own nodes over `recording`'s corpus answers, citations checked against the
    built corpus."""
    return partial(
        engine_nodes, libraries=recorded_libraries(recording), validator=built_validator()
    )
