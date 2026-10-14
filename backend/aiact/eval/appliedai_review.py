"""The appliedAI disagreement review of one stored run (V9; INIT > Disagreement review).

`aiact evaluate appliedai-review <run_id>` drafts `eval/reports/appliedai_review.md` from a stored
`appliedai` run: every case with the experts' label and the engine's answer, and every case that
goes to the disagreement review (`metrics.needs_appliedai_review`, the run report's "appliedAI
disagreement review" count) with an empty verdict for the user to write: engine error, outdated
label (the 2023 label no longer fits the law), label error (the label didn't fit even the 2021
text, so no change in law explains it, and the engine's answer is right today), or ambiguous. INIT
names three verdicts; `label error` is the user's fourth (decision 002), so the report can tell
legal change from expert error. Annex I cases (the `annex_i` tag, "Annex II" in the experts' 2021
wording) are listed in their own section.

Running the command again reads the verdicts back and keeps them, so the same command recomputes
risk-class accuracy before and after excluding the cases marked outdated label or label error,
overall, without the Annex I cases, for the Annex I cases alone, and per appliedAI `function:*`
tag. Accuracy is `metrics.summarize`'s, so the "before" number equals the run report's. A report
holds the verdicts of one run: one whose verdicts belong to another run is never overwritten.
`--check` is the DoD's check: every disagreement has a verdict.

The rendering is in `appliedai_review_report`.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

import psycopg

from aiact.eval.cases import EVAL_DIR, CaseSet
from aiact.eval.metrics import (
    Outcome,
    Rate,
    is_not_assessed,
    needs_appliedai_review,
    risk_class_match,
    summarize,
)
from aiact.eval.report import RunInfo, StoredCase, load_run_info, load_stored_cases

REVIEW_FILE = EVAL_DIR / "reports" / "appliedai_review.md"
ANNEX_I_TAG = "annex_i"
FUNCTION_PREFIX = "function:"
NO_FUNCTION = "(none)"
TITLE = "# appliedAI disagreement review"
"""The review file's first line; `--out` never overwrites a file that doesn't start with it."""
VERDICT_MARK = "**Verdict:**"
RUN_LINE = re.compile(r"^- Run id: `([0-9a-f-]{36})`\s*$")
CASE_HEADING = re.compile(r"^### Case (\S+)\s*$")
ANNEX_I_DISAGREEMENTS = "## Annex I disagreements"
SECTION_END = re.compile(rf"^{ANNEX_I_DISAGREEMENTS} \(\d+\)$")
"""The one heading the report writes after a case's verdict; any other `#` line there is refused."""
DETAIL_PREFIXES = (
    "- Function: ",
    "- Experts: ",
    "- Engine: ",
    "- Match: ",
    "- Look first at: ",
    "- Experts' comment: ",
    "- Engine, ",
)
"""The lines the report writes between a case's heading and its verdict mark."""


class Verdict(StrEnum):
    """The user's verdict on one disagreement: INIT > Disagreement review's three, plus
    `label error` (decision 002)."""

    ENGINE_ERROR = "engine error"
    OUTDATED_LABEL = "outdated label"
    LABEL_ERROR = "label error"
    AMBIGUOUS = "ambiguous"


EXCLUDED_VERDICTS = frozenset({Verdict.OUTDATED_LABEL, Verdict.LABEL_ERROR})
"""The verdicts whose cases leave the "after" accuracy: the label, not the engine, is wrong."""


class NotAppliedAIRunError(ValueError):
    """The run asked for isn't a run of the appliedAI set."""


class ReviewFormatError(ValueError):
    """A review file edited so that its verdicts can't be read back safely; nothing is written."""


@dataclass(frozen=True)
class WrittenVerdict:
    """What the user wrote after `VERDICT_MARK`: the verdict, then any note of theirs."""

    verdict: Verdict
    text: str


@dataclass(frozen=True)
class ReviewCase:
    """One scored case of the run, as the review shows it."""

    stored: StoredCase

    @property
    def outcome(self) -> Outcome:
        return self.stored.outcome

    @property
    def case_id(self) -> str:
        return self.outcome.case.id

    @property
    def is_annex_i(self) -> bool:
        return ANNEX_I_TAG in self.outcome.case.tags

    @property
    def function(self) -> str:
        """appliedAI's own enterprise function (`function:*` tag), not `BusinessFunction`."""
        tags = self.outcome.case.tags
        found = (
            tag.removeprefix(FUNCTION_PREFIX) for tag in tags if tag.startswith(FUNCTION_PREFIX)
        )
        return next(found, NO_FUNCTION)

    @property
    def is_not_assessed(self) -> bool:
        return is_not_assessed(self.outcome)

    @property
    def is_counted_separately(self) -> bool:
        """`needs_more_information` on an `unclear` case: out of accuracy, counted on its own."""
        return not self.is_not_assessed and risk_class_match(self.outcome) is None

    @property
    def needs_review(self) -> bool:
        return not self.is_not_assessed and needs_appliedai_review(self.outcome)


@dataclass(frozen=True)
class Review:
    """A run's review: its cases (scoring errors left out, as in the run report) and the
    verdicts written so far, by case id."""

    info: RunInfo
    cases: tuple[ReviewCase, ...]
    scoring_errors: tuple[str, ...]
    verdicts: Mapping[str, WrittenVerdict]

    @property
    def disagreements(self) -> tuple[ReviewCase, ...]:
        return tuple(case for case in self.cases if case.needs_review)

    @property
    def missing(self) -> tuple[str, ...]:
        """The disagreements without a verdict yet."""
        return tuple(c.case_id for c in self.disagreements if c.case_id not in self.verdicts)

    @property
    def excluded(self) -> frozenset[str]:
        """The cases left out of the "after" accuracy, those with one of `EXCLUDED_VERDICTS`."""
        return frozenset(
            case_id
            for case_id, written in self.verdicts.items()
            if written.verdict in EXCLUDED_VERDICTS
        )

    def count(self, verdict: Verdict) -> int:
        """How many disagreements the user marked `verdict`."""
        return sum(written.verdict is verdict for written in self.verdicts.values())


def accuracy(cases: Iterable[ReviewCase], excluded: frozenset[str] = frozenset()) -> Rate:
    """Risk-class accuracy over `cases` less the `excluded` ids, as the run report counts it."""
    outcomes = [case.outcome for case in cases if case.case_id not in excluded]
    return summarize(outcomes, None).risk_class_accuracy


def build_review(
    info: RunInfo, stored: Sequence[StoredCase], verdicts: Mapping[str, WrittenVerdict]
) -> Review:
    """The review of a stored appliedAI run with the verdicts read back. Raises
    `NotAppliedAIRunError` for another set's run, and `ReviewFormatError` for a verdict on a case
    that isn't one of the run's disagreements."""
    if info.benchmark != CaseSet.APPLIEDAI.value:
        raise NotAppliedAIRunError(
            f"run {info.id} is a run of {info.benchmark}, not {CaseSet.APPLIEDAI.value}"
        )
    cases = tuple(ReviewCase(case) for case in stored if not case.is_scoring_error)
    errors = tuple(case.outcome.case.id for case in stored if case.is_scoring_error)
    review = Review(info, cases, errors, verdicts)
    under_review = {case.case_id for case in review.disagreements}
    stray = sorted(set(verdicts) - under_review)
    if stray:
        raise ReviewFormatError(
            f"a verdict on {', '.join(stray)}, not a disagreement of run {info.id}; "
            "move it out of the file, then run again"
        )
    return review


def load_review(conn: psycopg.Connection, run_id: UUID, path: Path = REVIEW_FILE) -> Review:
    """The review of stored run `run_id`, with the verdicts already written in `path`."""
    verdicts = read_review_file(path, run_id)
    return build_review(load_run_info(conn, run_id), load_stored_cases(conn, run_id), verdicts)


# --- reading the verdicts back ------------------------------------------------------------------


def read_review_file(path: Path, run_id: UUID) -> dict[str, WrittenVerdict]:
    """The verdicts written in the review at `path` (none when it doesn't exist yet). Raises
    `ReviewFormatError`, naming the file, for one that isn't a review (its first line isn't
    `TITLE`, so it's never overwritten), can't be read back, or holds another run's verdicts."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if text.splitlines()[:1] != [TITLE]:
        raise ReviewFormatError(
            f"{path} isn't an appliedAI review (its first line isn't `{TITLE}`); "
            "choose another --out"
        )
    try:
        verdicts = read_verdicts(text)
    except ReviewFormatError as error:
        raise ReviewFormatError(f"{path}: {error}") from None
    written_for = review_run_id(text)
    if verdicts and written_for != run_id:
        raise ReviewFormatError(
            f"{path} holds verdicts for run {written_for or 'n/a'}, not {run_id}; "
            "move it away to start the review of another run"
        )
    return verdicts


def review_run_id(text: str) -> UUID | None:
    """The run a review file was drafted from, from its `- Run id:` line."""
    found = (RUN_LINE.match(line) for line in text.splitlines())
    match = next((m for m in found if m), None)
    return UUID(match.group(1)) if match else None


def read_verdicts(text: str) -> dict[str, WrittenVerdict]:
    """Each `### Case <case id>` section's verdict, the text after `VERDICT_MARK` up to the next
    case heading (or `SECTION_END`); a section whose verdict is still empty is left out. Raises
    `ReviewFormatError` for anything a new rendering couldn't keep: a section without the mark, a
    line before it the report didn't write, a line starting with `#` in a verdict, text after a
    section's end, a case listed twice, or a verdict that doesn't start with one of `Verdict`'s
    values."""
    verdicts: dict[str, WrittenVerdict] = {}
    for case_id, lines in _case_sections(text):
        if case_id in verdicts:
            raise ReviewFormatError(f"{case_id} is listed twice")
        written = _section_text(case_id, lines)
        if written:
            verdicts[case_id] = WrittenVerdict(parse_verdict(case_id, written), written)
    return verdicts


def parse_verdict(case_id: str, text: str) -> Verdict:
    """The verdict a written text starts with (any case), followed by its end or a non-letter."""
    lowered = text.lower()
    for verdict in Verdict:
        rest = lowered.removeprefix(verdict.value)
        if rest != lowered and not rest[:1].isalpha():
            return verdict
    allowed = ", ".join(f"`{verdict.value}`" for verdict in Verdict)
    raise ReviewFormatError(f"{case_id}: a verdict starts with one of {allowed}")


def _case_sections(text: str) -> list[tuple[str, list[str]]]:
    """Each case's lines, from its heading to the next case heading or `SECTION_END`. Everything
    above the first case heading is the report's own and is ignored."""
    sections: list[tuple[str, list[str]]] = []
    is_open = False
    for line in text.splitlines():
        heading = CASE_HEADING.match(line)
        if heading:
            sections.append((heading.group(1), []))
            is_open = True
        elif not sections:
            continue
        elif is_open and SECTION_END.match(line):
            is_open = False
        elif is_open and line.startswith("#"):
            raise ReviewFormatError(
                f"{sections[-1][0]}: a line starts with `#`; a note line must not start with "
                "`#`, fix it by hand, then run again"
            )
        elif is_open:
            sections[-1][1].append(line)
        elif line.strip():
            raise ReviewFormatError(
                f"{sections[-1][0]}: a line after `{ANNEX_I_DISAGREEMENTS}` that the report "
                "didn't write; move it under a verdict, then run again"
            )
    return sections


def _section_text(case_id: str, lines: Sequence[str]) -> str:
    for index, line in enumerate(lines):
        if line.startswith(VERDICT_MARK):
            rest = [line.removeprefix(VERDICT_MARK), *lines[index + 1 :]]
            return "\n".join(rest).strip()
        if line.strip() and not line.startswith(DETAIL_PREFIXES):
            raise ReviewFormatError(
                f"{case_id}: a line before `{VERDICT_MARK}` that the report didn't write; "
                "move it after the mark, then run again"
            )
    raise ReviewFormatError(
        f"{case_id}: no line starts with `{VERDICT_MARK}` (written exactly so); "
        "fix it by hand, then run again"
    )
