"""Import the academic AI Act benchmark (Davvetas et al. 2026, arXiv 2603.09435) as cases.

The source is `scenarios.json` from github.com/davidath/ai-act-evaluation-benchmark (data under
CC BY 4.0). Each scenario is a set of short fields and a risk level; the fields are joined into
one description, unchanged, and the risk level maps onto `RiskClass`. The scenarios' generated
obligations aren't imported: this set checks the class and the role only (INIT > Test sets).
The labels are the authors', so the cite-or-ambiguous rule doesn't apply; the source's related
articles are kept as `related:` tags, not as `label_citation`.

The source is pinned: the import refuses a `scenarios.json` whose sha256 isn't `SOURCE_SHA256`.

The user's spot-check decisions live in `eval/cases/academic_overrides.yaml` (outside the set
folder, so the case loader never reads it). The import applies them on top of the source: a
changed status or class, notes, citations and extra tags per case id. Each override names the
source risk level and a fragment of the description it expects, so an override can't land on
the wrong case; an unknown id or a failed expectation is an error.

Last, the pattern-2 rule (user decision, B12 spot-check) tags every decided low case whose
system type starts with "Rule-based" or "Template-based" `scoring:low-or-out-of-scope`.
"""

import hashlib
import json
import random
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError

from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseFileError, CaseLabel, CaseSet
from aiact.eval.metrics import LOW_BUCKET, LOW_OR_OUT_OF_SCOPE_TAG
from aiact.schemas.base import ContractModel
from aiact.schemas.enums import Language, RiskClass, Role, Status

ACADEMIC_DIR = CASES_DIR / CaseSet.ACADEMIC.value
OVERRIDES_FILE = CASES_DIR / "academic_overrides.yaml"
SOURCE_COMMIT = "d323167f5597dfd9365b376c9afe7b0e414eb81a"
SOURCE_SHA256 = "0fc1c7491372cf0aa787b4b650f77245ec775f8bff0c4c84f253435c7dcb1b25"
"""scenarios.json at `SOURCE_COMMIT`; keep both in sync with eval/cases/academic/SOURCE.md."""

RULE_OR_TEMPLATE_BASED = re.compile(r"^(rule|template)[-\u2011]based", re.IGNORECASE)
"""Pattern 2: a system type the source calls rule- or template-based (hyphen or U+2011)."""
SPOTCHECK_SEED = 20260928
SPOTCHECK_PER_CLASS = 5
"""Five per class gives the story's ~20-case spot-check across all four risk levels."""

SourceRiskLevel = Literal["prohibited", "high-risk", "limited", "minimal"]

RISK_LEVELS: dict[str, RiskClass] = {
    "prohibited": RiskClass.PROHIBITED,
    "high-risk": RiskClass.HIGH_RISK,
    "limited": RiskClass.LIMITED_RISK,
    "minimal": RiskClass.MINIMAL_RISK,
}
ROLES: dict[str, Role] = {"Provider": Role.PROVIDER, "Deployer": Role.DEPLOYER}


class Scenario(ContractModel):
    """One record of the source's `scenarios.json` `data` list, validated as external input."""

    role: Literal["Provider", "Deployer"]
    intended_use: str = Field(min_length=1)
    system_type: str = Field(min_length=1)
    input_data: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    related_articles: tuple[int, ...]
    obligations: tuple[str, ...]
    risk_level: SourceRiskLevel


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CaseFileError(f"{path}: can't be read: {exc.strerror or exc}") from exc


def _decode(path: Path, content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaseFileError(f"{path}: not UTF-8 text") from exc


def read_scenarios(path: Path, expected_sha256: str = SOURCE_SHA256) -> tuple[Scenario, ...]:
    """Read and validate the source file (`{"license": ..., "data": [scenario, ...]}`); a file
    whose sha256 isn't `expected_sha256` is refused."""
    content = _read_bytes(path)
    digest = hashlib.sha256(content).hexdigest()
    if digest != expected_sha256:
        raise CaseFileError(
            f"{path}: sha256 {digest} isn't the pinned {expected_sha256} "
            f"(scenarios.json at commit {SOURCE_COMMIT})"
        )
    try:
        document: object = json.loads(_decode(path, content))
    except json.JSONDecodeError as exc:
        raise CaseFileError(f"{path}: not valid JSON: {exc.msg}") from exc
    records = document.get("data") if isinstance(document, dict) else None
    if not isinstance(records, list) or not records:
        raise CaseFileError(f"{path}: expected an object with a non-empty `data` list")
    return tuple(
        _scenario(record, f"{path}[data][{index}]") for index, record in enumerate(records)
    )


def _scenario(record: object, where: str) -> Scenario:
    try:
        return Scenario.model_validate(record)
    except ValidationError as exc:
        raise CaseFileError(f"{where}: {exc}") from exc


def case_id(index: int) -> str:
    """The case id for the scenario at 0-based `index` in the source file, e.g. `academic-0001`."""
    return f"academic-{index + 1:04d}"


def describe(scenario: Scenario) -> str:
    """Join the scenario's fields into the description the engine reads, wording unchanged."""
    return "\n".join(
        (
            f"Role: {scenario.role}",
            f"System type: {scenario.system_type}",
            f"Intended use: {scenario.intended_use}",
            f"Input data: {scenario.input_data}",
            f"Domain: {scenario.domain}",
        )
    )


def to_case(index: int, scenario: Scenario) -> BenchmarkCase:
    """Convert one scenario; the source position and related articles become tags."""
    related = tuple(f"related:art:{article}" for article in sorted(set(scenario.related_articles)))
    return BenchmarkCase(
        id=case_id(index),
        set_name=CaseSet.ACADEMIC,
        language=Language.EN,
        description=describe(scenario),
        label=CaseLabel(risk_class=RISK_LEVELS[scenario.risk_level], role=ROLES[scenario.role]),
        tags=(f"source:scenarios.json:data:{index}", *related),
    )


def convert(scenarios: Sequence[Scenario]) -> tuple[BenchmarkCase, ...]:
    """Convert every scenario, keeping the source order."""
    return tuple(to_case(index, scenario) for index, scenario in enumerate(scenarios))


class LabelOverride(ContractModel):
    """One spot-check decision, applied on top of the converted case with the same id."""

    id: str = Field(min_length=1)
    expect_class: SourceRiskLevel = Field(description="The source risk level the case must have.")
    expect_text: str = Field(min_length=1, description="A fragment its description must contain.")
    status: Status | None = None
    risk_class: RiskClass | None = None
    label_citation: tuple[str, ...] = ()
    notes: str = Field(min_length=1, description="Written into the case's `notes`.")
    reason: str = Field(min_length=1, description="Why, citing the provision; stays here.")
    approved: str = Field(min_length=1, description="Who approved it and when.")
    add_tags: tuple[str, ...] = ()


def read_overrides(path: Path = OVERRIDES_FILE) -> tuple[LabelOverride, ...]:
    """Read the override list; an unreadable or invalid file raises `CaseFileError`."""
    try:
        document: object = yaml.safe_load(_decode(path, _read_bytes(path)))
    except yaml.YAMLError as exc:
        raise CaseFileError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(document, list):
        raise CaseFileError(f"{path}: expected a list of overrides")
    overrides = tuple(
        _override(record, f"{path}[{index}]") for index, record in enumerate(document)
    )
    ids = [override.id for override in overrides]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise CaseFileError(f"{path}: more than one override for {', '.join(duplicates)}")
    return overrides


def _override(record: object, where: str) -> LabelOverride:
    try:
        return LabelOverride.model_validate(record)
    except ValidationError as exc:
        raise CaseFileError(f"{where}: {exc}") from exc


def apply_overrides(
    cases: Sequence[BenchmarkCase], overrides: Iterable[LabelOverride]
) -> tuple[BenchmarkCase, ...]:
    """The cases with each override applied; an override for an unknown id, or one whose
    expected class or text doesn't match its case, raises."""
    by_id = {override.id: override for override in overrides}
    unknown = sorted(set(by_id) - {case.id for case in cases})
    if unknown:
        raise CaseFileError(f"overrides for case ids the source doesn't have: {', '.join(unknown)}")
    return tuple(_overridden(case, by_id[case.id]) if case.id in by_id else case for case in cases)


def _check_target(case: BenchmarkCase, override: LabelOverride) -> None:
    """The override's expectations, checked on the converted (source) case."""
    source_class = case.label.risk_class if isinstance(case.label, CaseLabel) else None
    if source_class is not RISK_LEVELS[override.expect_class]:
        raise CaseFileError(
            f"override for {case.id} expects source class {override.expect_class}, "
            f"the case has {source_class}"
        )
    if override.expect_text not in case.description:
        # The description itself is never put into the message.
        raise CaseFileError(
            f"override for {case.id} expects its description to contain {override.expect_text!r}"
        )


def _overridden(case: BenchmarkCase, override: LabelOverride) -> BenchmarkCase:
    _check_target(case, override)
    label_changes = {
        key: value
        for key, value in (("status", override.status), ("risk_class", override.risk_class))
        if value is not None
    }
    record = case.model_dump() | {
        "label": case.model_dump()["label"] | label_changes,
        "label_citation": override.label_citation or case.label_citation,
        "notes": override.notes,
        "tags": (*case.tags, *override.add_tags),
    }
    try:
        return BenchmarkCase.model_validate(record)
    except ValidationError as exc:
        raise CaseFileError(f"override for {case.id} gives an invalid case: {exc}") from exc


def is_low_or_out_of_scope(scenario: Scenario, case: BenchmarkCase) -> bool:
    """Pattern 2: a decided low case whose source system type is rule- or template-based."""
    label = case.label
    return (
        isinstance(label, CaseLabel)
        and label.status is Status.DECIDED
        and label.risk_class in LOW_BUCKET
        and RULE_OR_TEMPLATE_BASED.match(scenario.system_type) is not None
    )


def tag_low_or_out_of_scope(
    scenarios: Sequence[Scenario], cases: Sequence[BenchmarkCase]
) -> tuple[BenchmarkCase, ...]:
    """Add the pattern-2 tag to every qualifying case; `cases` are in source order."""
    if len(scenarios) != len(cases):
        raise ValueError("expected one case per scenario, in source order")
    return tuple(
        _with_tag(case, LOW_OR_OUT_OF_SCOPE_TAG) if is_low_or_out_of_scope(scenario, case) else case
        for scenario, case in zip(scenarios, cases, strict=True)
    )


def _with_tag(case: BenchmarkCase, tag: str) -> BenchmarkCase:
    return case if tag in case.tags else case.model_copy(update={"tags": (*case.tags, tag)})


def build_cases(
    scenarios: Sequence[Scenario], overrides: Iterable[LabelOverride]
) -> tuple[BenchmarkCase, ...]:
    """The whole import: convert, apply the overrides, then the pattern-2 rule."""
    return tag_low_or_out_of_scope(scenarios, apply_overrides(convert(scenarios), overrides))


def write_cases(cases: Iterable[BenchmarkCase], out_dir: Path = ACADEMIC_DIR) -> tuple[Path, ...]:
    """Write one YAML list per risk class (`<risk_class>.yaml`), in id order; returns the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    by_class: dict[RiskClass, list[BenchmarkCase]] = {}
    for case in sorted(cases, key=lambda case: case.id):
        if isinstance(case.label, CaseLabel):
            by_class.setdefault(case.label.risk_class, []).append(case)
    paths: list[Path] = []
    for risk_class in RISK_LEVELS.values():
        if risk_class not in by_class:
            continue
        path = out_dir / f"{risk_class.value}.yaml"
        records = [
            case.model_dump(mode="json", exclude_defaults=True) for case in by_class[risk_class]
        ]
        path.write_text(_dump(records), encoding="utf-8")
        paths.append(path)
    return tuple(paths)


class _BlockDumper(yaml.SafeDumper):
    """Writes multi-line strings as `|` blocks, so a description reads as it does in the source."""


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_BlockDumper.add_representer(str, _represent_str)


def _dump(records: list[dict[str, object]]) -> str:
    header = (
        "# Generated by `aiact evaluate academic-import` from the source and\n"
        "# eval/cases/academic_overrides.yaml; do not edit. See SOURCE.md.\n"
    )
    body = yaml.dump(records, Dumper=_BlockDumper, allow_unicode=True, sort_keys=False, width=1000)
    return header + body


def spotcheck_sample(
    cases: Sequence[BenchmarkCase],
    per_class: int = SPOTCHECK_PER_CLASS,
    seed: int = SPOTCHECK_SEED,
) -> tuple[BenchmarkCase, ...]:
    """A seeded sample of `per_class` cases from each risk class, in id order."""
    rng = random.Random(seed)
    picked: list[BenchmarkCase] = []
    for risk_class in RISK_LEVELS.values():
        pool = sorted(
            (
                c
                for c in cases
                if isinstance(c.label, CaseLabel) and c.label.risk_class is risk_class
            ),
            key=lambda case: case.id,
        )
        picked.extend(rng.sample(pool, min(per_class, len(pool))))
    return tuple(sorted(picked, key=lambda case: case.id))
