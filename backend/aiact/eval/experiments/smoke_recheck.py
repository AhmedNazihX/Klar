"""The served-provider check, made again on smoke runs already stored (X2; decision 023 addendum).

In X2's paid run (2026-10-01), 25 probes replied in full but were stored as failed because their
generation record didn't show up within the ~18 s lookup (`predicted.not_pinned` = "generation …
not found after 12 attempts"). `aiact evaluate smoke-recheck` looks those records up again, with
the run's long window (`generations.DEFERRED_BUDGET_SECONDS`), and makes no model call.

Only completed runs are rechecked, and every run named is read and checked before any lookup or
write. A failed probe is rechecked only when its lookup was the one thing that failed it: its
`not_pinned` is a lookup a later try may settle (a record not found, a transport error, a 5xx or
a 429: `generations.may_come_later`), it has no `provider_error`, and its reply is one the run
would have kept, read from the stored `predicted` exactly as the live path classed it:
- an `error` whose type is a node's output error or a `ValidationError` (`BROKEN_ERROR_TYPES`) is
  a **broken** answer (a reply cut off by the output cap raises one of these, so it stays broken);
- an `error` of any other type (a transport, provider or database error) was never an answer, so
  the probe is not rechecked;
- no `error`: the stored outcome is the **answer**; it is read back into the node's outcome model
  and scored with the shared matchers against the case's label, as `smoke.is_correct` scores it;
- no `error`, but the node's refusal outcome (X2b): a **refused** probe, unscored. It is read
  from the stored row without re-validating it: a refusal stored before decision 030 carries
  the findings decision 029 assumed, which the outcome model now rejects.

Every call confirmed on the arm's pinned provider (the same exact-name check as the live path,
`smoke_served.settle`): the probe gets the score its reply earns, and `predicted.smoke.recheck`
keeps the audit trail. Shown served by another provider: it stays failed, with that provider in
`not_pinned`. Still not readable: the row is left as it is. A confirmed or
other-provider row no longer qualifies, so running the recheck again changes nothing more. The
run's config gets one `rechecks` entry per recheck that found something to check; its status is
never touched.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from pydantic import JsonValue, ValidationError

from aiact.engine.nodes import facts
from aiact.engine.state import CheckOutcome, FactsOutcome
from aiact.eval.cases import CASES_DIR
from aiact.eval.experiments.smoke import (
    ARMS,
    BROKEN_ERROR_TYPES,
    EXPERIMENT,
    PROVIDER_ERROR_FINISH,
    NodeName,
    Probe,
    ProbeKind,
    RunStatus,
    broken_correct,
    is_correct,
    plan_probes,
)
from aiact.eval.experiments.smoke_served import (
    Served,
    VerifyAll,
    checked_row,
    settle,
    stored_ids,
    stored_smoke_info,
)
from aiact.eval.experiments.smoke_verdict import SmokeRunError
from aiact.eval.records import PostgresRunStore
from aiact.eval.runner import CaseRecord, Score, label_record
from aiact.llm.generations import may_come_later
from aiact.schemas import PROVIDER_REFUSAL

RECHECK_BY = "smoke-recheck"
NOT_OUTCOME = frozenset({"smoke", "not_pinned"})
"""The keys a stored answer carries next to the node's outcome."""


class RecheckError(ValueError):
    """A probe that qualifies can't be rescored: its case is gone, its label changed since the
    run, or its stored answer doesn't read back into the node's outcome."""


class RecheckResult(StrEnum):
    CONFIRMED = "confirmed"
    OTHER_PROVIDER = "other_provider"
    STILL_FAILING = "still_failing"


@dataclass(frozen=True)
class StoredRow:
    case_id: str
    predicted: dict[str, JsonValue]
    label: dict[str, JsonValue]
    scores: dict[str, Score]


@dataclass(frozen=True)
class ProbeRecheck:
    """What the recheck found for one probe, and the score its reply earns."""

    case_id: str
    result: RecheckResult
    kind: ProbeKind
    correct: bool | None
    served_by: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class RunRecheck:
    run_id: UUID
    arm: str
    probes: tuple[ProbeRecheck, ...]

    @property
    def confirmed(self) -> int:
        return sum(probe.result is RecheckResult.CONFIRMED for probe in self.probes)

    @property
    def other_provider(self) -> int:
        return sum(probe.result is RecheckResult.OTHER_PROVIDER for probe in self.probes)

    @property
    def still_failing(self) -> int:
        return len(self.probes) - self.confirmed


# --- Which probes qualify, and their score ------------------------------------------------------


def reply_kind(predicted: Mapping[str, JsonValue]) -> ProbeKind | None:
    """How the live path classed the stored reply: answered, broken, or None when it got no
    answer (a transport or provider error, or a reply the provider broke off)."""
    if "provider_error" in predicted:
        return None
    calls = stored_smoke_info(predicted).get("calls", [])
    if isinstance(calls, list) and any(
        isinstance(call, dict) and call.get("finish_reason") == PROVIDER_ERROR_FINISH
        for call in calls
    ):
        return None
    error = predicted.get("error")
    if error is None:
        return ProbeKind.ANSWERED
    is_broken = isinstance(error, dict) and error.get("type") in BROKEN_ERROR_TYPES
    return ProbeKind.BROKEN if is_broken else None


def qualifies(row: StoredRow) -> bool:
    """A failed probe whose only fault was a generation record not found in time."""
    reason = row.predicted.get("not_pinned")
    if row.scores.get("failed") is not True or not isinstance(reason, str):
        return False
    return may_come_later(reason) and reply_kind(row.predicted) is not None


def is_stored_refusal(node: NodeName, stored: Mapping[str, JsonValue]) -> bool:
    """Whether the stored outcome is the node's refusal outcome (`smoke.is_refused`), read from
    the row itself: a refusal stored before decision 030 no longer validates."""
    if node is NodeName.FACTS:
        questions = stored.get("follow_up_questions")
        return isinstance(questions, list) and any(
            isinstance(q, dict) and q.get("id") == facts.PERSON_REVIEW_ID for q in questions
        )
    step = stored.get("step")
    return isinstance(step, dict) and step.get("error") == PROVIDER_REFUSAL


def rescore(probe: Probe, predicted: Mapping[str, JsonValue]) -> tuple[ProbeKind, bool | None]:
    """The kind and correctness the live path gives this stored reply; a refusal is unscored."""
    kind = reply_kind(predicted)
    if kind is None:
        raise RecheckError(f"probe {probe.probe_id} got no answer; nothing to rescore")
    if kind is ProbeKind.BROKEN:
        return kind, broken_correct(probe.node)
    stored = {key: value for key, value in predicted.items() if key not in NOT_OUTCOME}
    if is_stored_refusal(probe.node, stored):
        return ProbeKind.REFUSED, None
    model = FactsOutcome if probe.node is NodeName.FACTS else CheckOutcome
    try:
        outcome = model.model_validate(stored)
    except ValidationError as error:
        raise RecheckError(
            f"probe {probe.probe_id}: the stored answer doesn't read back"
        ) from error
    return kind, is_correct(probe, outcome)


def _probe_for(row: StoredRow, probes: Mapping[str, Probe]) -> Probe:
    probe = probes.get(row.case_id)
    if probe is None:
        raise RecheckError(f"probe {row.case_id} is not planned from the current cases")
    if label_record(probe.case) != row.label:
        raise RecheckError(f"the case of probe {row.case_id} changed since the run")
    return probe


# --- The new rows -------------------------------------------------------------------------------


def _audit(row: StoredRow, served: Served, checked_at: datetime) -> dict[str, JsonValue]:
    return {
        "at": checked_at.isoformat(),
        "original_not_pinned": row.predicted.get("not_pinned"),
        "served_by": list(served.providers),
        "by": RECHECK_BY,
    }


def rechecked_record(
    row: StoredRow, rescored: tuple[ProbeKind, bool | None], served: Served, checked_at: datetime
) -> CaseRecord:
    """The row after a recheck that settled it: confirmed (the reply's own score) or another
    provider (still failed, with that provider as the reason). Its cost stays as stored:
    `update_case` writes only the prediction and scores."""
    kind, correct = rescored
    confirmed: dict[str, Score] = {
        "broken": kind is ProbeKind.BROKEN,
        "failed": False,
        "refused": kind is ProbeKind.REFUSED,
        "correct": correct,
        "is_error": kind is not ProbeKind.ANSWERED,
    }
    record = CaseRecord(row.case_id, row.predicted, row.label, row.scores, None, 0.0, 0)
    return checked_row(record, served, "recheck", _audit(row, served, checked_at), confirmed)


def _result(served: Served) -> RecheckResult:
    if served.as_pinned is True:
        return RecheckResult.CONFIRMED
    if served.as_pinned is False:
        return RecheckResult.OTHER_PROVIDER
    return RecheckResult.STILL_FAILING


# --- One stored run -----------------------------------------------------------------------------


def _load(connection: psycopg.Connection, run_id: UUID) -> tuple[str, list[StoredRow]]:
    """A completed smoke run's arm and rows; any other run is refused."""
    row = connection.execute(
        "select config->>'experiment', config->>'arm', config->'outcome'->>'status'"
        " from eval_runs where id = %s",
        (run_id,),
    ).fetchone()
    if row is None:
        raise SmokeRunError(f"no run {run_id} in eval_runs")
    experiment, arm, status = row
    if experiment != EXPERIMENT or arm not in ARMS:
        raise SmokeRunError(f"run {run_id} is not an {EXPERIMENT} run")
    if status != RunStatus.COMPLETED.value:
        raise SmokeRunError(f"run {run_id} did not complete (status {status}); not rechecked")
    rows = connection.execute(
        "select case_id, predicted, label, scores from eval_case_results"
        " where run_id = %s order by case_id",
        (run_id,),
    ).fetchall()
    return arm, [StoredRow(*stored) for stored in rows]


@dataclass(frozen=True)
class PreparedRun:
    """A run's qualifying probes, each with the score its reply earns and its generation ids:
    everything that can refuse the recheck, worked out before any lookup or write."""

    run_id: UUID
    arm: str
    chosen: tuple[StoredRow, ...]
    rescored: Mapping[str, tuple[ProbeKind, bool | None]]
    generation_ids: Mapping[str, tuple[str, ...]]


def prepare_run(
    connection: psycopg.Connection, run_id: UUID, cases_dir: Path | None = None
) -> PreparedRun:
    """Read one stored run and pick its qualifying probes; reads only. Its rows are looked up in
    the plan of every node, which holds the probes of any narrower plan (X2's, or an X2b run of
    some nodes or cases) as well as the prohibited, transparency and thin-case facts probes."""
    arm, rows = _load(connection, run_id)
    every_probe = plan_probes(cases_dir or CASES_DIR, nodes=tuple(NodeName))
    probes = {probe.probe_id: probe for probe in every_probe}
    chosen = tuple(row for row in rows if qualifies(row))
    rescored = {row.case_id: rescore(_probe_for(row, probes), row.predicted) for row in chosen}
    ids = {row.case_id: _generation_ids(row) for row in chosen}
    return PreparedRun(run_id, arm, chosen, rescored, ids)


def apply_recheck(
    connection: psycopg.Connection,
    prepared: PreparedRun,
    verify: VerifyAll,
    now: datetime | None = None,
) -> RunRecheck:
    """Look the prepared probes' records up again and store what that settles, in one
    transaction."""
    ids = prepared.generation_ids
    chosen = prepared.chosen
    found = verify([gid for row in chosen for gid in ids[row.case_id]]) if chosen else {}
    checked_at = now or datetime.now(UTC)
    pinned = ARMS[prepared.arm].served_by
    results: list[ProbeRecheck] = []
    updates: list[CaseRecord] = []
    for row in chosen:
        served = settle(ids[row.case_id], found, pinned)
        kind, correct = prepared.rescored[row.case_id]
        result = _result(served)
        results.append(
            ProbeRecheck(row.case_id, result, kind, correct, served.providers, served.not_counted)
        )
        if result is not RecheckResult.STILL_FAILING:
            updates.append(rechecked_record(row, (kind, correct), served, checked_at))
    summary = RunRecheck(prepared.run_id, prepared.arm, tuple(results))
    if chosen:
        _store(connection, summary, updates, checked_at)
    return summary


def recheck_run(
    connection: psycopg.Connection,
    run_id: UUID,
    verify: VerifyAll,
    cases_dir: Path | None = None,
    now: datetime | None = None,
) -> RunRecheck:
    """Recheck the qualifying probes of one stored smoke run and store what it settles."""
    return apply_recheck(connection, prepare_run(connection, run_id, cases_dir), verify, now)


def _generation_ids(row: StoredRow) -> tuple[str, ...]:
    ids = stored_ids(stored_smoke_info(row.predicted), "generation_ids")
    if not ids:
        raise RecheckError(f"probe {row.case_id} stored no generation id")
    return ids


def _store(
    connection: psycopg.Connection,
    summary: RunRecheck,
    updates: Sequence[CaseRecord],
    checked_at: datetime,
) -> None:
    """The settled rows and the run's `config.rechecks` entry, in one transaction."""
    entry: dict[str, JsonValue] = {
        "at": checked_at.isoformat(),
        "by": RECHECK_BY,
        "probes_rechecked": len(summary.probes),
        "confirmed": summary.confirmed,
        "other_provider": summary.other_provider,
        "still_failing": summary.still_failing,
    }
    store = PostgresRunStore(connection)
    with connection.transaction():
        for record in updates:
            store.update_case(summary.run_id, record)
        connection.execute(
            "update eval_runs set config = jsonb_set(config, '{rechecks}',"
            " coalesce(config -> 'rechecks', '[]'::jsonb) || %s) where id = %s",
            (Jsonb([entry]), summary.run_id),
        )


# --- The printed summary ------------------------------------------------------------------------


def comparison_pair(rechecks: Sequence[RunRecheck]) -> dict[str, UUID] | None:
    """The Luna and Gemini run ids when exactly one of each was rechecked."""
    by_arm: dict[str, list[UUID]] = {}
    for recheck in rechecks:
        by_arm.setdefault(recheck.arm, []).append(recheck.run_id)
    if sorted(by_arm) != sorted(ARMS) or any(len(ids) != 1 for ids in by_arm.values()):
        return None
    return {arm: ids[0] for arm, ids in by_arm.items()}


def _describe(probe: ProbeRecheck) -> str:
    if probe.result is not RecheckResult.CONFIRMED:
        return f"still failing: {probe.reason}"
    score = "" if probe.correct is None else (", correct" if probe.correct else ", wrong")
    return f"confirmed on {', '.join(sorted(set(probe.served_by)))}: {probe.kind.value}{score}"


def format_recheck(recheck: RunRecheck) -> str:
    lines = [
        f"{recheck.arm}: run {recheck.run_id}, {len(recheck.probes)} probes rechecked, "
        f"{recheck.confirmed} confirmed on {ARMS[recheck.arm].served_by}, "
        f"{recheck.still_failing} still failing"
    ]
    lines += [f"  {probe.case_id}: {_describe(probe)}" for probe in recheck.probes]
    return "\n".join(lines)
