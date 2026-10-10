"""X1b: calibrate search's relevance cut-off (`SEARCH_MAX_DISTANCE`, `SEARCH_MIN_KEYWORD_IDF`;
C8, decision 003) on what Q&A and MCP search: the default query instruction, the whole corpus.

Four kinds of probe, each searched once with its vector embedded once:
- **answerable**: the answerable Q&A questions (B7), with the provisions an answer must cite;
- **description**: the Annex-matching descriptions (X0), the longest queries a search can get;
- **unanswerable**: B7's unanswerable questions, reported per tag (`unanswerable:other_law`,
  `national_law`, `off_topic`);
- **off_topic**: the short strings in `OFF_TOPIC_PROBES`, in English and German.

For each probe the run stores what decides `found` (`SearchResults.found`):
- `best_similarity`: the top meaning-arm similarity, without a cut-off. A cut-off `d` keeps a
  meaning-arm hit when its similarity is at least `1 - d`, and the top one is always among the
  hits returned (its score beats any keyword-only row's), so `found` holds for it exactly then.
- `top_keyword_idf`: the best keyword-arm row's summed IDF, from a search that cuts every
  meaning-arm row (`max_distance=0`), so the keyword rows rank alone and the best comes first.
- `is_named`: the query names a provision the corpus has (`exact_references`), always found.
`is_found` combines them for any pair of values, so one run sweeps every candidate. A real
search with the configured settings stores `found` beside it, as a check. For answerable items
the run also stores provision recall in the top `TOP_K` (V6's measure) at every candidate
distance, since a cut-off can drop a required provision ranked low without making the query
unfound.

It costs only the query embeddings (about $0.0002 for the whole set).
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from statistics import median
from uuid import UUID

import psycopg
from pydantic import JsonValue

from aiact.engine.usage import UsageMeter
from aiact.eval.cases import BenchmarkCase, QAItem
from aiact.eval.experiments.embeddings import Search, is_over_budget
from aiact.eval.ragas_metrics import embedding_config, provision_recall
from aiact.eval.runner import CaseRecord, RunStatus, RunStore, finish_after_failure
from aiact.llm.embeddings import OpenRouterEmbeddings
from aiact.retrieval.search import DEFAULT_LIMIT, QueryEmbedder, SearchResults, search_ai_act
from aiact.schemas import Language
from aiact.settings import Settings

logger = logging.getLogger(__name__)

BENCHMARK = "search_cutoff"
SEARCH_NODE = "search"
TOP_K = 5
"""Hits an answer is grounded on (V6's baseline), for the recall under a cut-off."""
DISTANCES: tuple[float, ...] = tuple(round(0.20 + 0.01 * step, 2) for step in range(21))
"""Candidate cut-offs, 0.20 to 0.40 (similarity 0.80 to 0.60)."""
KEYWORD_IDFS: tuple[float, ...] = (9.0, 12.0, 15.0, 18.0, 21.0, 24.0, 27.0, 30.0)
"""Candidate `SEARCH_MIN_KEYWORD_IDF` values (C8's guess was 9)."""
DEFAULT_MAX_COST_USD = 0.01

OFF_TOPIC_PROBES: tuple[tuple[str, Language, str], ...] = (
    ("probe-off-en-joke", Language.EN, "tell me a joke"),
    ("probe-off-en-holiday", Language.EN, "best holiday destinations in Spain"),
    ("probe-off-en-football", Language.EN, "football results"),
    ("probe-off-en-pie", Language.EN, "How do I bake an apple pie without eggs?"),
    ("probe-off-en-vat", Language.EN, "What is the VAT rate on restaurant meals in Italy?"),
    ("probe-off-en-printer", Language.EN, "Why does my printer keep jamming?"),
    ("probe-off-en-rent", Language.EN, "Can my landlord raise the rent twice in one year?"),
    ("probe-off-en-keys", Language.EN, "asdf qwerty zxcv"),
    ("probe-off-de-wetter", Language.DE, "Wie wird das Wetter morgen in Berlin?"),
    ("probe-off-de-rezept", Language.DE, "Rezept für Käsespätzle"),
    ("probe-off-de-zug", Language.DE, "Wann fährt der nächste Zug nach Hamburg?"),
    ("probe-off-de-steuer", Language.DE, "Bis wann muss ich meine Steuererklärung abgeben?"),
    ("probe-off-de-witz", Language.DE, "Erzähl mir einen Witz"),
    ("probe-off-de-urlaub", Language.DE, "Wie viele Urlaubstage stehen mir gesetzlich zu?"),
)
"""Off-topic strings (C8's three, and more of the kind), not benchmark cases: (id, language,
text)."""


class ProbeKind(StrEnum):
    ANSWERABLE = "answerable"
    DESCRIPTION = "description"
    UNANSWERABLE = "unanswerable"
    OFF_TOPIC = "off_topic"


@dataclass(frozen=True)
class Probe:
    id: str
    text: str
    language: Language
    kind: ProbeKind
    group: str
    """What the report groups by: the kind, or an unanswerable item's tag."""
    targets: tuple[str, ...] = ()
    """The provisions an answerable item's answer must cite."""


def build_probes(
    qa_items: Sequence[QAItem], annex_cases: Sequence[BenchmarkCase]
) -> tuple[Probe, ...]:
    """Every probe, in kind order, each kind in id order."""
    items = sorted(qa_items, key=lambda item: item.id)
    answerable = [
        Probe(item.id, item.question, item.language, ProbeKind.ANSWERABLE,
              ProbeKind.ANSWERABLE.value, item.required_provision_ids)
        for item in items if item.answerable
    ]  # fmt: skip
    descriptions = [
        Probe(case.id, case.description, case.language, ProbeKind.DESCRIPTION,
              ProbeKind.DESCRIPTION.value)
        for case in sorted(annex_cases, key=lambda case: case.id)
    ]  # fmt: skip
    unanswerable = [
        Probe(item.id, item.question, item.language, ProbeKind.UNANSWERABLE, _tag(item))
        for item in items if not item.answerable
    ]  # fmt: skip
    off_topic = [
        Probe(probe_id, text, language, ProbeKind.OFF_TOPIC, ProbeKind.OFF_TOPIC.value)
        for probe_id, language, text in OFF_TOPIC_PROBES
    ]
    return (*answerable, *descriptions, *unanswerable, *off_topic)


def _tag(item: QAItem) -> str:
    """The item's `unanswerable:*` tag, or `unanswerable` when it has none."""
    return next((tag for tag in item.tags if tag.startswith("unanswerable:")), "unanswerable")


class OnceEmbedder:
    """A `QueryEmbedder` that embeds each text once: every probe is searched several times."""

    def __init__(self, inner: QueryEmbedder) -> None:
        self._inner = inner
        self._vectors: dict[str, list[float]] = {}
        self.model = inner.model
        self.dimensions = inner.dimensions

    def embed_query(self, text: str) -> list[float]:
        if text not in self._vectors:
            self._vectors[text] = self._inner.embed_query(text)
        return self._vectors[text]


@dataclass(frozen=True)
class Measurement:
    best_similarity: float | None
    top_keyword_idf: float | None
    is_named: bool
    found: bool
    """`SearchResults.found` of a real search with the configured cut-off and IDF."""
    recall_by_distance: Mapping[float, float] = field(default_factory=dict)
    """Answerable items: provision recall in the top `TOP_K` at each candidate distance."""


def is_found(measurement: Measurement, max_distance: float, min_keyword_idf: float) -> bool:
    """What `SearchResults.found` is for the probe under this cut-off and IDF."""
    similarity = measurement.best_similarity
    idf = measurement.top_keyword_idf
    return (
        measurement.is_named
        or (similarity is not None and similarity >= 1 - max_distance)
        or (idf is not None and idf >= min_keyword_idf)
    )


def measure(
    probe: Probe,
    embedder: QueryEmbedder,
    connection: psycopg.Connection,
    settings: Settings,
    distances: Sequence[float] = DISTANCES,
    search: Search = search_ai_act,
) -> Measurement:
    """Search the probe without a cut-off, with every meaning-arm row cut, with the configured
    settings and (answerable items) at each candidate distance."""

    def run(max_distance: float | None, limit: int = DEFAULT_LIMIT) -> SearchResults:
        return search(probe.text, probe.language, max_distance=max_distance, limit=limit,
                      embedder=embedder, connection=connection)  # fmt: skip

    uncut = run(None)
    similarities = [hit.similarity for hit in uncut.hits if hit.similarity is not None]
    keyword_only = run(0.0)
    idfs = [hit.keyword_idf for hit in keyword_only.hits if hit.keyword_idf is not None]
    configured = run(settings.search_max_distance)
    found = _found_under(configured, settings.search_min_keyword_idf)
    recall = (
        {d: provision_recall(probe.targets, run(d, TOP_K).hits) for d in distances}
        if probe.kind is ProbeKind.ANSWERABLE
        else {}
    )
    return Measurement(
        best_similarity=max(similarities) if similarities else None,
        top_keyword_idf=max(idfs) if idfs else None,
        is_named=any(hit.reference_rank is not None for hit in uncut.hits),
        found=found,
        recall_by_distance=recall,
    )


def _found_under(results: SearchResults, min_keyword_idf: float) -> bool:
    """`SearchResults.found`, with the IDF of the run's `settings` rather than the process's (the
    cut-off was passed to the search itself)."""
    return any(
        hit.reference_rank is not None
        or hit.similarity is not None
        or (hit.keyword_idf or 0.0) >= min_keyword_idf
        for hit in results.hits
    )


@dataclass(frozen=True)
class Calibration:
    run_id: UUID
    status: RunStatus
    probes: tuple[Probe, ...]
    measurements: Mapping[str, Measurement]
    cost_usd: float
    tokens: int


def run_calibration(
    probes: Sequence[Probe],
    embeddings: OpenRouterEmbeddings,
    store: RunStore,
    connection: psycopg.Connection,
    settings: Settings,
    *,
    git_sha: str,
    is_git_dirty: bool = False,
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
    search: Search = search_ai_act,
) -> Calibration:
    """Measure every probe and record the run (benchmark `search_cutoff`, one row per probe).
    Before each probe the cap is checked; a probe whose embedding fails stops the run."""
    meter = UsageMeter()
    embedder = OnceEmbedder(meter.embedder(SEARCH_NODE, embeddings))
    config = _config(embeddings, settings, is_git_dirty, max_cost_usd)
    run_id = store.start_run(git_sha, BENCHMARK, config)
    measurements: dict[str, Measurement] = {}
    status = RunStatus.COMPLETED
    try:
        for probe in probes:
            if is_over_budget(meter, max_cost_usd):
                status = RunStatus.COST_CAP_REACHED
                break
            before = meter.usage()
            measurement = measure(probe, embedder, connection, settings, search=search)
            after = meter.usage()
            spent = (after.cost_usd - before.cost_usd, after.tokens - before.tokens)
            store.add_case(run_id, _record(probe, measurement, *spent))
            measurements[probe.id] = measurement
    except BaseException:
        finish_after_failure(store, run_id, _outcome(RunStatus.INTERRUPTED, probes, measurements,
                                                     meter, settings))  # fmt: skip
        raise
    store.finish_run(run_id, _outcome(status, probes, measurements, meter, settings))
    usage = meter.usage()
    return Calibration(run_id, status, tuple(probes), measurements, usage.cost_usd, usage.tokens)


def _config(
    embeddings: OpenRouterEmbeddings, settings: Settings, is_git_dirty: bool, max_cost_usd: float
) -> dict[str, JsonValue]:
    return {
        "model": None,
        "embedding": embedding_config(embeddings),
        "retrieval": {
            "search": "search_ai_act",
            "top_k": TOP_K,
            "max_distance": settings.search_max_distance,
            "min_keyword_idf": settings.search_min_keyword_idf,
            "distances": list(DISTANCES),
            "keyword_idfs": list(KEYWORD_IDFS),
        },
        "max_cost_usd": max_cost_usd,
        "git_dirty": is_git_dirty,
        "outcome": {"status": RunStatus.RUNNING.value},
    }


def _record(probe: Probe, measurement: Measurement, cost_usd: float, tokens: int) -> CaseRecord:
    recall: dict[str, float | bool | None] = {
        f"recall_at_{distance:.2f}": value
        for distance, value in measurement.recall_by_distance.items()
    }
    return CaseRecord(
        case_id=probe.id,
        predicted={},
        label={
            "kind": probe.kind.value,
            "group": probe.group,
            "language": probe.language.value,
            "targets": list(probe.targets),
        },
        scores={
            "best_similarity": measurement.best_similarity,
            "top_keyword_idf": measurement.top_keyword_idf,
            "is_named": measurement.is_named,
            "found": measurement.found,
            **recall,
            "is_error": False,
        },
        trace_id=None,
        cost_usd=cost_usd,
        tokens=tokens,
    )


def _outcome(
    status: RunStatus,
    probes: Sequence[Probe],
    measurements: Mapping[str, Measurement],
    meter: UsageMeter,
    settings: Settings,
) -> dict[str, JsonValue]:
    usage = meter.usage()
    measured = [probe for probe in probes if probe.id in measurements]
    distance = settings.search_max_distance
    return {
        "status": status.value,
        "finished_at": datetime.now(UTC).isoformat(),
        "cases_planned": len(probes),
        "cases_scored": len(measurements),
        "cost_usd": usage.cost_usd,
        "tokens": usage.tokens,
        "is_cost_complete": usage.is_cost_complete,
        "distributions": distributions(measured, measurements),
        "found_share_at_settings": (
            found_shares(measured, measurements, distance, settings.search_min_keyword_idf)
            if distance is not None
            else None
        ),
    }


def distributions(
    probes: Sequence[Probe], measurements: Mapping[str, Measurement]
) -> dict[str, JsonValue]:
    """Per group and language: count, min / median / max best similarity and top keyword IDF."""
    groups: dict[str, list[Measurement]] = {}
    for probe in probes:
        for key in (probe.group, f"{probe.group}/{probe.language.value}"):
            groups.setdefault(key, []).append(measurements[probe.id])
    return {key: _spread(values) for key, values in sorted(groups.items())}


def _spread(values: Sequence[Measurement]) -> dict[str, JsonValue]:
    similarities = [m.best_similarity for m in values if m.best_similarity is not None]
    idfs = [m.top_keyword_idf or 0.0 for m in values]
    return {
        "n": len(values),
        "similarity": _three(similarities),
        "keyword_idf": _three(idfs),
    }


def _three(values: Sequence[float]) -> list[JsonValue]:
    """[min, median, max], rounded; empty when there are none."""
    if not values:
        return []
    return [round(min(values), 3), round(median(values), 3), round(max(values), 3)]


def found_shares(
    probes: Sequence[Probe],
    measurements: Mapping[str, Measurement],
    max_distance: float,
    min_keyword_idf: float,
) -> dict[str, JsonValue]:
    """Per group: the share of its probes found under this cut-off and IDF."""
    groups: dict[str, list[bool]] = {}
    for probe in probes:
        verdict = is_found(measurements[probe.id], max_distance, min_keyword_idf)
        groups.setdefault(probe.group, []).append(verdict)
    return {group: round(sum(v) / len(v), 3) for group, v in sorted(groups.items())}


def mean_recall(
    probes: Sequence[Probe], measurements: Mapping[str, Measurement], max_distance: float
) -> float | None:
    """Answerable items' mean provision recall in the top `TOP_K` under the cut-off."""
    values = [
        measurements[probe.id].recall_by_distance[max_distance]
        for probe in probes
        if probe.kind is ProbeKind.ANSWERABLE
        and max_distance in measurements[probe.id].recall_by_distance
    ]
    return sum(values) / len(values) if values else None
