"""The role and obligations node (E7): every branch with invented answers, the model call with a
fake and a recorded model, and the B5d replay, which runs once those cases and recordings exist.

The descriptions and answers here are invented, not benchmark cases.
"""

from datetime import date
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr, ValidationError

from aiact.engine.graph import EngineNodes, build_graph
from aiact.engine.nodes import role_obligations as node
from aiact.engine.nodes.role_obligations import (
    Answer,
    ConditionAnswer,
    HighRiskRoleAnswer,
    KeyFact,
    LegacyAnswer,
    Modification,
    ModificationFact,
    ProvisionTextError,
    RoleAnswer,
    RoleFact,
    RoleObligationsCheck,
    RoleOutputError,
    citations,
    condition_ids,
    conditions_to_ask,
    to_outcome,
    working_class,
)
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState, RoleFinding
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseLabel, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import role_check_state, role_matches, runs_role_check, tag
from aiact.schemas import (
    DISCLAIMER,
    STEP_ORDER,
    ClassificationResult,
    EvidenceTag,
    Fact,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    LegacyStatus,
    Obligation,
    RiskClass,
    Role,
    SourceSpan,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.result import derived_status
from aiact.settings import Settings
from tests.conftest import REFUSAL_ROUTE
from tests.engine.built_corpus import unresolved_citations, whole_articles
from tests.engine.nodes.known_gaps import (
    E20_PROMPTS_RECORDING_PENDING,
    NOT_ASSESSED,
    KnownGap,
    expect_known_gap,
)
from tests.engine.nodes.pinned import assert_pinned_route
from tests.schemas.builders import open_question

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
ROLE_AS_OF = date(2026, 9, 29)
CV_TOOL = (
    "We are a 40-person logistics company. We use a tool that reads incoming job applications, "
    "scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't change it."
)
EMPLOYER = "You are an employer and use the system at the workplace."
PUBLIC_AUTHORITY = "You are a public authority or a Union institution, body, office or agency."
LAW_ENFORCEMENT = (
    "The system is listed in Annex III point 1, 6 or 7 and is used in law enforcement, "
    "migration, asylum or border control management."
)


def key_fact(value: Answer = Answer.NO, evidence: EvidenceTag = EvidenceTag.ASSUMED) -> KeyFact:
    return KeyFact(answer=value, evidence=evidence, fact=f"Answer {value.value}", fact_numbers=())


def legacy_answer(
    placed_before: Answer = Answer.NO,
    changed: Answer = Answer.NO,
    public_authority: Answer = Answer.NO,
) -> LegacyAnswer:
    """The Art. 111(2) facts, all stated; the default is a system not yet on the market."""
    return LegacyAnswer(
        placed_before=key_fact(placed_before, EvidenceTag.STATED),
        significant_design_change=key_fact(changed, EvidenceTag.STATED),
        for_public_authority=key_fact(public_authority, EvidenceTag.STATED),
    )


def role_answer(
    role: Role | None = Role.DEPLOYER,
    conditions: dict[str, Answer] | None = None,
    risk_class: RiskClass = RiskClass.HIGH_RISK,
    route: HighRiskRoute | None = HighRiskRoute.ANNEX_III,
    legacy: LegacyAnswer | None = None,
    **key_facts: KeyFact | ModificationFact,
) -> RoleAnswer:
    """An answer: the given role, every key fact "no (assumed)" unless overridden, and the
    conditions by their text, turned into the ids the prompt would list. With `legacy`, the
    high-risk answer that carries the Art. 111(2) facts."""
    ids = condition_ids(conditions_to_ask(risk_class, route, LawVersion.AMENDED))
    given = tuple(
        ConditionAnswer(id=ids[text], answer=value) for text, value in (conditions or {}).items()
    )
    values: dict[str, object] = {
        "role": RoleFact(
            role=role,
            evidence=EvidenceTag.STATED,
            fact="The company uses the tool",
            fact_numbers=(),
        ),
        "builds_on_gpai": key_fact(),
        "own_brand": key_fact(),
        "changed_purpose": key_fact(),
        "conditions": given,
        **key_facts,
        "substantial_modification": modification_fact(key_facts.get("substantial_modification")),
    }
    if legacy is not None:
        return HighRiskRoleAnswer.model_validate({**values, "legacy": legacy})
    return RoleAnswer.model_validate(values)


def modification_fact(given: KeyFact | ModificationFact | None = None) -> ModificationFact:
    """The Art. 25(1)(b) answer: "no (assumed)" by default; a plain key fact keeps its values."""
    if isinstance(given, ModificationFact):
        return given
    return ModificationFact.model_validate((given or key_fact()).model_dump())


def contested(evidence: EvidenceTag = EvidenceTag.STATED) -> ModificationFact:
    """A known change whose substantial-modification reading the law leaves open (own-d-12)."""
    return ModificationFact(
        answer=Modification.CONTESTED,
        evidence=evidence,
        fact="The company added an input the vendor's documentation neither allows nor forbids",
        fact_numbers=(),
    )


def state(
    risk_class: RiskClass = RiskClass.HIGH_RISK,
    route: HighRiskRoute | None = HighRiskRoute.ANNEX_III,
    language: Language = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
    transparency_duties: tuple[str, ...] = (),
    facts: tuple[Fact, ...] = (),
    description: str = CV_TOOL,
    annex_iii_exempt: bool = False,
) -> EngineState:
    """The state the node sees after the earlier checks put the system in `risk_class`."""
    built: EngineState = {
        "description": description,
        "language": language,
        "law_version": law_version,
        "as_of": ROLE_AS_OF,
        "exclude_source_example_ids": (),
        "facts": facts,
        "steps": (),
        "matches": (StepName.PROHIBITED,) if risk_class is RiskClass.PROHIBITED else (),
    }
    if risk_class is RiskClass.HIGH_RISK and route is not None:
        built["high_risk_route"] = route
    if transparency_duties:
        built["transparency_duties"] = transparency_duties
    if annex_iii_exempt:
        built["annex_iii_exempt"] = True
    return built


def finding(outcome: CheckOutcome) -> RoleFinding:
    assert outcome.role is not None
    return outcome.role


def articles(outcome: CheckOutcome) -> list[str]:
    return [obligation.article for obligation in finding(outcome).obligations]


# --- The class the earlier checks settled ---------------------------------------------------------


@pytest.mark.parametrize(
    ("risk_class", "route", "duties"),
    [
        (RiskClass.PROHIBITED, None, ()),
        (RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_I, ("art:50:1",)),
        (RiskClass.LIMITED_RISK, None, ("art:50:1",)),
        (RiskClass.MINIMAL_RISK, None, ()),
    ],
)
def test_working_class_follows_the_earlier_findings(
    risk_class: RiskClass, route: HighRiskRoute | None, duties: tuple[str, ...]
) -> None:
    assert working_class(state(risk_class, route, transparency_duties=duties)) == (
        risk_class,
        route,
    )


# --- Role, Art. 25 switches, GPAI --------------------------------------------------------------


def test_worked_example_stays_a_deployer_with_the_art_26_duties() -> None:
    outcome = to_outcome(role_answer(), state())
    assert outcome.step.step is StepName.ROLE_OBLIGATIONS
    assert outcome.step.status is Status.DECIDED
    assert finding(outcome).role is Role.DEPLOYER
    assert finding(outcome).role_switch_reason is None
    assert {"art:26:1", "art:26:2", "art:26:6"} <= set(articles(outcome))
    assert outcome.step.decision.startswith("Role: deployer.")


@pytest.mark.parametrize(
    ("language", "risk_class", "line"),
    [
        (
            Language.EN,
            RiskClass.HIGH_RISK,
            "duties listed for this high-risk system (amended text).",
        ),
        (
            Language.DE,
            RiskClass.HIGH_RISK,
            "Pflichten für ein System der Risikoklasse „Hochrisiko“ (geänderte Fassung).",
        ),
        (Language.EN, RiskClass.MINIMAL_RISK, "duties listed for this minimal risk system"),
        (Language.DE, RiskClass.MINIMAL_RISK, "der Risikoklasse „minimales Risiko“"),
    ],
)
def test_the_duties_line_names_the_class_and_text_in_words(
    language: Language, risk_class: RiskClass, line: str
) -> None:
    # The screens show this sentence as it is: no raw key such as `high_risk` (UI review).
    route = HighRiskRoute.ANNEX_III if risk_class is RiskClass.HIGH_RISK else None
    answer = role_answer(risk_class=risk_class, route=route)
    decision = to_outcome(answer, state(risk_class, route, language=language)).step.decision
    assert line in decision
    assert risk_class.value not in decision


@pytest.mark.parametrize(
    ("switch", "article"),
    [
        ("own_brand", "25(1)(a)"),
        ("substantial_modification", "25(1)(b)"),
        ("changed_purpose", "25(1)(c)"),
    ],
)
@pytest.mark.parametrize("base", [Role.DEPLOYER, Role.IMPORTER, Role.DISTRIBUTOR])
def test_each_art_25_switch_makes_a_provider_of_a_high_risk_system(
    switch: str, article: str, base: Role
) -> None:
    switched = {switch: key_fact(Answer.YES, EvidenceTag.STATED)}
    answer = role_answer(base).model_copy(update=switched)
    outcome = to_outcome(answer, state())
    reason = finding(outcome).role_switch_reason
    assert finding(outcome).role is Role.PROVIDER
    assert reason is not None
    assert f"Art. {article}" in reason
    assert outcome.step.status is Status.DECIDED
    assert "art:9" in articles(outcome)
    # A deployer still uses the system, so it keeps its duties; an importer or distributor that
    # became the provider has the provider's duties instead of its own (Art. 25(1)).
    uses_it = base is Role.DEPLOYER
    assert finding(outcome).also_role is (Role.DEPLOYER if uses_it else None)
    assert ({"art:26:1", "art:26:2", "art:26:6"} <= set(articles(outcome))) is uses_it
    assert not any(a.startswith(("art:23:", "art:24:")) for a in articles(outcome))


def test_a_switched_deployer_gets_provider_and_deployer_duties_once_each() -> None:
    answer = role_answer(
        conditions={EMPLOYER: Answer.YES}, own_brand=key_fact(Answer.YES, EvidenceTag.STATED)
    )
    outcome = to_outcome(answer, state())
    kept = articles(outcome)
    assert {"art:9", "art:16:i", "art:26:1", "art:26:2", "art:26:6", "art:26:7"} <= set(kept)
    assert kept.count("art:4:1") == 1  # AI literacy is on both lists, listed once
    assert outcome.step.decision.startswith("Role: provider, and also deployer.")


@pytest.mark.parametrize("risk_class", [RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK])
@pytest.mark.parametrize("switch", ["substantial_modification", "changed_purpose"])
def test_art_25_switches_only_apply_to_high_risk_systems(
    risk_class: RiskClass, switch: str
) -> None:
    answer = role_answer(risk_class=risk_class, route=None).model_copy(
        update={switch: key_fact(Answer.YES)}
    )
    duties = ("art:50:1",) if risk_class is RiskClass.LIMITED_RISK else ()
    outcome = to_outcome(answer, state(risk_class, None, transparency_duties=duties))
    assert finding(outcome).role is Role.DEPLOYER
    assert finding(outcome).role_switch_reason is None
    assert outcome.step.status is Status.DECIDED


# --- Own name on a system that isn't high-risk (Art. 3(3), user decision on own-d-05) -----------


def _white_labeller(risk_class: RiskClass, own_brand: Answer = Answer.YES) -> RoleAnswer:
    return role_answer(
        Role.DISTRIBUTOR,
        risk_class=risk_class,
        route=None,
        own_brand=key_fact(own_brand, EvidenceTag.STATED),
    )


@pytest.mark.parametrize(
    ("risk_class", "duties"),
    [(RiskClass.LIMITED_RISK, ("art:50:2",)), (RiskClass.MINIMAL_RISK, ())],
)
def test_a_white_labeller_below_high_risk_is_ambiguous_with_provider_assumed(
    risk_class: RiskClass, duties: tuple[str, ...]
) -> None:
    given = state(risk_class, None, transparency_duties=duties)
    outcome = to_outcome(_white_labeller(risk_class), given)
    step = outcome.step
    assert step.status is Status.LEGALLY_AMBIGUOUS
    assert step.missing_fact is None
    assert step.open_question is not None
    assert "Art. 3(3)" in step.open_question.question
    assert step.open_question.readings[0].explanation.startswith(
        "Provider"
    )  # the stricter reading first
    assert step.open_question.readings[1].explanation.startswith("Distributor")
    provider, distributor = step.open_question.readings
    assert (provider.title, distributor.title) == ("Provider", "Distributor")
    assert (provider.risk_class, distributor.risk_class) == (None, None)  # the class stays
    assert provider.citation is not None and provider.citation in step.citations
    assert provider.citation == distributor.citation  # both turn on Art. 3(3)
    assert provider.citation.provision_id == "art:3:3"
    assert (finding(outcome).role, finding(outcome).also_role) == (
        Role.PROVIDER,
        Role.DISTRIBUTOR,
    )
    if outcome.step.missing_fact is not None:  # the unknown own-name case
        decision = outcome.step.decision
        assert "whether that makes you its provider is legally open" in decision
        assert "pending an answer to" not in decision  # a yes doesn't settle the role
    assert finding(outcome).role_switch_reason is None  # no Art. 25 switch
    assert [c.provision_id for c in step.citations] == ["art:3:7", "art:3:3"]
    assert "Art. 50 guidelines point to provider" in step.decision
    assert "Working assumption: provider, keeping the distributor duties" in step.decision
    assert ("art:50:2" in articles(outcome)) is bool(duties)  # the provider's marking duty


def test_the_ambiguous_white_labeller_fits_the_result_contract() -> None:
    role_step = to_outcome(
        _white_labeller(RiskClass.MINIMAL_RISK), state(RiskClass.MINIMAL_RISK, None)
    ).step
    earlier = (
        StepResult(step=name, decision=f"{name.value}: no finding")
        for name in STEP_ORDER
        if name is not StepName.ROLE_OBLIGATIONS
    )
    steps = (*earlier, role_step)
    result = ClassificationResult(
        facts=(),
        steps=steps,
        risk_class=RiskClass.MINIMAL_RISK,
        status=derived_status(steps),
        role=Role.PROVIDER,
        law_version=LawVersion.AMENDED,
        as_of=date(2026, 9, 29),
        disclaimer=DISCLAIMER[Language.EN],
    )
    assert result.status is Status.LEGALLY_AMBIGUOUS


def test_the_ambiguity_reads_in_german() -> None:
    given = state(RiskClass.MINIMAL_RISK, None, language=Language.DE)
    step = to_outcome(_white_labeller(RiskClass.MINIMAL_RISK), given).step
    assert step.open_question is not None
    assert "Art. 3 Nr. 3" in step.open_question.question
    assert step.open_question.readings[1].explanation.startswith("Händler")
    assert "Rechtlich offen" in step.decision


def test_the_same_white_labeller_at_high_risk_is_a_decided_art_25_1_a_provider() -> None:
    answer = role_answer(Role.DISTRIBUTOR, own_brand=key_fact(Answer.YES, EvidenceTag.STATED))
    outcome = to_outcome(answer, state())
    assert outcome.step.status is Status.DECIDED
    assert outcome.step.open_question is None
    assert "25(1)(a)" in (finding(outcome).role_switch_reason or "")
    assert finding(outcome).also_role is None


def test_a_company_that_develops_its_system_stays_a_decided_provider() -> None:
    answer = role_answer(
        Role.PROVIDER, risk_class=RiskClass.MINIMAL_RISK, route=None, own_brand=key_fact(Answer.YES)
    )
    outcome = to_outcome(answer, state(RiskClass.MINIMAL_RISK, None))
    assert outcome.step.status is Status.DECIDED
    assert finding(outcome).role is Role.PROVIDER


@pytest.mark.parametrize("own_brand", [Answer.YES, Answer.UNKNOWN])
def test_a_prohibited_system_keeps_its_base_role_whatever_the_name(own_brand: Answer) -> None:
    # Art. 5 bans placing on the market, putting into service and use, whoever the operator is.
    answer = role_answer(
        Role.DEPLOYER,
        risk_class=RiskClass.PROHIBITED,
        route=None,
        own_brand=key_fact(own_brand, EvidenceTag.STATED),
    )
    outcome = to_outcome(answer, state(RiskClass.PROHIBITED, None))
    assert outcome.step.status is Status.DECIDED
    assert (finding(outcome).role, finding(outcome).also_role) == (Role.DEPLOYER, None)
    assert outcome.follow_up_questions == ()
    assert outcome.step.open_question is None


def test_ambiguity_with_an_open_gpai_answer_states_the_assumption_once() -> None:
    answer = _white_labeller(RiskClass.MINIMAL_RISK).model_copy(
        update={"builds_on_gpai": key_fact(Answer.UNKNOWN)}
    )
    step = to_outcome(answer, state(RiskClass.MINIMAL_RISK, None)).step
    assert step.status is Status.LEGALLY_AMBIGUOUS
    assert step.decision.count("Working assumption") == 1
    assert "Still to confirm: Is the system built on a general-purpose AI model" in step.decision
    german = to_outcome(answer, state(RiskClass.MINIMAL_RISK, None, language=Language.DE))
    assert german.step.decision.count("Arbeitsannahme") == 1


def test_an_unknown_own_name_below_high_risk_asks_for_it() -> None:
    answer = _white_labeller(RiskClass.LIMITED_RISK, Answer.UNKNOWN)
    given = state(RiskClass.LIMITED_RISK, None, transparency_duties=("art:50:1",))
    outcome = to_outcome(answer, given)
    assert outcome.step.status is Status.NEEDS_MORE_INFORMATION
    assert outcome.step.missing_fact is not None
    assert (outcome.step.missing_fact.id, outcome.step.missing_fact.about) == (
        "own_name",
        "art:3:3",
    )
    assert (finding(outcome).role, finding(outcome).also_role) == (
        Role.PROVIDER,
        Role.DISTRIBUTOR,
    )
    if outcome.step.missing_fact is not None:  # the unknown own-name case
        decision = outcome.step.decision
        assert "whether that makes you its provider is legally open" in decision
        assert "pending an answer to" not in decision  # a yes doesn't settle the role


def test_an_unsettled_switch_needs_information_with_provider_as_the_assumption() -> None:
    answer = role_answer(substantial_modification=key_fact(Answer.UNKNOWN, EvidenceTag.INFERRED))
    outcome = to_outcome(answer, state())
    assert outcome.step.status is Status.NEEDS_MORE_INFORMATION
    missing = outcome.step.missing_fact
    assert missing is not None
    assert (missing.id, missing.about) == ("substantial_modification", "art:25:1:b")
    assert finding(outcome).role is Role.PROVIDER
    assert finding(outcome).role_switch_reason is None
    assert "Working assumption: provider" in outcome.step.decision


@pytest.mark.parametrize(
    ("base", "own_duties"),
    [
        (Role.DEPLOYER, {"art:26:1", "art:26:2", "art:26:6"}),
        (Role.IMPORTER, {"art:23:1", "art:23:2"}),
        (Role.DISTRIBUTOR, {"art:24:1", "art:24:2"}),
    ],
)
def test_the_working_assumption_keeps_the_base_roles_duties(
    base: Role, own_duties: set[str]
) -> None:
    answer = role_answer(base, changed_purpose=key_fact(Answer.UNKNOWN))
    outcome = to_outcome(answer, state())
    assert (finding(outcome).role, finding(outcome).also_role) == (Role.PROVIDER, base)
    assert own_duties | {"art:9"} <= set(articles(outcome))


def test_every_unknown_deciding_fact_becomes_a_follow_up_question() -> None:
    answer = role_answer(
        builds_on_gpai=key_fact(Answer.UNKNOWN),
        own_brand=key_fact(Answer.UNKNOWN),
        changed_purpose=key_fact(Answer.UNKNOWN),
    )
    outcome = to_outcome(answer, state())
    ids = [question.id for question in outcome.follow_up_questions]
    assert ids == ["builds_on_gpai", "own_brand", "changed_purpose"]
    assert outcome.step.missing_fact == outcome.follow_up_questions[0]


def test_a_yes_switch_wins_over_an_unsettled_one() -> None:
    answer = role_answer(own_brand=key_fact(Answer.UNKNOWN), changed_purpose=key_fact(Answer.YES))
    outcome = to_outcome(answer, state())
    assert outcome.step.status is Status.DECIDED
    assert "25(1)(c)" in (finding(outcome).role_switch_reason or "")


# --- Every Art. 25(1) switch that applies (user, 2026-10-06, own-d-13) --------------------------


def switch_citations(outcome: CheckOutcome) -> list[str]:
    return [c.provision_id for c in outcome.step.citations if c.provision_id.startswith("art:25:")]


def test_every_switch_that_applies_is_reported_with_its_citation() -> None:
    answer = role_answer(
        own_brand=key_fact(Answer.YES, EvidenceTag.STATED),
        substantial_modification=key_fact(Answer.YES, EvidenceTag.STATED),
    )
    outcome = to_outcome(answer, state())
    reason = finding(outcome).role_switch_reason or ""
    assert "Art. 25(1)(a)" in reason
    assert "Art. 25(1)(b)" in reason
    assert switch_citations(outcome) == ["art:25:1:a", "art:25:1:b"]
    assert outcome.step.status is Status.DECIDED
    assert reason in outcome.step.decision


def test_a_changed_purpose_rules_out_a_substantial_modification() -> None:
    """(c) says the new purpose made the system high-risk, so the original wasn't, and (b)
    needs a system that already was: the model's answer to both reports (c) alone."""
    answer = role_answer(
        substantial_modification=key_fact(Answer.YES, EvidenceTag.INFERRED),
        changed_purpose=key_fact(Answer.YES, EvidenceTag.INFERRED),
    )
    outcome = to_outcome(answer, state())
    assert switch_citations(outcome) == ["art:25:1:c"]
    assert "25(1)(b)" not in (finding(outcome).role_switch_reason or "")
    assert (finding(outcome).role, finding(outcome).also_role) == (Role.PROVIDER, Role.DEPLOYER)
    assert "Answer yes" in [f.text for f in outcome.step.facts_used]  # (c)'s fact is shown


def test_own_brand_joins_a_changed_purpose() -> None:
    answer = role_answer(
        own_brand=key_fact(Answer.YES, EvidenceTag.STATED),
        changed_purpose=key_fact(Answer.YES, EvidenceTag.STATED),
    )
    assert switch_citations(to_outcome(answer, state())) == ["art:25:1:a", "art:25:1:c"]


def test_a_ruled_out_modification_is_neither_relied_on_nor_asked() -> None:
    answer = role_answer(
        substantial_modification=key_fact(Answer.UNKNOWN), changed_purpose=key_fact(Answer.YES)
    )
    outcome = to_outcome(answer, state())
    assert outcome.step.status is Status.DECIDED
    assert "substantial_modification" not in [q.id for q in outcome.follow_up_questions]


# --- A contested substantial modification (user, 2026-10-06, own-d-12) --------------------------


def test_a_contested_modification_is_ambiguous_with_provider_assumed() -> None:
    """The description says what changed and what the documentation foresees: whether that is a
    substantial modification is a question of law, not a missing fact."""
    outcome = to_outcome(role_answer(substantial_modification=contested()), state())
    step = outcome.step
    assert step.status is Status.LEGALLY_AMBIGUOUS
    assert step.missing_fact is None
    assert outcome.follow_up_questions == ()  # nothing a user could answer
    assert step.open_question is not None
    assert "Art. 3(23)" in step.open_question.question
    assert step.open_question.readings[0].explanation.startswith(
        "Provider"
    )  # the stricter reading first
    assert step.open_question.readings[1].explanation.startswith("Deployer")
    provider, deployer = step.open_question.readings
    assert provider.citation is not None and deployer.citation is not None
    assert (provider.citation.provision_id, deployer.citation.provision_id) == (
        "art:25:1:b",
        "art:3:23",
    )
    assert deployer.consequence == (
        "If this holds, the company keeps the deployer role and its duties."
    )
    assert (finding(outcome).role, finding(outcome).also_role) == (Role.PROVIDER, Role.DEPLOYER)
    assert finding(outcome).role_switch_reason is None  # assumed, not a settled switch
    assert [c.provision_id for c in step.citations] == ["art:3:4", "art:25:1:b", "art:3:23"]
    assert "Working assumption: provider, keeping the deployer duties" in step.decision
    assert {"art:9", "art:26:1"} <= set(articles(outcome))


def test_a_contested_modification_with_an_open_switch_still_asks_it() -> None:
    answer = role_answer(substantial_modification=contested(), own_brand=key_fact(Answer.UNKNOWN))
    outcome = to_outcome(answer, state())
    assert outcome.step.status is Status.LEGALLY_AMBIGUOUS
    assert [q.id for q in outcome.follow_up_questions] == ["own_brand"]
    assert "Still to confirm: Do you put your own name" in outcome.step.decision


@pytest.mark.parametrize(("other", "point"), [("own_brand", "a"), ("changed_purpose", "c")])
def test_a_switch_that_applies_settles_a_contested_modification(other: str, point: str) -> None:
    answer = role_answer(substantial_modification=contested()).model_copy(
        update={other: key_fact(Answer.YES, EvidenceTag.STATED)}
    )
    outcome = to_outcome(answer, state())
    assert outcome.step.status is Status.DECIDED
    assert switch_citations(outcome) == [f"art:25:1:{point}"]


def test_a_contested_modification_below_high_risk_changes_nothing() -> None:
    answer = role_answer(
        risk_class=RiskClass.MINIMAL_RISK, route=None, substantial_modification=contested()
    )
    outcome = to_outcome(answer, state(RiskClass.MINIMAL_RISK, None))
    assert (finding(outcome).role, outcome.step.status) == (Role.DEPLOYER, Status.DECIDED)


def test_the_contested_modification_reads_in_german() -> None:
    outcome = to_outcome(
        role_answer(substantial_modification=contested()), state(language=Language.DE)
    )
    question = outcome.step.open_question
    assert question is not None
    assert "Art. 3 Nr. 23" in question.question
    assert question.readings[1].explanation.startswith("Betreiber")
    assert "Arbeitsannahme: Anbieter, mit den Pflichten als Betreiber" in outcome.step.decision


def test_only_the_modification_answer_can_be_contested() -> None:
    schema = node.ROLE_RESPONSE_FORMAT["json_schema"]
    assert isinstance(schema, dict)
    definitions = schema["schema"]["$defs"]
    assert "contested" in definitions["Modification"]["enum"]
    assert "contested" not in definitions["Answer"]["enum"]
    properties = schema["schema"]["properties"]
    assert properties["substantial_modification"]["$ref"].endswith("/ModificationFact")
    assert properties["own_brand"]["$ref"].endswith("/KeyFact")


# --- Art. 2(2): an Annex I Section B product (user, 2026-09-30) ----------------------------------


def section_b_state(status: Status = Status.DECIDED, point: str = "annex:I:B:21") -> EngineState:
    """High-risk on an Annex I point after a high-risk step of `status` (an uncertain one names
    its gap)."""
    is_missing = status is Status.NEEDS_MORE_INFORMATION
    high_risk = StepResult(
        step=StepName.HIGH_RISK,
        decision="High-risk under Art. 6(1).",
        status=status,
        missing_fact=FollowUpQuestion(id="third_party_assessment", text="A notified body?")
        if is_missing
        else None,
        open_question=open_question("Open?", "Yes.", "No.")
        if status is Status.LEGALLY_AMBIGUOUS
        else None,
    )
    built = state(route=HighRiskRoute.ANNEX_I)
    return {**built, "annex_point": point, "steps": (high_risk,)}


def test_a_decided_section_b_product_lists_no_duties_and_cites_art_2_2() -> None:
    answer = role_answer(Role.PROVIDER, legacy=legacy_answer(placed_before=Answer.YES))
    outcome = to_outcome(answer, section_b_state())
    assert finding(outcome).obligations == ()
    cited = [c.provision_id for c in outcome.step.citations]
    assert "art:2:2" in cited
    assert "art:111:2" not in cited  # no duties, so nothing for Art. 111(2) to mark
    assert "No AI Act duties listed" in outcome.step.decision
    assert outcome.follow_up_questions == ()


@pytest.mark.parametrize("status", [Status.NEEDS_MORE_INFORMATION, Status.LEGALLY_AMBIGUOUS])
def test_an_assumed_section_b_product_keeps_its_duties_and_names_art_2_2_as_possible(
    status: Status,
) -> None:
    """Orchestrator's ruling (E8 review round 1): the cut is applied only to a decided
    high-risk step; an assumed one keeps every duty that may apply, the stricter reading."""
    answer = role_answer(Role.PROVIDER, legacy=legacy_answer())
    outcome = to_outcome(answer, section_b_state(status))
    assert {"art:4:1", "art:9"} <= set(articles(outcome))
    assert "If the system is high-risk as a product" in outcome.step.decision
    assert "No AI Act duties listed" not in outcome.step.decision
    assert "art:2:2" in [c.provision_id for c in outcome.step.citations]


def test_a_section_a_product_keeps_its_duties() -> None:
    outcome = to_outcome(
        role_answer(Role.PROVIDER, legacy=legacy_answer()), section_b_state(point="annex:I:A:11")
    )
    assert "art:9" in articles(outcome)
    assert "art:2:2" not in [c.provision_id for c in outcome.step.citations]
    assert "Section B" not in outcome.step.decision


def test_a_decided_section_b_request_asks_no_conditions_or_launch_facts() -> None:
    """The answers would be discarded, so they aren't asked: no conditions, no Art. 111(2)
    section, the plain answer schema."""
    decided, assumed = section_b_state(), section_b_state(Status.NEEDS_MORE_INFORMATION)
    assert node.asked_conditions(decided) == ()
    assert node.answer_model(decided) is RoleAnswer
    human = str(node.role_messages(decided, ())[-1].content)
    assert "Conditions:\n-" in human
    assert "Launch and design" not in human
    assert node.asked_conditions(assumed)
    assert node.answer_model(assumed) is HighRiskRoleAnswer
    assert "Launch and design" in str(node.role_messages(assumed, ())[-1].content)


def test_the_node_reads_a_plain_answer_for_a_decided_section_b_product() -> None:
    """Any other high-risk answer without the Art. 111(2) facts is a broken output."""
    check, _ = _fake_check(role_answer(Role.PROVIDER).model_dump_json())
    outcome = check(section_b_state())
    assert (finding(outcome).role, finding(outcome).obligations) == (Role.PROVIDER, ())


def test_an_unknown_role_asks_for_it() -> None:
    outcome = to_outcome(role_answer(None), state())
    assert outcome.step.missing_fact is not None
    assert outcome.step.missing_fact.id == "operator_role"
    assert (finding(outcome).role, finding(outcome).also_role) == (Role.PROVIDER, Role.DEPLOYER)
    assert {"art:9", "art:26:1"} <= set(articles(outcome))


def test_a_repurposed_gpai_system_reports_its_switch_next_to_the_gpai_rule() -> None:
    """own-d-03's recorded answer: GPAI "yes" and (c) "yes". The switch that applies is reported
    with its citation (user, 2026-10-06: every switch), and the model provider is still flagged."""
    answer = role_answer(
        builds_on_gpai=key_fact(Answer.YES, EvidenceTag.INFERRED),
        changed_purpose=key_fact(Answer.YES, EvidenceTag.STATED),
    )
    outcome = to_outcome(answer, state())
    assert (finding(outcome).role, finding(outcome).also_role) == (Role.PROVIDER, Role.DEPLOYER)
    assert "Art. 25(1)(c)" in (finding(outcome).role_switch_reason or "")
    assert switch_citations(outcome) == ["art:25:1:c"]
    assert {"art:3:3", "art:3:68"} <= {c.provision_id for c in outcome.step.citations}
    assert "art:53:1:b" in articles(outcome)
    assert outcome.step.status is Status.DECIDED


@pytest.mark.parametrize("risk_class", [RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK])
def test_a_gpai_system_below_high_risk_reports_no_switch(risk_class: RiskClass) -> None:
    answer = role_answer(
        risk_class=risk_class,
        route=None,
        builds_on_gpai=key_fact(Answer.YES, EvidenceTag.STATED),
        changed_purpose=key_fact(Answer.YES, EvidenceTag.STATED),
    )
    duties = ("art:50:1",) if risk_class is RiskClass.LIMITED_RISK else ()
    outcome = to_outcome(answer, state(risk_class, None, transparency_duties=duties))
    assert finding(outcome).role_switch_reason is None
    assert switch_citations(outcome) == []


@pytest.mark.parametrize("base", [Role.DEPLOYER, Role.PROVIDER])
def test_a_system_built_on_gpai_is_its_builders_and_flags_the_model_provider(base: Role) -> None:
    answer = role_answer(base, builds_on_gpai=key_fact(Answer.YES, EvidenceTag.STATED))
    outcome = to_outcome(answer, state())
    assert finding(outcome).role is Role.PROVIDER
    assert finding(outcome).role_switch_reason is None  # not an Art. 25 switch
    assert finding(outcome).also_role is (Role.DEPLOYER if base is Role.DEPLOYER else None)
    flag = next(o for o in finding(outcome).obligations if o.article == "art:53:1:b")
    assert flag.is_informational
    assert "Art. 53" in outcome.step.decision
    cited = [c.provision_id for c in outcome.step.citations]
    assert {"art:3:3", "art:3:68"} <= set(cited)
    assert "art:53:1:b" not in cited  # a duty of the model provider, not this role's basis


def test_a_provider_that_does_not_build_on_gpai_gets_no_flag() -> None:
    outcome = to_outcome(role_answer(Role.PROVIDER), state())
    assert finding(outcome).role is Role.PROVIDER
    assert "art:53:1:b" not in articles(outcome)
    assert "art:9" in articles(outcome)


def test_an_unknown_gpai_base_needs_information() -> None:
    answer = role_answer(Role.DEPLOYER, builds_on_gpai=key_fact(Answer.UNKNOWN))
    outcome = to_outcome(answer, state(RiskClass.MINIMAL_RISK, None))
    assert outcome.step.missing_fact is not None
    assert outcome.step.missing_fact.id == "builds_on_gpai"


def test_gpai_with_an_unknown_role_asks_whether_it_also_deploys() -> None:
    answer = role_answer(None, builds_on_gpai=key_fact(Answer.YES, EvidenceTag.STATED))
    outcome = to_outcome(answer, state())
    assert outcome.step.status is Status.NEEDS_MORE_INFORMATION
    assert outcome.step.missing_fact is not None
    assert outcome.step.missing_fact.id == "operator_role"
    assert [q.id for q in outcome.follow_up_questions] == ["operator_role"]
    assert (finding(outcome).role, finding(outcome).also_role) == (Role.PROVIDER, Role.DEPLOYER)
    assert "Working assumption: also deployer, pending an answer to:" in outcome.step.decision
    assert "Working assumption: provider" not in outcome.step.decision  # the GPAI rule settled it
    german = to_outcome(answer, state(language=Language.DE)).step.decision
    assert "Arbeitsannahme: zugleich Betreiber" in german


def test_an_unknown_gpai_base_keeps_the_flag_and_asks_a_provider() -> None:
    answer = role_answer(Role.PROVIDER, builds_on_gpai=key_fact(Answer.UNKNOWN))
    outcome = to_outcome(answer, state())
    assert outcome.step.status is Status.DECIDED  # a provider either way
    assert "art:53:1:b" in articles(outcome)  # kept, with its condition shown
    assert [q.id for q in outcome.follow_up_questions] == ["builds_on_gpai"]


@pytest.mark.parametrize(
    ("role", "prefix", "count"), [(Role.IMPORTER, "art:23:", 7), (Role.DISTRIBUTOR, "art:24:", 6)]
)
def test_importer_and_distributor_get_their_own_duties(role: Role, prefix: str, count: int) -> None:
    outcome = to_outcome(role_answer(role), state(route=HighRiskRoute.ANNEX_I))
    assert finding(outcome).role is role
    assert articles(outcome) == [f"{prefix}{n}" for n in range(1, count + 1)]


def test_german_decision_and_question_texts() -> None:
    answer = role_answer(own_brand=key_fact(Answer.UNKNOWN))
    outcome = to_outcome(answer, state(language=Language.DE))
    assert outcome.step.decision.startswith("Rolle: Anbieter, zugleich Betreiber.")
    assert outcome.step.missing_fact is not None
    assert "Marke" in outcome.step.missing_fact.text


# --- Conditional duties (applies_if) ------------------------------------------------------------


def test_conditions_filter_the_duties_yes_keeps_no_drops_unknown_keeps() -> None:
    conditions = {EMPLOYER: Answer.YES, PUBLIC_AUTHORITY: Answer.NO}
    outcome = to_outcome(role_answer(conditions=conditions), state())
    kept = articles(outcome)
    assert "art:26:7" in kept  # employer: yes
    assert "art:26:8" not in kept  # public authority: no
    assert "art:26:9" in kept  # DPIA: not answered, kept with its condition
    assert "left out because their condition doesn't apply" in outcome.step.decision


@pytest.mark.parametrize("role", [Role.PROVIDER, Role.DEPLOYER])
def test_art_49_4_non_public_registration_follows_the_law_enforcement_condition(
    role: Role,
) -> None:
    # Hand-checked against Art. 49(4): Annex III points 1, 6 and 7 in law enforcement, migration,
    # asylum and border control register in the secure non-public section of the EU database.
    police = to_outcome(role_answer(role, {LAW_ENFORCEMENT: Answer.YES}), state())
    registration = next(o for o in finding(police).obligations if o.article == "art:49:4")
    assert registration.applies_from == date(2027, 12, 2)
    assert "non-public" in registration.duty
    retailer = to_outcome(role_answer(role, {LAW_ENFORCEMENT: Answer.NO}), state())
    assert "art:49:4" not in articles(retailer)


def test_art_50_rows_follow_the_transparency_findings_not_the_model() -> None:
    answer = role_answer(Role.PROVIDER)
    with_chatbot = to_outcome(answer, state(transparency_duties=("art:50:1",)))
    assert "art:50:1" in articles(with_chatbot)
    assert "art:50:2" not in articles(with_chatbot)
    without = to_outcome(answer, state())
    assert not any(a.startswith("art:50:") for a in articles(without))


def test_conditions_asked_leave_out_those_settled_by_other_findings() -> None:
    asked = conditions_to_ask(RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III, LawVersion.AMENDED)
    assert EMPLOYER in asked
    assert LAW_ENFORCEMENT in asked
    assert len(asked) == len(set(asked))
    assert not any("general-purpose AI model" in c for c in asked)
    assert not any("interact directly" in c for c in asked)


def test_an_ambiguous_art_5_match_keeps_every_prohibition_without_asking() -> None:
    assert conditions_to_ask(RiskClass.PROHIBITED, None, LawVersion.AMENDED) == ()
    answer = role_answer(risk_class=RiskClass.PROHIBITED, route=None)
    outcome = to_outcome(answer, state(RiskClass.PROHIBITED, None))
    assert articles(outcome) == ["art:5:1", "art:5:1:ba", "art:5:1:bb"]


@pytest.mark.parametrize("risk_class", [RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK])
def test_art_6_4_follows_the_high_risk_steps_exemption(risk_class: RiskClass) -> None:
    assert not any(
        "Art. 6(3)" in c for c in conditions_to_ask(risk_class, None, LawVersion.AMENDED)
    )
    answer = role_answer(Role.PROVIDER, risk_class=risk_class, route=None)
    duties = ("art:50:1",) if risk_class is RiskClass.LIMITED_RISK else ()
    exempt = to_outcome(
        answer, state(risk_class, None, transparency_duties=duties, annex_iii_exempt=True)
    )
    assert "art:6:4" in articles(exempt)
    plain = to_outcome(answer, state(risk_class, None, transparency_duties=duties))
    assert "art:6:4" not in articles(plain)


@pytest.mark.parametrize(
    ("language", "says"),
    [
        (
            Language.EN,
            "Duties not modelled for the original text: the obligations table "
            "covers only the amended text",
        ),
        (
            Language.DE,
            "Pflichten für die ursprüngliche Fassung nicht modelliert: Die "
            "Pflichtentabelle deckt nur die geänderte Fassung ab",
        ),
    ],
)
def test_the_original_text_lists_no_duties_and_says_they_are_not_modelled(
    language: Language, says: str
) -> None:
    """E11's DoD: decision 020 keeps the duties to the amended text; under the original one the
    obligations result is an explicit "not modelled", never an error."""
    outcome = to_outcome(role_answer(), state(language=language, law_version=LawVersion.ORIGINAL))
    assert finding(outcome).obligations == ()
    assert says in outcome.step.decision
    assert finding(outcome).role is Role.DEPLOYER


def test_the_original_text_asks_neither_the_conditions_nor_the_art_111_2_facts() -> None:
    original = state(law_version=LawVersion.ORIGINAL)
    assert node.answer_model(original) is RoleAnswer
    assert node.asked_conditions(original) == ()
    human = str(node.role_messages(original, ())[-1].content)
    assert "Launch and design" not in human
    assert "Conditions:\n-\n" in human


# --- Citations ----------------------------------------------------------------------------------

EVERY_BRANCH = [
    pytest.param(role_answer(), state(), id="deployer"),
    pytest.param(role_answer(None), state(), id="unknown-role"),
    pytest.param(role_answer(Role.IMPORTER), state(), id="importer"),
    pytest.param(role_answer(Role.DISTRIBUTOR), state(), id="distributor"),
    pytest.param(role_answer(Role.PROVIDER), state(), id="provider"),
    pytest.param(role_answer(builds_on_gpai=key_fact(Answer.YES)), state(), id="gpai"),
    pytest.param(
        role_answer(own_brand=key_fact(Answer.UNKNOWN)), state(language=Language.DE), id="de"
    ),
    pytest.param(
        role_answer(risk_class=RiskClass.PROHIBITED, route=None),
        state(RiskClass.PROHIBITED, None, law_version=LawVersion.ORIGINAL),
        id="original",
    ),
]


@pytest.mark.parametrize(("answer", "given"), EVERY_BRANCH)
def test_every_outcome_cites_the_provisions_its_role_rests_on(
    answer: RoleAnswer, given: EngineState
) -> None:
    step = to_outcome(answer, given).step
    cited = step.citations
    assert cited
    assert not whole_articles(step)  # paragraphs and points only (E16)
    for citation in cited:
        assert citation.language is given["language"]
        assert citation.law_version is given["law_version"]
        assert citation.quote


@pytest.mark.parametrize(
    ("switch", "article"),
    [
        ("own_brand", "art:25:1:a"),
        ("substantial_modification", "art:25:1:b"),
        ("changed_purpose", "art:25:1:c"),
    ],
)
def test_a_switch_cites_its_point_of_art_25_and_the_base_role(switch: str, article: str) -> None:
    answer = role_answer().model_copy(update={switch: key_fact(Answer.YES)})
    cited = to_outcome(answer, state()).step.citations
    assert [(c.provision_id, c.document_id) for c in cited] == [
        ("art:3:4", "ai-act-consolidated"),
        (article, "ai-act-consolidated"),
    ]
    assert "deployer" in cited[0].quote


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        pytest.param(role_answer(), ["art:3:4"], id="no-match"),
        pytest.param(
            role_answer(own_brand=key_fact(Answer.YES, EvidenceTag.STATED)),
            ["art:3:4", "art:25:1:a"],
            id="match",
        ),
    ],
)
def test_the_step_cites_the_points_it_checked_not_art_3_or_art_25(
    answer: RoleAnswer, expected: list[str]
) -> None:
    """E16, both ways: a deployer that keeps its role cites its definition, Art. 3(4); one that
    switches under Art. 25(1) cites the point too, never Art. 3 or Art. 25 as a whole."""
    cited = to_outcome(answer, state()).step.citations
    assert [c.provision_id for c in cited] == expected


@pytest.mark.parametrize(
    ("role", "article"),
    [
        (Role.PROVIDER, "art:3:3"),
        (Role.DEPLOYER, "art:3:4"),
        (Role.IMPORTER, "art:3:6"),
        (Role.DISTRIBUTOR, "art:3:7"),
    ],
)
def test_the_base_role_cites_its_definition(role: Role, article: str) -> None:
    cited = to_outcome(role_answer(role), state()).step.citations
    assert [c.provision_id for c in cited] == [article]


@pytest.mark.parametrize("base", [Role.DEPLOYER, Role.IMPORTER, Role.DISTRIBUTOR])
def test_the_gpai_rule_cites_the_provider_and_downstream_provider_definitions(base: Role) -> None:
    answer = role_answer(base, builds_on_gpai=key_fact(Answer.YES, EvidenceTag.STATED))
    outcome = to_outcome(answer, state())
    cited = [c.provision_id for c in outcome.step.citations]
    own = {Role.DEPLOYER: "art:3:4", Role.IMPORTER: "art:3:6", Role.DISTRIBUTOR: "art:3:7"}[base]
    assert cited == [own, "art:3:3", "art:3:68"]
    assert "art:53:1:b" in articles(outcome)  # the flag row keeps its own provision


def test_an_unknown_role_cites_both_definitions_it_assumes() -> None:
    cited = to_outcome(role_answer(None), state()).step.citations
    assert [c.provision_id for c in cited] == ["art:3:3", "art:3:4"]


def test_the_node_quotes_from_its_own_settings_data_dir(tmp_path: Path) -> None:
    content = role_answer(legacy=legacy_answer()).model_dump_json()
    chat = GenericFakeChatModel(messages=iter([AIMessage(content=content)]))
    settings = _settings().model_copy(update={"aiact_data_dir": tmp_path})
    with pytest.raises(ProvisionTextError, match="cannot read"):
        RoleObligationsCheck(settings, chat=chat)(state())


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        ("not json\n", "not valid JSON"),
        ('{"provision_id": "art:3:4"}\n', "lacks provision_id or text"),
        ('{"provision_id": "art:3:3", "text": "Provider."}\n', "has no art:3:4"),
    ],
)
def test_a_broken_parsed_text_raises_a_provision_error(
    tmp_path: Path, content: str, problem: str
) -> None:
    parsed = tmp_path / "parsed"
    parsed.mkdir()
    (parsed / "ai-act-consolidated.en.jsonl").write_text(content, encoding="utf-8")
    with pytest.raises(ProvisionTextError, match=problem):
        citations(["art:3:4"], LawVersion.AMENDED, Language.EN, tmp_path)


def test_a_parsed_text_that_is_not_utf8_raises_a_provision_error(tmp_path: Path) -> None:
    parsed = tmp_path / "parsed"
    parsed.mkdir()
    (parsed / "ai-act-consolidated.en.jsonl").write_bytes(b"\xff\xfe not utf-8\n")
    with pytest.raises(ProvisionTextError, match="not valid UTF-8"):
        citations(["art:3:4"], LawVersion.AMENDED, Language.EN, tmp_path)


def _with_steps(given: EngineState, *names: StepName) -> EngineState:
    ran = tuple(StepResult(step=name, decision=f"{name.value} ran") for name in names)
    return {**given, "steps": ran}


def test_rows_the_earlier_checks_left_out_count_as_conditions_not_met() -> None:
    # Transparency reported only Art. 50(1) and the high-risk step no Art. 6(3) exemption, so
    # Art. 50(2) and Art. 6(4) don't apply: nothing about the input is missing.
    answer = role_answer(
        Role.PROVIDER,
        risk_class=RiskClass.LIMITED_RISK,
        route=None,
        builds_on_gpai=key_fact(Answer.UNKNOWN),  # keeps the GPAI flag out of the count
    )
    given = state(RiskClass.LIMITED_RISK, None, transparency_duties=("art:50:1",))
    ran = _with_steps(given, StepName.HIGH_RISK, StepName.TRANSPARENCY)
    decision = to_outcome(answer, ran).step.decision
    assert "2 conditional duties left out because their condition doesn't apply" in decision
    assert "no earlier check reported" not in decision


def test_rows_whose_settling_check_is_absent_say_so() -> None:
    answer = role_answer(
        Role.PROVIDER,
        risk_class=RiskClass.MINIMAL_RISK,
        route=None,
        builds_on_gpai=key_fact(Answer.UNKNOWN),  # keeps the GPAI flag, so only Art. 6(4) drops
    )
    partial = to_outcome(answer, state(RiskClass.MINIMAL_RISK, None)).step.decision
    assert "1 duties left out because no earlier check reported the finding" in partial
    assert "condition doesn't apply" not in partial


# --- Facts used ---------------------------------------------------------------------------------


def test_facts_used_cite_the_extracted_facts_or_carry_the_answers_own_tag() -> None:
    bought = Fact(
        text="Bought from a vendor",
        evidence=EvidenceTag.STATED,
        source_span=SourceSpan(start=0, end=10),
    )
    stated_role = RoleFact(
        role=Role.DEPLOYER, evidence=EvidenceTag.STATED, fact="Uses it", fact_numbers=(1, 9)
    )
    answer = role_answer(role=None).model_copy(update={"role": stated_role})
    outcome = to_outcome(answer, state(facts=(bought,)))
    used = outcome.step.facts_used
    assert used[0] == bought  # cited, out-of-range numbers ignored
    assert {f.evidence for f in used[1:]} == {EvidenceTag.ASSUMED}  # the assumed "no"s


def test_an_uncited_stated_answer_becomes_inferred() -> None:
    answer = role_answer(own_brand=key_fact(Answer.NO, EvidenceTag.STATED))
    used = to_outcome(answer, state()).step.facts_used
    assert all(f.evidence is not EvidenceTag.STATED for f in used)


# --- The findings in the state and the graph ----------------------------------------------------


def test_findings_are_only_accepted_from_their_own_check() -> None:
    step = StepResult(step=StepName.TRANSPARENCY, decision="No Art. 50 duty")
    with pytest.raises(ValidationError, match="only the role_obligations check sets role"):
        CheckOutcome(step=step, role=RoleFinding(role=Role.DEPLOYER))
    with pytest.raises(ValidationError, match="only the high_risk check sets high_risk_route"):
        CheckOutcome(step=step, high_risk_route=HighRiskRoute.ANNEX_III)
    role_step = StepResult(step=StepName.ROLE_OBLIGATIONS, decision="Role: deployer.")
    with pytest.raises(ValidationError, match="only the transparency check"):
        CheckOutcome(step=role_step, transparency_duties=("art:50:1",))
    high_risk = StepResult(step=StepName.HIGH_RISK, decision="Exempt under Art. 6(3)")
    with pytest.raises(ValidationError, match="not high-risk"):
        CheckOutcome(step=high_risk, high_risk_route=HighRiskRoute.ANNEX_III, annex_iii_exempt=True)
    # E5's open minor (E8): an Annex point needs the route it rests on.
    with pytest.raises(ValidationError, match="annex_point is set only with"):
        CheckOutcome(step=high_risk, annex_iii_exempt=True, annex_point="annex:III:4:a")


def _settings() -> Settings:
    values = {"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **REFUSAL_ROUTE, **values)  # pyright: ignore[reportCallIssue]


def _fake_check(content: str) -> tuple[RoleObligationsCheck, GenericFakeChatModel]:
    chat = GenericFakeChatModel(messages=iter([AIMessage(content=content)]))
    return RoleObligationsCheck(_settings(), chat=chat), chat


def test_the_node_reads_the_earlier_findings_through_the_graph() -> None:
    answer = role_answer(conditions={EMPLOYER: Answer.YES}, legacy=legacy_answer())
    check, _ = _fake_check(answer.model_dump_json())
    high_risk = CheckOutcome(
        step=StepResult(step=StepName.HIGH_RISK, decision="Annex III point 4(a)"),
        high_risk_route=HighRiskRoute.ANNEX_III,
    )
    scripted = scripted_nodes(Script(checks={StepName.HIGH_RISK: high_risk}))
    checks = {**scripted.checks, StepName.ROLE_OBLIGATIONS: check}
    graph = build_graph(
        EngineNodes(facts=scripted.facts, checks=checks, finalize=scripted.finalize)
    )
    final = graph.invoke(
        {
            "description": CV_TOOL,
            "language": Language.EN,
            "law_version": LawVersion.AMENDED,
            "as_of": date(2026, 9, 29),
            "exclude_source_example_ids": (),
        }
    )
    assert final["high_risk_route"] is HighRiskRoute.ANNEX_III
    assert final["role"].role is Role.DEPLOYER
    assert "art:26:7" in [o.article for o in final["role"].obligations]
    assert final["steps"][-1].step is StepName.ROLE_OBLIGATIONS


# --- Art. 111(2): high-risk systems already on the market (C7b) ------------------------------
# Hand-checked against Art. 111(2): a system on the market or in use before its route's Chapter
# III date is covered only after a significant change to its design or intended purpose from that
# date (a substantial modification, Art. 3(23), per recital 177); for public authorities,
# providers and deployers comply by 2 Aug 2030. The class stays high-risk either way.

LEGACY_ARTICLE = "art:111:2"
SUBSTANTIAL_MODIFICATION = "art:3:23"
PER_PRODUCT = {
    Language.EN: "This covers copies placed on the market or put into service before "
    "2 December 2027; copies supplied on or after that date may be fully covered.",
    Language.DE: "Dies gilt für Exemplare, die vor dem 2. Dezember 2027 in Verkehr gebracht oder "
    "in Betrieb genommen wurden; ab diesem Datum bereitgestellte Exemplare können vollständig "
    "erfasst sein.",
}
PUBLIC_AUTHORITY_ASSUMED = {
    Language.EN: "Art. 111(2): the system was on the market or in use before 2 December 2027; "
    "until it is confirmed whether public authorities are meant to use it, the earlier date is "
    "assumed, so {count} high-risk duties apply from 2 August 2030; the class stays high-risk.",
    Language.DE: "Art. 111 Abs. 2: Das System war vor dem 2. Dezember 2027 in Verkehr oder in "
    "Betrieb; solange nicht geklärt ist, ob Behörden es verwenden sollen, wird das frühere Datum "
    "angenommen; daher gelten {count} Hochrisiko-Pflichten ab dem 2. August 2030. Das System "
    "bleibt als Hochrisiko-System eingestuft.",
}
DEPLOYER_DUTIES = ("art:26:1", "art:26:2", "art:26:6")


def legacy_outcome(
    legacy: LegacyAnswer,
    role: Role = Role.DEPLOYER,
    route: HighRiskRoute = HighRiskRoute.ANNEX_III,
    language: Language = Language.EN,
) -> CheckOutcome:
    answer = role_answer(role, route=route, legacy=legacy)
    return to_outcome(answer, state(route=route, language=language))


def by_article(outcome: CheckOutcome) -> dict[str, Obligation]:
    return {o.article: o for o in finding(outcome).obligations}


def cited(outcome: CheckOutcome) -> list[str]:
    return [c.provision_id for c in outcome.step.citations]


def test_a_legacy_system_without_a_design_change_marks_its_duties() -> None:
    outcome = legacy_outcome(legacy_answer(placed_before=Answer.YES))
    duties = by_article(outcome)
    for article in DEPLOYER_DUTIES:
        assert duties[article].legacy is LegacyStatus.UNCHANGED
        assert duties[article].applies_from == date(2027, 12, 2)
    assert duties["art:4:1"].legacy is None  # AI literacy has its own date
    marked = sum(o.legacy is LegacyStatus.UNCHANGED for o in finding(outcome).obligations)
    assert outcome.step.decision.endswith(
        "Art. 111(2): the system was on the market or in use before 2 December 2027, so "
        f"{marked} high-risk duties apply only if its design "
        "or intended purpose changes significantly on or after that date (a substantial "
        "modification); the class stays high-risk."
    )
    assert "hasn't changed significantly since" not in outcome.step.decision
    assert PER_PRODUCT[Language.EN] not in outcome.step.decision  # a deployer uses its copy
    assert cited(outcome)[-2:] == [LEGACY_ARTICLE, SUBSTANTIAL_MODIFICATION]
    assert outcome.step.status is Status.DECIDED
    assert outcome.follow_up_questions == ()


def test_a_legacy_system_whose_design_changes_keeps_its_duties() -> None:
    outcome = legacy_outcome(legacy_answer(placed_before=Answer.YES, changed=Answer.YES))
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert set(DEPLOYER_DUTIES) <= set(articles(outcome))
    assert "Art. 111(2)" not in outcome.step.decision
    assert LEGACY_ARTICLE not in cited(outcome)


@pytest.mark.parametrize(
    ("route", "since"),
    [(HighRiskRoute.ANNEX_III, "2 December 2027"), (HighRiskRoute.ANNEX_I, "2 August 2028")],
)
def test_a_legacy_public_authority_system_applies_from_2_aug_2030(
    route: HighRiskRoute, since: str
) -> None:
    legacy = legacy_answer(placed_before=Answer.YES, public_authority=Answer.YES)
    outcome = legacy_outcome(legacy, Role.PROVIDER, route)
    art_9 = by_article(outcome)["art:9"]
    assert (art_9.applies_from, art_9.legacy) == (
        date(2030, 8, 2),
        LegacyStatus.PUBLIC_AUTHORITY,
    )
    assert f"before {since}" in outcome.step.decision
    assert "apply from 2 August 2030" in outcome.step.decision
    assert LEGACY_ARTICLE in cited(outcome)


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize("public_authority", [Answer.NO, Answer.YES])
@pytest.mark.parametrize("role", [Role.PROVIDER, Role.IMPORTER, Role.DISTRIBUTOR])
def test_a_supplier_of_a_legacy_system_gets_the_per_product_caveat(
    role: Role, public_authority: Answer, language: Language
) -> None:
    legacy = legacy_answer(Answer.YES, public_authority=public_authority)
    outcome = legacy_outcome(legacy, role, language=language)
    assert {o.legacy for o in finding(outcome).obligations} - {None}
    assert outcome.step.decision.endswith(PER_PRODUCT[language])


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize("unsettled", [Answer.UNKNOWN, "assumed yes", "assumed no"])
def test_an_unsettled_public_authority_answer_words_the_2030_date_as_an_assumption(
    unsettled: Answer | str, language: Language
) -> None:
    given = {
        Answer.UNKNOWN: key_fact(Answer.UNKNOWN),
        "assumed yes": key_fact(Answer.YES),
        "assumed no": key_fact(Answer.NO),
    }[unsettled]
    legacy = legacy_answer(Answer.YES).model_copy(update={"for_public_authority": given})
    outcome = legacy_outcome(legacy, language=language)
    count = sum(o.legacy is LegacyStatus.PUBLIC_AUTHORITY for o in finding(outcome).obligations)
    assert count
    assert outcome.step.decision.endswith(PUBLIC_AUTHORITY_ASSUMED[language].format(count=count))
    assert "is meant for public authorities" not in outcome.step.decision
    assert [q.id for q in outcome.follow_up_questions] == ["for_public_authority"]


@pytest.mark.parametrize("language", list(Language))
def test_a_settled_public_authority_answer_states_it(language: Language) -> None:
    outcome = legacy_outcome(
        legacy_answer(Answer.YES, public_authority=Answer.YES), language=language
    )
    expected = {
        Language.EN: "and is meant for public authorities, so",
        Language.DE: "und soll bestimmungsgemäß von Behörden verwendet werden; daher",
    }[language]
    assert expected in outcome.step.decision
    assert "angenommen" not in outcome.step.decision
    assert "is assumed" not in outcome.step.decision


@pytest.mark.parametrize("role", [Role.IMPORTER, Role.DISTRIBUTOR])
def test_a_supplier_of_a_legacy_public_authority_system_keeps_the_ordinary_marking(
    role: Role,
) -> None:
    legacy = legacy_answer(Answer.YES, public_authority=Answer.YES)
    outcome = legacy_outcome(legacy, role)
    marks = {o.legacy for o in finding(outcome).obligations} - {None}
    assert marks == {LegacyStatus.UNCHANGED}
    assert "2 August 2030" not in outcome.step.decision
    assert outcome.step.decision.endswith(PER_PRODUCT[Language.EN])


def test_no_caveat_without_a_marking_or_for_a_deployer() -> None:
    changed = legacy_outcome(legacy_answer(Answer.YES, Answer.YES), Role.PROVIDER)
    assert PER_PRODUCT[Language.EN] not in changed.step.decision
    deployer = legacy_outcome(legacy_answer(Answer.YES, public_authority=Answer.YES))
    assert PER_PRODUCT[Language.EN] not in deployer.step.decision


def test_the_check_again_sentence_cites_only_the_article() -> None:
    planned = legacy_outcome(legacy_answer(Answer.NO), Role.PROVIDER)
    assert LEGACY_ARTICLE in cited(planned)
    assert SUBSTANTIAL_MODIFICATION not in cited(planned)
    assert PER_PRODUCT[Language.EN] not in planned.step.decision


@pytest.mark.parametrize("language", list(Language))
def test_the_design_change_question_asks_about_changes_from_the_date(language: Language) -> None:
    outcome = legacy_outcome(legacy_answer(Answer.YES, Answer.UNKNOWN), language=language)
    [question] = outcome.follow_up_questions
    expected = {
        Language.EN: "Is a significant change to the system's design or intended purpose "
        "planned or foreseen for on or after 2 December 2027?",
        Language.DE: "Ist ab dem 2. Dezember 2027 eine erhebliche Veränderung der Konzeption "
        "oder der Zweckbestimmung des Systems geplant oder vorgesehen?",
    }
    assert question.text == expected[language]


CHECK_AT_LAUNCH = {
    Language.EN: "If the system is placed on the market or put into service before "
    "2 December 2027 and its design or intended purpose doesn't change significantly "
    "afterwards, Art. 111(2) may limit these duties; check again at launch.",
    Language.DE: "Wird das System vor dem 2. Dezember 2027 in Verkehr gebracht oder in Betrieb "
    "genommen und danach in seiner Konzeption oder Zweckbestimmung nicht erheblich verändert, "
    "kann Art. 111 Abs. 2 diese Pflichten einschränken; prüfen Sie dies beim Inverkehrbringen "
    "oder bei der Inbetriebnahme erneut.",
}


@pytest.mark.parametrize("language", list(Language))
def test_a_planned_launch_keeps_the_full_duties_and_says_to_check_again(
    language: Language,
) -> None:
    # User decision 2026-10-01 (decision 022 addendum): "placed before" is read as of today, so
    # a launch that is only planned, even before the date, is "no" and lists the full duties.
    planned = legacy_outcome(legacy_answer(placed_before=Answer.NO), language=language)
    no_legacy_facts = to_outcome(role_answer(), state(language=language))
    assert finding(planned).obligations == finding(no_legacy_facts).obligations
    assert {o.legacy for o in finding(planned).obligations} == {None}
    assert planned.step.decision == f"{no_legacy_facts.step.decision} {CHECK_AT_LAUNCH[language]}"
    assert LEGACY_ARTICLE in cited(planned)
    assert planned.follow_up_questions == ()


def test_a_system_in_use_today_counts_as_placed_before_and_gets_no_check_again() -> None:
    in_use = legacy_outcome(legacy_answer(placed_before=Answer.YES))
    assert by_article(in_use)["art:26:1"].legacy is LegacyStatus.UNCHANGED
    assert "check again at launch" not in in_use.step.decision


def test_an_unknown_launch_date_keeps_the_duties_and_asks_with_the_routes_date() -> None:
    outcome = legacy_outcome(
        legacy_answer(placed_before=Answer.UNKNOWN), route=HighRiskRoute.ANNEX_I
    )
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    [question] = outcome.follow_up_questions
    assert question.id == "placed_before_chapter_iii"
    assert question.about == LEGACY_ARTICLE
    assert question.text.startswith("Is the system already on the market or in use today?")
    assert "apply from 2 August 2028" in question.text
    assert outcome.step.status is Status.DECIDED  # the role is settled; only dates are open


def test_an_unknown_design_change_keeps_the_duties_and_asks() -> None:
    legacy = legacy_answer(placed_before=Answer.YES, changed=Answer.UNKNOWN)
    outcome = legacy_outcome(legacy)
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert [q.id for q in outcome.follow_up_questions] == ["significant_design_change"]


def test_an_unknown_public_authority_answer_takes_the_earlier_2030_date_and_asks() -> None:
    legacy = legacy_answer(placed_before=Answer.YES, public_authority=Answer.UNKNOWN)
    outcome = legacy_outcome(legacy)
    assert by_article(outcome)["art:26:1"].legacy is LegacyStatus.PUBLIC_AUTHORITY
    assert [q.id for q in outcome.follow_up_questions] == ["for_public_authority"]


def test_a_system_in_use_with_a_silent_description_keeps_its_duties_and_asks_both() -> None:
    # The prompt has the model answer "unknown" for the design change and public use when the
    # description is silent about them: nothing is marked, and both are asked.
    legacy = legacy_answer(Answer.YES, Answer.UNKNOWN, Answer.UNKNOWN)
    outcome = legacy_outcome(legacy)
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert [q.id for q in outcome.follow_up_questions] == [
        "significant_design_change",
        "for_public_authority",
    ]
    assert LEGACY_ARTICLE not in cited(outcome)


def test_an_all_unknown_launch_keeps_the_duties_and_asks_all_three() -> None:
    outcome = legacy_outcome(legacy_answer(Answer.UNKNOWN, Answer.UNKNOWN, Answer.UNKNOWN))
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert len(outcome.follow_up_questions) == 3


def test_a_design_change_settles_it_without_asking_about_public_use() -> None:
    outcome = legacy_outcome(legacy_answer(Answer.YES, Answer.YES, Answer.UNKNOWN))
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert outcome.follow_up_questions == ()


def test_a_law_version_without_duties_drops_the_legacy_facts() -> None:
    answer = role_answer(legacy=legacy_answer(Answer.UNKNOWN, Answer.UNKNOWN, Answer.UNKNOWN))
    outcome = to_outcome(answer, state(law_version=LawVersion.ORIGINAL))
    assert finding(outcome).obligations == ()
    assert LEGACY_ARTICLE not in cited(outcome)
    assert outcome.follow_up_questions == ()
    assert "Art. 111(2)" not in outcome.step.decision


def test_assumed_answers_never_mark_duties_and_are_asked() -> None:
    # The base prompt primes "no (assumed)" for silent switches: under Art. 111(2) an assumed
    # "no" design change or public use settles nothing.
    legacy = legacy_answer(Answer.YES).model_copy(
        update={
            "significant_design_change": key_fact(Answer.NO),
            "for_public_authority": key_fact(Answer.NO),
        }
    )
    outcome = legacy_outcome(legacy)
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert [q.id for q in outcome.follow_up_questions] == [
        "significant_design_change",
        "for_public_authority",
    ]
    assert "Art. 111(2)" not in outcome.step.decision


def test_an_assumed_launch_before_the_date_is_asked() -> None:
    legacy = legacy_answer(changed=Answer.NO).model_copy(
        update={"placed_before": key_fact(Answer.YES)}
    )
    outcome = legacy_outcome(legacy)
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert [q.id for q in outcome.follow_up_questions] == ["placed_before_chapter_iii"]


def test_an_assumed_no_launch_keeps_the_full_duties_and_the_check_again_sentence() -> None:
    legacy = legacy_answer().model_copy(update={"placed_before": key_fact(Answer.NO)})
    outcome = legacy_outcome(legacy)
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert outcome.step.decision.endswith(CHECK_AT_LAUNCH[Language.EN])
    assert outcome.follow_up_questions == ()


def test_a_design_change_skips_the_launch_question() -> None:
    outcome = legacy_outcome(legacy_answer(Answer.UNKNOWN, Answer.YES, Answer.UNKNOWN))
    assert {o.legacy for o in finding(outcome).obligations} == {None}
    assert outcome.follow_up_questions == ()


EVIDENCE_ANSWERS = [(answer, evidence) for answer in Answer for evidence in EvidenceTag]


@pytest.mark.parametrize("placed", EVIDENCE_ANSWERS)
@pytest.mark.parametrize("changed", EVIDENCE_ANSWERS)
@pytest.mark.parametrize("public", EVIDENCE_ANSWERS)
def test_only_settled_facts_can_mark_duties(
    placed: tuple[Answer, EvidenceTag],
    changed: tuple[Answer, EvidenceTag],
    public: tuple[Answer, EvidenceTag],
) -> None:
    legacy = LegacyAnswer(
        placed_before=key_fact(*placed),
        significant_design_change=key_fact(*changed),
        for_public_authority=key_fact(*public),
    )
    marks = {o.legacy for o in finding(legacy_outcome(legacy)).obligations} - {None}
    if not marks:
        return
    assert placed[0] is Answer.YES and placed[1] is not EvidenceTag.ASSUMED
    assert changed[0] is Answer.NO and changed[1] is not EvidenceTag.ASSUMED
    if marks == {LegacyStatus.UNCHANGED}:
        assert public[0] is Answer.NO and public[1] is not EvidenceTag.ASSUMED


def test_the_legacy_facts_are_shown_as_facts_used() -> None:
    outcome = legacy_outcome(legacy_answer(placed_before=Answer.YES))
    shown = [(f.text, f.evidence) for f in outcome.step.facts_used]
    assert ("Answer yes", EvidenceTag.INFERRED) in shown  # placed before: stated, no fact cited


def test_the_legacy_texts_read_in_german() -> None:
    legacy = legacy_answer(placed_before=Answer.YES, public_authority=Answer.YES)
    outcome = legacy_outcome(legacy, language=Language.DE)
    assert "Art. 111 Abs. 2" in outcome.step.decision
    assert "vor dem 2. Dezember 2027" in outcome.step.decision
    unchanged = legacy_outcome(legacy_answer(Answer.YES), language=Language.DE).step.decision
    assert unchanged.endswith(
        "nur, wenn seine Konzeption oder Zweckbestimmung ab diesem Datum erheblich verändert "
        "wird (eine wesentliche Veränderung). Das System bleibt als Hochrisiko-System eingestuft."
    )
    assert "ab dem 2. August 2030" in outcome.step.decision
    assert outcome.step.decision.endswith("Das System bleibt als Hochrisiko-System eingestuft.")
    unknown = legacy_outcome(legacy_answer(Answer.UNKNOWN), language=Language.DE)
    assert "ab dem 2. Dezember 2027" in unknown.follow_up_questions[0].text


def test_a_prohibited_or_limited_answer_carries_no_legacy_facts() -> None:
    for risk_class in (RiskClass.PROHIBITED, RiskClass.LIMITED_RISK):
        assert node.answer_model(state(risk_class, None)) is RoleAnswer
    assert node.answer_model(state()) is HighRiskRoleAnswer


# --- The model call -----------------------------------------------------------------------------


def test_the_prompt_puts_the_instructions_first_and_the_description_last() -> None:
    conditions = conditions_to_ask(RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III, LawVersion.AMENDED)
    messages = node.role_messages(state(), conditions)
    assert messages[0].content == node.ROLE_INSTRUCTIONS
    human = str(messages[-1].content)
    assert human.endswith(CV_TOOL)
    assert "Risk class so far: high_risk (annex_iii route)" in human
    assert f"c1: {conditions[0]}" in human
    assert "Launch and design:" in human
    assert "rules apply from 2 December 2027" in human
    assert 'answer it "unknown": never assume it away' in human
    # Placed before is read as of today: in use now is "yes", a planned launch is "no".
    assert "already on the market or in use today" in human
    assert 'only planned, is "no", even if the launch is planned before' in human
    assert "or will be" not in human
    # Art. 3(23) via recital 177: only a change from the date, not foreseen in the assessment.
    assert "A change made before that date" in human
    assert "didn't foresee or plan" in human


E20_ROLE_RULE = (
    "When the company builds its own system on another provider's model (builds_on_gpai below), "
    'answer "deployer" when it also uses that system itself under its own authority, and '
    '"provider" when only others use it; the application then adds the provider role, since one '
    "operator may hold more than one role at once (Art. 3(4); recital 83)."
)
"""E20's base role for a company that builds on another provider's model (decision 035 follow-up
1), as role_obligations.md words it: it deploys what it uses itself (Art. 3(4)), and one operator
can be both provider and deployer (recital 83; guide-prohibited para 19, guide-art50 para 15)."""


def test_the_prompt_states_the_base_role_of_a_builder_on_a_gpai_model() -> None:
    """The sentence sits in `role`, after its options and before `builds_on_gpai`'s own
    definition."""
    flat = " ".join(node.ROLE_INSTRUCTIONS.split())
    assert E20_ROLE_RULE in flat
    start = flat.index("- role: the company's own role for this system, before any switch.")
    assert start < flat.index(E20_ROLE_RULE) < flat.index("- builds_on_gpai:")


def test_only_a_high_risk_request_asks_the_legacy_facts() -> None:
    # Other classes send the request E7 recorded, unchanged.
    for risk_class in (RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK, RiskClass.PROHIBITED):
        messages = node.role_messages(state(risk_class, None), ())
        assert "Launch and design" not in str(messages[-1].content)


def test_the_node_reads_the_legacy_facts_from_the_model() -> None:
    answer = role_answer(legacy=legacy_answer(placed_before=Answer.YES))
    check, _ = _fake_check(answer.model_dump_json())
    outcome = check(state())
    assert {o.legacy for o in finding(outcome).obligations if o.high_risk_route} == {
        LegacyStatus.UNCHANGED
    }


def test_a_high_risk_answer_without_the_legacy_facts_is_a_broken_output() -> None:
    check, _ = _fake_check(role_answer().model_dump_json())
    with pytest.raises(RoleOutputError, match="legacy"):
        check(state())


def test_the_node_is_pinned_to_the_engine_provider() -> None:
    check = RoleObligationsCheck(_settings())
    assert_pinned_route(check._route, 4000)  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize("content", ["not json", '{"role": {"role": "deployer"}}'])
def test_a_broken_answer_raises_without_quoting_the_description(content: str) -> None:
    check, _ = _fake_check(content)
    with pytest.raises(RoleOutputError) as caught:
        check(state())
    assert CV_TOOL not in str(caught.value)


def test_the_output_cap_leaves_room_for_reasoning() -> None:
    """E7's recordings used up to 2206 of 3000 output tokens; the contested answer adds more."""
    check = RoleObligationsCheck(_settings())
    assert_pinned_route(check._route, 4000)  # pyright: ignore[reportAttributeAccessIssue]


REFUSAL_TEXT = "I'm sorry, but I cannot assist with that request."


def _filtered_check(content: str = REFUSAL_TEXT) -> RoleObligationsCheck:
    """The node over a reply the provider's content filter stopped (decision 029)."""
    reply = AIMessage(content=content, response_metadata={"finish_reason": "content_filter"})
    return RoleObligationsCheck(_settings(), chat=GenericFakeChatModel(messages=iter([reply])))


def test_a_provider_refusal_assumes_no_role_for_a_person_to_review() -> None:
    """Decision 030: no role and no duty assumed; both definitions cited for the reviewer."""
    outcome = _filtered_check()(state())
    step = outcome.step
    assert step.status is Status.NEEDS_MORE_INFORMATION
    assert step.error == "provider_refusal"
    assert step.missing_fact is not None
    assert step.missing_fact.id == "role_person_review"
    assert outcome.follow_up_questions == (step.missing_fact,)
    assert step.decision == NOT_ASSESSED["en"]
    assert [c.provision_id for c in step.citations] == ["art:3:3", "art:3:4"]
    assert outcome.role is None


def test_a_role_refusal_is_reported_in_german() -> None:
    outcome = _filtered_check()(state(language=Language.DE))
    assert outcome.step.decision == NOT_ASSESSED["de"]
    assert outcome.step.missing_fact is not None
    assert outcome.step.missing_fact.text.startswith("Bitte lassen Sie")


def test_a_filtered_role_reply_with_a_usable_answer_is_used() -> None:
    usable = role_answer(legacy=legacy_answer()).model_dump_json()
    outcome = _filtered_check(usable)(state())
    assert (outcome.step.status, outcome.step.error) == (Status.DECIDED, None)
    assert finding(outcome).role is Role.DEPLOYER


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


REBRANDER = (
    "We are a software reseller in Munich. We license a US vendor's CV-screening AI that ranks "
    "job applicants, put our own brand on it and sell it to German employers under our name."
)


RECORD_COMMAND = "uv run pytest tests/engine/nodes/test_role_obligations.py --record-mode=once"
"""Records the role replays; a missing recording fails its replay, never a skip."""


@E20_PROMPTS_RECORDING_PENDING
@pytest.mark.vcr
def test_recorded_rebrander_becomes_the_provider(luna_settings: Settings) -> None:
    run_state = state(description=REBRANDER)
    outcome = RoleObligationsCheck(luna_settings)(run_state)
    assert not unresolved_citations(outcome.step, run_state)
    assert not whole_articles(outcome.step)
    assert finding(outcome).role is Role.PROVIDER
    assert "25(1)(a)" in (finding(outcome).role_switch_reason or "")
    assert "art:9" in articles(outcome)


# --- B5d replay: the own role cases -------------------------------------------------------------

ROLE_CASES_DIR = CASES_DIR / CaseSet.OWN.value / "d"


def _role_cases() -> list[BenchmarkCase]:
    """The B5d cases (every YAML file under `own/d/`), or none while the folder doesn't exist."""
    paths = sorted(ROLE_CASES_DIR.rglob("*.yaml")) if ROLE_CASES_DIR.is_dir() else []
    return [case for path in paths for case in load_yaml_file(path)]


B5D_CASES = _role_cases()


KNOWN_GAPS: dict[str, KnownGap] = {}
"""Recorded cases whose role outcome differs from the label, with the reason; each fails when it
starts matching, so the entry is removed. E20 removed own-d-03's (a base role of provider, which
lost the deployer role; decision 035 follow-up 1): the role prompt now says which base role a
company has that builds its own system on another provider's model."""


def b5d_matches(outcome: CheckOutcome, case: BenchmarkCase) -> bool:
    """Everything `test_b5d_case_replay` asserts: the role, exactly the tagged Art. 25(1)
    switches, any tagged `also_role`, no deployer role kept on a case without one tagged (E20: the
    base-role rule for a builder on a GPAI model must not add one, as on own-d-06), and
    `role_matches`."""
    label = case.label
    assert isinstance(label, CaseLabel)
    found = finding(outcome)
    switches = {f"art:25:1:{s[-1]}" for s in tag(case, "role_switch") if s != "none"}
    cited = {c.provision_id for c in outcome.step.citations}
    also = [Role(role) for role in tag(case, "also_role")]
    return (
        found.role is label.role
        and (not switches or {c for c in cited if c.startswith("art:25:1:")} == switches)
        and all(found.also_role is role for role in also)
        and (bool(also) or found.also_role is not Role.DEPLOYER)
        and role_matches(outcome, case)
    )


@pytest.mark.parametrize(
    ("base", "is_match"),
    [(Role.PROVIDER, True), (Role.DEPLOYER, False)],
    ids=["only-others-use-it", "also-uses-it"],
)
def test_a_provider_only_builder_matches_only_without_a_deployer_role(
    base: Role, is_match: bool
) -> None:
    """E20's guard on own-d-06 (provider only, no `also_role` tag): built on a GPAI model, a
    provider base matches; a deployer base, which keeps the deployer role, doesn't."""
    case = next(c for c in B5D_CASES if c.id == "own-d-06-shop-chat-on-llm")
    run_state = role_check_state(case, ROLE_AS_OF)
    gpai = key_fact(Answer.YES, EvidenceTag.STATED)
    answer = role_answer(base, risk_class=RiskClass.LIMITED_RISK, route=None, builds_on_gpai=gpai)
    outcome = to_outcome(answer, run_state)
    assert finding(outcome).role is Role.PROVIDER
    assert b5d_matches(outcome, case) is is_match


@E20_PROMPTS_RECORDING_PENDING
@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    B5D_CASES or [pytest.param(None, marks=pytest.mark.skip(reason="B5d cases not merged yet"))],
    ids=lambda case: case.id if isinstance(case, BenchmarkCase) else "no-cases",
)
def test_b5d_case_replay(case: BenchmarkCase, luna_settings: Settings) -> None:
    """Each B5d case's expected role, from the class its label gives, and its status when the
    label is legally ambiguous (own-d-12, closed by E8's contested answer); a case tagged with
    Art. 25(1) switches cites exactly those points (every switch that applies is reported, user,
    2026-10-06), one tagged `also_role:` keeps that role, and an untagged one keeps none (E20).
    Replays the recording
    `recordings/engine/nodes/test_role_obligations/test_b5d_case_replay[<id>].yaml`; a missing
    one fails. Record with `RECORD_COMMAND`."""
    if not runs_role_check(case):
        pytest.skip("the role check doesn't run for this case, or its label names no role")
    run_state = role_check_state(case, ROLE_AS_OF)
    outcome = RoleObligationsCheck(luna_settings)(run_state)
    assert not unresolved_citations(outcome.step, run_state)
    assert not whole_articles(outcome.step)
    found = finding(outcome)
    switches = sorted(c for c in cited(outcome) if c.startswith("art:25:1:"))
    shown = (found.role, found.also_role, switches, outcome.step.status, outcome.step.decision)
    matches = b5d_matches(outcome, case)
    expect_known_gap(KNOWN_GAPS, outcome, case, matches=matches, shown=shown)
    assert matches, shown
