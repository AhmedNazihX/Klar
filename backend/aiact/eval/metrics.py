"""Deterministic metrics: a result compared with its case label, no model involved (INIT > Metrics).

Each per-case scorer returns True (hit), False (miss) or None (the metric doesn't apply), the
shape `eval_case_results.scores` stores; a rate is hits over the cases where it applies. A case
whose classifier failed has no result: it counts as a miss for risk-class and role accuracy, and
is left out of the metrics that are defined on answers (false-low-risk, Annex point, downgrade).

Scoring rules decided here:
- A `legally_ambiguous` label is scored under uncertain-outcome handling, not risk-class accuracy
  (decision 001 for hr-ex-307; INIT > Label rules). The same holds for appliedAI `unclear`, which
  INIT scores on status.
- `needs_more_information` is reported separately (INIT > Metrics): an ambiguous-labelled case
  answered with it leaves both the risk-class accuracy and the ambiguous recall denominator and
  is counted on its own. For appliedAI this is `score_appliedai`'s `is_counted_separately`.
- Every other label is scored on the result's working-assumption class, whatever its status.
"""

from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Sequence

from pydantic import Field

from aiact.eval.cases import AppliedAILabel, BenchmarkCase, CaseLabel, score_appliedai
from aiact.schemas.base import ContractModel
from aiact.schemas.enums import RiskClass, Status
from aiact.schemas.evidence import Citation
from aiact.schemas.result import ClassificationResult

RISK_RANK: dict[RiskClass, int] = {
    RiskClass.OUT_OF_SCOPE: 0,
    RiskClass.MINIMAL_RISK: 1,
    RiskClass.LIMITED_RISK: 2,
    RiskClass.HIGH_RISK: 3,
    RiskClass.PROHIBITED: 4,
}
"""Severity order for "classified lower": a prohibited system answered high_risk is too low."""

UNSAFE_CLASSES = frozenset({RiskClass.HIGH_RISK, RiskClass.PROHIBITED})
APPLIEDAI_CLASS: dict[AppliedAILabel, RiskClass] = {
    AppliedAILabel.HIGH: RiskClass.HIGH_RISK,
    AppliedAILabel.PROHIBITED: RiskClass.PROHIBITED,
}
"""The appliedAI labels that name one class, for the false-low-risk rate."""

SOFT_WORDING_TAG = "wording:soft"
"""Marks the softened description of a soft-wording pair (B6); the downgrade rate scores these."""
CONSISTENCY_GROUP_PREFIX = "triple:"
"""Tag prefix linking the paraphrases of one system in the consistency set (B8)."""

ART_6_3_FILTER = "art_6_3_filter"
"""The Art. 6(3) basis; a lettered form such as `art_6_3_filter:d` names the exemption point."""

CitationExists = Callable[[Citation], bool]
Scorer = Callable[["Outcome"], bool | None]


class Outcome(ContractModel):
    """One case of a run: its label and the classifier's result (None when it failed)."""

    case: BenchmarkCase
    result: ClassificationResult | None = None


class Rate(ContractModel):
    """Hits over the cases (or items) a metric applies to."""

    hits: int = Field(ge=0)
    total: int = Field(ge=0)

    @property
    def value(self) -> float | None:
        return self.hits / self.total if self.total else None


class PrecisionRecall(ContractModel):
    """How well one uncertain status is predicted against the labels that carry it."""

    true_positives: int = Field(ge=0)
    predicted: int = Field(ge=0, description="Results with the status.")
    labelled: int = Field(ge=0, description="Cases labelled with the status.")

    @property
    def precision(self) -> Rate:
        return Rate(hits=self.true_positives, total=self.predicted)

    @property
    def recall(self) -> Rate:
        return Rate(hits=self.true_positives, total=self.labelled)


# --- label helpers -----------------------------------------------------------------------------


def label_status(case: BenchmarkCase) -> Status:
    """The status a case expects; appliedAI `unclear` means `legally_ambiguous`."""
    if isinstance(case.label, CaseLabel):
        return case.label.status
    return Status.LEGALLY_AMBIGUOUS if case.label is AppliedAILabel.UNCLEAR else Status.DECIDED


def _is_ambiguous(case: BenchmarkCase) -> bool:
    return label_status(case) is Status.LEGALLY_AMBIGUOUS


def _unsafe_label_class(case: BenchmarkCase) -> RiskClass | None:
    """The labelled class when it is high_risk or prohibited and the label isn't ambiguous."""
    if _is_ambiguous(case):
        return None
    label = case.label
    risk_class = label.risk_class if isinstance(label, CaseLabel) else APPLIEDAI_CLASS.get(label)
    return risk_class if risk_class in UNSAFE_CLASSES else None


def _answered_needs_info_on_ambiguous(outcome: Outcome) -> bool:
    result = outcome.result
    return (
        _is_ambiguous(outcome.case)
        and result is not None
        and result.status is Status.NEEDS_MORE_INFORMATION
    )


# --- per-case scorers --------------------------------------------------------------------------


def risk_class_match(outcome: Outcome) -> bool | None:
    """Risk-class accuracy, with the appliedAI mapping for that set."""
    label, result = outcome.case.label, outcome.result
    if isinstance(label, AppliedAILabel):
        if result is None:
            return False
        score = score_appliedai(label, result.risk_class, result.status)
        return None if score.is_counted_separately else score.is_match
    if label.status is Status.LEGALLY_AMBIGUOUS:
        return None
    return result is not None and result.risk_class is label.risk_class


def false_low_risk(outcome: Outcome) -> bool | None:
    """Whether a high-risk or prohibited system was classified lower (the costliest error)."""
    expected, result = _unsafe_label_class(outcome.case), outcome.result
    if expected is None or result is None:
        return None
    return RISK_RANK[result.risk_class] < RISK_RANK[expected]


def annex_point_match(outcome: Outcome) -> bool | None:
    """For a high-risk result on a case labelled high-risk with an Annex point: is it the same?"""
    label, result = outcome.case.label, outcome.result
    if not isinstance(label, CaseLabel) or label.status is Status.LEGALLY_AMBIGUOUS:
        return None
    if label.risk_class is not RiskClass.HIGH_RISK or label.annex_point is None:
        return None
    if result is None or result.risk_class is not RiskClass.HIGH_RISK:
        return None
    return result.annex_point == label.annex_point


def role_match(outcome: Outcome) -> bool | None:
    """Role accuracy, Art. 25 switches included: the label's role against the result's."""
    label, result = outcome.case.label, outcome.result
    if not isinstance(label, CaseLabel) or label.role is None:
        return None
    return result is not None and result.role is label.role


def downgraded(outcome: Outcome) -> bool | None:
    """The downgrade rate's per-case score: a soft-worded high-risk description classified lower."""
    if SOFT_WORDING_TAG not in outcome.case.tags:
        return None
    return false_low_risk(outcome)


def citations_exist(outcome: Outcome, exists: CitationExists) -> bool | None:
    """Whether every citation in the result resolves; None when there is nothing to check."""
    citations = _citations(outcome.result)
    return all(exists(citation) for citation in citations) if citations else None


def case_scores(outcome: Outcome, exists: CitationExists | None = None) -> dict[str, bool | None]:
    """Every per-case score, keyed as `eval_case_results.scores` stores them. Without a citation
    resolver (for example an empty corpus) citation existence is left out."""
    scores = {name: scorer(outcome) for name, scorer in SCORERS.items()}
    if exists is None:
        return scores
    return scores | {"citation_existence": citations_exist(outcome, exists)}


def metric_scorer(
    exists: CitationExists | None = None,
) -> Callable[[BenchmarkCase, ClassificationResult], dict[str, bool | None]]:
    """`case_scores` in the runner's scorer shape: `(case, result) -> scores` (V1)."""

    def score(case: BenchmarkCase, result: ClassificationResult) -> dict[str, bool | None]:
        return case_scores(Outcome(case=case, result=result), exists)

    return score


SCORERS: dict[str, Scorer] = {
    "risk_class_accuracy": risk_class_match,
    "false_low_risk": false_low_risk,
    "annex_point_accuracy": annex_point_match,
    "role_accuracy": role_match,
    "downgrade": downgraded,
}


def _citations(result: ClassificationResult | None) -> tuple[Citation, ...]:
    if result is None:
        return ()
    return tuple(citation for step in result.steps for citation in step.citations)


# --- aggregates --------------------------------------------------------------------------------


def rate(outcomes: Iterable[Outcome], scorer: Scorer) -> Rate:
    """Hits over the outcomes the scorer applies to."""
    scores = [score for score in map(scorer, outcomes) if score is not None]
    return Rate(hits=sum(scores), total=len(scores))


def uncertain_outcomes(outcomes: Sequence[Outcome], status: Status) -> PrecisionRecall:
    """Precision and recall of one uncertain status against the labels that carry it.

    For `legally_ambiguous`, ambiguous-labelled cases answered `needs_more_information` are left
    out (see `needs_info_on_ambiguous`). A failed case counts only against recall.
    """
    scored = [
        outcome
        for outcome in outcomes
        if status is not Status.LEGALLY_AMBIGUOUS or not _answered_needs_info_on_ambiguous(outcome)
    ]
    pairs = [
        (o.result is not None and o.result.status is status, label_status(o.case) is status)
        for o in scored
    ]
    return PrecisionRecall(
        true_positives=sum(is_predicted and is_labelled for is_predicted, is_labelled in pairs),
        predicted=sum(is_predicted for is_predicted, _ in pairs),
        labelled=sum(is_labelled for _, is_labelled in pairs),
    )


def needs_info_on_ambiguous(outcomes: Iterable[Outcome]) -> int:
    """Ambiguous-labelled cases answered `needs_more_information`, reported on their own."""
    return sum(map(_answered_needs_info_on_ambiguous, outcomes))


def consistency(outcomes: Iterable[Outcome], prefix: str = CONSISTENCY_GROUP_PREFIX) -> Rate:
    """Groups (linked by a `prefix` tag) whose members all got a result with the same class."""
    groups: defaultdict[str, list[Outcome]] = defaultdict(list)
    for outcome in outcomes:
        for tag in outcome.case.tags:
            if tag.startswith(prefix):
                groups[tag].append(outcome)
    scored = [members for members in groups.values() if len(members) > 1]
    hits = sum(_same_class(members) for members in scored)
    return Rate(hits=hits, total=len(scored))


def _same_class(members: Sequence[Outcome]) -> bool:
    classes = {member.result.risk_class if member.result else None for member in members}
    return len(classes) == 1 and None not in classes


def citation_existence(outcomes: Iterable[Outcome], exists: CitationExists | None) -> Rate:
    """Citations that resolve over all citations in all results (hard rule: 100%); an empty
    rate without a resolver."""
    if exists is None:
        return Rate(hits=0, total=0)
    citations = [citation for outcome in outcomes for citation in _citations(outcome.result)]
    return Rate(hits=sum(map(exists, citations)), total=len(citations))


def appliedai_review_count(outcomes: Iterable[Outcome]) -> int:
    """appliedAI cases that go to the disagreement review (INIT > Disagreement review)."""
    count = 0
    for outcome in outcomes:
        label, result = outcome.case.label, outcome.result
        if not isinstance(label, AppliedAILabel):
            continue
        if (
            result is None
            or score_appliedai(label, result.risk_class, result.status).needs_disagreement_review
        ):
            count += 1
    return count


# --- Commission example rules (decision 001) ---------------------------------------------------


def basis_matches(answer: str, accepted_bases: Collection[str]) -> bool:
    """Whether a result's basis is correct under decision 001's `accepted_bases` rule.

    A bare `art_6_3_filter` matches any lettered entry; a lettered `art_6_3_filter:<x>` matches
    the same letter or a bare entry; any other basis must match exactly.
    """
    if answer in accepted_bases:
        return True
    if answer == ART_6_3_FILTER:
        return any(entry.startswith(f"{ART_6_3_FILTER}:") for entry in accepted_bases)
    if answer.startswith(f"{ART_6_3_FILTER}:"):
        return ART_6_3_FILTER in accepted_bases
    return False


def flags_flip_variant(result: ClassificationResult, provisions: Collection[str]) -> bool:
    """Whether the result asked about or flagged a verdict-flipping feature (decision 001 rule).

    It counts when a follow-up question is `about` one of the variant's provisions, or a step
    that isn't decided cites one. Provisions match along the hierarchy: `annex:III:7` and
    `annex:III:7:a` match each other.
    """
    about = [question.about for question in result.follow_up_questions if question.about]
    uncertain_cites = [
        citation.provision_id
        for step in result.steps
        if step.status is not Status.DECIDED
        for citation in step.citations
    ]
    return any(
        _same_branch(found, wanted) for found in (*about, *uncertain_cites) for wanted in provisions
    )


def _same_branch(left: str, right: str) -> bool:
    shorter, longer = sorted((left, right), key=len)
    return longer == shorter or longer.startswith(f"{shorter}:")


# --- run summary -------------------------------------------------------------------------------


class RunMetrics(ContractModel):
    """Every deterministic metric of one run."""

    cases: int
    failed: int
    risk_class_accuracy: Rate
    false_low_risk: Rate
    annex_point_accuracy: Rate
    role_accuracy: Rate
    ambiguous: PrecisionRecall
    needs_more_information: PrecisionRecall
    needs_info_on_ambiguous: int
    downgrade: Rate
    consistency: Rate
    citation_existence: Rate
    appliedai_disagreement_review: int


def summarize(outcomes: Sequence[Outcome], exists: CitationExists | None) -> RunMetrics:
    """Compute every deterministic metric over one run's outcomes."""
    return RunMetrics(
        cases=len(outcomes),
        failed=sum(outcome.result is None for outcome in outcomes),
        risk_class_accuracy=rate(outcomes, risk_class_match),
        false_low_risk=rate(outcomes, false_low_risk),
        annex_point_accuracy=rate(outcomes, annex_point_match),
        role_accuracy=rate(outcomes, role_match),
        ambiguous=uncertain_outcomes(outcomes, Status.LEGALLY_AMBIGUOUS),
        needs_more_information=uncertain_outcomes(outcomes, Status.NEEDS_MORE_INFORMATION),
        needs_info_on_ambiguous=needs_info_on_ambiguous(outcomes),
        downgrade=rate(outcomes, downgraded),
        consistency=consistency(outcomes),
        citation_existence=citation_existence(outcomes, exists),
        appliedai_disagreement_review=appliedai_review_count(outcomes),
    )
