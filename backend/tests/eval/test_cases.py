import json
from collections import Counter
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aiact.engine.nodes import high_risk_texts, role_texts, scope_texts
from aiact.engine.nodes.high_risk_retrieval import ANNEX_III_POINTS
from aiact.engine.nodes.role_texts import KeyQuestion, legacy_questions
from aiact.engine.nodes.scope_texts import ScopeQuestion
from aiact.eval.cases import (
    CASES_DIR,
    QA_DIR_NAME,
    AppliedAILabel,
    BenchmarkCase,
    CaseFileError,
    CaseLabel,
    CaseSet,
    CommissionVerdict,
    FlipVariant,
    QAItem,
    SourceLabelStatus,
    derived_from_pile_a,
    load_cases,
    load_jsonl,
    load_qa_items,
    load_yaml_file,
    score_appliedai,
)
from aiact.eval.metrics import SOFT_WORDING_TAG
from aiact.eval.split import SPLIT_FILE, Split
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
    assert all("pair:fixture-001" in case.tags for case in cases)


def test_loads_appliedai_jsonl_skipping_blank_lines() -> None:
    cases = load_jsonl(FIXTURES / "appliedai.jsonl")
    assert [case.label for case in cases] == [AppliedAILabel.LOW, AppliedAILabel.HIGH]


def test_jsonl_case_from_another_set_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "appliedai.jsonl"
    path.write_text(json.dumps(VALID_CASE) + "\n", encoding="utf-8")
    with pytest.raises(CaseFileError, match="set_name"):
        load_jsonl(path)
    assert [case.id for case in load_jsonl(path, CaseSet.OWN)] == ["tmp-001"]


def test_missing_jsonl_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_jsonl(tmp_path / "private" / "appliedai.jsonl")


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


def write_case_with_as_of(folder: Path, as_of: str) -> Path:
    """A case file with an unquoted `as_of` line, as a hand-written case file has it."""
    path = write_yaml(folder, "dated.yaml", VALID_CASE)
    path.write_text(path.read_text(encoding="utf-8") + f"as_of: {as_of}\n", encoding="utf-8")
    return path


def test_a_case_date_loads_as_a_date(tmp_path: Path) -> None:
    (case,) = load_yaml_file(write_case_with_as_of(tmp_path, "2026-12-15"))
    assert case.as_of == date(2026, 12, 15)


def test_an_invalid_case_date_fails_the_loader(tmp_path: Path) -> None:
    with pytest.raises(CaseFileError, match=r"(?s)dated\.yaml\[0\].*as_of"):
        load_yaml_file(write_case_with_as_of(tmp_path, "2026-1215"))


@pytest.mark.parametrize("impossible", ["2026-13-45", "2026-02-30"])
def test_an_impossible_case_date_names_the_file_and_field(tmp_path: Path, impossible: str) -> None:
    with pytest.raises(CaseFileError, match=r"(?s)dated\.yaml.*as_of"):
        load_yaml_file(write_case_with_as_of(tmp_path, impossible))


def test_a_case_without_a_date_takes_the_run_date() -> None:
    assert BenchmarkCase.model_validate(VALID_CASE).as_of is None


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


# --- F7b extensions: Commission rows, pairs, answers, business function ------------------------

COMMISSION_CASE: dict[str, object] = {
    **VALID_CASE,
    "set_name": "commission_b",
    "source_example_id": "hr-ex-901",
    "accepted_bases": ["art_6_3_filter:d", "outside_use_case"],
    "label_status": "settled",
}
FLIP_VARIANT: dict[str, object] = {
    "feature": "it also infers deception",
    "resulting_verdict": "high",
    "provision_ids": ["annex:III:7:a"],
}


def test_commission_rewrites_carry_their_row_fields() -> None:
    settled, ambiguous = load_cases(CaseSet.COMMISSION_B, FIXTURES)
    assert settled.accepted_bases == ("art_6_3_filter:d", "outside_use_case")
    assert settled.label_status is SourceLabelStatus.SETTLED
    assert settled.flip_variants == (
        FlipVariant(
            feature="the tool also infers whether an applicant is telling the truth",
            resulting_verdict=CommissionVerdict.HIGH,
            provision_ids=("annex:III:7:a",),
        ),
    )
    assert settled.flip_variant_provisions == ("annex:III:7:a",)
    assert settled.business_function == "legal"
    assert ambiguous.label_status is SourceLabelStatus.LEGALLY_AMBIGUOUS


def test_soft_pair_fixture_carries_pair_id_and_key_fact_answers() -> None:
    plain, soft = load_cases(CaseSet.SOFT_PAIRS, FIXTURES)
    assert plain.pair_id == soft.pair_id == "fixture-001"
    assert plain.key_fact_answers == {}
    assert soft.key_fact_answers == {
        "ranks_people": "Yes, it orders the applications by a score.",
        "annex:III:4:a": "HR uses the order to decide whom to invite.",
    }
    assert soft.business_function == "hr"


def test_flip_variant_provisions_are_listed_once_in_order() -> None:
    other = {**FLIP_VARIANT, "provision_ids": ["annex:III:1:b", "annex:III:7:a"]}
    case = BenchmarkCase.model_validate(with_changes(flip_variants=[FLIP_VARIANT, other]))
    assert case.flip_variant_provisions == ("annex:III:7:a", "annex:III:1:b")


@pytest.mark.parametrize(
    "changes",
    [
        {"accepted_bases": ["art_6_3_filter:b"], "label": {"risk_class": "high_risk"}},
        {"accepted_bases": ["within_use_case"]},
        {"accepted_bases": ["art_6_3_filter:e"]},
        {"accepted_bases": ["outside"]},
        {"source_example_id": None},
        {"label_status": "open"},
        {"label_status": "legally_ambiguous"},
        {"source_example_id": "ex-1"},
        {"flip_variants": [{**FLIP_VARIANT, "provision_ids": []}]},
        {"flip_variants": [{**FLIP_VARIANT, "resulting_verdict": "high_risk"}]},
        {"flip_variants": [{**FLIP_VARIANT, "provision_ids": ["Annex III 7(a)"]}]},
        {"pair_id": "Pair 1"},
        {"key_fact_answers": {"Ranks People?": "yes"}},
        {"key_fact_answers": {"ranks_people": ""}},
        {"business_function": "Human Resources"},
    ],
    ids=[
        "high-label-with-a-not-high-basis",
        "not-high-label-with-a-high-basis",
        "art-6-3-letter-out-of-range",
        "unknown-basis",
        "bases-without-a-source-example",
        "unknown-label-status",
        "ambiguous-row-with-a-decided-label",
        "bad-source-example-id",
        "flip-variant-without-provisions",
        "flip-variant-engine-verdict",
        "flip-variant-free-text-provision",
        "bad-pair-id",
        "bad-key-fact-key",
        "empty-key-fact-answer",
        "business-function-not-a-slug",
    ],
)
def test_invalid_extension_fields_are_rejected(tmp_path: Path, changes: dict[str, object]) -> None:
    path = write_yaml(tmp_path, "case.yaml", {**COMMISSION_CASE, **changes})
    with pytest.raises(CaseFileError):
        load_yaml_file(path)


def test_valid_commission_case_and_ambiguous_row() -> None:
    assert BenchmarkCase.model_validate(COMMISSION_CASE).accepted_bases[0] == "art_6_3_filter:d"
    ambiguous = BenchmarkCase.model_validate(
        {
            **COMMISSION_CASE,
            "label": {"risk_class": "high_risk", "status": "legally_ambiguous"},
            "label_status": "legally_ambiguous",
            "notes": "Open question and both readings.",
        }
    )
    assert ambiguous.label_status is SourceLabelStatus.LEGALLY_AMBIGUOUS


def test_a_pair_id_links_exactly_two_cases(tmp_path: Path) -> None:
    folder = tmp_path / "soft_pairs"
    pair = with_changes(set_name="soft_pairs", pair_id="p-1")
    write_yaml(folder, "a.yaml", [pair, {**pair, "id": "tmp-002"}])
    assert len(load_cases(CaseSet.SOFT_PAIRS, tmp_path)) == 2
    write_yaml(folder, "b.yaml", {**pair, "id": "tmp-003"})
    with pytest.raises(CaseFileError, match="pair_id p-1 must link exactly two cases"):
        load_cases(CaseSet.SOFT_PAIRS, tmp_path)


def test_derived_from_pile_a_names_the_offending_cases() -> None:
    cases = [
        BenchmarkCase.model_validate(with_changes(id=f"tmp-{n}", source_example_id=source))
        for n, source in enumerate(["hr-ex-001", "hr-ex-002", None])
    ]
    assert derived_from_pile_a(cases, {"hr-ex-001", "hr-ex-003"}) == ("tmp-0",)
    assert derived_from_pile_a(cases, set()) == ()


# --- Annex points ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "point", ["annex:I:A:11", "annex:I:B:21", "annex:III:4:a", "annex:III:2", "annex:III:5:d"]
)
def test_annex_i_and_iii_points_pass_the_pattern(point: str) -> None:
    label = CaseLabel.model_validate({"risk_class": "high_risk", "annex_point": point})
    assert label.annex_point == (point,)


@pytest.mark.parametrize(
    "point",
    ["annex:I:1", "annex:I:a:11", "annex:I:C:1", "annex:III:4:A", "annex:II:1", "annex:III"],
)
def test_other_annex_ids_fail_the_pattern(point: str) -> None:
    with pytest.raises(ValidationError):
        CaseLabel.model_validate({"risk_class": "high_risk", "annex_point": point})


def test_a_label_can_name_several_annex_points() -> None:
    (case,) = load_cases(CaseSet.ANNEX_MATCH, FIXTURES)
    assert isinstance(case.label, CaseLabel)
    assert case.label.annex_point == ("annex:I:A:11", "annex:III:5:d")
    assert CaseLabel(risk_class=RiskClass.MINIMAL_RISK).annex_point == ()
    null_point = CaseLabel.model_validate({"risk_class": "minimal_risk", "annex_point": None})
    assert null_point.annex_point == ()


def test_annex_match_labels_need_a_citation(tmp_path: Path) -> None:
    item = with_changes(set_name="annex_match", label_citation=[])
    with pytest.raises(CaseFileError, match="label_citation"):
        load_yaml_file(write_yaml(tmp_path, "item.yaml", item))


def test_the_moved_fixture_uses_a_section_b_point() -> None:
    ambiguous = load_cases(CaseSet.OWN, FIXTURES)[0]
    assert isinstance(ambiguous.label, CaseLabel)
    assert ambiguous.label.annex_point == ("annex:I:B:21",)


# --- Q&A items ---------------------------------------------------------------------------------

VALID_QA: dict[str, object] = {
    "id": "qa-001",
    "language": "en",
    "question": "What does Art. 4 require?",
    "required_provision_ids": ["art:4"],
    "reference_answer": "AI literacy measures.",
}


def test_loads_answerable_and_unanswerable_qa_items() -> None:
    answerable, unanswerable = load_qa_items(FIXTURES)
    assert answerable.required_provision_ids == ("art:50:2", "art:113")
    assert answerable.answerable
    assert not unanswerable.answerable
    assert unanswerable.required_provision_ids == ()
    assert unanswerable.language is Language.DE


@pytest.mark.parametrize(
    "changes",
    [
        {"required_provision_ids": []},
        {"reference_answer": None},
        {"answerable": False},
        {"required_provision_ids": ["Art. 4"]},
        {"question": ""},
        {"set_name": "qa"},
    ],
    ids=[
        "answerable-without-provisions",
        "answerable-without-answer",
        "unanswerable-with-provisions",
        "free-text-provision",
        "empty-question",
        "unknown-field",
    ],
)
def test_invalid_qa_items_are_rejected(tmp_path: Path, changes: dict[str, object]) -> None:
    write_yaml(tmp_path / "qa", "items.yaml", [{**VALID_QA, **changes}])
    with pytest.raises(CaseFileError):
        load_qa_items(tmp_path)


def test_qa_loader_rejects_duplicates_and_a_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Q&A"):
        load_qa_items(tmp_path)
    write_yaml(tmp_path / "qa", "a.yaml", [VALID_QA, VALID_QA])
    with pytest.raises(CaseFileError, match="duplicate case id qa-001"):
        load_qa_items(tmp_path)


# --- the committed case files ------------------------------------------------------------------


YAML_SETS = sorted(set(CaseSet) - {CaseSet.APPLIEDAI})


def test_every_committed_case_file_validates() -> None:
    loaded = {case_set: load_cases(case_set) for case_set in YAML_SETS}
    assert loaded[CaseSet.OWN]
    assert all(isinstance(item, QAItem) for item in load_qa_items())


QA_ANSWERABLE_RANGE = range(20, 31)
QA_UNANSWERABLE_RANGE = range(8, 11)


def test_the_committed_qa_set_has_its_counts_in_both_languages() -> None:
    """B7's DoD: 20-30 answerable and 8-10 unanswerable questions, each kind in EN and DE."""
    items = load_qa_items()
    answerable = [item for item in items if item.answerable]
    unanswerable = [item for item in items if not item.answerable]
    assert len(answerable) in QA_ANSWERABLE_RANGE
    assert len(unanswerable) in QA_UNANSWERABLE_RANGE
    for kind in (answerable, unanswerable):
        assert {item.language for item in kind} == {Language.EN, Language.DE}


ANNEX_MATCH_RANGE = range(30, 51)


def test_the_committed_annex_match_set_has_its_counts_and_points() -> None:
    """X0's DoD: 30-50 items in EN and DE, each naming and citing the Annex points it expects,
    written from scratch (no Commission example as source), and every Annex III point expected
    at least once (X1a measures retrieval over all of them)."""
    items = load_cases(CaseSet.ANNEX_MATCH)
    assert len(items) in ANNEX_MATCH_RANGE
    assert {item.language for item in items} == {Language.EN, Language.DE}
    expected: set[str] = set()
    for item in items:
        assert isinstance(item.label, CaseLabel)
        assert item.label.annex_point, item.id
        assert set(item.label.annex_point) <= set(item.label_citation), item.id
        assert item.source_example_id is None, item.id
        expected.update(item.label.annex_point)
    assert set(ANNEX_III_POINTS) - expected == set()


SOFT_PAIR_RANGE = range(10, 21)
MIN_GERMAN_SHARE = 0.25
PLAIN_WORDING_TAG = "wording:plain"


def _asked_id(value: object) -> str | None:
    """The id of a fixed question the engine can ask; a scope note (no question) has none."""
    if isinstance(value, KeyQuestion):
        return value.id
    if isinstance(value, ScopeQuestion) and value.question is not None:
        return value.id
    return None


def _fixed_question_ids() -> frozenset[str]:
    """Every fixed follow-up question id of the scope, high-risk and role nodes: the keys a
    stored answer may have (decision 019 as amended 2026-10-07)."""
    legacy = legacy_questions(date(2026, 8, 2), "art:111:2")
    values: list[object] = list(vars(legacy).values())
    for module in (scope_texts, high_risk_texts, role_texts):
        for value in vars(module).values():
            values.extend(value.values() if isinstance(value, Mapping) else [value])
    return frozenset(qid for qid in map(_asked_id, values) if qid is not None)


def test_the_committed_soft_pair_set_has_its_pairs_and_answers() -> None:
    """B6's DoD: 10-20 pairs, each the same high-risk system worded plainly and softly with one
    label; the softened case is tagged `wording:soft` (the tag the downgrade rate reads) and
    carries `key_fact_answers` keyed by the ids of the engine's fixed questions (decision 019);
    both languages, at least a quarter German."""
    question_ids = _fixed_question_ids()
    cases = load_cases(CaseSet.SOFT_PAIRS)
    assert all(case.pair_id is not None for case in cases)
    pairs = {
        pair_id: [case for case in cases if case.pair_id == pair_id]
        for pair_id in {case.pair_id for case in cases}
    }
    assert len(pairs) in SOFT_PAIR_RANGE
    for pair_id, pair in pairs.items():
        soft = [case for case in pair if SOFT_WORDING_TAG in case.tags]
        assert len(soft) == 1, pair_id
        (plain,) = [case for case in pair if case is not soft[0]]
        assert PLAIN_WORDING_TAG in plain.tags, pair_id
        assert plain.description != soft[0].description, pair_id
        assert soft[0].key_fact_answers, pair_id
        assert set(soft[0].key_fact_answers) <= question_ids, pair_id
        first, second = pair
        assert first.label == second.label, pair_id
        assert isinstance(first.label, CaseLabel)
        assert first.label.risk_class is RiskClass.HIGH_RISK, pair_id
        assert first.language is second.language, pair_id
        assert all(f"pair:{pair_id}" in case.tags for case in pair), pair_id
    languages = Counter(pair[0].language for pair in pairs.values())
    assert set(languages) == {Language.EN, Language.DE}
    assert languages[Language.DE] / len(pairs) >= MIN_GERMAN_SHARE


def test_no_committed_case_derives_from_a_pile_a_example() -> None:
    """B6's rule over every committed case: Pile A stays retrievable, so no case may come from it.
    Worktrees without the split (the Engine lane's sparse checkout) skip, as test_isolation does."""
    if not SPLIT_FILE.is_file():
        pytest.skip(f"{SPLIT_FILE} is missing (this worktree leaves the split out)")
    split = Split.model_validate_json(SPLIT_FILE.read_text(encoding="utf-8"))
    cases = [case for case_set in YAML_SETS for case in load_cases(case_set)]
    assert derived_from_pile_a(cases, split.pile_a) == ()


def test_every_pile_b_example_has_exactly_one_rewrite() -> None:
    """B4's DoD: each Pile B example is rewritten once, and no rewrite comes from elsewhere (a case
    without a source id counts as None and fails). Skips without the split, as above."""
    if not SPLIT_FILE.is_file():
        pytest.skip(f"{SPLIT_FILE} is missing (this worktree leaves the split out)")
    split = Split.model_validate_json(SPLIT_FILE.read_text(encoding="utf-8"))
    sources = Counter(case.source_example_id for case in load_cases(CaseSet.COMMISSION_B))
    assert sources == Counter(split.pile_b)


# --- file-level rules --------------------------------------------------------------------------

DUPLICATE_TOP_LEVEL = """\
id: tmp-001
set_name: own
language: en
language: de
description: A made-up system.
label: {risk_class: minimal_risk}
label_citation: ["art:6:3"]
"""
DUPLICATE_ANSWER = """\
id: tmp-001
set_name: own
language: en
description: A made-up system.
label: {risk_class: minimal_risk}
label_citation: ["art:6:3"]
key_fact_answers:
  ranks_people: "yes"
  ranks_people: "no"
"""


@pytest.mark.parametrize(
    ("text", "key"),
    [(DUPLICATE_TOP_LEVEL, "language"), (DUPLICATE_ANSWER, "ranks_people")],
    ids=["top-level-field", "key-fact-answer"],
)
def test_a_repeated_key_is_rejected(tmp_path: Path, text: str, key: str) -> None:
    path = tmp_path / "case.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CaseFileError, match=f"duplicate key '{key}'"):
        load_yaml_file(path)


def test_a_repeated_key_in_a_qa_item_is_rejected(tmp_path: Path) -> None:
    folder = tmp_path / "qa"
    folder.mkdir()
    (folder / "items.yaml").write_text(
        yaml.safe_dump(VALID_QA) + "question: Again?\n", encoding="utf-8"
    )
    with pytest.raises(CaseFileError, match="duplicate key 'question'"):
        load_qa_items(tmp_path)


def test_the_same_key_in_different_mappings_is_fine(tmp_path: Path) -> None:
    path = write_yaml(tmp_path, "cases.yaml", [VALID_CASE, with_changes(id="tmp-002")])
    assert len(load_yaml_file(path)) == 2


@pytest.mark.parametrize("name", ["case.yml", "cases.json", "sub/case.yaml.bak"])
def test_a_stray_file_in_a_case_or_qa_folder_is_rejected(tmp_path: Path, name: str) -> None:
    for folder in (tmp_path / "own", tmp_path / QA_DIR_NAME):
        stray = folder / name
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("id: tmp-001\n", encoding="utf-8")
    with pytest.raises(CaseFileError, match=r"not a \.yaml case file"):
        load_cases(CaseSet.OWN, tmp_path)
    with pytest.raises(CaseFileError, match=r"not a \.yaml case file"):
        load_qa_items(tmp_path)


def test_placeholders_and_notes_are_allowed_but_not_loaded(tmp_path: Path) -> None:
    write_yaml(tmp_path / "own", "a.yaml", VALID_CASE)
    for name in (".gitkeep", ".DS_Store", "SOURCE.md"):
        (tmp_path / "own" / name).write_text("not a case\n", encoding="utf-8")
    assert [case.id for case in load_cases(CaseSet.OWN, tmp_path)] == ["tmp-001"]


def test_hidden_yaml_files_load_like_any_other(tmp_path: Path) -> None:
    write_yaml(tmp_path / "own", ".hidden.yaml", VALID_CASE)
    write_yaml(tmp_path / "own" / ".drafts", "c.yaml", with_changes(id="tmp-002"))
    assert [case.id for case in load_cases(CaseSet.OWN, tmp_path)] == ["tmp-002", "tmp-001"]


@pytest.mark.parametrize("name", [".hidden.yml", ".drafts/c.json", ".notes"])
def test_other_hidden_files_are_rejected(tmp_path: Path, name: str) -> None:
    stray = tmp_path / "own" / name
    stray.parent.mkdir(parents=True)
    stray.write_text("id: tmp-001\n", encoding="utf-8")
    with pytest.raises(CaseFileError, match=r"not a \.yaml case file"):
        load_cases(CaseSet.OWN, tmp_path)


MERGED_CASES = """\
- &base
  id: tmp-001
  set_name: own
  language: en
  description: A made-up system.
  label: {risk_class: minimal_risk}
  label_citation: ["art:6:3"]
- <<: *base
  id: tmp-002
"""


def test_a_merge_key_loads_as_with_safe_load(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(MERGED_CASES, encoding="utf-8")
    first, second = load_yaml_file(path)
    assert (first.id, second.id) == ("tmp-001", "tmp-002")
    assert second.description == first.description


def test_a_real_duplicate_next_to_a_merge_key_still_fails(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(MERGED_CASES + "  id: tmp-003\n", encoding="utf-8")
    with pytest.raises(CaseFileError, match="duplicate key 'id'"):
        load_yaml_file(path)
