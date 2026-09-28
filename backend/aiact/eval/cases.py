"""Benchmark cases: the schema, the loader and the appliedAI label mapping (INIT > Evaluation).

A case is one system description with its labelled answer. Cases live under
`eval/cases/<set>/**/*.yaml`; a YAML file holds one case (a mapping) or several (a list), so a
soft-wording pair or a consistency triple can share a file. The appliedAI extraction is JSONL in
`eval/private/` (gitignored, licence unclear) and keeps the experts' own coarse label, which
`score_appliedai` maps onto the engine's `RiskClass` and `Status` at scoring time.
"""

import json
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import Field, ValidationError, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import Language, RiskClass, Role, Status
from aiact.settings import BACKEND_DIR

EVAL_DIR = BACKEND_DIR.parent / "eval"
CASES_DIR = EVAL_DIR / "cases"
APPLIEDAI_FILE = EVAL_DIR / "private" / "appliedai.jsonl"

CASE_ID_PATTERN = r"^[a-z0-9][a-z0-9_.:-]{0,127}$"
ANNEX_POINT_PATTERN = r"^annex:(I|III)(:[0-9a-z]+)+$"
"""A provision_id inside Annex I or III, for example `annex:III:4:a`."""


class CaseSet(StrEnum):
    """The benchmark sets; each YAML set is the folder of the same name under `eval/cases/`."""

    COMMISSION_B = "commission_b"
    OWN = "own"
    SOFT_PAIRS = "soft_pairs"
    CONSISTENCY = "consistency"
    ACADEMIC = "academic"
    APPLIEDAI = "appliedai"


OWN_LABELLED_SETS = frozenset(
    {CaseSet.COMMISSION_B, CaseSet.OWN, CaseSet.SOFT_PAIRS, CaseSet.CONSISTENCY}
)
"""Sets whose labels are the student's own, so the cite-or-ambiguous rule applies."""


class AppliedAILabel(StrEnum):
    """The appliedAI experts' label: coarser than `RiskClass`, given against the 2021 draft."""

    HIGH = "high"
    PROHIBITED = "prohibited"
    LOW = "low"
    UNCLEAR = "unclear"


class CaseLabel(ContractModel):
    """The expected answer in the engine's vocabulary. An uncertain status keeps the stricter
    reading in `risk_class`, as the engine does (INIT > Risk classes)."""

    risk_class: RiskClass
    status: Status = Status.DECIDED
    role: Role | None = None
    annex_point: str | None = Field(default=None, pattern=ANNEX_POINT_PATTERN)


class BenchmarkCase(ContractModel):
    """One labelled system description."""

    id: str = Field(pattern=CASE_ID_PATTERN)
    set_name: CaseSet
    language: Language
    description: str = Field(min_length=1)
    label: CaseLabel | AppliedAILabel = Field(
        description="`AppliedAILabel` for the appliedAI set only; `CaseLabel` everywhere else."
    )
    label_citation: tuple[str, ...] = Field(
        default=(),
        description="The provision_ids or Commission example ids that settle the label.",
    )
    source_example_id: str | None = Field(
        default=None, description="The Commission example a rewritten case comes from (B4)."
    )
    notes: str | None = None
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _label_matches_set(self) -> Self:
        is_appliedai = self.set_name is CaseSet.APPLIEDAI
        if is_appliedai != isinstance(self.label, AppliedAILabel):
            raise ValueError("the appliedAI set, and only it, uses an appliedAI label")
        return self

    @model_validator(mode="after")
    def _cite_or_ambiguous(self) -> Self:
        """INIT > Label rules: a label cites what settles it, or is ambiguous with the open
        question and both readings in `notes`."""
        if self.set_name not in OWN_LABELLED_SETS or not isinstance(self.label, CaseLabel):
            return self
        if self.label.status is Status.LEGALLY_AMBIGUOUS:
            if not self.notes:
                raise ValueError("an ambiguous label needs the open question and readings in notes")
        elif not self.label_citation:
            raise ValueError("a label that isn't legally_ambiguous needs a label_citation")
        return self


class CaseFileError(ValueError):
    """A case file that can't be read or doesn't validate; the message names the file."""


def load_cases(case_set: CaseSet, cases_dir: Path = CASES_DIR) -> tuple[BenchmarkCase, ...]:
    """Load and validate every `*.yaml` file under `cases_dir/<set>/`, subfolders included."""
    set_dir = cases_dir / case_set.value
    if not set_dir.is_dir():
        raise FileNotFoundError(f"no case folder for set {case_set.value}: {set_dir}")
    cases = tuple(case for path in sorted(set_dir.rglob("*.yaml")) for case in load_yaml_file(path))
    for case in cases:
        if case.set_name is not case_set:
            raise CaseFileError(f"case {case.id} has set_name {case.set_name} in {set_dir}")
    return _unique(cases, set_dir)


def load_yaml_file(path: Path) -> tuple[BenchmarkCase, ...]:
    """Validate one YAML file holding a single case (a mapping) or several (a list)."""
    try:
        document: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CaseFileError(f"{path}: not valid YAML: {exc}") from exc
    records = [document] if isinstance(document, dict) else document
    if not isinstance(records, list) or not records:
        raise CaseFileError(f"{path}: expected a case mapping or a non-empty list of cases")
    return tuple(_validate(record, f"{path}[{index}]") for index, record in enumerate(records))


def load_jsonl(path: Path) -> tuple[BenchmarkCase, ...]:
    """Validate a JSONL file with one case per non-blank line, such as `APPLIEDAI_FILE`."""
    cases: list[BenchmarkCase] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CaseFileError(f"{path}:{number}: not valid JSON: {exc.msg}") from exc
        cases.append(_validate(record, f"{path}:{number}"))
    return _unique(cases, path)


def _validate(record: object, where: str) -> BenchmarkCase:
    try:
        return BenchmarkCase.model_validate(record)
    except ValidationError as exc:
        raise CaseFileError(f"{where}: {exc}") from exc


def _unique(cases: Iterable[BenchmarkCase], where: Path) -> tuple[BenchmarkCase, ...]:
    checked = tuple(cases)
    seen: set[str] = set()
    for case in checked:
        if case.id in seen:
            raise CaseFileError(f"duplicate case id {case.id} in {where}")
        seen.add(case.id)
    return checked


class AppliedAIScore(ContractModel):
    """How one engine answer scores against an appliedAI label (INIT > Label mapping)."""

    is_match: bool
    needs_disagreement_review: bool = Field(
        description="Every mismatch, plus `out_of_scope` for `low`, which matches but is reviewed."
    )
    is_counted_separately: bool = Field(
        description="`needs_more_information` on an `unclear` case, reported on its own."
    )


APPLIEDAI_MATCHES: dict[AppliedAILabel, frozenset[RiskClass]] = {
    AppliedAILabel.HIGH: frozenset({RiskClass.HIGH_RISK}),
    AppliedAILabel.PROHIBITED: frozenset({RiskClass.PROHIBITED}),
    AppliedAILabel.LOW: frozenset(
        {RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK, RiskClass.OUT_OF_SCOPE}
    ),
}
"""The engine classes each class-like label accepts. `unclear` is scored on status instead.
Annex II references in the labels are read as Annex I."""


def score_appliedai(label: AppliedAILabel, risk_class: RiskClass, status: Status) -> AppliedAIScore:
    """Score an engine answer against an appliedAI label.

    For high, prohibited and low an uncertain answer is scored on its working-assumption class,
    so "assumed high-risk pending legal review" matches `high`.
    """
    if label is AppliedAILabel.UNCLEAR:
        is_match = status is Status.LEGALLY_AMBIGUOUS
        return AppliedAIScore(
            is_match=is_match,
            needs_disagreement_review=not is_match,
            is_counted_separately=status is Status.NEEDS_MORE_INFORMATION,
        )
    is_match = risk_class in APPLIEDAI_MATCHES[label]
    is_out_of_scope_low = label is AppliedAILabel.LOW and risk_class is RiskClass.OUT_OF_SCOPE
    return AppliedAIScore(
        is_match=is_match,
        needs_disagreement_review=not is_match or is_out_of_scope_low,
        is_counted_separately=False,
    )
