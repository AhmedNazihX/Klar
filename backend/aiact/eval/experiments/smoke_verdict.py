"""The smoke test's verdict, read from the two stored runs by run id (X2; decision 023).

The fixed rule: Luna is dropped if more than 10% of its answers are broken, or if its accuracy is
10 or more percentage points below Gemini's on the same probes. Both are compared in integers, so
exactly 10% broken keeps Luna and exactly 10 points below drops it.

- The broken share is over the model's replies (answered or broken), facts included.
- Accuracy is over the labelled probes both models replied to; a broken answer counts as wrong.
- More than 10% of probes without a usable answer, for either model, makes the verdict
  `inconclusive` (decision 023 addendum, parts 4-6, accepted by the user on 2026-10-01).

Only completed runs are compared, and both must have planned the same probes.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID

import psycopg
from pydantic import JsonValue

from aiact.eval.experiments.smoke import ARMS, EXPERIMENT, GEMINI, LUNA, NodeName, ProbeKind
from aiact.eval.experiments.smoke import RunStatus as SmokeRunStatus

BROKEN_SHARE_LIMIT = (1, 10)
"""Luna is dropped when more than 1 in 10 of its answers are broken (decision 023)."""
ACCURACY_GAP_LIMIT = (10, 100)
"""Luna is dropped when its accuracy is 10 or more points (of 100) below Gemini's (decision 023)."""
FAILED_SHARE_LIMIT = (1, 10)
"""More than 1 in 10 probes without an answer, for either model, makes the verdict inconclusive."""


@dataclass(frozen=True)
class ProbeScore:
    """One stored probe row, as the verdict reads it."""

    probe_id: str
    kind: ProbeKind
    correct: bool | None

    @property
    def node(self) -> NodeName:
        return NodeName(self.probe_id.split(":", 1)[0])


def probe_score(probe_id: str, scores: Mapping[str, JsonValue]) -> ProbeScore:
    """Read a stored row's scores; a row that isn't a smoke probe raises `ValueError`. A row still
    pending its provider check (a run stopped before the check) counts as failed; a refusal
    (X2b) is neither answered nor broken."""
    NodeName(probe_id.split(":", 1)[0])
    broken, failed, correct = scores.get("broken"), scores.get("failed"), scores.get("correct")
    if not isinstance(broken, bool) or not isinstance(failed, bool):
        raise ValueError(f"row {probe_id} has no broken/failed flags; not a smoke probe")
    if correct is not None and not isinstance(correct, bool):
        raise ValueError(f"row {probe_id} has a non-boolean correct score")
    is_failed = failed or scores.get("pending_verification") is True
    kind = ProbeKind.FAILED if is_failed else ProbeKind.BROKEN if broken else ProbeKind.ANSWERED
    if kind is ProbeKind.ANSWERED and scores.get("refused") is True:
        kind = ProbeKind.REFUSED  # rows stored before X2b have no refused flag
    return ProbeScore(probe_id, kind, correct)


@dataclass(frozen=True)
class ArmSummary:
    """One model's counts over the planned probes; a probe it has no row for counts as failed."""

    name: str
    planned: int
    answered: int
    broken: int
    failed: int
    broken_by_node: Mapping[str, int]

    @property
    def replied(self) -> int:
        """Probes where the model gave an answer, fitting or broken."""
        return self.answered + self.broken


def summarize(name: str, scores: Sequence[ProbeScore], planned: Sequence[str]) -> ArmSummary:
    by_id = {score.probe_id: score for score in scores}
    kinds = [by_id[pid].kind if pid in by_id else ProbeKind.FAILED for pid in planned]
    broken_by_node: dict[str, int] = {}
    for score in scores:
        if score.kind is ProbeKind.BROKEN:
            broken_by_node[score.node.value] = broken_by_node.get(score.node.value, 0) + 1
    return ArmSummary(
        name=name,
        planned=len(planned),
        answered=kinds.count(ProbeKind.ANSWERED),
        broken=kinds.count(ProbeKind.BROKEN),
        failed=kinds.count(ProbeKind.FAILED),
        broken_by_node=broken_by_node,
    )


class Verdict(StrEnum):
    KEEP_LUNA = "keep_luna"
    DROP_LUNA = "drop_luna"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Comparison:
    """Both models' counts, their accuracy on the same scored probes, and the rule's verdict."""

    luna: ArmSummary
    gemini: ArmSummary
    scored: int
    """Labelled probes both models replied to (a broken answer counts as wrong)."""
    luna_correct: int
    gemini_correct: int
    verdict: Verdict
    reasons: tuple[str, ...]
    notes: tuple[str, ...] = ()
    """Lines printed under the table, e.g. that a run's rows were rescored by a recheck."""

    @property
    def luna_accuracy(self) -> float | None:
        return self.luna_correct / self.scored if self.scored else None

    @property
    def gemini_accuracy(self) -> float | None:
        return self.gemini_correct / self.scored if self.scored else None


def _exceeds(count: int, total: int, limit: tuple[int, int]) -> bool:
    """`count / total > numerator / denominator`, in integers so 10% is exact."""
    numerator, denominator = limit
    return count * denominator > total * numerator


def compare(luna: Sequence[ProbeScore], gemini: Sequence[ProbeScore]) -> Comparison:
    """Apply decision 023's rule to the two runs' probes."""
    planned = sorted({score.probe_id for score in (*luna, *gemini)})
    luna_summary = summarize(LUNA.name, luna, planned)
    gemini_summary = summarize(GEMINI.name, gemini, planned)
    luna_by_id = {s.probe_id: s for s in luna if s.kind is not ProbeKind.FAILED}
    gemini_by_id = {s.probe_id: s for s in gemini if s.kind is not ProbeKind.FAILED}
    common = [
        pid
        for pid in planned
        if pid in luna_by_id
        and pid in gemini_by_id
        and luna_by_id[pid].correct is not None
        and gemini_by_id[pid].correct is not None
    ]
    luna_correct = sum(luna_by_id[pid].correct is True for pid in common)
    gemini_correct = sum(gemini_by_id[pid].correct is True for pid in common)
    verdict, reasons = _verdict(
        luna_summary, gemini_summary, len(common), luna_correct, gemini_correct
    )
    return Comparison(
        luna_summary, gemini_summary, len(common), luna_correct, gemini_correct, verdict, reasons
    )


def _verdict(
    luna: ArmSummary, gemini: ArmSummary, scored: int, luna_correct: int, gemini_correct: int
) -> tuple[Verdict, tuple[str, ...]]:
    unusable = [
        f"{arm.name}: {arm.failed} of {arm.planned} probes got no answer"
        for arm in (luna, gemini)
        if arm.replied == 0 or _exceeds(arm.failed, arm.planned, FAILED_SHARE_LIMIT)
    ]
    if not scored:
        unusable.append("no probe scored for both")
    if unusable:
        return Verdict.INCONCLUSIVE, tuple(unusable)
    reasons: list[str] = []
    if _exceeds(luna.broken, luna.replied, BROKEN_SHARE_LIMIT):
        reasons.append(f"luna: {luna.broken} of {luna.replied} answers broken, more than 10%")
    numerator, denominator = ACCURACY_GAP_LIMIT
    if (gemini_correct - luna_correct) * denominator >= scored * numerator:
        reasons.append(
            f"luna: {luna_correct}/{scored} correct, 10 or more points below gemini's "
            f"{gemini_correct}/{scored}"
        )
    return (Verdict.DROP_LUNA if reasons else Verdict.KEEP_LUNA), tuple(reasons)


# --- Reading stored runs ------------------------------------------------------------------------


class SmokeRunError(LookupError):
    """A run id that isn't a complete stored smoke run, or two runs that can't be compared."""


@dataclass(frozen=True)
class StoredRun:
    arm: str
    probes_planned: int
    scores: tuple[ProbeScore, ...]
    rechecks: tuple[Mapping[str, JsonValue], ...] = ()
    """The run's `config.rechecks` entries, oldest first (`smoke_recheck`)."""


def recheck_notes(run: StoredRun) -> tuple[str, ...]:
    """One line per recheck that confirmed at least one probe, with the probes it found served
    by another provider when there were any; a recheck that confirmed none is left out."""
    return tuple(
        _recheck_note(run.arm, entry) for entry in run.rechecks if _count(entry, "confirmed")
    )


def _count(entry: Mapping[str, JsonValue], key: str) -> int:
    value = entry.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _recheck_note(arm: str, entry: Mapping[str, JsonValue]) -> str:
    other = _count(entry, "other_provider")
    elsewhere = f", {other} found served by another provider" if other else ""
    return (
        f"{arm}: rechecked on {str(entry.get('at', ''))[:10]}: {_count(entry, 'confirmed')} "
        f"probes confirmed late{elsewhere} ({entry.get('by')})"
    )


def _rechecks(value: JsonValue) -> tuple[Mapping[str, JsonValue], ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(entry, dict) for entry in value):
        raise SmokeRunError("config.rechecks is not a list of entries")
    return tuple(entry for entry in value if isinstance(entry, dict))


def load_run(connection: psycopg.Connection, run_id: UUID) -> StoredRun:
    """A completed smoke run's arm, planned probe count, probe scores and rechecks."""
    row = connection.execute(
        "select config->>'experiment', config->>'arm', config->'outcome'->>'status',"
        " (config->'outcome'->>'probes_planned')::int, config->'rechecks'"
        " from eval_runs where id = %s",
        (run_id,),
    ).fetchone()
    if row is None:
        raise SmokeRunError(f"no run {run_id} in eval_runs")
    experiment, arm, status, planned, rechecks = row
    if experiment != EXPERIMENT or arm not in ARMS:
        raise SmokeRunError(f"run {run_id} is not an {EXPERIMENT} run")
    if status != SmokeRunStatus.COMPLETED.value or planned is None:
        raise SmokeRunError(f"run {run_id} did not complete (status {status}); run it again")
    rows = connection.execute(
        "select case_id, scores from eval_case_results where run_id = %s order by case_id",
        (run_id,),
    ).fetchall()
    if len(rows) != planned:
        raise SmokeRunError(f"run {run_id} planned {planned} probes but stored {len(rows)}")
    scores = tuple(probe_score(case_id, scores) for case_id, scores in rows)
    return StoredRun(arm, planned, scores, _rechecks(rechecks))


def compare_runs(connection: psycopg.Connection, run_ids: Mapping[str, UUID]) -> Comparison:
    """The verdict over the stored Luna and Gemini runs; each must be the model it is given as,
    and both must have planned the same probes."""
    runs: dict[str, StoredRun] = {}
    for expected in (LUNA.name, GEMINI.name):
        run = load_run(connection, run_ids[expected])
        if run.arm != expected:
            raise SmokeRunError(f"run {run_ids[expected]} is the {run.arm} run, not {expected}")
        runs[expected] = run
    luna, gemini = runs[LUNA.name], runs[GEMINI.name]
    luna_ids = {s.probe_id for s in luna.scores}
    if luna.probes_planned != gemini.probes_planned or luna_ids != {
        s.probe_id for s in gemini.scores
    }:
        raise SmokeRunError("the two runs did not plan the same probes; run both from one commit")
    notes = (*recheck_notes(luna), *recheck_notes(gemini))
    return replace(compare(luna.scores, gemini.scores), notes=notes)


# --- The printed report -------------------------------------------------------------------------


def _share(count: int, total: int) -> str:
    return f"{count}/{total} ({100 * count / total:.1f}%)" if total else f"{count}/0"


def format_comparison(comparison: Comparison, run_ids: Mapping[str, UUID]) -> str:
    """The comparison as a markdown table, for decision 004."""
    rows = [
        "| Model | Run id | Broken answers | No answer | Accuracy (same probes) |",
        "| --- | --- | --- | --- | --- |",
    ]
    arms = (
        (comparison.luna, comparison.luna_correct),
        (comparison.gemini, comparison.gemini_correct),
    )
    for arm, correct in arms:
        by_node = ", ".join(f"{node} {n}" for node, n in sorted(arm.broken_by_node.items()))
        broken = _share(arm.broken, arm.replied) + (f": {by_node}" if by_node else "")
        rows.append(
            f"| {ARMS[arm.name].model} | {run_ids.get(arm.name, '-')} | {broken} | "
            f"{_share(arm.failed, arm.planned)} | {_share(correct, comparison.scored)} |"
        )
    rows += ["", *comparison.notes] if comparison.notes else []
    rows += ["", f"Verdict: {comparison.verdict.value}"]
    rows += [f"- {reason}" for reason in comparison.reasons]
    return "\n".join(rows)
