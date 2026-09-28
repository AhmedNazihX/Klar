import pytest

from aiact.eval.cases import AppliedAILabel, BenchmarkCase, CaseSet
from aiact.eval.metrics import (
    CONSISTENCY_GROUP_PREFIX,
    LOW_OR_OUT_OF_SCOPE_TAG,
    SOFT_WORDING_TAG,
    Rate,
    academic_review_count,
    annex_point_match,
    basis_matches,
    case_scores,
    citation_existence,
    citations_exist,
    consistency,
    downgraded,
    false_low_risk,
    flags_flip_variant,
    needs_info_on_ambiguous,
    rate,
    risk_class_match,
    role_match,
    summarize,
    uncertain_outcomes,
)
from aiact.schemas import Citation, FollowUpQuestion, RiskClass, Role, Status, StepName
from tests.eval.outcomes import (
    HIGH_ANNEX_POINT,
    WORKED_EXAMPLE_PROVISIONS,
    appliedai_case,
    case,
    outcome,
    result,
)
from tests.schemas.builders import ambiguous, steps_with
from tests.schemas.worked_example import cite

R = RiskClass
LOWER_THAN_HIGH = [R.LIMITED_RISK, R.MINIMAL_RISK, R.OUT_OF_SCOPE]


def exists_in_worked_example(citation: Citation) -> bool:
    return citation.provision_id in WORKED_EXAMPLE_PROVISIONS


def exists_except_art_5(citation: Citation) -> bool:
    return citation.provision_id != "art:5:1"


# --- rate --------------------------------------------------------------------------------------


def test_rate_value_is_none_without_applicable_cases() -> None:
    assert Rate(hits=0, total=0).value is None
    assert Rate(hits=3, total=4).value == 0.75


def test_rate_counts_only_applicable_scores() -> None:
    outcomes = [
        outcome(case("a")),
        outcome(case("b", R.MINIMAL_RISK)),
        outcome(case("c", status=Status.LEGALLY_AMBIGUOUS)),
    ]
    assert rate(outcomes, risk_class_match) == Rate(hits=1, total=2)


# --- risk-class accuracy -----------------------------------------------------------------------


@pytest.mark.parametrize("predicted", list(RiskClass))
def test_risk_class_match_compares_classes(predicted: RiskClass) -> None:
    score = risk_class_match(outcome(case("a", R.LIMITED_RISK), result(predicted)))
    assert score is (predicted is R.LIMITED_RISK)


@pytest.mark.parametrize("status", [Status.LEGALLY_AMBIGUOUS, Status.NEEDS_MORE_INFORMATION])
def test_uncertain_result_is_scored_on_its_working_assumption(status: Status) -> None:
    assert risk_class_match(outcome(case("a"), result(R.HIGH_RISK, status))) is True


def test_ambiguous_label_is_left_out_of_accuracy() -> None:
    label = case("a", status=Status.LEGALLY_AMBIGUOUS)
    assert risk_class_match(outcome(label)) is None


def test_failed_case_is_an_accuracy_miss() -> None:
    assert risk_class_match(outcome(case("a"), failed=True)) is False


@pytest.mark.parametrize(
    ("label", "predicted", "status", "expected"),
    [
        (AppliedAILabel.HIGH, R.HIGH_RISK, Status.LEGALLY_AMBIGUOUS, True),
        (AppliedAILabel.LOW, R.OUT_OF_SCOPE, Status.DECIDED, True),
        (AppliedAILabel.LOW, R.HIGH_RISK, Status.DECIDED, False),
        (AppliedAILabel.UNCLEAR, R.HIGH_RISK, Status.LEGALLY_AMBIGUOUS, True),
        (AppliedAILabel.UNCLEAR, R.HIGH_RISK, Status.DECIDED, False),
        (AppliedAILabel.UNCLEAR, R.HIGH_RISK, Status.NEEDS_MORE_INFORMATION, None),
    ],
    ids=["high-assumed", "low-out-of-scope", "low-miss", "unclear-hit", "unclear-miss", "nmi"],
)
def test_appliedai_accuracy_uses_the_mapping(
    label: AppliedAILabel, predicted: RiskClass, status: Status, expected: bool | None
) -> None:
    labelled = appliedai_case("ai-1", label)
    assert risk_class_match(outcome(labelled, result(predicted, status))) is expected


# --- academic set: low bucket and low-or-out-of-scope ------------------------------------------

LOW = [R.LIMITED_RISK, R.MINIMAL_RISK]


@pytest.mark.parametrize("labelled", LOW)
@pytest.mark.parametrize("predicted", list(RiskClass))
def test_academic_low_labels_share_one_bucket(labelled: RiskClass, predicted: RiskClass) -> None:
    academic = case("acad", labelled, set_name=CaseSet.ACADEMIC)
    assert risk_class_match(outcome(academic, result(predicted))) is (predicted in LOW)


@pytest.mark.parametrize(
    ("labelled", "predicted"),
    [(R.LIMITED_RISK, R.MINIMAL_RISK), (R.MINIMAL_RISK, R.LIMITED_RISK)],
)
def test_own_set_still_scores_limited_and_minimal_exactly(
    labelled: RiskClass, predicted: RiskClass
) -> None:
    assert risk_class_match(outcome(case("own", labelled), result(predicted))) is False
    assert risk_class_match(outcome(case("own", labelled), result(labelled))) is True


def test_academic_high_label_is_still_exact() -> None:
    academic = case("acad", R.HIGH_RISK, set_name=CaseSet.ACADEMIC)
    assert risk_class_match(outcome(academic, result(R.LIMITED_RISK))) is False
    assert false_low_risk(outcome(academic, result(R.LIMITED_RISK))) is True
    assert false_low_risk(outcome(academic, result(R.MINIMAL_RISK))) is True


@pytest.mark.parametrize("predicted", list(RiskClass))
def test_tagged_academic_low_case_also_accepts_out_of_scope(predicted: RiskClass) -> None:
    tagged = case(
        "acad", R.MINIMAL_RISK, set_name=CaseSet.ACADEMIC, tags=(LOW_OR_OUT_OF_SCOPE_TAG,)
    )
    expected = predicted in {*LOW, R.OUT_OF_SCOPE}
    assert risk_class_match(outcome(tagged, result(predicted))) is expected


def test_untagged_academic_low_case_rejects_out_of_scope() -> None:
    academic = case("acad", R.MINIMAL_RISK, set_name=CaseSet.ACADEMIC)
    assert risk_class_match(outcome(academic, result(R.OUT_OF_SCOPE))) is False


def test_the_tag_means_nothing_outside_the_academic_set() -> None:
    own = case("own", R.MINIMAL_RISK, tags=(LOW_OR_OUT_OF_SCOPE_TAG,))
    assert risk_class_match(outcome(own, result(R.OUT_OF_SCOPE))) is False
    assert risk_class_match(outcome(own, result(R.LIMITED_RISK))) is False


def test_academic_review_counts_out_of_scope_answers_on_tagged_cases() -> None:
    tag = (LOW_OR_OUT_OF_SCOPE_TAG,)
    outcomes = [
        outcome(
            case("a", R.MINIMAL_RISK, set_name=CaseSet.ACADEMIC, tags=tag), result(R.OUT_OF_SCOPE)
        ),
        outcome(
            case("b", R.MINIMAL_RISK, set_name=CaseSet.ACADEMIC, tags=tag), result(R.MINIMAL_RISK)
        ),
        outcome(case("c", R.MINIMAL_RISK, set_name=CaseSet.ACADEMIC, tags=tag), failed=True),
        outcome(case("d", R.MINIMAL_RISK, set_name=CaseSet.ACADEMIC), result(R.OUT_OF_SCOPE)),
        outcome(case("e", R.MINIMAL_RISK, tags=tag), result(R.OUT_OF_SCOPE)),
    ]
    assert academic_review_count(outcomes) == 1
    assert summarize(outcomes, None).academic_disagreement_review == 1


@pytest.mark.parametrize(
    "labelled",
    [
        case("acad", R.MINIMAL_RISK, status=Status.LEGALLY_AMBIGUOUS),
        case("acad", R.HIGH_RISK),
    ],
    ids=["ambiguous", "high-risk"],
)
def test_review_count_follows_accuracy_for_tagged_non_low_cases(labelled: BenchmarkCase) -> None:
    tagged = labelled.model_copy(
        update={"set_name": CaseSet.ACADEMIC, "tags": (LOW_OR_OUT_OF_SCOPE_TAG,)}
    )
    answered = outcome(tagged, result(R.OUT_OF_SCOPE))
    assert risk_class_match(answered) is not True
    assert academic_review_count([answered]) == 0


# --- false-low-risk and downgrade --------------------------------------------------------------


@pytest.mark.parametrize("predicted", list(RiskClass))
def test_false_low_risk_on_a_high_risk_label(predicted: RiskClass) -> None:
    score = false_low_risk(outcome(case("a"), result(predicted)))
    assert score is (predicted in LOWER_THAN_HIGH)


def test_prohibited_answered_high_risk_is_too_low() -> None:
    assert false_low_risk(outcome(case("a", R.PROHIBITED), result(R.HIGH_RISK))) is True
    assert false_low_risk(outcome(case("a", R.PROHIBITED), result(R.PROHIBITED))) is False


@pytest.mark.parametrize(
    "label",
    [
        case("low", R.MINIMAL_RISK),
        case("ambiguous", status=Status.LEGALLY_AMBIGUOUS),
        appliedai_case("ai-low", AppliedAILabel.LOW),
    ],
    ids=["low-label", "ambiguous-label", "appliedai-low"],
)
def test_false_low_risk_needs_a_settled_high_or_prohibited_label(label: BenchmarkCase) -> None:
    assert false_low_risk(outcome(label, result(R.MINIMAL_RISK))) is None


def test_false_low_risk_skips_failed_cases_and_maps_appliedai_high() -> None:
    assert false_low_risk(outcome(case("a"), failed=True)) is None
    high = appliedai_case("ai-high", AppliedAILabel.HIGH)
    assert false_low_risk(outcome(high, result(R.MINIMAL_RISK))) is True


def test_downgrade_scores_only_soft_worded_cases() -> None:
    soft = case("soft", tags=("pair:p1", SOFT_WORDING_TAG))
    plain = case("plain", tags=("pair:p1",))
    assert downgraded(outcome(soft, result(R.MINIMAL_RISK))) is True
    assert downgraded(outcome(soft, result(R.HIGH_RISK))) is False
    assert downgraded(outcome(plain, result(R.MINIMAL_RISK))) is None


# --- Annex point and role ----------------------------------------------------------------------


def test_annex_point_scored_on_high_risk_results_only() -> None:
    label = case("a", annex_point=HIGH_ANNEX_POINT)
    assert annex_point_match(outcome(label)) is True
    assert annex_point_match(outcome(label, result(annex_point="annex:III:4:b"))) is False
    assert annex_point_match(outcome(label, result(R.MINIMAL_RISK))) is None
    assert annex_point_match(outcome(label, failed=True)) is None


@pytest.mark.parametrize(
    "label",
    [
        case("no-point"),
        case("not-high", R.MINIMAL_RISK),
        case("ambiguous", status=Status.LEGALLY_AMBIGUOUS, annex_point=HIGH_ANNEX_POINT),
        appliedai_case("ai-high", AppliedAILabel.HIGH),
    ],
    ids=["no-point", "not-high", "ambiguous", "appliedai"],
)
def test_annex_point_needs_a_high_risk_label_with_a_point(label: BenchmarkCase) -> None:
    assert annex_point_match(outcome(label)) is None


def test_role_match() -> None:
    assert role_match(outcome(case("a", role=Role.DEPLOYER))) is True
    assert role_match(outcome(case("a", role=Role.PROVIDER))) is False
    assert role_match(outcome(case("a"))) is None


def test_role_missing_from_an_early_end_or_a_failure_is_a_miss() -> None:
    label = case("a", R.PROHIBITED, role=Role.PROVIDER)
    assert role_match(outcome(label, result(R.PROHIBITED))) is False
    assert role_match(outcome(label, failed=True)) is False


# --- uncertain outcomes ------------------------------------------------------------------------


def test_ambiguous_precision_and_recall() -> None:
    ambiguous_label = case("amb", status=Status.LEGALLY_AMBIGUOUS)
    outcomes = [
        outcome(ambiguous_label, result(status=Status.LEGALLY_AMBIGUOUS)),  # true positive
        outcome(case("amb-2", status=Status.LEGALLY_AMBIGUOUS)),  # missed: answered decided
        outcome(case("settled"), result(status=Status.LEGALLY_AMBIGUOUS)),  # false positive
        outcome(appliedai_case("ai-unclear", AppliedAILabel.UNCLEAR), failed=True),  # missed
        outcome(case("settled-2")),
    ]
    scores = uncertain_outcomes(outcomes, Status.LEGALLY_AMBIGUOUS)
    assert scores.precision == Rate(hits=1, total=2)
    assert scores.recall == Rate(hits=1, total=3)


def test_needs_info_on_an_ambiguous_label_is_counted_separately() -> None:
    nmi = result(status=Status.NEEDS_MORE_INFORMATION)
    outcomes = [
        outcome(case("amb", status=Status.LEGALLY_AMBIGUOUS), nmi),
        outcome(appliedai_case("ai-unclear", AppliedAILabel.UNCLEAR), nmi),
        outcome(case("nmi", status=Status.NEEDS_MORE_INFORMATION), nmi),
    ]
    ambiguous = uncertain_outcomes(outcomes, Status.LEGALLY_AMBIGUOUS)
    assert (ambiguous.predicted, ambiguous.labelled) == (0, 0)
    assert needs_info_on_ambiguous(outcomes) == 2
    # Counted only in their own row: not false positives for needs-more-information either.
    needs_info = uncertain_outcomes(outcomes, Status.NEEDS_MORE_INFORMATION)
    assert needs_info.precision == Rate(hits=1, total=1)
    assert needs_info.recall == Rate(hits=1, total=1)
    assert risk_class_match(outcomes[0]) is None
    assert risk_class_match(outcomes[1]) is None


def test_a_failed_case_with_an_uncertain_label_is_a_miss_where_its_label_is_scored() -> None:
    unclear = outcome(appliedai_case("ai-unclear", AppliedAILabel.UNCLEAR), failed=True)
    ambiguous = outcome(case("amb", status=Status.LEGALLY_AMBIGUOUS), failed=True)
    needs_info = outcome(case("nmi", status=Status.NEEDS_MORE_INFORMATION), failed=True)
    assert risk_class_match(unclear) is False  # appliedAI unclear stays in accuracy (INIT table)
    assert risk_class_match(ambiguous) is None  # own ambiguous labels are not in accuracy
    assert risk_class_match(needs_info) is False
    outcomes = [unclear, ambiguous, needs_info]
    assert uncertain_outcomes(outcomes, Status.LEGALLY_AMBIGUOUS).recall == Rate(hits=0, total=2)
    assert uncertain_outcomes(outcomes, Status.NEEDS_MORE_INFORMATION).recall == Rate(
        hits=0, total=1
    )
    assert needs_info_on_ambiguous(outcomes) == 0


# --- consistency -------------------------------------------------------------------------------


def test_consistency_counts_groups_with_one_class() -> None:
    first = f"{CONSISTENCY_GROUP_PREFIX}t1"
    second = f"{CONSISTENCY_GROUP_PREFIX}t2"
    outcomes = [
        *(outcome(case(f"t1-{n}", tags=(first,))) for n in range(3)),
        outcome(case("t2-0", tags=(second,))),
        outcome(case("t2-1", tags=(second,)), result(R.MINIMAL_RISK)),
        outcome(case("t2-2", tags=(second,))),
        outcome(case("alone", tags=(f"{CONSISTENCY_GROUP_PREFIX}t3",))),
        outcome(case("untagged")),
    ]
    assert consistency(outcomes) == Rate(hits=1, total=2)


def test_a_failed_paraphrase_makes_its_group_inconsistent() -> None:
    tag = (f"{CONSISTENCY_GROUP_PREFIX}t1",)
    outcomes = [outcome(case("a", tags=tag)), outcome(case("b", tags=tag), failed=True)]
    assert consistency(outcomes) == Rate(hits=0, total=1)


# --- citation existence ------------------------------------------------------------------------


def test_citation_existence_counts_every_citation() -> None:
    outcomes = [outcome(case("a")), outcome(case("b"), failed=True)]
    # Per case: the failed case has no citations; one missing citation misses the whole case.
    assert citation_existence(outcomes, exists_in_worked_example) == Rate(hits=1, total=1)
    assert citation_existence(outcomes, exists_except_art_5) == Rate(hits=0, total=1)
    assert citation_existence(outcomes, None) == Rate(hits=0, total=0)


def test_citations_exist_per_case() -> None:
    assert citations_exist(outcome(case("a")), exists_in_worked_example) is True
    assert citations_exist(outcome(case("a")), exists_except_art_5) is False
    assert citations_exist(outcome(case("a"), failed=True), exists_except_art_5) is None


def test_case_scores_hold_only_numbers_booleans_or_null() -> None:
    label = case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT)
    assert case_scores(outcome(label), exists_in_worked_example) == {
        "risk_class_accuracy": True,
        "false_low_risk": False,
        "annex_point_accuracy": True,
        "role_accuracy": True,
        "downgrade": None,
        "citation_existence": True,
    }


# --- decision 001: accepted bases and flip variants --------------------------------------------


@pytest.mark.parametrize(
    ("answer", "accepted", "expected"),
    [
        ("art_6_3_filter", ["art_6_3_filter:d", "outside_use_case"], True),
        ("art_6_3_filter:d", ["art_6_3_filter:d"], True),
        ("art_6_3_filter:a", ["art_6_3_filter:d"], False),
        ("art_6_3_filter:b", ["art_6_3_filter"], True),
        ("outside_use_case", ["art_6_3_filter:d", "outside_use_case"], True),
        ("within_use_case", ["outside_use_case"], False),
        ("art_6_3_filter", ["outside_use_case"], False),
        ("art_6_3_filter_x", ["art_6_3_filter"], False),
    ],
)
def test_basis_matching_rule(answer: str, accepted: list[str], expected: bool) -> None:
    assert basis_matches(answer, accepted) is expected


def test_flip_variant_flagged_by_a_follow_up_about_its_provision() -> None:
    question = FollowUpQuestion(
        id="deception", text="Does it infer deception?", about="annex:III:7:a"
    )
    base = result()
    asked = result(follow_up_questions=(*base.follow_up_questions, question))
    assert flags_flip_variant(asked, ["annex:III:7"])
    assert flags_flip_variant(asked, ["annex:III:7:a"])
    assert not flags_flip_variant(asked, ["annex:III:7:b"])
    assert not flags_flip_variant(base, ["annex:III:7:a"])


def test_flip_variant_flagged_by_a_citation_of_an_uncertain_step() -> None:
    open_step = ambiguous(StepName.HIGH_RISK).model_copy(
        update={"citations": (cite("art:5:1:c", "social scoring"),)}
    )
    flagged = result(status=Status.LEGALLY_AMBIGUOUS, steps=steps_with(open_step))
    assert flags_flip_variant(flagged, ["art:5:1:c"])
    # The decided prohibited step cites art:5:1 too, which alone is no flag.
    assert not flags_flip_variant(result(), ["art:5:1:c"])


# --- summary -----------------------------------------------------------------------------------


def test_summarize_collects_every_metric() -> None:
    outcomes = [
        outcome(case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT)),
        outcome(case("b"), result(R.MINIMAL_RISK)),
        outcome(appliedai_case("ai-1", AppliedAILabel.LOW), result(R.OUT_OF_SCOPE)),
        outcome(case("c", set_name=CaseSet.OWN), failed=True),
    ]
    metrics = summarize(outcomes, exists_in_worked_example)
    assert (metrics.cases, metrics.failed) == (4, 1)
    assert metrics.risk_class_accuracy == Rate(hits=2, total=4)
    assert metrics.false_low_risk == Rate(hits=1, total=2)
    assert metrics.annex_point_accuracy == Rate(hits=1, total=1)
    assert metrics.role_accuracy == Rate(hits=1, total=1)
    assert metrics.appliedai_disagreement_review == 1
    assert metrics.citation_existence.value == 1.0
