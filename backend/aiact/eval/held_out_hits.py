"""Held-out (Pile B) rows a stored run retrieved, read from its LangSmith traces (V8's DoD: the
gap run's traces show at least one, the reported run's none; decision 012).

Each lookup is a run of its own in the trace (`aiact.retrieval.tracing`): a search records the
provision ids it returned (`HIT_IDS`), a provision lookup the id it fetched (`PROVISION_ID`,
only when it resolved). A retrieved id counts as held out when a held-out row of the corpus has
it (`provisions.is_held_out`, read when the check runs). Traces that can't show it are counted
apart, never as "none retrieved": a trace LangSmith returns no runs for, one still being
ingested, and one with a search that recorded no hit ids (traced before V8 added them). A run
with no trace left to check is refused (`NoTraceToCheckError`). The report names counts only:
no case, no description, no example text.
"""

from collections.abc import Sequence
from uuid import UUID

import psycopg

from aiact.eval.metrics import Rate
from aiact.eval.tool_calls import (
    LookupTool,
    RunSource,
    StoredTraces,
    TraceRun,
    is_ingesting,
    stored_traces,
    trace_runs,
)
from aiact.retrieval import tracing as lookup_tracing
from aiact.schemas.base import ContractModel

HELD_OUT_IDS = "select distinct provision_id from provisions where is_held_out"


class NoTraceToCheckError(LookupError):
    """No trace of the stored run can show what it retrieved."""


class HeldOutHits(ContractModel):
    """What a stored run's traces show about the held-out rows they retrieved."""

    checked: int
    with_held_out: int
    held_out_ids: int
    """Distinct held-out provision ids retrieved over the whole run."""
    no_runs: int
    ingesting: int
    without_hit_ids: int
    untraced: int


def held_out_ids(conn: psycopg.Connection) -> frozenset[str]:
    """The provision ids of the corpus's held-out rows."""
    return frozenset(row[0] for row in conn.execute(HELD_OUT_IDS).fetchall())


def retrieved_ids(runs: Sequence[TraceRun]) -> frozenset[str] | None:
    """Every provision id the trace's lookups returned or fetched; None when a search recorded no
    hit ids, so the trace can't tell."""
    found: set[str] = set()
    for run in runs:
        if run.error is not None or run.name not in LookupTool:
            continue
        key = (
            lookup_tracing.HIT_IDS
            if run.name == LookupTool.SEARCH_AI_ACT
            else lookup_tracing.PROVISION_ID
        )
        value = run.metadata.get(key)
        if run.name == LookupTool.SEARCH_AI_ACT and not isinstance(value, list):
            return None
        if isinstance(value, str):
            found.add(value)
        elif isinstance(value, list):
            found.update(item for item in value if isinstance(item, str))
    return frozenset(found)


def count_hits(source: RunSource, stored: StoredTraces, held_out: frozenset[str]) -> HeldOutHits:
    """Read every trace of the run and count the ones that retrieved a held-out row."""
    checked = with_held_out = no_runs = ingesting = without_hit_ids = 0
    found: set[str] = set()
    for trace_id in stored.trace_ids:
        runs = trace_runs(source, trace_id)
        ids = retrieved_ids(runs) if runs and not is_ingesting(runs) else None
        if not runs:
            no_runs += 1
        elif is_ingesting(runs):
            ingesting += 1
        elif ids is None:
            without_hit_ids += 1
        else:
            checked += 1
            hits = ids & held_out
            with_held_out += bool(hits)
            found |= hits
    return HeldOutHits(
        checked=checked,
        with_held_out=with_held_out,
        held_out_ids=len(found),
        no_runs=no_runs,
        ingesting=ingesting,
        without_hit_ids=without_hit_ids,
        untraced=stored.untraced,
    )


def render_markdown(run_id: UUID, hits: HeldOutHits) -> str:
    share = Rate(hits=hits.with_held_out, total=hits.checked)
    lines = [
        f"## Held-out rows retrieved, run {run_id}",
        "",
        f"- Traces checked: {hits.checked}",
        f"- Traces that retrieved a held-out row: {hits.with_held_out} of {hits.checked}"
        f" ({share.percent})",
        f"- Distinct held-out rows retrieved: {hits.held_out_ids}",
        f"- Left out, a search without recorded hit ids: {hits.without_hit_ids} (traced before"
        " V8 recorded them)",
        f"- Left out, still being ingested: {hits.ingesting}",
        f"- Left out, no runs returned: {hits.no_runs} (expired, another workspace, or not yet"
        " ingested)",
        f"- Cases without a trace: {hits.untraced}",
    ]
    return "\n".join(lines) + "\n"


def held_out_report(conn: psycopg.Connection, source: RunSource, run_id: UUID) -> str:
    """The held-out rows a stored run retrieved, as markdown. Raises `NoTraceToCheckError` when
    no trace of the run can show it."""
    hits = count_hits(source, stored_traces(conn, run_id), held_out_ids(conn))
    if not hits.checked:
        raise NoTraceToCheckError(
            "no trace of this run can show what it retrieved"
            f" ({hits.no_runs} with no runs returned, {hits.ingesting} still being ingested,"
            f" {hits.without_hit_ids} with a search that recorded no hit ids,"
            f" {hits.untraced} cases without a trace)"
        )
    return render_markdown(run_id, hits)
