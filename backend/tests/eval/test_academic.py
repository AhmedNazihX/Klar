import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from aiact.eval.academic import (
    RULE_OR_TEMPLATE_BASED,
    LabelOverride,
    Scenario,
    apply_overrides,
    build_cases,
    convert,
    read_overrides,
    read_scenarios,
    spotcheck_sample,
    write_cases,
)
from aiact.eval.cases import BenchmarkCase, CaseFileError, CaseLabel, CaseSet, load_cases
from aiact.eval.metrics import LOW_BUCKET, LOW_OR_OUT_OF_SCOPE_TAG
from aiact.schemas import Language, RiskClass, Role, Status

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "academic" / "scenarios.json"
FIXTURE_SHA256 = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
FIXTURE_OVERRIDES = FIXTURE.with_name("overrides.yaml")
IMPORTED_COUNT = 339
"""scenarios.json at the pinned commit in eval/cases/academic/SOURCE.md."""
RULE_TAGGED_COUNT = 95
"""Decided low cases in the pinned source whose system type is rule- or template-based."""
SYSTEM_TYPE_PREFIX = "System type: "


def fixture_scenarios() -> tuple[Scenario, ...]:
    return read_scenarios(FIXTURE, FIXTURE_SHA256)


def fixture_cases() -> tuple[BenchmarkCase, ...]:
    return convert(fixture_scenarios())


def write_json(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def read_unpinned(path: Path) -> tuple[Scenario, ...]:
    return read_scenarios(path, hashlib.sha256(path.read_bytes()).hexdigest())


# --- conversion --------------------------------------------------------------------------------


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


# --- reading the source ------------------------------------------------------------------------


def test_a_source_with_another_checksum_is_refused() -> None:
    with pytest.raises(CaseFileError, match="isn't the pinned"):
        read_scenarios(FIXTURE)
    assert len(read_scenarios(FIXTURE, FIXTURE_SHA256)) == 4


def test_unknown_risk_level_is_rejected_with_its_position(tmp_path: Path) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["data"][2]["risk_level"] = "unacceptable"
    with pytest.raises(CaseFileError, match=r"(?s)\[data\]\[2\].*risk_level"):
        read_unpinned(write_json(tmp_path, document))


@pytest.mark.parametrize("content", ["[]", '{"data": []}', '{"license": "x"}', "{not json"])
def test_file_without_a_scenario_list_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "scenarios.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(CaseFileError):
        read_unpinned(path)


def test_unreadable_or_non_utf8_files_are_case_file_errors(tmp_path: Path) -> None:
    with pytest.raises(CaseFileError, match="can't be read"):
        read_scenarios(tmp_path)
    with pytest.raises(CaseFileError, match="can't be read"):
        read_overrides(tmp_path)
    binary = tmp_path / "latin1.yaml"
    binary.write_bytes("- id: caf\xe9\n".encode("latin-1"))
    with pytest.raises(CaseFileError, match="not UTF-8"):
        read_unpinned(binary)
    with pytest.raises(CaseFileError, match="not UTF-8"):
        read_overrides(binary)


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


# --- overrides ---------------------------------------------------------------------------------


def override(**changes: object) -> LabelOverride:
    fields: dict[str, object] = {
        "id": "academic-0001",
        "expect_class": "minimal",
        "expect_text": "invoices",
        "notes": "n",
        "reason": "r",
        "approved": "a",
    }
    return LabelOverride.model_validate(fields | changes)


def test_overrides_change_status_notes_citations_and_tags() -> None:
    cases = apply_overrides(fixture_cases(), read_overrides(FIXTURE_OVERRIDES))
    tagged, ambiguous, untouched = cases[0], cases[1], cases[2]
    assert ambiguous.label == CaseLabel(
        risk_class=RiskClass.HIGH_RISK, status=Status.LEGALLY_AMBIGUOUS, role=Role.DEPLOYER
    )
    assert ambiguous.label_citation == ("annex:III:4:a",)
    assert ambiguous.notes == "Open question and both readings."
    assert tagged.label == fixture_cases()[0].label
    assert tagged.tags[-1] == "fixture:extra"
    assert untouched == fixture_cases()[2]


def test_override_for_an_unknown_id_fails_loudly() -> None:
    with pytest.raises(CaseFileError, match="academic-9999"):
        apply_overrides(fixture_cases(), [override(id="academic-9999")])


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"expect_class": "high-risk"}, "expects source class high-risk"),
        ({"expect_text": "payroll"}, "expects its description to contain 'payroll'"),
    ],
    ids=["wrong-class", "wrong-text"],
)
def test_override_whose_target_does_not_match_fails(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(CaseFileError, match=message):
        apply_overrides(fixture_cases(), [override(**changes)])


def test_duplicate_or_invalid_overrides_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "overrides.yaml"
    entry = (
        "- {id: academic-0001, expect_class: minimal, expect_text: x,"
        " notes: n, reason: r, approved: a}\n"
    )
    path.write_text(entry * 2, encoding="utf-8")
    with pytest.raises(CaseFileError, match="more than one override for academic-0001"):
        read_overrides(path)
    path.write_text("- {id: academic-0001, expect_class: minimal, notes: n}\n", encoding="utf-8")
    with pytest.raises(CaseFileError, match="expect_text"):
        read_overrides(path)


# --- pattern 2: the rule- or template-based tag ------------------------------------------------


def scenario(system_type: str, risk_level: str) -> Scenario:
    return Scenario.model_validate(
        {
            "role": "Provider",
            "intended_use": "Made-up use",
            "system_type": system_type,
            "input_data": "Made-up data",
            "domain": "Made-up domain",
            "related_articles": [],
            "obligations": [],
            "risk_level": risk_level,
        }
    )


RULE_SCENARIOS = (
    scenario("Rule\u2011based FAQ bot", "limited"),  # non-breaking hyphen, as in the source
    scenario("template-based letter writer", "minimal"),  # lower case, ASCII hyphen
    scenario("TEMPLATE-BASED card maker", "minimal"),
    scenario("Rule\u2011based fraud scorer", "high-risk"),
    scenario("Rule-based social scorer", "prohibited"),
    scenario("Rule-based advice tool", "minimal"),  # made ambiguous by an override below
    scenario("Tool with a rule-based core", "minimal"),  # doesn't start with the phrase
    scenario("Recommendation engine", "limited"),
)


def test_the_rule_tags_exactly_the_decided_low_rule_or_template_cases() -> None:
    ambiguous = override(
        id="academic-0006",
        expect_text="Made-up use",
        status="legally_ambiguous",
        notes="Open question and both readings.",
    )
    cases = build_cases(RULE_SCENARIOS, [ambiguous])
    tagged = [case.id for case in cases if LOW_OR_OUT_OF_SCOPE_TAG in case.tags]
    assert tagged == ["academic-0001", "academic-0002", "academic-0003"]


def test_committed_rule_tags_match_the_rule_on_every_case() -> None:
    cases = load_cases(CaseSet.ACADEMIC)
    tagged = [case for case in cases if LOW_OR_OUT_OF_SCOPE_TAG in case.tags]
    assert len(tagged) == RULE_TAGGED_COUNT
    for case in cases:
        label = case.label
        assert isinstance(label, CaseLabel)
        system_type = next(
            line.removeprefix(SYSTEM_TYPE_PREFIX)
            for line in case.description.splitlines()
            if line.startswith(SYSTEM_TYPE_PREFIX)
        )
        qualifies = (
            label.status is Status.DECIDED
            and label.risk_class in LOW_BUCKET
            and RULE_OR_TEMPLATE_BASED.match(system_type) is not None
        )
        assert (LOW_OR_OUT_OF_SCOPE_TAG in case.tags) is qualifies, case.id


# --- the committed set -------------------------------------------------------------------------


def test_committed_overrides_are_applied_to_the_committed_set() -> None:
    by_id = {case.id: case for case in load_cases(CaseSet.ACADEMIC)}
    for entry in read_overrides():
        case = by_id[entry.id]
        assert case.notes == entry.notes
        assert set(entry.add_tags) <= set(case.tags)
        if entry.status is not None and isinstance(case.label, CaseLabel):
            assert case.label.status is entry.status
    ambiguous = sorted(
        case.id
        for case in by_id.values()
        if isinstance(case.label, CaseLabel) and case.label.status is Status.LEGALLY_AMBIGUOUS
    )
    assert ambiguous == ["academic-0005", "academic-0136", "academic-0150"]
    reviewed = [f"academic-0{n}" for n in (160, 253, 308, 314, 324, 327)]
    assert all(LOW_OR_OUT_OF_SCOPE_TAG in by_id[case_id].tags for case_id in reviewed)


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
