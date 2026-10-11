"""Tool-call correctness (V7; INIT > Metrics): did each engine step call the lookups it should
have, for example the prohibited step fetched Art. 5? Checked on the LangSmith traces of a stored
run, and reported as a rate per step.

- **What a step should look up** (`EXPECTED_LOOKUPS`) is stated here from the law, not read from
  the engine: scope reads the AI-system definition (Art. 3(1)) and Art. 2 and searches the
  definition guidelines; the prohibited check reads Art. 5 and searches its guidelines; the
  high-risk check reads every Annex III point and the Annex I list and searches the guidelines;
  transparency reads Art. 50 and searches its guidelines; the role check resolves a role
  definition (any of Art. 3(3), (4), (6), (7)), which the citation validator looks up.
- **What a step did look up** is read from its trace: every lookup is a run of its own
  (`aiact.retrieval.tracing`), with the provision id or the search's document filter as metadata,
  which a metadata-only trace keeps. A lookup belongs to the nearest step run above it. Only a
  lookup that succeeded counts: a lookup that found nothing fetched nothing.
- **The rate** of a step is the share of the traces where the step ran in which every expected
  lookup was made. A step that didn't run (the run ended early) isn't counted. The report also
  counts, per expected lookup, the traces that missed it.
- **Only traces that can be scored.** A trace LangSmith returns no runs for (expired, another
  workspace, not yet ingested) and a trace without a single lookup run (recorded before lookups
  were traced, or not fully ingested) would read as a step that skipped its lookups, so both are
  counted apart and left out of the rates. So is a trace with a lookup run that has no end time
  yet: a lookup's metadata arrives with its end, so until then it would read as a lookup of
  nothing. A stored run with no trace left to score is refused (`NoLookupRunsError`).

Traces are read with only the fields the check needs (never a run's inputs or outputs, which a
development trace carries in full), and the report names no case and quotes no description.
"""

from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

import psycopg
from langsmith import Client
from langsmith.schemas import Run
from pydantic import Field, JsonValue, ValidationError

from aiact.eval.metrics import Rate
from aiact.retrieval import tracing as lookup_tracing
from aiact.schemas import STEP_ORDER, StepName
from aiact.schemas.base import ContractModel
from aiact.settings import Settings


class LookupTool(StrEnum):
    """The lookups a step can make, by the name of their trace run."""

    GET_PROVISION = "get_provision"
    GET_OMNIBUS_PROVISION = "get_omnibus_provision"
    SEARCH_AI_ACT = "search_ai_act"


SELECTED_FIELDS: tuple[str, ...] = (
    "id",
    "trace_id",
    "name",
    "run_type",
    "start_time",
    "end_time",
    "parent_run_id",
    "error",
    "extra",
)
"""The run fields read from LangSmith: what the check reads, plus `run_type` and `start_time`,
which a `langsmith.schemas.Run` requires; never `inputs` or `outputs`. `end_time` tells a run
whose end (with a lookup's metadata) has been ingested."""


class TraceRun(ContractModel):
    """One run of a trace, reduced to what the check reads."""

    id: str
    parent_run_id: str | None = None
    name: str
    error: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    has_ended: bool = True
    """False while the run's end (its error and a lookup's metadata) isn't ingested."""


@dataclass(frozen=True)
class LookupCall:
    """One lookup a step made: the provision id it fetched, or the documents and document types
    a search was limited to."""

    tool: LookupTool
    targets: frozenset[str]
    succeeded: bool


class ExpectedLookup(ContractModel):
    """A lookup a step should make: `tool` reaching any of `targets` (all of them with
    `needs_all`)."""

    label: str
    tool: LookupTool
    targets: frozenset[str]
    needs_all: bool = False

    def is_met(self, calls: Collection[LookupCall]) -> bool:
        reached = frozenset[str]().union(
            *(call.targets for call in calls if call.tool is self.tool and call.succeeded)
        )
        return self.targets <= reached if self.needs_all else bool(self.targets & reached)


ANNEX_III_POINTS: frozenset[str] = frozenset(
    f"annex:III:{point}"
    for point in (
        *("1:a", "1:b", "1:c", "2", "3:a", "3:b", "3:c", "3:d", "4:a", "4:b"),
        *("5:a", "5:b", "5:c", "5:d", "6:a", "6:b", "6:c", "6:d", "6:e"),
        *("7:a", "7:b", "7:c", "7:d", "8:a", "8:b"),
    )
)
"""Every Annex III point a use can fall under (the leaves of the annex)."""
ANNEX_I_POINTS: frozenset[str] = frozenset(
    {*(f"annex:I:A:{n}" for n in range(1, 13)), *(f"annex:I:B:{n}" for n in range(13, 22))}
)
"""Every Annex I point either law version may have (the Omnibus renumbered machinery)."""
ROLE_DEFINITIONS = frozenset({"art:3:3", "art:3:4", "art:3:6", "art:3:7"})
"""Provider, deployer, importer, distributor."""


def _fetched(label: str, *ids: str, needs_all: bool = False) -> ExpectedLookup:
    return ExpectedLookup(
        label=label, tool=LookupTool.GET_PROVISION, targets=frozenset(ids), needs_all=needs_all
    )


def _searched(label: str, *within: str) -> ExpectedLookup:
    return ExpectedLookup(label=label, tool=LookupTool.SEARCH_AI_ACT, targets=frozenset(within))


EXPECTED_LOOKUPS: Mapping[StepName, tuple[ExpectedLookup, ...]] = {
    StepName.SCOPE: (
        _fetched("Art. 3(1) fetched", "art:3:1"),
        _fetched("Art. 2 fetched", "art:2"),
        _searched("definition guidelines searched", "guide-definition"),
    ),
    StepName.PROHIBITED: (
        _fetched("Art. 5 fetched", "art:5"),
        _searched("prohibited-practice guidelines searched", "guide-prohibited"),
    ),
    StepName.HIGH_RISK: (
        _fetched("every Annex III point fetched", *ANNEX_III_POINTS, needs_all=True),
        _fetched("Annex I fetched", *ANNEX_I_POINTS),
        _searched("guidelines searched", "guideline"),
    ),
    StepName.TRANSPARENCY: (
        _fetched("Art. 50 fetched", "art:50"),
        _searched("Art. 50 guidelines searched", "guide-art50"),
    ),
    StepName.ROLE_OBLIGATIONS: (_fetched("role definition (Art. 3) fetched", *ROLE_DEFINITIONS),),
}
"""What each step should look up (the module docstring gives the reasons)."""


class StepCheck(ContractModel):
    """One step of one trace: the expected lookups it missed."""

    step: StepName
    missing: tuple[str, ...]

    @property
    def is_correct(self) -> bool:
        return not self.missing


class StepRate(ContractModel):
    """A step's tool-call correctness over the traces where it ran."""

    step: StepName
    rate: Rate
    missed: dict[str, int]
    """Per expected lookup (its label), the traces that missed it."""


class TraceRecordError(ValueError):
    """A trace run doesn't hold what the check expects; the message names the run."""


def lookup_call(run: TraceRun) -> LookupCall | None:
    """The lookup `run` made, or None when it isn't a lookup."""
    if run.name not in LookupTool:
        return None
    tool = LookupTool(run.name)
    keys = (
        (lookup_tracing.DOC_KEYS, lookup_tracing.DOC_TYPES)
        if tool is LookupTool.SEARCH_AI_ACT
        else (lookup_tracing.PROVISION_ID,)
    )
    targets: set[str] = set()
    for key in keys:
        targets |= _strings(run, run.metadata.get(key))
    return LookupCall(tool=tool, targets=frozenset(targets), succeeded=run.error is None)


def _strings(run: TraceRun, value: JsonValue) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return {item for item in value if isinstance(item, str)}
    raise TraceRecordError(f"lookup run {run.id} has malformed metadata {value!r}")


def step_lookups(runs: Sequence[TraceRun]) -> dict[StepName, tuple[LookupCall, ...]]:
    """Every step that ran in the trace, with the lookups made under it."""
    by_id = {run.id: run for run in runs}
    found: dict[StepName, list[LookupCall]] = {
        StepName(run.name): [] for run in runs if run.name in StepName
    }
    for run in runs:
        call = lookup_call(run)
        step = _owning_step(run, by_id) if call is not None else None
        if call is not None and step is not None:
            found[step].append(call)
    return {step: tuple(calls) for step, calls in found.items()}


def _owning_step(run: TraceRun, by_id: Mapping[str, TraceRun]) -> StepName | None:
    """The nearest step run above `run`, or None when no step holds it."""
    seen: set[str] = set()
    parent_id = run.parent_run_id
    while parent_id is not None and parent_id in by_id and parent_id not in seen:
        seen.add(parent_id)
        parent = by_id[parent_id]
        if parent.name in StepName:
            return StepName(parent.name)
        parent_id = parent.parent_run_id
    return None


def check_trace(runs: Sequence[TraceRun]) -> tuple[StepCheck, ...]:
    """Each step that ran, in the check order, with the expected lookups it missed."""
    lookups = step_lookups(runs)
    return tuple(
        StepCheck(
            step=step,
            missing=tuple(
                expected.label
                for expected in EXPECTED_LOOKUPS[step]
                if not expected.is_met(lookups[step])
            ),
        )
        for step in STEP_ORDER
        if step in lookups
    )


def step_rates(checks: Iterable[StepCheck]) -> tuple[StepRate, ...]:
    """The rate per step over all `checks`, in the check order; a step that never ran has 0/0."""
    by_step: dict[StepName, list[StepCheck]] = {step: [] for step in STEP_ORDER}
    for check in checks:
        by_step[check.step].append(check)
    return tuple(_rate(step, by_step[step]) for step in STEP_ORDER)


def _rate(step: StepName, checks: Sequence[StepCheck]) -> StepRate:
    missed = Counter(label for check in checks for label in check.missing)
    return StepRate(
        step=step,
        rate=Rate(hits=sum(check.is_correct for check in checks), total=len(checks)),
        missed={e.label: missed[e.label] for e in EXPECTED_LOOKUPS[step] if missed[e.label]},
    )


class TraceCounts(ContractModel):
    """How a stored run's cases split into scored traces and the ones left out."""

    scored: int = Field(ge=0)
    no_lookups: int = Field(ge=0, description="Traces with runs but no lookup run.")
    ingesting: int = Field(ge=0, description="Traces with a lookup run that has no end yet.")
    no_runs: int = Field(ge=0, description="Traces LangSmith returned no runs for.")
    untraced: int = Field(ge=0, description="Cases stored without a trace id.")


def render_markdown(run_id: UUID, rates: Sequence[StepRate], counts: TraceCounts) -> str:
    lines = [
        f"## Tool-call correctness, run {run_id}",
        "",
        f"- Traces scored: {counts.scored}",
        f"- Left out, no lookup run: {counts.no_lookups} (recorded before lookups were traced,"
        " or not fully ingested)",
        f"- Left out, still being ingested: {counts.ingesting} (a lookup run has no end yet)",
        f"- Left out, no runs returned: {counts.no_runs} (expired, another workspace, or not yet"
        " ingested)",
        f"- Cases without a trace: {counts.untraced}",
        "",
        "| Step | Correct | Count | Missed |",
        "| --- | ---: | ---: | --- |",
        *(_row(rate) for rate in rates),
    ]
    return "\n".join(lines) + "\n"


def _row(rate: StepRate) -> str:
    missed = "; ".join(f"{label} ({count})" for label, count in rate.missed.items())
    cells = (rate.step.value, rate.rate.percent, f"{rate.rate.hits}/{rate.rate.total}", missed)
    return f"| {' | '.join(cells)} |"


# --- Reading the traces -------------------------------------------------------------------------


class RunSource(Protocol):
    """Where a trace's runs come from (`langsmith.Client`, or a recording in tests)."""

    def list_runs(self, *, trace_id: str, select: Sequence[str]) -> Iterable[Run]: ...


class TracingNotConfiguredError(RuntimeError):
    """No LangSmith key is set, so no trace can be read."""


def langsmith_source(settings: Settings) -> Client:
    """A LangSmith client to read traces with. Raises `TracingNotConfiguredError` without a key."""
    key = settings.langsmith_api_key
    if key is None or not key.get_secret_value():
        raise TracingNotConfiguredError("LANGSMITH_API_KEY is not set; no trace can be read")
    return Client(api_key=key.get_secret_value(), api_url=settings.langsmith_endpoint or None)


class StoredTraces(ContractModel):
    """The trace ids a stored run recorded, and how many of its cases had none."""

    trace_ids: tuple[str, ...]
    untraced: int


class RunNotFoundError(LookupError):
    """No `eval_case_results` row has the requested run id."""


class NoLookupRunsError(LookupError):
    """No trace of the stored run can be scored, so no step has a rate."""


def stored_traces(conn: psycopg.Connection, run_id: UUID) -> StoredTraces:
    """The trace ids of a stored run's cases, in case order. Raises `RunNotFoundError` for a run
    with no cases."""
    rows = conn.execute(
        "select trace_id from eval_case_results where run_id = %s order by case_id", (run_id,)
    ).fetchall()
    if not rows:
        raise RunNotFoundError(f"no stored cases for run {run_id}")
    trace_ids = tuple(row[0] for row in rows if row[0])
    return StoredTraces(trace_ids=trace_ids, untraced=len(rows) - len(trace_ids))


def trace_runs(source: RunSource, trace_id: str) -> tuple[TraceRun, ...]:
    """The runs of one trace, as the check reads them. Raises `TraceRecordError` (naming only the
    error type: a run's fields may quote what was traced) when a run can't be read."""
    # `list_runs` is deprecated and removed after 31 Jan 2027; its replacement is
    # `client.traces.list_runs` (async, needs the project id).
    runs = source.list_runs(trace_id=trace_id, select=SELECTED_FIELDS)
    try:
        return tuple(_trace_run(run) for run in runs)
    except ValidationError as error:
        raise TraceRecordError(
            f"trace {trace_id}: a run could not be read ({type(error).__name__})"
        ) from error


def _trace_run(run: Run) -> TraceRun:
    metadata = (run.extra or {}).get("metadata")
    return TraceRun(
        id=str(run.id),
        parent_run_id=None if run.parent_run_id is None else str(run.parent_run_id),
        name=run.name,
        error=run.error,
        metadata=metadata if isinstance(metadata, dict) else {},
        has_ended=run.end_time is not None,
    )


def has_lookup_runs(runs: Sequence[TraceRun]) -> bool:
    return any(run.name in LookupTool for run in runs)


def is_ingesting(runs: Sequence[TraceRun]) -> bool:
    """Whether a lookup run of the trace has no end yet (its metadata comes with the end)."""
    return any(run.name in LookupTool and not run.has_ended for run in runs)


def check_traces(
    source: RunSource, stored: StoredTraces
) -> tuple[tuple[StepCheck, ...], TraceCounts]:
    """The step checks of every trace that can be scored, and how the traces split."""
    checks: list[StepCheck] = []
    no_runs = no_lookups = ingesting = 0
    for trace_id in stored.trace_ids:
        runs = trace_runs(source, trace_id)
        if not runs:
            no_runs += 1
        elif not has_lookup_runs(runs):
            no_lookups += 1
        elif is_ingesting(runs):
            ingesting += 1
        else:
            checks.extend(check_trace(runs))
    counts = TraceCounts(
        scored=len(stored.trace_ids) - no_runs - no_lookups - ingesting,
        no_lookups=no_lookups,
        ingesting=ingesting,
        no_runs=no_runs,
        untraced=stored.untraced,
    )
    return tuple(checks), counts


def tool_call_report(conn: psycopg.Connection, source: RunSource, run_id: UUID) -> str:
    """The per-step tool-call correctness of a stored run, as markdown. Raises
    `NoLookupRunsError` when no trace of the run can be scored."""
    checks, counts = check_traces(source, stored_traces(conn, run_id))
    if not counts.scored:
        raise NoLookupRunsError(
            "no lookup runs in these traces: LangSmith returned no runs for them (expired, another"
            " workspace, or not yet ingested), no case got past the facts step, every case was"
            " stored without a trace id, or the traces were recorded before tool-call tracing"
            f" ({counts.no_runs} with no runs returned, {counts.no_lookups} without a lookup run,"
            f" {counts.ingesting} still being ingested, {counts.untraced} cases without a trace)"
        )
    return render_markdown(run_id, step_rates(checks), counts)
