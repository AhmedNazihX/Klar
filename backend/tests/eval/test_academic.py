import json
from collections import Counter
from pathlib import Path

import pytest

from aiact.eval.academic import (
    convert,
    read_scenarios,
    spotcheck_sample,
    write_cases,
)
from aiact.eval.cases import BenchmarkCase, CaseFileError, CaseLabel, CaseSet, load_cases
from aiact.schemas import Language, RiskClass, Role

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "academic" / "scenarios.json"
IMPORTED_COUNT = 339
"""scenarios.json at the pinned commit in eval/cases/academic/SOURCE.md."""


def fixture_cases() -> tuple[BenchmarkCase, ...]:
    return convert(read_scenarios(FIXTURE))


def test_scenarios_convert_to_labelled_cases_in_source_order() -> None:
    cases = fixture_cases()
    assert [case.id for case in cases] == [f"academic-000{n}" for n in range(1, 5)]
    assert [case.label for case in cases] == [
        CaseLabel(risk_class=RiskClass.MINIMAL_RISK, role=Role.PROVIDER),
        CaseLabel(risk_class=RiskClass.HIGH_RISK, role=Role.DEPLOYER),
        CaseLabel(risk_class=RiskClass.LIMITED_RISK, role=Role.PROVIDER),
        CaseLabel(risk_class=RiskClass.PROHIBITED, role=Role.DEPLOYER),
    ]
    assert {case.set_name for case in cases} == {CaseSet.ACADEMIC}
    assert {case.language for case in cases} == {Language.EN}


def test_description_joins_the_fields_unchanged() -> None:
    assert fixture_cases()[0].description == (
        "Role: Provider\n"
        "System type: Text classifier\n"
        "Intended use: Sorts incoming invoices into folders\n"
        "Input data: Invoice PDFs\n"
        "Domain: Accounting"
    )


def test_related_articles_become_sorted_unique_tags_not_citations() -> None:
    case = fixture_cases()[0]
    assert case.tags == ("source:scenarios.json:data:0", "related:art:4", "related:art:50")
    assert case.label_citation == ()


def test_unknown_risk_level_is_rejected_with_its_position(tmp_path: Path) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["data"][2]["risk_level"] = "unacceptable"
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(CaseFileError, match=r"(?s)\[data\]\[2\].*risk_level"):
        read_scenarios(path)


@pytest.mark.parametrize("content", ["[]", '{"data": []}', '{"license": "x"}', "{not json"])
def test_file_without_a_scenario_list_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "scenarios.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(CaseFileError):
        read_scenarios(path)


def test_written_files_load_back_unchanged(tmp_path: Path) -> None:
    cases = fixture_cases()
    paths = write_cases(cases, tmp_path / "academic")
    assert [path.name for path in paths] == [
        "prohibited.yaml",
        "high_risk.yaml",
        "limited_risk.yaml",
        "minimal_risk.yaml",
    ]
    loaded = load_cases(CaseSet.ACADEMIC, tmp_path)
    assert sorted(loaded, key=lambda case: case.id) == list(cases)


def test_spotcheck_sample_is_seeded_and_stratified() -> None:
    cases = fixture_cases()
    sample = spotcheck_sample(cases, per_class=1)
    assert sample == spotcheck_sample(cases, per_class=1)
    assert len(sample) == len(cases)
    assert spotcheck_sample(cases, per_class=5) == tuple(cases)


def test_committed_academic_set_validates() -> None:
    cases = load_cases(CaseSet.ACADEMIC)
    assert len(cases) == IMPORTED_COUNT
    classes = Counter(case.label.risk_class for case in cases if isinstance(case.label, CaseLabel))
    assert sum(classes.values()) == IMPORTED_COUNT
    assert set(classes) == {
        RiskClass.PROHIBITED,
        RiskClass.HIGH_RISK,
        RiskClass.LIMITED_RISK,
        RiskClass.MINIMAL_RISK,
    }


def test_committed_spotcheck_sample_is_twenty_cases_five_per_class() -> None:
    sample = spotcheck_sample(load_cases(CaseSet.ACADEMIC))
    classes = Counter(case.label.risk_class for case in sample if isinstance(case.label, CaseLabel))
    assert set(classes.values()) == {5}
    assert len(sample) == 20
