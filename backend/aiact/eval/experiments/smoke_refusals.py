"""X2b's rule over stored smoke runs: does a second model answer what the engine model's provider
refused (decision 033)? Read-only; the runs are `aiact evaluate smoke` runs (X2's harness, with a
node and case subset).

- **M**, the refused probes: every probe (node and case) the engine model's provider refused in
  at least one of its runs. The refusal rate varies from run to run (E10), so several engine
  runs are read together.
- The second model's run probes those cases. Of the M probes, it **answered** (not refused,
  not broken, not failed), **matched** the label (a check probe, scored by `matchers`; facts has
  no label, decision 023), was **refused** too, gave a **broken** answer, or gave **no answer**
  (a transport or provider error, a reply not shown to come from its pinned provider, or a
  probe its run didn't plan).
- **The rule** (fixed before the run, decision 033): the second model is adopted for refused
  requests if it answers at least `ANSWERED_SHARE` of the M probes and matches the label on at
  least `MATCHED_SHARE` of the labelled probes it answers. Both are compared in integers.
- **Inconclusive**, and neither applied, when the engine model refused nothing, or when more
  than `smoke_verdict.FAILED_SHARE_LIMIT` of the M probes got no answer from the second model
  (decision 023 addendum, part 4). An inconclusive run is repeated.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

import psycopg

from aiact.eval.experiments.smoke import CHECK_ORDER, LUNA, NodeName, ProbeKind
from aiact.eval.experiments.smoke_verdict import (
    FAILED_SHARE_LIMIT,
    ProbeScore,
    SmokeRunError,
    load_run,
)

ANSWERED_SHARE = (4, 5)
"""The second model must answer at least 4 in 5 of the refused probes (decision 033)."""
MATCHED_SHARE = (4, 5)
"""It must match the label on at least 4 in 5 of the labelled probes it answers (decision 033)."""
NODE_ORDER = (NodeName.FACTS, *CHECK_ORDER)


@dataclass(frozen=True)
class NodeRow:
    """One node's counts: the probes the engine model ran and those its provider refused, and
    what the second model did with the refused ones."""

    node: NodeName
    cases_run: int
    refused: int
    answered: int
    matched: int
    labelled: int
    """Answered probes that carry a label (every check; facts carries none)."""
    refused_by_both: int
    broken: int
    no_answer: int


class Verdict(StrEnum):
    ADOPT = "adopt"
    REJECT = "reject"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class RefusalTable:
    rows: tuple[NodeRow, ...]
    verdict: Verdict
    reasons: tuple[str, ...]


def _at_least(count: int, total: int, share: tuple[int, int]) -> bool:
    """`count / total >= numerator / denominator`, in integers."""
    numerator, denominator = share
    return count * denominator >= total * numerator


def _exceeds(count: int, total: int, limit: tuple[int, int]) -> bool:
    numerator, denominator = limit
    return count * denominator > total * numerator


def _node_row(
    node: NodeName,
    engine_runs: Sequence[Sequence[ProbeScore]],
    second: Mapping[str, ProbeScore],
) -> NodeRow:
    run = {s.probe_id for scores in engine_runs for s in scores if s.node is node}
    refused = {
        s.probe_id
        for scores in engine_runs
        for s in scores
        if s.node is node and s.kind is ProbeKind.REFUSED
    }
    kinds = [second[pid].kind if pid in second else ProbeKind.FAILED for pid in refused]
    answered = [
        second[pid] for pid in refused if pid in second and second[pid].kind is ProbeKind.ANSWERED
    ]
    labelled = [score for score in answered if score.correct is not None]
    return NodeRow(
        node=node,
        cases_run=len(run),
        refused=len(refused),
        answered=len(answered),
        matched=sum(score.correct is True for score in labelled),
        labelled=len(labelled),
        refused_by_both=kinds.count(ProbeKind.REFUSED),
        broken=kinds.count(ProbeKind.BROKEN),
        no_answer=kinds.count(ProbeKind.FAILED),
    )


def tabulate(
    engine_runs: Sequence[Sequence[ProbeScore]], second: Sequence[ProbeScore]
) -> RefusalTable:
    """The per-node table and decision 033's verdict over the engine model's runs and the
    second model's run."""
    by_id = {score.probe_id: score for score in second}
    rows = tuple(_node_row(node, engine_runs, by_id) for node in NODE_ORDER)
    refused, no_answer = sum(r.refused for r in rows), sum(r.no_answer for r in rows)
    if not refused:
        return RefusalTable(rows, Verdict.INCONCLUSIVE, ("the engine model refused nothing",))
    if _exceeds(no_answer, refused, FAILED_SHARE_LIMIT):
        reason = f"{no_answer} of {refused} refused probes got no answer from the second model"
        return RefusalTable(rows, Verdict.INCONCLUSIVE, (reason,))
    answered = sum(r.answered for r in rows)
    matched, labelled = sum(r.matched for r in rows), sum(r.labelled for r in rows)
    reasons: list[str] = []
    if not _at_least(answered, refused, ANSWERED_SHARE):
        reasons.append(f"answered {answered} of {refused} refused probes, fewer than 4 in 5")
    if not _at_least(matched, labelled, MATCHED_SHARE):
        reasons.append(f"matched the label on {matched} of {labelled}, fewer than 4 in 5")
    return RefusalTable(rows, Verdict.REJECT if reasons else Verdict.ADOPT, tuple(reasons))


# --- Reading stored runs ------------------------------------------------------------------------


@dataclass(frozen=True)
class RunInfo:
    run_id: UUID
    arm: str
    cost_usd: float


def _cost(connection: psycopg.Connection, run_id: UUID) -> float:
    row = connection.execute("select cost_usd from eval_runs where id = %s", (run_id,)).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def compare_stored(
    connection: psycopg.Connection, engine_run_ids: Sequence[UUID], second_run_id: UUID
) -> tuple[RefusalTable, tuple[RunInfo, ...]]:
    """The table over stored, completed smoke runs: the engine runs must be the engine model's
    (`LUNA`), the second run another model's."""
    engine_runs = []
    infos = []
    for run_id in engine_run_ids:
        run = load_run(connection, run_id)
        if run.arm != LUNA.name:
            raise SmokeRunError(f"run {run_id} is the {run.arm} run, not the engine model's")
        engine_runs.append(run.scores)
        infos.append(RunInfo(run_id, run.arm, _cost(connection, run_id)))
    second = load_run(connection, second_run_id)
    if second.arm == LUNA.name:
        raise SmokeRunError(f"run {second_run_id} is the engine model's, not a second model's")
    infos.append(RunInfo(second_run_id, second.arm, _cost(connection, second_run_id)))
    return tabulate(engine_runs, second.scores), tuple(infos)


# --- The printed report -------------------------------------------------------------------------


def format_table(table: RefusalTable, runs: Sequence[RunInfo]) -> str:
    """The table per node and the runs with their cost, as markdown, for decision 033."""
    lines = [
        "| Node | Cases run | Refused by Luna | Answered by the second model | Matching the label |"
        " Refused by both | Broken | No answer |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in table.rows:
        matched = f"{row.matched}/{row.labelled}" if row.node is not NodeName.FACTS else "-"
        lines.append(
            f"| {row.node.value} | {row.cases_run} | {row.refused} | {row.answered} | {matched} |"
            f" {row.refused_by_both} | {row.broken} | {row.no_answer} |"
        )
    lines += ["", "| Run | Model | Cost (USD) |", "| --- | --- | --- |"]
    lines += [f"| {run.run_id} | {run.arm} | {run.cost_usd:.4f} |" for run in runs]
    lines += ["", f"Verdict: {table.verdict.value}"]
    lines += [f"- {reason}" for reason in table.reasons]
    return "\n".join(lines)
