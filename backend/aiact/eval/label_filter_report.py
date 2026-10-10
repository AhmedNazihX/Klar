"""The label filter's disagreements report, `eval/reports/label_disagreements.md` (story B9).

The report is generated from the cases and the second model's answers (`label_filter.ANSWERS_FILE`)
and is the one place the user writes a resolution: under each disagreement, after
`**Resolution:**`, the label kept or changed and why. Regenerating it keeps every resolution
written so far, and one whose disagreement has gone (the label was changed, or the case edited)
moves to its own section instead of being lost. `check_report` is the DoD's check: every case
labelled, every disagreement resolved.

A difference is counted where the label states something: the class and the status always, the
role when the label names one, and the Annex point when both say high_risk and the label names
points (any one of them matches, as in scoring).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.label_filter import REPORTS_DIR, FilterAnswer, FilterRecord, is_current
from aiact.schemas import RiskClass, Role, Status

REPORT_FILE = REPORTS_DIR / "label_disagreements.md"
RESOLUTION_MARK = "**Resolution:**"
CASE_HEADING = re.compile(r"^### (\S+)\s*$")


class Difference(StrEnum):
    CLASS = "class"
    STATUS = "status"
    ROLE = "role"
    ANNEX_POINT = "annex point"


def differences(label: CaseLabel, answer: FilterAnswer) -> tuple[Difference, ...]:
    """Where the second model's answer departs from what the label states."""
    found: list[Difference] = []
    if answer.risk_class is not label.risk_class:
        found.append(Difference.CLASS)
    if answer.status is not label.status:
        found.append(Difference.STATUS)
    if label.role is not None and answer.role is not label.role:
        found.append(Difference.ROLE)
    both_high = label.risk_class is answer.risk_class is RiskClass.HIGH_RISK
    if both_high and label.annex_point and answer.annex_point not in label.annex_point:
        found.append(Difference.ANNEX_POINT)
    return tuple(found)


@dataclass(frozen=True)
class Disagreement:
    case: BenchmarkCase
    answer: FilterAnswer
    differences: tuple[Difference, ...]


@dataclass(frozen=True)
class Comparison:
    """Every case sorted into one of three: agreeing, disagreeing, or without a current answer
    (never sent, or its call failed; `errors` says which)."""

    agreeing: tuple[BenchmarkCase, ...]
    disagreements: tuple[Disagreement, ...]
    unlabelled: tuple[BenchmarkCase, ...]
    errors: Mapping[str, str]
    cost_usd: float


def compare(
    cases: Sequence[BenchmarkCase], records: Mapping[str, FilterRecord], model: str, provider: str
) -> Comparison:
    """Compare each case's label with its current answer from `model` on `provider`."""
    agreeing: list[BenchmarkCase] = []
    disagreements: list[Disagreement] = []
    unlabelled: list[BenchmarkCase] = []
    errors: dict[str, str] = {}
    cost = 0.0
    for case in cases:
        record = records.get(case.id)
        if record is None or record.answer is None or not is_current(record, case, model, provider):
            unlabelled.append(case)
            errors[case.id] = _why_unlabelled(record)
            continue
        cost += record.cost_usd
        label = case.label
        if not isinstance(label, CaseLabel):
            raise ValueError(f"{case.id}: the filter labels own-labelled sets only")
        found = differences(label, record.answer)
        if found:
            disagreements.append(Disagreement(case, record.answer, found))
        else:
            agreeing.append(case)
    return Comparison(tuple(agreeing), tuple(disagreements), tuple(unlabelled), errors, cost)


def _why_unlabelled(record: FilterRecord | None) -> str:
    if record is None:
        return "not labelled yet"
    if record.error:
        return f"the call failed: {record.error}"
    return "the case or the model changed since it was labelled"


def read_resolutions(text: str) -> dict[str, str]:
    """Each case's resolution as written in a report (empty when none is written yet): the text
    after `RESOLUTION_MARK` up to the next heading."""
    resolutions: dict[str, str] = {}
    case_id: str | None = None
    lines: list[str] | None = None
    for line in [*text.splitlines(), "#"]:
        if line.startswith("#"):
            if case_id is not None and lines is not None:
                resolutions[case_id] = "\n".join(lines).strip()
            heading = CASE_HEADING.match(line)
            case_id, lines = (heading.group(1) if heading else None), None
        elif lines is not None:
            lines.append(line)
        elif case_id is not None and line.startswith(RESOLUTION_MARK):
            lines = [line.removeprefix(RESOLUTION_MARK)]
    return resolutions


def read_report_resolutions(path: Path = REPORT_FILE) -> dict[str, str]:
    """The resolutions in the report at `path`; none when it doesn't exist yet."""
    return read_resolutions(path.read_text(encoding="utf-8")) if path.exists() else {}


@dataclass(frozen=True)
class ReportCheck:
    unresolved: tuple[str, ...]
    unlabelled: tuple[str, ...]

    @property
    def is_ok(self) -> bool:
        return not self.unresolved and not self.unlabelled


def check_report(comparison: Comparison, resolutions: Mapping[str, str]) -> ReportCheck:
    """The DoD: every case has a current answer and every disagreement a written resolution."""
    unresolved = tuple(
        d.case.id for d in comparison.disagreements if not resolutions.get(d.case.id)
    )
    return ReportCheck(unresolved, tuple(case.id for case in comparison.unlabelled))


# --- rendering ----------------------------------------------------------------------------------

HEADER = """\
# Label disagreements (second-model filter)

Generated by `aiact evaluate label-filter` (story B9; INIT > Label rules for own cases) from the
answers in `eval/reports/label_filter_answers.jsonl`. {model} on `{provider}` labelled every case
of the own-labelled sets blind: it read the description, the case's fixed answers and the date,
with the AI Act's consolidated text, never the label, its citation, the notes or a guideline.
This catches mistakes; it is not validation, and there is no external legal review of the labels.

**How to resolve.** Under each disagreement, after `**Resolution:**`, write `kept: <reason>` or
`changed: <reason>`. A changed label is edited in its case file with a row in
`eval/LABEL_CHANGES.md`. Regenerating this file keeps every resolution;
`aiact evaluate label-filter --check` fails while one is missing or a case is unlabelled.
"""


def render_report(
    comparison: Comparison, resolutions: Mapping[str, str], model: str, provider: str
) -> str:
    """The report: a summary per set, the cases without an answer, each disagreement with its
    resolution, and the resolutions whose disagreement has gone."""
    current = {d.case.id for d in comparison.disagreements}
    earlier = {cid: text for cid, text in resolutions.items() if cid not in current and text}
    parts = [
        HEADER.format(model=model, provider=provider),
        _summary(comparison),
        _unlabelled(comparison),
        _disagreements(comparison.disagreements, resolutions),
    ]
    if earlier:
        parts.append(_earlier(earlier))
    return "\n".join(part for part in parts if part)


def _summary(comparison: Comparison) -> str:
    rows = [
        "## Summary",
        "",
        "| Set | Cases | Agree | Disagree | Not labelled |",
        "|---|---|---|---|---|",
    ]
    for case_set in CaseSet:
        counts = (
            sum(c.set_name is case_set for c in comparison.agreeing),
            sum(d.case.set_name is case_set for d in comparison.disagreements),
            sum(c.set_name is case_set for c in comparison.unlabelled),
        )
        if any(counts):
            rows.append(f"| {case_set.value} | {sum(counts)} | {' | '.join(map(str, counts))} |")
    by_kind = {
        kind: sum(kind in d.differences for d in comparison.disagreements) for kind in Difference
    }
    kinds = ", ".join(f"{kind.value} {count}" for kind, count in by_kind.items())
    rows += ["", f"Differences by kind (a case can have several): {kinds}.", ""]
    rows.append(f"Cost of the answers compared: ${comparison.cost_usd:.4f}.")
    return "\n".join(rows) + "\n"


def _unlabelled(comparison: Comparison) -> str:
    if not comparison.unlabelled:
        return ""
    lines = [f"## Not labelled ({len(comparison.unlabelled)})", ""]
    lines += [f"- `{c.id}`: {comparison.errors[c.id]}" for c in comparison.unlabelled]
    return "\n".join(lines) + "\n"


def _disagreements(found: Sequence[Disagreement], resolutions: Mapping[str, str]) -> str:
    lines = [f"## Disagreements ({len(found)})", ""]
    for disagreement in found:
        lines += _disagreement(disagreement, resolutions.get(disagreement.case.id, ""))
    return "\n".join(lines)


def _disagreement(disagreement: Disagreement, resolution: str) -> list[str]:
    case, answer = disagreement.case, disagreement.answer
    label = case.label
    assert isinstance(label, CaseLabel)  # `compare` admits own labels only
    cites = ", ".join(case.label_citation) or "none (see the case's notes)"
    return [
        f"### {case.id}",
        "",
        f"- Set: {case.set_name.value}; language: {case.language.value}",
        f"- Label: {_reading(label.risk_class, label.status, label.role, label.annex_point)}; "
        f"cites {cites}",
        f"- Second model: "
        f"{_reading(answer.risk_class, answer.status, answer.role, _points(answer.annex_point))}",
        f"- Differs on: {', '.join(d.value for d in disagreement.differences)}",
        f"- Its reason: {' '.join(answer.reason.split())}",
        "",
        f"{RESOLUTION_MARK} {resolution}".rstrip(),
        "",
    ]


def _points(point: str | None) -> tuple[str, ...]:
    return (point,) if point else ()


def _reading(
    risk_class: RiskClass | None, status: Status, role: Role | None, points: Sequence[str]
) -> str:
    shown = risk_class.value if risk_class else "no class"
    who = f"role {role.value}" if role else "no role"
    where = " or ".join(points) if points else "no Annex point"
    return f"{shown}, {status.value}; {who}; {where}"


def _earlier(resolutions: Mapping[str, str]) -> str:
    lines = [
        "## Resolved earlier, no longer disagreeing",
        "",
        "Kept so no resolution is lost: the label or the case changed since it was written.",
        "",
    ]
    for case_id, text in resolutions.items():
        lines += [f"### {case_id}", "", f"{RESOLUTION_MARK} {text}", ""]
    return "\n".join(lines)
