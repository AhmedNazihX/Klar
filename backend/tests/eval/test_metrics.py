from pathlib import Path

import pytest

from aiact.eval.baselines import BaselineAnswer, to_result
from aiact.eval.cases import (
    AppliedAILabel,
    BenchmarkCase,
    CaseLabel,
    CaseSet,
    CommissionVerdict,
    FlipVariant,
    load_cases,
)
from aiact.eval.metrics import (
    CONSISTENCY_GROUP_PREFIX,
    LOW_OR_OUT_OF_SCOPE_TAG,
    SOFT_WORDING_TAG,
    Rate,
    academic_review_count,
    annex_point_match,
    basis_match,
    basis_matches,
    case_scores,
    citation_existence,
    citation_match,
    citation_matches,
    citations_exist,
    consistency,
    description_asked,
    description_asked_wrongly,
    downgraded,
    false_low_risk,
    flags_flip_variant,
    flip_variant_flagged,
    needs_info_on_ambiguous,
    rate,
    result_bases,
    risk_class_match,
    role_match,
    summarize,
    uncertain_outcomes,
)
from aiact.schemas import (
    Citation,
    ClassificationResult,
    FollowUpQuestion,
    Language,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from tests.eval.outcomes import (
    HIGH_ANNEX_POINT,
    WORKED_EXAMPLE_PROVISIONS,
    appliedai_case,
    case,
    description_result,
    outcome,
    refused_result,
    result,
    thin_case,
)
from tests.schemas.builders import ambiguous, rebuild, steps_with, stored_before_decision_030
from tests.schemas.worked_example import cite, worked_example_result

R = RiskClass
CASE_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cases"
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
        "basis_accuracy": None,
        "flip_variant_flagged": None,
        "citation_accuracy": False,
        "description_asked": None,
        "description_asked_wrongly": False,
        "not_assessed": False,
        "citation_existence": True,
    }


def test_case_scores_key_each_new_score_by_its_own_scorer() -> None:
    scores = case_scores(outcome(commission_case("outside_use_case"), result(R.MINIMAL_RISK)))
    assert (scores["basis_accuracy"], scores["flip_variant_flagged"]) == (True, None)
    assert scores["citation_accuracy"] is False


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


def exempt_result(*letters: str) -> ClassificationResult:
    """A minimal-risk result whose high-risk step exempts the use under Art. 6(3)."""
    citations = tuple(cite(f"art:6:3:{letter}", "the condition") for letter in letters)
    step = StepResult(step=StepName.HIGH_RISK, decision="Exempt", citations=citations)
    return result(R.MINIMAL_RISK, steps=steps_with(step))


def asked_about(provision_id: str) -> ClassificationResult:
    question = FollowUpQuestion(id="variant", text="Does it do more?", about=provision_id)
    base = result()
    return result(follow_up_questions=(*base.follow_up_questions, question))


def commission_case(
    *bases: str, status: Status = Status.DECIDED, risk_class: RiskClass = R.MINIMAL_RISK
) -> BenchmarkCase:
    """A rewritten Commission case, validated (model_copy alone would skip the rules)."""
    base = case("c", risk_class, status=status)
    changes = {"source_example_id": "hr-ex-901", "accepted_bases": bases}
    return BenchmarkCase.model_validate({**base.model_dump(), **changes})


def test_result_bases_follow_the_high_risk_answer() -> None:
    annex_i = result(annex_point="annex:I:A:11")
    assert result_bases(result()) == ("within_use_case",)
    assert result_bases(annex_i) == ("safety_component",)
    assert result_bases(exempt_result("d")) == ("art_6_3_filter:d",)
    assert result_bases(exempt_result("a", "d", "a")) == ("art_6_3_filter:a", "art_6_3_filter:d")
    # The worked example's high-risk step cites the bare art:6:3, which names no exemption.
    assert result_bases(result(R.MINIMAL_RISK)) == ("outside_use_case", "not_safety_component")
    assert result_bases(result(R.PROHIBITED)) == ()


def test_result_bases_read_the_high_risk_step_not_the_final_class() -> None:
    # An open prohibited step keeps the class prohibited above a decided high-risk finding.
    prohibited_above_high = rebuild(
        worked_example_result(),
        risk_class=R.PROHIBITED,
        status=Status.LEGALLY_AMBIGUOUS,
        steps=steps_with(ambiguous(StepName.PROHIBITED)),
    )
    assert prohibited_above_high.annex_point == HIGH_ANNEX_POINT
    assert result_bases(prohibited_above_high) == ("within_use_case",)


def baseline_high_risk_without_a_point() -> ClassificationResult:
    """What `baselines.to_result` gives for a high_risk answer whose Annex point is null."""
    answer = BaselineAnswer(
        risk_class=R.HIGH_RISK,
        status=Status.DECIDED,
        role=Role.DEPLOYER,
        annex_point=None,
        transparency_duties=(),
        reason="Ranks job applicants.",
        missing_fact=None,
        open_question=None,
    )
    return to_result(answer, Language.EN, "baseline")


def test_a_high_risk_answer_without_a_point_is_a_listed_basis() -> None:
    no_point = baseline_high_risk_without_a_point()
    assert (no_point.risk_class, no_point.annex_point) == (R.HIGH_RISK, None)
    assert result_bases(no_point) == ("within_use_case", "safety_component")
    for not_listed in ("outside_use_case", "not_safety_component", "art_6_3_filter:d"):
        assert basis_match(outcome(commission_case(not_listed), no_point)) is False
    high = commission_case("within_use_case", risk_class=R.HIGH_RISK)
    annex_i = commission_case("safety_component", risk_class=R.HIGH_RISK)
    assert basis_match(outcome(high, no_point)) is True
    assert basis_match(outcome(annex_i, no_point)) is True


@pytest.mark.parametrize(
    ("cited", "label_citation", "expected"),
    [
        ("art:6:3", ["art:6:3:d"], True),
        ("art:6:3:d", ["art:6:3:d"], True),
        ("art:6:3:d", ["art:6:3"], True),
        ("art:6:3:a", ["art:6:3:d"], False),
        ("annex:III:4:a", ["art:6:3", "annex:III:4:a"], True),
        ("art:5:1", ["art:5:1:c"], False),
        ("art:6:31", ["art:6:3"], False),
    ],
)
def test_citation_matching_rule(cited: str, label_citation: list[str], expected: bool) -> None:
    assert citation_matches(cited, label_citation) is expected


def test_citation_accuracy_counts_any_label_citation() -> None:
    def cited_as(*label_citation: str) -> BenchmarkCase:
        return BenchmarkCase.model_validate(
            {**case("a").model_dump(), "label_citation": label_citation}
        )

    # The worked example cites art:3:1, art:5:1, annex:III:4:a, art:6:3, art:50:1, art:26:1.
    assert citation_match(outcome(cited_as("art:6:2", "annex:III:4:a"))) is True
    assert citation_match(outcome(cited_as("art:6:3:b"))) is True
    assert citation_match(outcome(cited_as("art:6:2", "art:5:1:c"))) is False
    assert citation_match(outcome(cited_as("art:6:2"), failed=True)) is None
    assert citation_match(outcome(appliedai_case("ai-1", AppliedAILabel.HIGH))) is None


def test_basis_accuracy_uses_the_accepted_bases_rule() -> None:
    either = commission_case("art_6_3_filter:d", "outside_use_case")
    assert basis_match(outcome(either, exempt_result("d"))) is True
    assert basis_match(outcome(either, result(R.MINIMAL_RISK))) is True
    assert basis_match(outcome(either, exempt_result("a"))) is False
    assert basis_match(outcome(either, result())) is False
    bare = commission_case("art_6_3_filter")
    assert basis_match(outcome(bare, exempt_result("b"))) is True
    assert basis_match(outcome(bare, result(R.MINIMAL_RISK))) is False


def test_basis_accuracy_applies_only_where_it_can_be_scored() -> None:
    either = commission_case("art_6_3_filter:d", "outside_use_case")
    ambiguous = commission_case("art_6_3_filter:b", status=Status.LEGALLY_AMBIGUOUS)
    assert basis_match(outcome(case("a"), exempt_result("d"))) is None
    assert basis_match(outcome(ambiguous, exempt_result("b"))) is None
    assert basis_match(outcome(either, failed=True)) is None
    assert basis_match(outcome(either, result(R.PROHIBITED))) is None


def test_flip_variant_flagged_per_case() -> None:
    variant = FlipVariant(
        feature="infers deception",
        resulting_verdict=CommissionVerdict.HIGH,
        provision_ids=("annex:III:7:a",),
    )
    with_variant = case("v").model_copy(update={"flip_variants": (variant,)})
    assert flip_variant_flagged(outcome(with_variant, asked_about("annex:III:7:a"))) is True
    assert flip_variant_flagged(outcome(with_variant)) is False
    assert flip_variant_flagged(outcome(with_variant, failed=True)) is None
    assert flip_variant_flagged(outcome(case("a"), asked_about("annex:III:7:a"))) is None


def test_annex_point_matches_any_labelled_point() -> None:
    label = case("a").model_copy(
        update={
            "label": CaseLabel(
                risk_class=R.HIGH_RISK, annex_point=("annex:I:A:11", "annex:III:4:a")
            )
        }
    )
    assert annex_point_match(outcome(label)) is True
    assert annex_point_match(outcome(label, result(annex_point="annex:I:A:11"))) is True
    assert annex_point_match(outcome(label, result(annex_point="annex:III:4:b"))) is False


# --- summary -----------------------------------------------------------------------------------


def test_summarize_reaches_basis_citation_and_flip_variant_metrics_on_fixtures() -> None:
    settled, ambiguous = load_cases(CaseSet.COMMISSION_B, CASE_FIXTURES)
    outcomes = [
        outcome(settled, exempt_result("d")),  # basis hit, flip miss, citation hit
        outcome(settled, asked_about("annex:III:7")),  # basis miss, flip hit, citation hit
        outcome(settled, result(R.MINIMAL_RISK)),  # basis hit ("not listed"), flip miss
        outcome(ambiguous, exempt_result("b")),  # ambiguous, no variants, no label citation
    ]
    metrics = summarize(outcomes, None)
    assert metrics.basis_accuracy == Rate(hits=2, total=3)
    assert metrics.flip_variant_flagged == Rate(hits=1, total=3)
    assert metrics.citation_accuracy == Rate(hits=3, total=3)


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


# --- needs a description (E13) -----------------------------------------------------------------


def test_a_thin_case_answered_with_a_description_request_is_a_hit() -> None:
    assert description_asked(outcome(thin_case("t"), description_result())) is True


@pytest.mark.parametrize("predicted", list(RiskClass))
def test_a_thin_case_answered_with_a_class_is_a_miss(predicted: RiskClass) -> None:
    assert description_asked(outcome(thin_case("t"), result(predicted))) is False


def test_a_failed_thin_case_is_a_miss() -> None:
    assert description_asked(outcome(thin_case("t"), failed=True)) is False


def test_a_thin_case_leaves_risk_class_accuracy() -> None:
    assert risk_class_match(outcome(thin_case("t"), description_result())) is None
    assert risk_class_match(outcome(thin_case("t"), result())) is None
    assert description_asked_wrongly(outcome(thin_case("t"), description_result())) is None


def test_another_case_answered_with_a_description_request_is_a_false_flag() -> None:
    flagged = outcome(case("a"), description_result())
    assert description_asked_wrongly(flagged) is True
    assert description_asked_wrongly(outcome(case("a"))) is False
    assert description_asked_wrongly(outcome(case("a"), failed=True)) is None
    assert description_asked(flagged) is None


def test_a_false_flag_misses_class_and_role_but_is_not_a_false_low() -> None:
    label = case("a", role=Role.DEPLOYER, tags=(SOFT_WORDING_TAG,))
    flagged = outcome(label, description_result())
    assert risk_class_match(flagged) is False
    assert role_match(flagged) is False
    assert false_low_risk(flagged) is None
    assert downgraded(flagged) is None
    assert annex_point_match(flagged) is None
    assert basis_match(flagged) is None


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        (AppliedAILabel.HIGH, False),
        (AppliedAILabel.PROHIBITED, False),
        (AppliedAILabel.LOW, False),
        (AppliedAILabel.UNCLEAR, None),
    ],
)
def test_an_appliedai_case_answered_with_a_description_request(
    label: AppliedAILabel, expected: bool | None
) -> None:
    """A class label misses; `unclear` answered needs-more-information is counted apart."""
    flagged = outcome(appliedai_case("x", label), description_result())
    assert risk_class_match(flagged) is expected
    assert description_asked_wrongly(flagged) is True


def test_a_thin_case_answered_so_is_a_needs_more_information_true_positive() -> None:
    outcomes = [outcome(thin_case("t"), description_result())]
    scores = uncertain_outcomes(outcomes, Status.NEEDS_MORE_INFORMATION)
    assert (scores.true_positives, scores.predicted, scores.labelled) == (1, 1, 1)


def test_a_group_with_a_description_request_is_not_consistent() -> None:
    tag = f"{CONSISTENCY_GROUP_PREFIX}t"
    outcomes = [
        outcome(case("a", tags=(tag,))),
        outcome(case("b", tags=(tag,)), description_result()),
    ]
    assert consistency(outcomes) == Rate(hits=0, total=1)


def test_the_summary_counts_both_description_rows() -> None:
    outcomes = [
        outcome(thin_case("t1"), description_result()),
        outcome(thin_case("t2"), result()),
        outcome(case("a"), description_result()),
        outcome(case("b")),
        outcome(case("c")),
    ]
    metrics = summarize(outcomes, None)
    assert metrics.description_asked == Rate(hits=1, total=2)
    assert metrics.description_asked_wrongly == Rate(hits=1, total=3)
    assert metrics.risk_class_accuracy == Rate(hits=2, total=3)


# --- not assessed: the provider refused a check (decision 030) ---------------------------------


def test_a_refused_case_scores_only_as_not_assessed() -> None:
    label = case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT)
    scores = case_scores(outcome(label, refused_result()), exists_in_worked_example)
    assert scores.pop("not_assessed") is True
    assert scores.pop("citation_existence") is True
    assert set(scores.values()) == {None}


def test_a_failed_case_has_no_not_assessed_score() -> None:
    assert case_scores(outcome(case("a"), failed=True))["not_assessed"] is None


def test_summarize_leaves_not_assessed_cases_out_and_counts_them_apart() -> None:
    label = case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT)
    # Stored before decision 030: a refused check next to a lower class it assumed.
    old_refusal = stored_before_decision_030(result(R.MINIMAL_RISK))
    outcomes = [
        outcome(label),
        outcome(case("b", role=Role.DEPLOYER), refused_result()),
        outcome(case("c", role=Role.PROVIDER), old_refusal),
    ]
    metrics = summarize(outcomes, exists_in_worked_example)
    assert (metrics.cases, metrics.not_assessed, metrics.failed) == (3, 2, 0)
    assert metrics.risk_class_accuracy == Rate(hits=1, total=1)
    assert metrics.risk_class_accuracy_not_assessed_as_miss == Rate(hits=1, total=3)
    assert metrics.false_low_risk == Rate(hits=0, total=1)
    assert metrics.role_accuracy == Rate(hits=1, total=1)
    assert metrics.needs_more_information.predicted == 0
    assert metrics.citation_existence == Rate(hits=3, total=3)


def test_a_consistency_group_with_a_not_assessed_member_is_left_out() -> None:
    def member(case_id: str, group: str) -> BenchmarkCase:
        return case(case_id, tags=(f"triple:{group}",))

    outcomes = [
        outcome(member("a1", "a")),
        outcome(member("a2", "a"), refused_result()),
        outcome(member("b1", "b")),
        outcome(member("b2", "b")),
    ]
    assert consistency(outcomes) == Rate(hits=1, total=1)
