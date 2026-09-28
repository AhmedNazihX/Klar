from pathlib import Path

import pytest
import yaml

from aiact.eval.cases import (
    CASES_DIR,
    AppliedAILabel,
    BenchmarkCase,
    CaseFileError,
    CaseLabel,
    CaseSet,
    load_cases,
    load_jsonl,
    load_yaml_file,
    score_appliedai,
)
from aiact.schemas import Language, RiskClass, Role, Status

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cases"

VALID_CASE: dict[str, object] = {
    "id": "tmp-001",
    "set_name": "own",
    "language": "en",
    "description": "A made-up system.",
    "label": {"risk_class": "minimal_risk"},
    "label_citation": ["art:6:3"],
}


def write_yaml(folder: Path, name: str, content: object) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return path


def with_changes(**changes: object) -> dict[str, object]:
    return {**VALID_CASE, **changes}


# --- loader ------------------------------------------------------------------------------------


def test_loads_every_yaml_file_in_a_set_including_subfolders() -> None:
    cases = load_cases(CaseSet.OWN, FIXTURES)
    assert [case.id for case in cases] == ["fixture-own-002", "fixture-own-001"]
    ambiguous, chatbot = cases
    assert chatbot.label == CaseLabel(risk_class=RiskClass.LIMITED_RISK, role=Role.PROVIDER)
    assert chatbot.label_citation == ("art:50:1",)
    assert isinstance(ambiguous.label, CaseLabel)
    assert ambiguous.label.status is Status.LEGALLY_AMBIGUOUS
    assert ambiguous.language is Language.DE


def test_a_yaml_file_can_hold_a_list_of_cases() -> None:
    cases = load_cases(CaseSet.SOFT_PAIRS, FIXTURES)
    assert [case.id for case in cases] == ["fixture-soft-001a", "fixture-soft-001b"]
    assert {case.tags for case in cases} == {("pair:fixture-001",)}


def test_loads_appliedai_jsonl_skipping_blank_lines() -> None:
    cases = load_jsonl(FIXTURES / "appliedai.jsonl")
    assert [case.label for case in cases] == [AppliedAILabel.LOW, AppliedAILabel.HIGH]


def test_missing_set_folder_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="academic"):
        load_cases(CaseSet.ACADEMIC, tmp_path)


def test_case_filed_under_the_wrong_set_is_rejected(tmp_path: Path) -> None:
    write_yaml(tmp_path / "commission_b", "x.yaml", VALID_CASE)
    with pytest.raises(CaseFileError, match="set_name"):
        load_cases(CaseSet.COMMISSION_B, tmp_path)


def test_duplicate_ids_across_files_are_rejected(tmp_path: Path) -> None:
    write_yaml(tmp_path / "own", "a.yaml", VALID_CASE)
    write_yaml(tmp_path / "own" / "sub", "b.yaml", VALID_CASE)
    with pytest.raises(CaseFileError, match="duplicate case id tmp-001"):
        load_cases(CaseSet.OWN, tmp_path)


def test_invalid_case_error_names_the_file_and_position(tmp_path: Path) -> None:
    path = write_yaml(tmp_path, "bad.yaml", [VALID_CASE, with_changes(id="tmp-002", language="fr")])
    with pytest.raises(CaseFileError, match=r"(?s)bad\.yaml\[1\].*language"):
        load_yaml_file(path)


@pytest.mark.parametrize("content", ["", "just text\n", "[]\n"])
def test_file_without_cases_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(CaseFileError, match="expected a case mapping"):
        load_yaml_file(path)


def test_malformed_yaml_and_json_are_reported(tmp_path: Path) -> None:
    yaml_path = tmp_path / "broken.yaml"
    yaml_path.write_text("id: [unclosed\n", encoding="utf-8")
    with pytest.raises(CaseFileError, match="not valid YAML"):
        load_yaml_file(yaml_path)
    jsonl_path = tmp_path / "broken.jsonl"
    jsonl_path.write_text('{"id": "x"\n', encoding="utf-8")
    with pytest.raises(CaseFileError, match=r"broken\.jsonl:1: not valid JSON"):
        load_jsonl(jsonl_path)


def test_committed_case_folders_exist() -> None:
    yaml_sets = set(CaseSet) - {CaseSet.APPLIEDAI}
    assert all((CASES_DIR / case_set.value).is_dir() for case_set in yaml_sets)


# --- schema rules ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"label_citation": []},
        {"label": {"risk_class": "high_risk", "status": "legally_ambiguous"}},
        {"label": "high"},
        {"set_name": "appliedai"},
        {"id": "Has Spaces"},
        {"label": {"risk_class": "high_risk", "annex_point": "annex:II:1"}},
        {"unknown_field": 1},
    ],
    ids=[
        "decided-without-citation",
        "ambiguous-without-notes",
        "appliedai-label-in-own-set",
        "case-label-in-appliedai-set",
        "bad-id",
        "annex-ii-point",
        "unknown-field",
    ],
)
def test_invalid_cases_are_rejected(tmp_path: Path, changes: dict[str, object]) -> None:
    path = write_yaml(tmp_path, "case.yaml", with_changes(**changes))
    with pytest.raises(CaseFileError):
        load_yaml_file(path)


def test_ambiguous_label_with_notes_needs_no_citation() -> None:
    case = BenchmarkCase.model_validate(
        with_changes(
            label={"risk_class": "high_risk", "status": "legally_ambiguous"},
            label_citation=[],
            notes="Open question and both readings.",
        )
    )
    assert case.label_citation == ()


@pytest.mark.parametrize("case_set", [CaseSet.ACADEMIC, CaseSet.APPLIEDAI])
def test_external_labels_need_no_citation(case_set: CaseSet) -> None:
    label: object = "unclear" if case_set is CaseSet.APPLIEDAI else {"risk_class": "high_risk"}
    case = BenchmarkCase.model_validate(
        with_changes(set_name=case_set.value, label=label, label_citation=[])
    )
    assert case.label_citation == ()


# --- appliedAI mapping -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "matching"),
    [
        (AppliedAILabel.HIGH, {RiskClass.HIGH_RISK}),
        (AppliedAILabel.PROHIBITED, {RiskClass.PROHIBITED}),
        (
            AppliedAILabel.LOW,
            {RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK, RiskClass.OUT_OF_SCOPE},
        ),
    ],
)
@pytest.mark.parametrize("status", list(Status))
def test_class_labels_match_on_the_working_assumption_class(
    label: AppliedAILabel, matching: set[RiskClass], status: Status
) -> None:
    for risk_class in RiskClass:
        score = score_appliedai(label, risk_class, status)
        assert score.is_match is (risk_class in matching), (label, risk_class, status)
        assert score.is_counted_separately is False


def test_assumed_high_risk_pending_review_matches_high() -> None:
    score = score_appliedai(AppliedAILabel.HIGH, RiskClass.HIGH_RISK, Status.LEGALLY_AMBIGUOUS)
    assert score.is_match
    assert not score.needs_disagreement_review


def test_low_matched_by_out_of_scope_goes_to_disagreement_review() -> None:
    score = score_appliedai(AppliedAILabel.LOW, RiskClass.OUT_OF_SCOPE, Status.DECIDED)
    assert score.is_match
    assert score.needs_disagreement_review


@pytest.mark.parametrize("risk_class", [RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK])
def test_low_matched_in_scope_needs_no_review(risk_class: RiskClass) -> None:
    score = score_appliedai(AppliedAILabel.LOW, risk_class, Status.DECIDED)
    assert score.is_match
    assert not score.needs_disagreement_review


def test_every_mismatch_goes_to_disagreement_review() -> None:
    score = score_appliedai(AppliedAILabel.HIGH, RiskClass.MINIMAL_RISK, Status.DECIDED)
    assert not score.is_match
    assert score.needs_disagreement_review


@pytest.mark.parametrize("risk_class", list(RiskClass))
def test_unclear_matches_only_legally_ambiguous(risk_class: RiskClass) -> None:
    ambiguous = score_appliedai(AppliedAILabel.UNCLEAR, risk_class, Status.LEGALLY_AMBIGUOUS)
    assert ambiguous.is_match
    assert not ambiguous.needs_disagreement_review
    assert not ambiguous.is_counted_separately
    decided = score_appliedai(AppliedAILabel.UNCLEAR, risk_class, Status.DECIDED)
    assert not decided.is_match
    assert decided.needs_disagreement_review


def test_unclear_with_needs_more_information_is_counted_separately() -> None:
    score = score_appliedai(
        AppliedAILabel.UNCLEAR, RiskClass.HIGH_RISK, Status.NEEDS_MORE_INFORMATION
    )
    assert not score.is_match
    assert score.is_counted_separately
