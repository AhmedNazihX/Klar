"""How a check's outcome is scored against an own case's label, and the state a check is replayed
with. One copy, shared by the E3-E7 replay tests and the X2 smoke test, so the two
can't drift apart.

- scope (B5b): out of scope exactly when the label is, with its status; an out-of-scope finding
  cites the provision the label rests on first.
- prohibited (B5c): matched exactly when the label is prohibited, with the label's status (a
  label of another class needs a decided Art. 5 step), citing every `prohibition:` tag; a case
  whose prohibition doesn't apply yet on its date cites Art. 113(a); one whose significant harm
  the description leaves open (`trap:significant_harm_unsettled`) may be ambiguous or missing a
  fact (B12's rule).
- high_risk (B5e, INIT's worked example): the label's class, route, Annex point and status, the
  tagged missing fact, the Art. 2(2) note for a decided Section B case, and every `cites:` tag.
- transparency (B5a): the label's status; no Art. 50 duty for a minimal_risk label and at least
  one for limited_risk (rule 2: the class describes the system); of the duties the labelled role
  bears itself (Art. 50(1)-(2) a provider, (3)-(4) a deployer), exactly the tagged
  `obligation:art:50:` ones, so a trap duty listed fails; every tagged one listed. A case tagged
  for the grace period (`timing:art111_4_grace`) needs it given outright: Art. 111(4) cited and
  the placed-on-the-market sentence, not the one for an unknown date or one only put into
  service. A case tagged without it (`timing:art111_4_no_grace`) must not cite Art. 111(4); one
  only put into service (`timing:art111_4_put_into_service`) is a doubt and isn't scored.
- role_obligations (B5d): the label's role, and its status when the label is legally ambiguous.
  The check is given the class the label settles (the role-only replay the user chose on
  2026-09-29).
"""

from datetime import date

from aiact.engine.nodes.prohibited_practices import APPLICATION_DATES
from aiact.engine.nodes.transparency import GRACE_PERIOD, PLACED_BEFORE_SENTENCE, grace_sentence
from aiact.engine.state import CheckOutcome, EngineState
from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.schemas import HighRiskRoute, Language, LawVersion, RiskClass, Role, Status, StepName

WORKED_EXAMPLE = BenchmarkCase(
    id="init-worked-example",
    set_name=CaseSet.OWN,
    language=Language.EN,
    description=(
        "We're a 40-person logistics company. We use a tool that reads incoming job applications, "
        "scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't "
        "change it."
    ),
    label=CaseLabel(
        risk_class=RiskClass.HIGH_RISK, role=Role.DEPLOYER, annex_point=("annex:III:4:a",)
    ),
    label_citation=("annex:III:4:a", "art:6:3"),
    notes="INIT > Worked example (not a benchmark case): ranking is profiling, so no Art. 6(3).",
    tags=("cites:art:6:3",),
)
"""INIT's worked example as a case: E5 replays it, and the smoke test probes it."""


def case_label(case: BenchmarkCase) -> CaseLabel:
    if not isinstance(case.label, CaseLabel):
        raise ValueError(f"case {case.id} has no engine-vocabulary label")
    return case.label


def tag(case: BenchmarkCase, name: str) -> list[str]:
    """The values of the case's `<name>:<value>` tags."""
    prefix = f"{name}:"
    return [item.removeprefix(prefix) for item in case.tags if item.startswith(prefix)]


def cited(outcome: CheckOutcome) -> list[str]:
    return [citation.provision_id for citation in outcome.step.citations]


# --- States -------------------------------------------------------------------------------------


def replay_state(case: BenchmarkCase, as_of: date) -> EngineState:
    """The state a check is replayed with: the case's description and language, the amended
    text, and no facts, answers, exclusions or earlier steps. A dated case (`case.as_of`) is
    replayed at its own date; `as_of` is the run's date for every other case."""
    return {
        "description": case.description,
        "language": case.language,
        "law_version": LawVersion.AMENDED,
        "as_of": case.as_of or as_of,
        "answers": {},
        "exclude_source_example_ids": (),
        "facts": (),
        "steps": (),
        "matches": (),
    }


def role_check_state(case: BenchmarkCase, as_of: date) -> EngineState:
    """The replay state plus the class the label settles, as the earlier checks would leave it:
    the Art. 5 match, the high-risk route (Annex I when a label point is in Annex I, else
    Annex III), or an Art. 50(1) duty for limited_risk."""
    label = case_label(case)
    is_prohibited = label.risk_class is RiskClass.PROHIBITED
    state: EngineState = {
        **replay_state(case, as_of),
        "matches": (StepName.PROHIBITED,) if is_prohibited else (),
    }
    if label.risk_class is RiskClass.HIGH_RISK:
        is_annex_i = any(point.startswith("annex:I:") for point in label.annex_point)
        route = HighRiskRoute.ANNEX_I if is_annex_i else HighRiskRoute.ANNEX_III
        return {**state, "high_risk_route": route}
    if label.risk_class is RiskClass.LIMITED_RISK:
        return {**state, "transparency_duties": ("art:50:1",)}
    return state


def runs_role_check(case: BenchmarkCase) -> bool:
    """The role check doesn't run out of scope, and can only be scored on a labelled role."""
    label = case_label(case)
    return label.risk_class is not RiskClass.OUT_OF_SCOPE and label.role is not None


# --- Matching -----------------------------------------------------------------------------------


def scope_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    label = case_label(case)
    is_out = label.risk_class is RiskClass.OUT_OF_SCOPE
    if outcome.matched is not is_out or outcome.step.status is not label.status:
        return False
    return not is_out or case.label_citation[0] in cited(outcome)


NOT_YET_APPLICABLE = "trap:prohibition_not_yet_applicable"
HARM_UNSETTLED = "trap:significant_harm_unsettled"
UNSETTLED_HARM_STATUSES = frozenset({Status.LEGALLY_AMBIGUOUS, Status.NEEDS_MORE_INFORMATION})
"""B12's rule: a description that can't settle significant harm is flagged as either."""


def prohibited_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    label = case_label(case)
    is_prohibited = label.risk_class is RiskClass.PROHIBITED
    statuses = {label.status if is_prohibited else Status.DECIDED}
    if HARM_UNSETTLED in case.tags:
        statuses |= UNSETTLED_HARM_STATUSES
    if outcome.matched is not is_prohibited or outcome.step.status not in statuses:
        return False
    needed = {*tag(case, "prohibition")}
    if NOT_YET_APPLICABLE in case.tags:
        needed.add(APPLICATION_DATES)
    return needed <= set(cited(outcome))


def expected_route(case: BenchmarkCase) -> HighRiskRoute:
    """Annex III when a label point is in Annex III or a tag puts the case on both routes
    (Annex III is preferred), else Annex I."""
    label = case_label(case)
    is_annex_iii = any(point.startswith("annex:III:") for point in label.annex_point)
    also_iii = "annex_iii" in tag(case, "also_route")
    return HighRiskRoute.ANNEX_III if is_annex_iii or also_iii else HighRiskRoute.ANNEX_I


def high_risk_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    label = case_label(case)
    step = outcome.step
    if label.risk_class is not RiskClass.HIGH_RISK:
        return (
            outcome.high_risk_route is None
            and not outcome.annex_iii_exempt
            and outcome.annex_point is None
            and step.status is label.status
        )
    points = {*tag(case, "annex_i_point"), *label.annex_point}
    asked = step.missing_fact.id if step.missing_fact else None
    section_b_decided = "b" in tag(case, "annex_i_section") and label.status is Status.DECIDED
    names_art_2_2 = "2(2)" in step.decision or "Art. 2 Abs. 2" in step.decision
    return (
        outcome.high_risk_route is expected_route(case)
        and not outcome.annex_iii_exempt
        and outcome.annex_point in points
        and step.status is label.status
        and all(asked == fact for fact in tag(case, "missing_fact"))
        and (names_art_2_2 or not section_b_decided)
        and set(tag(case, "cites")) <= set(cited(outcome))
    )


ROLE_DUTIES: dict[Role, frozenset[str]] = {
    Role.PROVIDER: frozenset({"art:50:1", "art:50:2"}),
    Role.DEPLOYER: frozenset({"art:50:3", "art:50:4"}),
}
"""The Art. 50 duties each role bears itself."""
WITH_GRACE = "timing:art111_4_grace"
WITHOUT_GRACE = "timing:art111_4_no_grace"


def transparency_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    label = case_label(case)
    if outcome.step.status is not label.status:
        return False
    listed = set(outcome.transparency_duties)
    if label.risk_class is RiskClass.MINIMAL_RISK and listed:
        return False
    if label.risk_class is RiskClass.LIMITED_RISK and not listed:
        return False
    tagged = {item for item in tag(case, "obligation") if item.startswith("art:50:")}
    own = ROLE_DUTIES.get(label.role, frozenset()) if label.role else frozenset()
    if listed & own != tagged & own or not tagged <= listed:
        return False
    is_grace_cited = GRACE_PERIOD in cited(outcome)
    if WITH_GRACE in case.tags:
        given = grace_sentence(PLACED_BEFORE_SENTENCE, case.language)
        return is_grace_cited and given in outcome.step.decision
    return not (WITHOUT_GRACE in case.tags and is_grace_cited)


def role_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    label = case_label(case)
    if outcome.role is None or outcome.role.role is not label.role:
        return False
    return label.status is not Status.LEGALLY_AMBIGUOUS or outcome.step.status is label.status
