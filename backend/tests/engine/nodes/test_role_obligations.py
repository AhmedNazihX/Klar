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
    KeyFact,
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
from aiact.schemas import (
    DISCLAIMER,
    STEP_ORDER,
    ClassificationResult,
    EvidenceTag,
    Fact,
    HighRiskRoute,
    Language,
    LawVersion,
    RiskClass,
    Role,
    SourceSpan,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.result import derived_status
from aiact.settings import Settings

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
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


def role_answer(
    role: Role | None = Role.DEPLOYER,
    conditions: dict[str, Answer] | None = None,
    risk_class: RiskClass = RiskClass.HIGH_RISK,
    route: HighRiskRoute | None = HighRiskRoute.ANNEX_III,
    **key_facts: KeyFact,
) -> RoleAnswer:
    """An answer: the given role, every key fact "no (assumed)" unless overridden, and the
    conditions by their text, turned into the ids the prompt would list."""
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
        "substantial_modification": key_fact(),
        "changed_purpose": key_fact(),
        "conditions": given,
    }
    return RoleAnswer.model_validate({**values, **key_facts})


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
        "as_of": date(2026, 9, 29),
        "answers": {},
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
    assert "art:16:a" in articles(outcome)
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
    assert {"art:16:a", "art:16:i", "art:26:1", "art:26:2", "art:26:6", "art:26:7"} <= set(kept)
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
    assert step.open_question.readings[0].startswith("Provider")  # the stricter reading first
    assert step.open_question.readings[1].startswith("Distributor")
    assert (finding(outcome).role, finding(outcome).also_role) == (
        Role.PROVIDER,
        Role.DISTRIBUTOR,
    )
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
    assert step.open_question.readings[1].startswith("Händler")
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
    assert own_duties | {"art:16:a"} <= set(articles(outcome))


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


def test_an_unknown_role_asks_for_it() -> None:
    outcome = to_outcome(role_answer(None), state())
    assert outcome.step.missing_fact is not None
    assert outcome.step.missing_fact.id == "operator_role"
    assert (finding(outcome).role, finding(outcome).also_role) == (Role.PROVIDER, Role.DEPLOYER)
    assert {"art:16:a", "art:26:1"} <= set(articles(outcome))


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
    assert "art:16:a" in articles(outcome)


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


def test_the_original_text_lists_no_duties_and_says_why() -> None:
    outcome = to_outcome(role_answer(), state(law_version=LawVersion.ORIGINAL))
    assert finding(outcome).obligations == ()
    assert "covers only the amended text, not the original text" in outcome.step.decision
    assert finding(outcome).role is Role.DEPLOYER


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
    cited = to_outcome(answer, given).step.citations
    assert cited
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
    content = role_answer().model_dump_json()
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


def _settings() -> Settings:
    values = {"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def _fake_check(content: str) -> tuple[RoleObligationsCheck, GenericFakeChatModel]:
    chat = GenericFakeChatModel(messages=iter([AIMessage(content=content)]))
    return RoleObligationsCheck(_settings(), chat=chat), chat


def test_the_node_reads_the_earlier_findings_through_the_graph() -> None:
    check, _ = _fake_check(role_answer(conditions={EMPLOYER: Answer.YES}).model_dump_json())
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
            "answers": {},
            "exclude_source_example_ids": (),
        }
    )
    assert final["high_risk_route"] is HighRiskRoute.ANNEX_III
    assert final["role"].role is Role.DEPLOYER
    assert "art:26:7" in [o.article for o in final["role"].obligations]
    assert final["steps"][-1].step is StepName.ROLE_OBLIGATIONS


# --- The model call -----------------------------------------------------------------------------


def test_the_prompt_puts_the_instructions_first_and_the_description_last() -> None:
    conditions = conditions_to_ask(RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III, LawVersion.AMENDED)
    messages = node.role_messages(state(), conditions)
    assert messages[0].content == node.ROLE_INSTRUCTIONS
    human = str(messages[-1].content)
    assert human.endswith(CV_TOOL)
    assert "Risk class so far: high_risk (annex_iii route)" in human
    assert f"c1: {conditions[0]}" in human


def test_the_node_is_pinned_to_the_engine_provider() -> None:
    check = RoleObligationsCheck(_settings())
    assert check._model.openrouter_provider == {  # pyright: ignore[reportAttributeAccessIssue]
        "data_collection": "deny",
        "zdr": True,
        "order": [LUNA_PROVIDER],
        "allow_fallbacks": False,
    }


@pytest.mark.parametrize("content", ["not json", '{"role": {"role": "deployer"}}'])
def test_a_broken_answer_raises_without_quoting_the_description(content: str) -> None:
    check, _ = _fake_check(content)
    with pytest.raises(RoleOutputError) as caught:
        check(state())
    assert CV_TOOL not in str(caught.value)


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


REBRANDER = (
    "We are a software reseller in Munich. We license a US vendor's CV-screening AI that ranks "
    "job applicants, put our own brand on it and sell it to German employers under our name."
)


@pytest.mark.vcr
def test_recorded_rebrander_becomes_the_provider(luna_settings: Settings) -> None:
    outcome = RoleObligationsCheck(luna_settings)(state(description=REBRANDER))
    assert finding(outcome).role is Role.PROVIDER
    assert "25(1)(a)" in (finding(outcome).role_switch_reason or "")
    assert "art:16:a" in articles(outcome)


# --- B5d replay: the own role cases, once they and their recordings exist ----------------------

ROLE_CASES_DIR = CASES_DIR / CaseSet.OWN.value / "d"


def _role_cases() -> list[BenchmarkCase]:
    """The B5d cases (every YAML file under `own/d/`), or none while the folder doesn't exist."""
    paths = sorted(ROLE_CASES_DIR.rglob("*.yaml")) if ROLE_CASES_DIR.is_dir() else []
    return [case for path in paths for case in load_yaml_file(path)]


def _case_state(label: CaseLabel, case: BenchmarkCase) -> EngineState:
    route = None
    if label.risk_class is RiskClass.HIGH_RISK:
        is_annex_i = (label.annex_point or "").startswith("annex:I:")
        route = HighRiskRoute.ANNEX_I if is_annex_i else HighRiskRoute.ANNEX_III
    duties = ("art:50:1",) if label.risk_class is RiskClass.LIMITED_RISK else ()
    return state(
        label.risk_class,
        route,
        language=case.language,
        transparency_duties=duties,
        description=case.description,
    )


B5D_CASES = _role_cases()

KNOWN_STATUS_GAPS: dict[str, str] = {
    "own-d-12-lender-extra-input": "node returns needs_more_information (substantial "
    "modification unknown) where the label is legally_ambiguous; open for the user",
}
"""Status mismatches reported to the user, not yet decided; the role still has to match."""


@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    B5D_CASES or [pytest.param(None, marks=pytest.mark.skip(reason="B5d cases not merged yet"))],
    ids=lambda case: case.id if isinstance(case, BenchmarkCase) else "no-cases",
)
def test_b5d_case_replay(
    case: BenchmarkCase,
    luna_settings: Settings,
    record_mode: str,
    vcr_cassette_dir: str,
    default_cassette_name: str,
) -> None:
    """Each B5d case's expected role, from the class its label gives. Replays the recording
    `recordings/engine/nodes/test_role_obligations/test_b5d_case_replay[<id>].yaml`; record with
    `uv run pytest tests/engine/nodes/test_role_obligations.py -k b5d --record-mode=once`."""
    label = case.label
    assert isinstance(label, CaseLabel)
    if label.risk_class is RiskClass.OUT_OF_SCOPE or label.role is None:
        pytest.skip("the role check doesn't run for this case, or its label names no role")
    cassette = Path(vcr_cassette_dir) / f"{default_cassette_name}.yaml"
    if record_mode == "none" and not cassette.exists():
        pytest.skip(
            f"B5d case {case.id} has no recording yet; record it with "
            "`uv run pytest tests/engine/nodes/test_role_obligations.py -k b5d --record-mode=once`"
        )
    outcome = RoleObligationsCheck(luna_settings)(_case_state(label, case))
    assert finding(outcome).role is label.role
    if label.status is Status.LEGALLY_AMBIGUOUS:
        gap = KNOWN_STATUS_GAPS.get(case.id)
        if gap and outcome.step.status is not label.status:
            pytest.xfail(gap)
        assert outcome.step.status is label.status
