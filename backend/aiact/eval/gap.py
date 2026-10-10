"""The held-out vs in-corpus gap from two stored runs (INIT > Benchmark isolation 4, Metrics).

`aiact evaluate gap <heldout run> <all run>` reads both runs by id, checks they both completed
and are the same benchmark, classifier, models, subset, seed and appended answers with the two
exclude modes (so they covered the same cases with the same inputs), and prints their
risk-class accuracy (with and without the contaminated cases, decision 016) and the gap:
held-out accuracy minus in-corpus accuracy, in percentage points (INIT's definition; a large gap
means the engine leans on memorised examples). Reports quote the gap from this output, never
from their own arithmetic (T1). The output ends with the comparison's known limits, so a report
quoting it carries them.
"""

from uuid import UUID

import psycopg

from aiact.eval.isolation import ContaminatedList, load_contaminated
from aiact.eval.metrics import Rate, summarize
from aiact.eval.report import (
    RunInfo,
    StoredCase,
    contaminated_cases,
    load_run_info,
    load_stored_cases,
    scored_metrics,
)
from aiact.eval.runner import RunStatus

HELDOUT = "heldout"
ALL = "all"
MATCHED_SETTINGS = (
    "benchmark",
    "classifier",
    "model",
    "second_model",
    "subset",
    "seed",
    "answers_from",
)
"""What two runs share to be compared; the exclude mode is what differs."""

LIMITS = (
    "Pile A example rows are judged by 6-gram coverage only (threshold 0.8, B13), since sibling "
    "examples share long reasoning sentences; a Pile B example quoted inside a Pile A example row "
    "below that coverage would not be caught.",
    "Some Pile A examples are near-twins of Pile B ones (for example hr-ex-024, -067, -124, -187 "
    "share 50-58% of their 8-word runs with a Pile B example; C4's audit). They stay retrievable "
    "in both runs (decision 012), so the gap understates how much the engine leans on memorised "
    "examples.",
    "The guideline search returns Pile A examples whose stock phrasing shares 8-word runs with "
    "their Pile B siblings, and the high-risk prompt carries the Act's full Annex III text (E5's "
    "isolation audit); both are allowed under decision 012 and present in both runs.",
    "Searching alone is weak for softly worded German descriptions: own-e-14 brought no Annex III "
    "row into a top-50 law search (E5), so the high-risk step lists every Annex III point instead.",
)
"""The comparison's known limits (BACKLOG > V8, from B13, C4 and E5)."""


class RunMismatchError(ValueError):
    """The two runs can't be compared: other settings, an unfinished run, or not one `heldout`
    and one `all` run."""


def check_pair(heldout: RunInfo, everything: RunInfo) -> None:
    """Raise `RunMismatchError` unless the runs are a held-out run and its gap run."""
    if (heldout.exclude_mode, everything.exclude_mode) != (HELDOUT, ALL):
        raise RunMismatchError(
            f"give the {HELDOUT} run first and the {ALL} run second; got exclude modes "
            f"{heldout.exclude_mode} and {everything.exclude_mode}"
        )
    for run in (heldout, everything):
        # A run stopped at its cost cap, or interrupted, covered fewer cases.
        if run.status != RunStatus.COMPLETED:
            raise RunMismatchError(
                f"run {run.id} has status {run.status or 'n/a'}, not {RunStatus.COMPLETED}: "
                "it may have left cases out"
            )
    for name in MATCHED_SETTINGS:
        first, second = getattr(heldout, name), getattr(everything, name)
        if first != second:
            raise RunMismatchError(f"the runs differ in {name}: {first} and {second}")


def _accuracies(cases: tuple[StoredCase, ...], contaminated: ContaminatedList) -> tuple[Rate, Rate]:
    scored = [case for case in cases if not case.is_scoring_error]
    outcomes = [case.outcome for case in scored]
    flagged = contaminated_cases(outcomes, contaminated)
    clean = summarize([o for o in outcomes if o.case.id not in flagged], None)
    return scored_metrics(scored).risk_class_accuracy, clean.risk_class_accuracy


def gap_points(heldout: Rate, everything: Rate) -> str:
    """Held-out minus in-corpus accuracy, in percentage points; n/a without both rates."""
    if heldout.value is None or everything.value is None:
        return "n/a"
    return f"{(heldout.value - everything.value) * 100:+.1f} pp"


def render_markdown(
    heldout: RunInfo, everything: RunInfo, rates: dict[str, tuple[Rate, Rate]]
) -> str:
    lines = [
        f"## Held-out vs in-corpus gap: `{heldout.benchmark}`",
        "",
        f"- Held-out run (the reported number): {heldout.id}, status {heldout.status or 'n/a'}",
        f"- Gap run (every example retrievable): {everything.id}, status "
        f"{everything.status or 'n/a'}",
        "",
        "| Risk-class accuracy | Held-out run | Gap run | Gap (held-out minus gap run) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, (held, every) in rates.items():
        lines.append(
            f"| {name} | {held.percent} ({held.hits}/{held.total}) | "
            f"{every.percent} ({every.hits}/{every.total}) | {gap_points(held, every)} |"
        )
    lines += ["", "Known limits of this comparison:", *(f"- {limit}" for limit in LIMITS)]
    return "\n".join(lines) + "\n"


def gap_report(conn: psycopg.Connection, heldout_id: UUID, all_id: UUID) -> str:
    """The gap between a stored held-out run and its gap run, as markdown."""
    heldout, everything = load_run_info(conn, heldout_id), load_run_info(conn, all_id)
    check_pair(heldout, everything)
    contaminated = load_contaminated()
    held_all, held_clean = _accuracies(load_stored_cases(conn, heldout_id), contaminated)
    every_all, every_clean = _accuracies(load_stored_cases(conn, all_id), contaminated)
    rates = {
        "Every case": (held_all, every_all),
        f"Without the contaminated cases ({contaminated.decision})": (held_clean, every_clean),
    }
    return render_markdown(heldout, everything, rates)
