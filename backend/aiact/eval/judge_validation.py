"""The judge's validation (INIT > Evaluation > Judge; story V4, decision 006).

About fifty English and German cases (`eval/judge_validation/cases.yaml`), each one claim and the
text it must rest on, are labelled yes or no by hand (`labels.yaml`, the user's). Both judges answer
every case, so they can be compared with the labels and with each other: Jev's probability of yes
and the backup judge's verdict with its reason go to `answers.jsonl` as each case ends, so an
interrupted run resumes and an answered case is never paid for twice. `report.md` then gives each
judge's agreement with the labels (rate and Cohen's kappa, per language and per check), Jev's
calibration (Brier score, expected calibration error and the reliability bins), and for each
candidate margin around 0.5 how many cases would go to the backup judge and how well the combined
judge agrees with the labels. The margin is the unsure threshold `aiact.eval.judge` applies.
"""

import hashlib
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import Field, ValidationError, model_validator

from aiact.eval.cases import EVAL_DIR, _UniqueKeyLoader
from aiact.eval.judge import (
    BACKUP_CALL_ESTIMATE_USD,
    JEV_CALL_ESTIMATE_USD,
    YES_AT,
    BackupJudge,
    JevJudge,
    JudgeCheck,
    JudgeError,
    JudgeItem,
    failure,
    is_unsure,
    needs_backup,
)
from aiact.llm import DecisionsError
from aiact.schemas import Language
from aiact.schemas.base import ContractModel

logger = logging.getLogger(__name__)

VALIDATION_DIR = EVAL_DIR / "judge_validation"
CASES_FILE = VALIDATION_DIR / "cases.yaml"
LABELS_FILE = VALIDATION_DIR / "labels.yaml"
ANSWERS_FILE = VALIDATION_DIR / "answers.jsonl"
REPORT_FILE = VALIDATION_DIR / "report.md"

MARGINS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
"""The candidate unsure margins: 0.0 lets Jev decide everything; 0.5 sends every case Jev isn't
certain about (probability strictly between 0 and 1) to the backup judge."""
CALIBRATION_BINS = 5
CASE_ESTIMATE_USD = JEV_CALL_ESTIMATE_USD + BACKUP_CALL_ESTIMATE_USD
"""The most one case can cost: both judges answer it."""
DEFAULT_MAX_COST_USD = 0.10


class JudgeValidationError(ValueError):
    """A validation file can't be read: bad YAML, an unknown or repeated id, a label that isn't
    yes or no."""


class ValidationCase(JudgeItem):
    """One hand-labelled case; its label lives apart, in `labels.yaml`."""

    id: str = Field(pattern=r"^jv-(en|de)-\d{2}$")
    provisions: tuple[str, ...] = Field(
        default=(), description="The provisions the source text quotes, for the reader."
    )

    @model_validator(mode="after")
    def _id_names_the_language(self) -> "ValidationCase":
        if self.id.split("-")[1] != self.language.value:
            raise ValueError(f"{self.id} is not a {self.language.value} id")
        return self


def _read_yaml(path: Path) -> object:
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise JudgeValidationError(f"{path}: can't be read: {exc}") from exc


def load_cases(path: Path = CASES_FILE) -> tuple[ValidationCase, ...]:
    """Every case of `path`, a YAML list, in file order."""
    records = _read_yaml(path)
    if not isinstance(records, list) or not records:
        raise JudgeValidationError(f"{path}: expected a non-empty list of cases")
    try:
        cases = tuple(ValidationCase.model_validate(record) for record in records)
    except ValidationError as exc:
        raise JudgeValidationError(f"{path}: {exc.error_count()} invalid fields") from exc
    ids = [case.id for case in cases]
    repeated = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if repeated:
        raise JudgeValidationError(f"{path}: repeated ids {', '.join(repeated)}")
    return cases


def load_labels(cases: Sequence[ValidationCase], path: Path = LABELS_FILE) -> dict[str, bool]:
    """The hand labels by case id: yes (true) or no (false). A case left empty is unlabelled and
    not in the result."""
    document = _read_yaml(path)
    if not isinstance(document, dict):
        raise JudgeValidationError(f"{path}: expected a mapping of case id to yes or no")
    known = {case.id for case in cases}
    unknown = sorted(str(key) for key in document if key not in known)
    if unknown:
        raise JudgeValidationError(f"{path}: unknown case ids {', '.join(unknown)}")
    wrong = sorted(
        str(key) for key, value in document.items() if not isinstance(value, bool | None)
    )
    if wrong:
        raise JudgeValidationError(f"{path}: not yes, no or empty: {', '.join(wrong)}")
    return {str(key): value for key, value in document.items() if isinstance(value, bool)}


# --- the run -------------------------------------------------------------------------------------


class JudgeRecord(ContractModel):
    """Both judges' answers to one case, a line of the answers file. A failed judge has its
    answer None and its error named by type or status only, never the case's text."""

    case_id: str
    input_sha256: str
    jev_model: str
    p_yes: float | None = Field(ge=0.0, le=1.0)
    jev_error: str | None = None
    backup_model: str
    backup_provider: str
    holds: bool | None
    reason: str | None
    backup_error: str | None = None
    cost_usd: float = Field(ge=0)
    is_cost_estimated: bool = Field(
        default=False, description="The backup call reported no cost; its estimate counts."
    )
    tokens: int = Field(ge=0)

    @property
    def is_complete(self) -> bool:
        return self.p_yes is not None and self.holds is not None


def input_sha256(case: ValidationCase) -> str:
    """Identifies what both judges read of a case, so an edited case is asked again."""
    text = "\n".join((case.check.value, case.language.value, case.claim, case.source))
    return hashlib.sha256(text.encode()).hexdigest()


def judge_case(case: ValidationCase, jev: JevJudge, backup: BackupJudge) -> JudgeRecord:
    """Both judges' answers; a judge that fails leaves its error, and what it spent counts."""
    p_yes, jev_error, cost, tokens = None, None, 0.0, 0
    try:
        answer = jev.ask(case)
        p_yes, cost, tokens = answer.p_yes, answer.cost_usd, answer.tokens
    except DecisionsError as exc:
        jev_error, cost, tokens = failure(exc), exc.cost_usd, exc.tokens
    holds, reason, backup_error, is_estimated = None, None, None, False
    try:
        verdict = backup.ask(case)
        holds, reason, is_estimated = verdict.holds, verdict.reason, verdict.is_cost_estimated
        cost, tokens = cost + verdict.cost_usd, tokens + verdict.tokens
    except JudgeError as exc:
        backup_error, is_estimated = str(exc), exc.is_cost_estimated
        cost, tokens = cost + exc.cost_usd, tokens + exc.tokens
    return JudgeRecord(
        case_id=case.id,
        input_sha256=input_sha256(case),
        jev_model=jev.model,
        p_yes=p_yes,
        jev_error=jev_error,
        backup_model=backup.model,
        backup_provider=backup.provider,
        holds=holds,
        reason=reason,
        backup_error=backup_error,
        cost_usd=cost,
        is_cost_estimated=is_estimated,
        tokens=tokens,
    )


def read_records(path: Path = ANSWERS_FILE) -> dict[str, JudgeRecord]:
    """The latest record per case id; none when the file doesn't exist yet."""
    if not path.exists():
        return {}
    records: dict[str, JudgeRecord] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = JudgeRecord.model_validate_json(line)
        except ValidationError as exc:
            raise JudgeValidationError(f"{path}: line {number} is not a judge record") from exc
        records[record.case_id] = record
    return records


@dataclass(frozen=True)
class Route:
    """The models a record must come from to count."""

    jev_model: str
    backup_model: str
    backup_provider: str

    def record_for(
        self, case: ValidationCase, records: Mapping[str, JudgeRecord]
    ) -> JudgeRecord | None:
        """The case's record when it answers the case as it is now and comes from this route
        (one judge may have failed in it); else None."""
        record = records.get(case.id)
        if record is None or record.input_sha256 != input_sha256(case):
            return None
        models = (record.jev_model, record.backup_model, record.backup_provider)
        return (
            record if models == (self.jev_model, self.backup_model, self.backup_provider) else None
        )


def answered_records(
    cases: Sequence[ValidationCase], records: Mapping[str, JudgeRecord], route: Route
) -> tuple[JudgeRecord, ...]:
    """The current records from `route` that hold both judges' answers, in case order."""
    found = (route.record_for(case, records) for case in cases)
    return tuple(record for record in found if record is not None and record.is_complete)


def cases_to_run(
    cases: Sequence[ValidationCase], records: Mapping[str, JudgeRecord], route: Route
) -> tuple[ValidationCase, ...]:
    """The cases without both answers from `route`: new, edited or failed ones."""
    answered = {record.case_id for record in answered_records(cases, records, route)}
    return tuple(case for case in cases if case.id not in answered)


@dataclass(frozen=True)
class RunSummary:
    planned: int
    answered: int
    failed: int
    cost_usd: float
    tokens: int
    stopped_by_cap: bool


def run_validation(
    cases: Sequence[ValidationCase],
    judge_one: Callable[[ValidationCase], JudgeRecord],
    *,
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
    path: Path = ANSWERS_FILE,
) -> RunSummary:
    """Judge `cases` one at a time, appending each record as it ends. No case starts unless the
    money spent plus `CASE_ESTIMATE_USD` stays within `max_cost_usd`."""
    spent, tokens, answered, failed = 0.0, 0, 0, 0
    for case in cases:
        if spent + CASE_ESTIMATE_USD > max_cost_usd:
            return RunSummary(len(cases), answered, failed, spent, tokens, stopped_by_cap=True)
        record = judge_one(case)
        _append(path, record)
        spent, tokens = spent + record.cost_usd, tokens + record.tokens
        answered, failed = answered + record.is_complete, failed + (not record.is_complete)
    return RunSummary(len(cases), answered, failed, spent, tokens, stopped_by_cap=False)


def _append(path: Path, record: JudgeRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{record.model_dump_json()}\n")


def estimate_usd(count: int) -> float:
    """An upper estimate for `count` cases (both judges each)."""
    return count * CASE_ESTIMATE_USD


# --- the measures --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Scored:
    """A labelled case with its current record."""

    case: ValidationCase
    record: JudgeRecord
    label: bool


@dataclass(frozen=True)
class Agreement:
    """How often two yes/no answers agree, over the cases both gave."""

    n: int
    agreed: int
    kappa: float | None
    """Cohen's kappa; None when there is no case or chance agreement is already certain."""

    @property
    def rate(self) -> float | None:
        return self.agreed / self.n if self.n else None


def agreement(pairs: Iterable[tuple[bool, bool]]) -> Agreement:
    pairs = tuple(pairs)
    n = len(pairs)
    agreed = sum(left == right for left, right in pairs)
    if not n:
        return Agreement(0, 0, None)
    left_yes = sum(left for left, _ in pairs) / n
    right_yes = sum(right for _, right in pairs) / n
    chance = left_yes * right_yes + (1 - left_yes) * (1 - right_yes)
    kappa = None if chance == 1 else (agreed / n - chance) / (1 - chance)
    return Agreement(n, agreed, kappa)


@dataclass(frozen=True)
class CalibrationBin:
    low: float
    high: float
    n: int
    mean_p: float | None
    yes_rate: float | None


def calibration_bins(
    points: Sequence[tuple[float, bool]], bins: int = CALIBRATION_BINS
) -> tuple[CalibrationBin, ...]:
    """Equal-width bins of Jev's probability of yes, each with the share of cases labelled yes;
    the last bin includes 1.0."""
    result = []
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        inside = [
            (p, label) for p, label in points if low <= p < high or (index == bins - 1 and p == 1)
        ]
        count = len(inside)
        mean_p = sum(p for p, _ in inside) / count if count else None
        yes_rate = sum(label for _, label in inside) / count if count else None
        result.append(CalibrationBin(low, high, count, mean_p, yes_rate))
    return tuple(result)


def brier_score(points: Sequence[tuple[float, bool]]) -> float | None:
    """The mean squared distance between Jev's probability and the label (0 is perfect)."""
    return sum((p - label) ** 2 for p, label in points) / len(points) if points else None


def expected_calibration_error(bins: Sequence[CalibrationBin]) -> float | None:
    """The bins' gap between mean probability and yes rate, weighted by their share of cases."""
    total = sum(item.n for item in bins)
    if not total:
        return None
    return sum(
        item.n / total * abs(item.mean_p - item.yes_rate)
        for item in bins
        if item.mean_p is not None and item.yes_rate is not None
    )


def combined_verdict(record: JudgeRecord, margin: float) -> bool | None:
    """The judge's answer at `margin` (as `Judge.judge` gives it): Jev's when sure, else the
    backup judge's; None when the judge that had to answer failed."""
    if record.p_yes is not None and not is_unsure(record.p_yes, margin):
        return record.p_yes >= YES_AT
    return record.holds


@dataclass(frozen=True)
class MarginRow:
    margin: float
    sent_to_backup: int
    """Of the labelled cases with a record: those Jev was unsure about or failed on."""
    with_labels: Agreement
    unmeasured: int
    """Labelled cases with no combined answer (the judge that had to answer failed)."""


def margin_rows(
    scored: Sequence[Scored], margins: Sequence[float] = MARGINS
) -> tuple[MarginRow, ...]:
    rows = []
    for margin in margins:
        answers = [(combined_verdict(s.record, margin), s.label) for s in scored]
        pairs = [(answer, label) for answer, label in answers if answer is not None]
        sent = sum(needs_backup(s.record.p_yes, margin) for s in scored)
        rows.append(MarginRow(margin, sent, agreement(pairs), len(answers) - len(pairs)))
    return tuple(rows)


def recommended_margin(rows: Sequence[MarginRow]) -> float | None:
    """The smallest margin with the highest agreement with the labels: no margin sends more
    cases to the backup judge without agreeing more often. None without a measured row."""
    measured = [row for row in rows if row.with_labels.rate is not None]
    if not measured:
        return None
    best = max(row.with_labels.agreed / row.with_labels.n for row in measured)
    return min(row.margin for row in measured if row.with_labels.agreed / row.with_labels.n == best)


# --- the report ----------------------------------------------------------------------------------


def scored_cases(
    cases: Sequence[ValidationCase],
    labels: Mapping[str, bool],
    records: Mapping[str, JudgeRecord],
    route: Route,
) -> tuple[Scored, ...]:
    """The labelled cases whose record answers them as they are now, from `route`. A record
    with one judge failed still counts: the measures leave out only that judge's answer."""
    return tuple(
        Scored(case, record, labels[case.id])
        for case in cases
        if case.id in labels and (record := route.record_for(case, records)) is not None
    )


def jev_pairs(scored: Iterable[Scored]) -> list[tuple[bool, bool]]:
    return [(s.record.p_yes >= YES_AT, s.label) for s in scored if s.record.p_yes is not None]


def backup_pairs(scored: Iterable[Scored]) -> list[tuple[bool, bool]]:
    return [(s.record.holds, s.label) for s in scored if s.record.holds is not None]


def jev_points(scored: Iterable[Scored]) -> list[tuple[float, bool]]:
    return [(s.record.p_yes, s.label) for s in scored if s.record.p_yes is not None]


def judges_pairs(records: Iterable[JudgeRecord]) -> list[tuple[bool, bool]]:
    """Jev's answer at 0.5 against the backup judge's, over every complete record: needs no
    labels."""
    return [
        (record.p_yes >= YES_AT, record.holds)
        for record in records
        if record.p_yes is not None and record.holds is not None
    ]


def in_language(scored: Sequence[Scored], language: Language) -> list[Scored]:
    return [s for s in scored if s.case.language is language]


def in_check(scored: Sequence[Scored], check: JudgeCheck) -> list[Scored]:
    return [s for s in scored if s.case.check is check]
