"""Import the academic AI Act benchmark (Davvetas et al. 2026, arXiv 2603.09435) as cases.

The source is `scenarios.json` from github.com/davidath/ai-act-evaluation-benchmark (data under
CC BY 4.0). Each scenario is a set of short fields and a risk level; the fields are joined into
one description, unchanged, and the risk level maps onto `RiskClass`. The scenarios' generated
obligations aren't imported: this set checks the class and the role only (INIT > Test sets).
The labels are the authors', so the cite-or-ambiguous rule doesn't apply; the source's related
articles are kept as `related:` tags, not as `label_citation`.
"""

import json
import random
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError

from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseFileError, CaseLabel, CaseSet
from aiact.schemas.base import ContractModel
from aiact.schemas.enums import Language, RiskClass, Role

ACADEMIC_DIR = CASES_DIR / CaseSet.ACADEMIC.value
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


def read_scenarios(path: Path) -> tuple[Scenario, ...]:
    """Read and validate the source file (`{"license": ..., "data": [scenario, ...]}`)."""
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
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
    header = "# Converted by `aiact eval academic-import`; do not edit by hand. See SOURCE.md.\n"
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
