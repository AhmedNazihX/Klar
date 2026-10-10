"""The label filter's disagreements reports (story B9).

Each group of `label_filter.OUTPUT_GROUPS` has its own report next to its answers file:
`eval/reports/label_disagreements.md` for the own sets, `eval/reports/pile_b/label_disagreements.md`
for Pile B (a folder the Engine lane can't read). A report is generated from the cases and the
second model's answers and is the one place the user writes a resolution: under each
disagreement, after `**Resolution:**`, the label kept or changed and why.

A resolution belongs to one disagreement, not to a case: the report writes the disagreement's
fingerprint (the case's input, its label and the answer) next to it. Regenerating keeps every
resolution written so far; one whose disagreement has gone or changed (the label was changed, the
case edited, or a new answer differs) moves to its own section, and the new disagreement is
unresolved until the user writes again. `check_report` is the DoD's check: every case labelled,
every disagreement resolved.

A difference is counted where the label states something: the class and the status always, the
role when the label names one, and the Annex point when both say high_risk and the label names
points (any one of them matches, as in scoring).
"""

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

from aiact.eval.cases import EVAL_DIR, BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.label_filter import (
    OUTPUT_GROUPS,
    REPORTS_DIR,
    FilterAnswer,
    FilterRecord,
    answers_file,
    input_sha256,
    is_current,
    reports_folder,
)
from aiact.schemas import RiskClass, Role, Status

REPORT_NAME = "label_disagreements.md"
RESOLUTION_MARK = "**Resolution:**"
CASE_HEADING = re.compile(r"^### (\S+)\s*$")
FINGERPRINT_LINE = re.compile(r"^- Disagreement: `([0-9a-f]+)`\s*$")
SECTION_HEADINGS = ("## ", "### ")
"""A resolution runs up to the next of these; a line starting with a lone `#` stays in it."""
FINGERPRINT_CHARS = 16


def report_file(case_set: CaseSet, reports_dir: Path = REPORTS_DIR) -> Path:
    return reports_folder(case_set, reports_dir) / REPORT_NAME


class ReportFormatError(ValueError):
    """A report a person edited so that a resolution can't be read back safely."""


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


class ResolutionKey(NamedTuple):
    case_id: str
    fingerprint: str


@dataclass(frozen=True)
class Disagreement:
    case: BenchmarkCase
    answer: FilterAnswer
    differences: tuple[Difference, ...]

    @property
    def key(self) -> ResolutionKey:
        """The case and what it disagrees on: a new input, label or answer is a new key."""
        label = self.case.model_dump_json(include={"label"})
        seen = f"{input_sha256(self.case)}\n{label}\n{self.answer.model_dump_json()}"
        digest = hashlib.sha256(seen.encode()).hexdigest()[:FINGERPRINT_CHARS]
        return ResolutionKey(self.case.id, digest)


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


def read_resolutions(text: str) -> dict[ResolutionKey, str]:
    """Each disagreement's resolution as written in a report (empty when none is written yet):
    the text after `RESOLUTION_MARK` up to the next `## ` or `### ` heading. Raises
    `ReportFormatError` for a case section without the mark, or with a line before it that the
    report didn't write: regenerating would lose that text."""
    return dict(_read_section(case_id, lines) for case_id, lines in _case_sections(text))


def _case_sections(text: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith(SECTION_HEADINGS):
            heading = CASE_HEADING.match(line)
            sections.append((heading.group(1) if heading else "", []))
        elif sections:
            sections[-1][1].append(line)
    return [(case_id, lines) for case_id, lines in sections if case_id]


def _read_section(case_id: str, lines: Sequence[str]) -> tuple[ResolutionKey, str]:
    fingerprint = ""
    for index, line in enumerate(lines):
        if line.startswith(RESOLUTION_MARK):
            rest = [line.removeprefix(RESOLUTION_MARK), *lines[index + 1 :]]
            return ResolutionKey(case_id, fingerprint), "\n".join(rest).strip()
        written = FINGERPRINT_LINE.match(line)
        if written:
            fingerprint = written.group(1)
        elif line.strip() and not line.startswith("- "):
            raise ReportFormatError(
                f"{case_id}: a line before `{RESOLUTION_MARK}` that the report didn't write; "
                "move it after the mark, then run again"
            )
    raise ReportFormatError(
        f"{case_id}: no line starts with `{RESOLUTION_MARK}` (written exactly so); "
        "fix it by hand, then run again"
    )


def read_report_resolutions(path: Path) -> dict[ResolutionKey, str]:
    """The resolutions in the report at `path`; none when it doesn't exist yet. Raises
    `ReportFormatError` naming the file when one can't be read back."""
    if not path.exists():
        return {}
    try:
        return read_resolutions(path.read_text(encoding="utf-8"))
    except ReportFormatError as error:
        raise ReportFormatError(f"{path}: {error}") from None


@dataclass(frozen=True)
class ReportCheck:
    unresolved: tuple[str, ...]
    unlabelled: tuple[str, ...]

    @property
    def is_ok(self) -> bool:
        return not self.unresolved and not self.unlabelled


def check_report(comparison: Comparison, resolutions: Mapping[ResolutionKey, str]) -> ReportCheck:
    """The DoD: every case has a current answer and every disagreement a written resolution of
    that same disagreement."""
    unresolved = tuple(d.case.id for d in comparison.disagreements if not resolutions.get(d.key))
    return ReportCheck(unresolved, tuple(case.id for case in comparison.unlabelled))


@dataclass(frozen=True)
class GroupReport:
    """One group's report: where it goes, what it compares and what was written in it."""

    path: Path
    answers_path: Path
    comparison: Comparison
    resolutions: Mapping[ResolutionKey, str]


def group_reports(
    cases: Sequence[BenchmarkCase],
    records: Mapping[str, FilterRecord],
    model: str,
    provider: str,
    reports_dir: Path = REPORTS_DIR,
) -> tuple[GroupReport, ...]:
    """A report per group of `OUTPUT_GROUPS` that has cases or a report already. Raises
    `ReportFormatError` before anything is written when one report can't be read back."""
    reports: list[GroupReport] = []
    for group in OUTPUT_GROUPS:
        group_cases = tuple(case for case in cases if case.set_name in group)
        path = report_file(group[0], reports_dir)
        if not group_cases and not path.exists():
            continue
        comparison = compare(group_cases, records, model, provider)
        resolutions = read_report_resolutions(path)
        answers = answers_file(group[0], reports_dir)
        reports.append(GroupReport(path, answers, comparison, resolutions))
    return tuple(reports)


def display_path(path: Path) -> str:
    """`path` from the repo root when it lies under it, else its name."""
    try:
        return path.relative_to(EVAL_DIR.parent).as_posix()
    except ValueError:
        return path.name


# --- rendering ----------------------------------------------------------------------------------

HEADER = """\
# Label disagreements (second-model filter)

Generated by `aiact evaluate label-filter` (story B9; INIT > Label rules for own cases) from the
answers in `{answers}`. {model} on `{provider}` labelled every case of these sets
blind: it read the description, the case's fixed answers and the date, with the AI Act's
consolidated text, never the label, its citation, the notes or a guideline.
This catches mistakes; it is not validation, and there is no external legal review of the labels.

**How to resolve.** Under each disagreement, after `**Resolution:**`, write `kept: <reason>` or
`changed: <reason>`. A changed label is edited in its case file with a row in
`eval/LABEL_CHANGES.md`. Edit only after the mark, and keep the mark exactly as written.
Regenerating this file keeps every resolution, tied to the disagreement it answers (the
`Disagreement` fingerprint): if that disagreement changes, the resolution moves to "Resolved
earlier" and the new one needs its own. `aiact evaluate label-filter --check` fails while a
resolution is missing or a case is unlabelled.
"""


def render_report(
    comparison: Comparison,
    resolutions: Mapping[ResolutionKey, str],
    model: str,
    provider: str,
    answers: str,
) -> str:
    """The report: a summary per set, the cases without an answer, each disagreement with its
    resolution, and the resolutions whose disagreement has gone or changed. `answers` names the
    answers file it was built from."""
    current = {d.key for d in comparison.disagreements}
    earlier = {key: text for key, text in resolutions.items() if key not in current and text}
    parts = [
        HEADER.format(model=model, provider=provider, answers=answers),
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


def _disagreements(found: Sequence[Disagreement], resolutions: Mapping[ResolutionKey, str]) -> str:
    lines = [f"## Disagreements ({len(found)})", ""]
    for disagreement in found:
        lines += _disagreement(disagreement, resolutions.get(disagreement.key, ""))
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
        f"- Its reason: {_one_line(answer.reason)}",
        f"- Disagreement: `{disagreement.key.fingerprint}`",
        "",
        f"{RESOLUTION_MARK} {resolution}".rstrip(),
        "",
    ]


def _one_line(text: str) -> str:
    """Model-written text on one line, so a reply can't start a heading or a resolution."""
    return " ".join(text.split())


def _points(point: str | None) -> tuple[str, ...]:
    return (_one_line(point),) if point else ()


def _reading(
    risk_class: RiskClass | None, status: Status, role: Role | None, points: Sequence[str]
) -> str:
    shown = risk_class.value if risk_class else "no class"
    who = f"role {role.value}" if role else "no role"
    where = " or ".join(points) if points else "no Annex point"
    return f"{shown}, {status.value}; {who}; {where}"


def _earlier(resolutions: Mapping[ResolutionKey, str]) -> str:
    lines = [
        "## Resolved earlier, no longer this disagreement",
        "",
        "Kept so no resolution is lost: the label, the case or the second model's answer changed",
        "since it was written. A case listed here and above needs a resolution above.",
        "",
    ]
    for key, text in resolutions.items():
        lines += [
            f"### {key.case_id}",
            "",
            f"- Disagreement: `{key.fingerprint}`",
            "",
            f"{RESOLUTION_MARK} {text}",
            "",
        ]
    return "\n".join(lines)
