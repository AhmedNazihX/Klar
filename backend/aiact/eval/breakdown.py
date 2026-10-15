"""One stored run's metrics per group of cases: language, business function or Commission area (W1).

`aiact evaluate breakdown <run_id> --by language|business_function|area` reads the run's rows
from `eval_runs` and `eval_case_results` (the labels the run stored, not today's case files),
groups the scored cases and recomputes each group's metrics with the report's own code
(`report.scored_metrics`). It writes nothing and calls no model, so it can't change a measured
result (decision 024's amendment allows such tooling after the freeze).

Own cases are grouped by `business_function`, Commission cases by their `area:` tag; a case
without one is grouped as "(none)". Every group shows its case count, so the small ones read as
noisy. The output names groups and counts only, never a case id, so a Pile B run's breakdown can
be pasted like its report.
"""

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from uuid import UUID

import psycopg

from aiact.eval.cases import BenchmarkCase, CaseSet
from aiact.eval.head_to_head import AREA_TAG_PREFIX
from aiact.eval.ragas_metrics import BENCHMARK as QA_BENCHMARK
from aiact.eval.report import (
    DEVELOPMENT_CASES,
    RunInfo,
    StoredCase,
    load_run_info,
    load_stored_cases,
    scored_metrics,
)

NO_GROUP = "(none)"
NOISY = "Groups with few cases are noisy: read each rate with its count."


class GroupBy(StrEnum):
    """What the cases are grouped by."""

    LANGUAGE = "language"
    BUSINESS_FUNCTION = "business_function"
    AREA = "area"


class NotAClassificationRunError(ValueError):
    """The run holds no classifications (a Q&A run), so it has nothing to break down."""


def _language(case: BenchmarkCase) -> str:
    return case.language.value


def _business_function(case: BenchmarkCase) -> str:
    return case.business_function.value if case.business_function else NO_GROUP


def _area(case: BenchmarkCase) -> str:
    areas = [
        tag.removeprefix(AREA_TAG_PREFIX) for tag in case.tags if tag.startswith(AREA_TAG_PREFIX)
    ]
    return areas[0] if areas else NO_GROUP


GROUP_KEYS: Mapping[GroupBy, Callable[[BenchmarkCase], str]] = {
    GroupBy.LANGUAGE: _language,
    GroupBy.BUSINESS_FUNCTION: _business_function,
    GroupBy.AREA: _area,
}


def group_cases(cases: Sequence[StoredCase], by: GroupBy) -> dict[str, tuple[StoredCase, ...]]:
    """The scored cases (scoring errors left out, as in the report) by group, sorted by name with
    "(none)" last."""
    key = GROUP_KEYS[by]
    groups: dict[str, list[StoredCase]] = {}
    for stored in cases:
        if not stored.is_scoring_error:
            groups.setdefault(key(stored.outcome.case), []).append(stored)
    names = sorted(groups, key=lambda name: (name == NO_GROUP, name))
    return {name: tuple(groups[name]) for name in names}


def render_markdown(info: RunInfo, by: GroupBy, groups: Mapping[str, Sequence[StoredCase]]) -> str:
    lines = [
        f"## Run {info.id} by {by.value}",
        "",
        f"- Benchmark: `{info.benchmark}`",
        f"- Classifier: `{info.classifier or 'n/a'}`",
        f"- Exclude mode: `{info.exclude_mode or 'n/a'}`",
        f"- Status: {info.status or 'n/a'}",
    ]
    if info.benchmark == CaseSet.OWN.value:
        lines.append(f"- Own cases are {DEVELOPMENT_CASES}")
    lines += [
        f"- {NOISY}",
        "",
        f"| {by.value} | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy "
        "| Role accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, cases in groups.items():
        metrics = scored_metrics(cases)
        lines.append(
            f"| {name} | {len(cases)} | {metrics.risk_class_accuracy.with_counts} | "
            f"{metrics.false_low_risk.with_counts} | {metrics.annex_point_accuracy.with_counts} | "
            f"{metrics.role_accuracy.with_counts} |"
        )
    return "\n".join(lines) + "\n"


def breakdown_report(conn: psycopg.Connection, run_id: UUID, by: GroupBy) -> str:
    """The stored run's metrics per group, as markdown (read-only)."""
    info = load_run_info(conn, run_id)
    if info.benchmark == QA_BENCHMARK:
        raise NotAClassificationRunError(
            f"run {run_id} is a Q&A run: it holds no classifications to break down"
        )
    return render_markdown(info, by, group_cases(load_stored_cases(conn, run_id), by))
