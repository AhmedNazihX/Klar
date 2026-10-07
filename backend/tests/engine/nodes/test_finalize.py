"""The finalize node (E8): constructed states run through the graph to one result. Checks whose
finding is all that matters are stubs; where a rule lives in a check (the route on both routes,
Art. 2(2) for Section B, a provider refusal), the check's own outcome builder or node runs.

The descriptions, facts and questions here are invented, not benchmark cases.
"""

from collections.abc import Mapping
from datetime import date
from typing import cast

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.engine.graph import CheckNode, EngineNodes, build_graph
from aiact.engine.nodes import role_obligations
from aiact.engine.nodes.finalize import LEGAL_REVIEW, FinalizeOutputError, finalize
from aiact.engine.nodes.high_risk import HighRiskCheck
from aiact.engine.nodes.key_facts import Answer
from aiact.engine.nodes.prohibited import ProhibitedCheck
from aiact.engine.scripted import no_match
from aiact.engine.state import CheckOutcome, EngineInput, EngineState, FactsOutcome, RoleFinding
from aiact.obligations.list import CHAPTER_III_DATES
from aiact.schemas import (
    DISCLAIMER,
    STEP_ORDER,
    YES_NO,
    ClassificationResult,
    EvidenceTag,
    Fact,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    Obligation,
    RiskClass,
    Role,
    SourceSpan,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import Settings
from tests.engine.nodes.test_high_risk import YES, annex_i, annex_iii, art_6_3
from tests.engine.nodes.test_high_risk import FakeLibrary as HighRiskLibrary
from tests.engine.nodes.test_high_risk import answer as high_risk_answer
from tests.engine.nodes.test_high_risk import outcome as high_risk_outcome
from tests.engine.nodes.test_prohibited import FakeLibrary as ProhibitedLibrary
from tests.engine.nodes.test_role_obligations import legacy_answer, role_answer
from tests.schemas.builders import open_question

AS_OF = date(2026, 10, 6)
DESCRIPTION = "We use a tool that reads job applications and ranks the applicants for HR."
ENGINE_INPUT: EngineInput = {
    "description": DESCRIPTION,
    "language": Language.EN,
    "law_version": LawVersion.AMENDED,
    "as_of": AS_OF,
    "exclude_source_example_ids": (),
}
OPEN = open_question("Does the law settle this?", "Stricter.", "Lenient.")
LITERACY = Obligation(
    duty="Ensure AI literacy",
    duty_de="KI-Kompetenz fördern.",
    label_en="Build AI literacy",
    label_de="KI-Kompetenz fördern",
    article="art:4:1",
    applies_from=date(2025, 2, 2),
)

RANKS = Fact(text="The tool ranks applicants", evidence=EvidenceTag.STATED,
             source_span=SourceSpan(start=33, end=69))  # fmt: skip
BOUGHT = Fact(text="The company bought the tool", evidence=EvidenceTag.INFERRED)
EU_USE = Fact(text="The system is used in the EU", evidence=EvidenceTag.ASSUMED)
NO_CHAT = Fact(text="The tool doesn't talk to applicants", evidence=EvidenceTag.INFERRED)
NO_PRACTICE = Fact(text="No prohibited practice is described", evidence=EvidenceTag.INFERRED)

EU_LINK = FollowUpQuestion(id="eu_link", text="Is the system used in the EU?", about="art:2:1")
DECIDING = FollowUpQuestion(id="deciding_fact", text="Is the deciding fact true?")
FILTERED = AIMessage(
    content="I'm sorry, but I cannot assist with that request.",
    response_metadata={"finish_reason": "content_filter"},
)


def step(
    name: StepName,
    *facts: Fact,
    status: Status = Status.DECIDED,
    missing: FollowUpQuestion | None = None,
) -> StepResult:
    """A constructed step; an uncertain one names its gap (`DECIDING` when no question given)."""
    is_missing = status is Status.NEEDS_MORE_INFORMATION
    return StepResult(
        step=name,
        decision=f"Constructed {name.value} step",
        facts_used=facts,
        status=status,
        missing_fact=missing or (DECIDING if is_missing else None),
        open_question=OPEN if status is Status.LEGALLY_AMBIGUOUS else None,
    )


def role_outcome(
    role: Role = Role.DEPLOYER,
    also_role: Role | None = None,
    status: Status = Status.DECIDED,
    reason: str | None = None,
) -> CheckOutcome:
    finding = RoleFinding(
        role=role, also_role=also_role, role_switch_reason=reason, obligations=(LITERACY,)
    )
    return CheckOutcome(step=step(StepName.ROLE_OBLIGATIONS, BOUGHT, status=status), role=finding)


def high_risk(
    point: str = "annex:III:4:a",
    route: HighRiskRoute = HighRiskRoute.ANNEX_III,
    status: Status = Status.DECIDED,
) -> CheckOutcome:
    return CheckOutcome(
        step=step(StepName.HIGH_RISK, RANKS, status=status),
        high_risk_route=route,
        annex_point=point,
    )


def prohibited_match(status: Status = Status.DECIDED) -> CheckOutcome:
    return CheckOutcome(step=step(StepName.PROHIBITED, NO_PRACTICE, status=status), matched=True)


Check = CheckOutcome | CheckNode


def _node(given: Check) -> CheckNode:
    if isinstance(given, CheckOutcome):
        return lambda _state: given
    return given


def run_state(
    checks: Mapping[StepName, Check] | None = None,
    facts: FactsOutcome | None = None,
    language: Language = Language.EN,
) -> EngineState:
    """One run through the graph with the real finalize: each check returns its given outcome
    (or runs its given node); the rest find nothing, and the role step keeps a deployer."""
    given: dict[StepName, Check] = {StepName.ROLE_OBLIGATIONS: role_outcome(), **(checks or {})}
    nodes = EngineNodes(
        facts=lambda _state: facts or FactsOutcome(),
        checks={name: _node(given.get(name) or no_match(name)) for name in STEP_ORDER},
        finalize=finalize,
    )
    return cast(EngineState, build_graph(nodes).invoke({**ENGINE_INPUT, "language": language}))


def run(
    checks: Mapping[StepName, Check] | None = None,
    facts: FactsOutcome | None = None,
    language: Language = Language.EN,
) -> ClassificationResult:
    result = run_state(checks, facts, language).get("result")
    assert result is not None
    return result


def question_ids(result: ClassificationResult) -> list[str]:
    return [question.id for question in result.follow_up_questions]


def texts(facts: tuple[Fact, ...]) -> list[str]:
    return [fact.text for fact in facts]


def settings() -> Settings:
    pinned = {"engine_model": "openai/gpt-6-luna-20260922", "engine_provider": "azure/eu"}
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **pinned)  # pyright: ignore[reportCallIssue]


def filtered() -> GenericFakeChatModel:
    """A reply the provider's content filter stopped, as recorded for E4's refused cases."""
    return GenericFakeChatModel(messages=iter([FILTERED]))


def real_role(answer: role_obligations.RoleAnswer) -> CheckNode:
    """The role check's own rules over a given answer: it reads the earlier findings."""
    return lambda state: role_obligations.to_outcome(answer, state)


# --- The class and what every result carries -----------------------------------------------------


def test_a_run_with_no_finding_is_a_decided_minimal_risk_result() -> None:
    result = run()
    assert (result.risk_class, result.status) == (RiskClass.MINIMAL_RISK, Status.DECIDED)
    assert result.role is Role.DEPLOYER
    assert result.obligations == (LITERACY,)
    assert (result.law_version, result.as_of) == (LawVersion.AMENDED, AS_OF)
    assert result.disclaimer == DISCLAIMER[Language.EN]
    assert result.legal_review is None
    assert result.not_assessed == ()


def test_a_decided_out_of_scope_step_ends_the_run_out_of_scope() -> None:
    out = CheckOutcome(step=step(StepName.SCOPE, EU_USE), matched=True)
    result = run({StepName.SCOPE: out})
    assert result.risk_class is RiskClass.OUT_OF_SCOPE
    assert [s.step for s in result.steps] == [StepName.SCOPE]
    assert (result.role, result.obligations, result.transparency_duties) == (None, (), ())
    assert texts(result.deciding_facts) == [EU_USE.text]


def test_a_decided_prohibited_match_ends_the_run_with_legal_review() -> None:
    result = run({StepName.PROHIBITED: prohibited_match()})
    assert result.risk_class is RiskClass.PROHIBITED
    assert [s.step for s in result.steps] == [StepName.SCOPE, StepName.PROHIBITED]
    assert result.role is None
    assert result.legal_review == LEGAL_REVIEW[Language.EN][RiskClass.PROHIBITED]
    assert texts(result.deciding_facts) == [NO_PRACTICE.text]


def test_art_50_duties_make_a_limited_risk_result() -> None:
    duties = CheckOutcome(
        step=step(StepName.TRANSPARENCY, NO_CHAT), transparency_duties=("art:50:1",)
    )
    result = run({StepName.TRANSPARENCY: duties})
    assert result.risk_class is RiskClass.LIMITED_RISK
    assert result.transparency_duties == ("art:50:1",)
    assert result.legal_review is None


def test_the_role_and_the_role_it_keeps_are_copied() -> None:
    reason = "Art. 25(1)(c): it uses the system for a new purpose that makes it high-risk."
    switched = role_outcome(Role.PROVIDER, Role.DEPLOYER, reason=reason)
    result = run({StepName.HIGH_RISK: high_risk(), StepName.ROLE_OBLIGATIONS: switched})
    assert (result.role, result.also_role) == (Role.PROVIDER, Role.DEPLOYER)
    assert result.role_switch_reason == reason


# --- Uncertain outcomes: the stricter reading as the labelled working assumption ------------------


def test_an_ambiguous_high_risk_step_keeps_high_risk_as_the_labelled_assumption() -> None:
    result = run({StepName.HIGH_RISK: high_risk(status=Status.LEGALLY_AMBIGUOUS)})
    assert result.risk_class is RiskClass.HIGH_RISK
    assert result.status is Status.LEGALLY_AMBIGUOUS
    texts_en = LEGAL_REVIEW[Language.EN]
    assert result.legal_review == " ".join(
        (texts_en[RiskClass.HIGH_RISK], texts_en["class_open"].format(risk_class="high-risk"))
    )
    assert RANKS.text in texts(result.deciding_facts)


def test_an_ambiguous_prohibited_step_keeps_prohibited_and_the_annex_point() -> None:
    """Decision 010 and F7b: the run goes on, the class stays prohibited, and the Annex point the
    high-risk check found is copied whatever the final class (the metrics read the basis). The
    legal review keeps the Art. 5 warning and adds what the open question leaves assumed."""
    result = run(
        {
            StepName.PROHIBITED: prohibited_match(Status.LEGALLY_AMBIGUOUS),
            StepName.HIGH_RISK: high_risk("annex:III:4:a"),
        }
    )
    assert result.risk_class is RiskClass.PROHIBITED
    assert result.status is Status.LEGALLY_AMBIGUOUS
    assert [s.step for s in result.steps] == list(STEP_ORDER)
    assert result.annex_point == "annex:III:4:a"
    assert result.role is Role.DEPLOYER  # the lenient reading's role and duties stay shown
    assert result.legal_review is not None
    assert result.legal_review.startswith(LEGAL_REVIEW[Language.EN][RiskClass.PROHIBITED])
    assert "the stricter reading (prohibited) is assumed" in result.legal_review


def test_a_needs_information_state_asks_the_missing_fact_first() -> None:
    scope = CheckOutcome(
        step=step(StepName.SCOPE, status=Status.NEEDS_MORE_INFORMATION, missing=EU_LINK),
        follow_up_questions=(EU_LINK,),
    )
    asked = FollowUpQuestion(id="ranks_people", text="Does the tool rank people?")
    result = run({StepName.SCOPE: scope}, FactsOutcome(follow_up_questions=(asked,)))
    assert result.risk_class is RiskClass.MINIMAL_RISK  # in scope assumed; later steps decide
    assert result.status is Status.NEEDS_MORE_INFORMATION
    assert question_ids(result)[:2] == ["eu_link", "ranks_people"]
    assert result.legal_review is None


def test_an_ambiguous_step_outranks_a_needs_information_step() -> None:
    scope = CheckOutcome(
        step=step(StepName.SCOPE, status=Status.NEEDS_MORE_INFORMATION, missing=EU_LINK),
        follow_up_questions=(EU_LINK,),
    )
    unsure = CheckOutcome(
        step=step(StepName.TRANSPARENCY, NO_CHAT, status=Status.LEGALLY_AMBIGUOUS),
        transparency_duties=("art:50:1",),
    )
    result = run({StepName.SCOPE: scope, StepName.TRANSPARENCY: unsure})
    assert result.status is Status.LEGALLY_AMBIGUOUS
    assert result.risk_class is RiskClass.LIMITED_RISK
    assert question_ids(result)[0] == "eu_link"  # the missing fact is still asked
    assert result.legal_review == " ".join(
        (
            LEGAL_REVIEW[Language.EN]["lead"],
            LEGAL_REVIEW[Language.EN]["class_open"].format(risk_class="limited risk"),
        )
    )


def test_an_ambiguous_role_names_the_role_assumed_not_the_class() -> None:
    owned = role_outcome(Role.PROVIDER, Role.DISTRIBUTOR, status=Status.LEGALLY_AMBIGUOUS)
    result = run({StepName.ROLE_OBLIGATIONS: owned})
    assert (result.risk_class, result.status) == (RiskClass.MINIMAL_RISK, Status.LEGALLY_AMBIGUOUS)
    assert result.legal_review == (
        "Have this result reviewed by a lawyer. The law doesn't settle the company's role, so the "
        "provider role is assumed until a lawyer has reviewed it."
    )


def test_an_ambiguous_scope_says_the_act_is_assumed_to_apply() -> None:
    scope = CheckOutcome(step=step(StepName.SCOPE, EU_USE, status=Status.LEGALLY_AMBIGUOUS))
    result = run({StepName.SCOPE: scope, StepName.HIGH_RISK: high_risk()})
    assert result.legal_review == " ".join(
        (LEGAL_REVIEW[Language.EN][RiskClass.HIGH_RISK], LEGAL_REVIEW[Language.EN]["scope_open"])
    )
    assert "stricter reading" not in (result.legal_review or "")


def _open_duty() -> CheckOutcome:
    return CheckOutcome(
        step=step(StepName.TRANSPARENCY, NO_CHAT, status=Status.LEGALLY_AMBIGUOUS),
        transparency_duties=("art:50:1",),
    )


def test_an_open_art_50_duty_on_a_high_risk_result_names_the_duty_not_the_class() -> None:
    result = run({StepName.HIGH_RISK: high_risk(), StepName.TRANSPARENCY: _open_duty()})
    assert result.risk_class is RiskClass.HIGH_RISK
    assert result.legal_review == (
        "Have this result reviewed by a lawyer: a high-risk system carries duties with legal "
        "consequences. The law and guidance don't settle whether an Art. 50 transparency duty "
        "applies, so it is assumed until a lawyer has reviewed it."
    )


def test_an_open_art_50_duty_on_a_limited_risk_result_is_the_class() -> None:
    result = run({StepName.TRANSPARENCY: _open_duty()})
    assert result.risk_class is RiskClass.LIMITED_RISK
    assert result.legal_review == (
        "Have this result reviewed by a lawyer. The law and guidance don't settle part of the "
        "classification, so the stricter reading (limited risk) is assumed until a lawyer has "
        "reviewed it."
    )


def test_the_open_question_clauses_read_in_german() -> None:
    owned = role_outcome(Role.PROVIDER, Role.DISTRIBUTOR, status=Status.LEGALLY_AMBIGUOUS)
    role = run({StepName.ROLE_OBLIGATIONS: owned}, language=Language.DE)
    assert role.legal_review == (
        "Lassen Sie dieses Ergebnis anwaltlich prüfen. Das Recht klärt die Rolle des Unternehmens "
        "nicht, daher wird bis zur anwaltlichen Prüfung die Rolle Anbieter angenommen."
    )
    ambiguous = high_risk(status=Status.LEGALLY_AMBIGUOUS)
    classed = run({StepName.HIGH_RISK: ambiguous}, language=Language.DE)
    assert classed.legal_review == (
        "Lassen Sie dieses Ergebnis anwaltlich prüfen: Ein Hochrisiko-System bringt Pflichten mit "
        "rechtlicher Tragweite mit sich. Recht und Leitlinien klären einen Teil der Einstufung "
        "nicht, daher wird bis zur anwaltlichen Prüfung die strengere Lesart (Hochrisiko) "
        "angenommen."
    )
    duty = run(
        {StepName.HIGH_RISK: high_risk(), StepName.TRANSPARENCY: _open_duty()},
        language=Language.DE,
    )
    assert duty.legal_review == (
        "Lassen Sie dieses Ergebnis anwaltlich prüfen: Ein Hochrisiko-System bringt Pflichten mit "
        "rechtlicher Tragweite mit sich. Recht und Leitlinien klären nicht, ob eine "
        "Transparenzpflicht nach Art. 50 gilt, daher wird sie bis zur anwaltlichen Prüfung "
        "angenommen."
    )


# --- The legal-review recommendation (INIT > Ethical considerations, decision 026 item 12) -------


LIMITED = CheckOutcome(step=step(StepName.TRANSPARENCY, NO_CHAT), transparency_duties=("art:50:1",))


@pytest.mark.parametrize(
    ("checks", "expected"),
    [
        ({StepName.HIGH_RISK: high_risk()}, RiskClass.HIGH_RISK),
        ({StepName.PROHIBITED: prohibited_match()}, RiskClass.PROHIBITED),
        (
            {StepName.PROHIBITED: prohibited_match(Status.NEEDS_MORE_INFORMATION)},
            RiskClass.PROHIBITED,
        ),
        (
            {StepName.HIGH_RISK: high_risk(status=Status.NEEDS_MORE_INFORMATION)},
            RiskClass.HIGH_RISK,
        ),
        ({StepName.TRANSPARENCY: LIMITED}, None),
        ({}, None),
    ],
    ids=[
        "high-risk",
        "prohibited",
        "prohibited-assumed",
        "high-risk-assumed",
        "limited",
        "minimal",
    ],
)
def test_legal_review_follows_the_class(
    checks: dict[StepName, CheckOutcome], expected: RiskClass | None
) -> None:
    result = run(checks)
    assert result.legal_review == (LEGAL_REVIEW[Language.EN][expected] if expected else None)


def test_the_legal_review_and_disclaimer_read_in_german() -> None:
    result = run({StepName.HIGH_RISK: high_risk()}, language=Language.DE)
    assert result.disclaimer == DISCLAIMER[Language.DE]
    assert result.legal_review is not None
    assert result.legal_review.startswith("Lassen Sie dieses Ergebnis anwaltlich prüfen")


# --- Deciding facts -----------------------------------------------------------------------------


def test_deciding_facts_come_from_the_class_step_the_uncertain_steps_and_the_role() -> None:
    scope = CheckOutcome(step=step(StepName.SCOPE, EU_USE))  # decided: not deciding
    unsure = step(StepName.TRANSPARENCY, NO_CHAT, status=Status.LEGALLY_AMBIGUOUS)
    result = run(
        {
            StepName.SCOPE: scope,
            StepName.HIGH_RISK: high_risk(),
            StepName.TRANSPARENCY: CheckOutcome(step=unsure),
        }
    )
    assert texts(result.deciding_facts) == [RANKS.text, NO_CHAT.text, BOUGHT.text]


def test_a_minimal_risk_result_rests_on_the_checks_it_fell_through() -> None:
    result = run(
        {
            StepName.HIGH_RISK: CheckOutcome(step=step(StepName.HIGH_RISK, RANKS)),
            StepName.TRANSPARENCY: CheckOutcome(step=step(StepName.TRANSPARENCY, NO_CHAT, RANKS)),
        }
    )
    assert texts(result.deciding_facts) == [RANKS.text, NO_CHAT.text, BOUGHT.text]


def test_a_limited_risk_result_rests_on_the_high_risk_and_transparency_checks() -> None:
    result = run(
        {
            StepName.HIGH_RISK: CheckOutcome(step=step(StepName.HIGH_RISK, RANKS)),
            StepName.TRANSPARENCY: CheckOutcome(
                step=step(StepName.TRANSPARENCY, NO_CHAT), transparency_duties=("art:50:1",)
            ),
        }
    )
    assert result.risk_class is RiskClass.LIMITED_RISK
    assert texts(result.deciding_facts) == [RANKS.text, NO_CHAT.text, BOUGHT.text]


def test_the_facts_node_facts_are_the_results_facts() -> None:
    result = run(facts=FactsOutcome(facts=(RANKS, BOUGHT)))
    assert result.facts == (RANKS, BOUGHT)


# --- Follow-up questions ------------------------------------------------------------------------


def test_of_two_questions_with_one_id_the_first_asked_is_kept() -> None:
    """Neither is a missing fact: the facts node's question, asked first, wins over a check's."""
    first = FollowUpQuestion(id="ranks_people", text="Does the tool rank people?")
    later = FollowUpQuestion(id="ranks_people", text="Does it sort the applicants?")
    hr = high_risk().model_copy(update={"follow_up_questions": (later,)})
    result = run({StepName.HIGH_RISK: hr}, FactsOutcome(follow_up_questions=(first,)))
    assert result.follow_up_questions == (first,)


def test_follow_up_questions_are_deduplicated_by_stable_id() -> None:
    """A check's questions may repeat its own missing fact, and two nodes may ask the same id:
    each id is asked once, a missing fact with its own text (the result contract needs it)."""
    from_facts = FollowUpQuestion(id="eu_link", text="Do you use it in the EU?")
    own_brand = FollowUpQuestion(id="own_brand", text="Do you put your name on it?")
    scope = CheckOutcome(
        step=step(StepName.SCOPE, status=Status.NEEDS_MORE_INFORMATION, missing=EU_LINK),
        follow_up_questions=(EU_LINK,),
    )
    role = role_outcome().model_copy(update={"follow_up_questions": (own_brand,)})
    hr = high_risk().model_copy(update={"follow_up_questions": (own_brand, EU_LINK)})
    result = run(
        {StepName.SCOPE: scope, StepName.HIGH_RISK: hr, StepName.ROLE_OBLIGATIONS: role},
        FactsOutcome(follow_up_questions=(from_facts,)),
    )
    assert question_ids(result) == ["eu_link", "own_brand"]
    assert result.follow_up_questions[0] == EU_LINK  # the step's text, not the facts node's


def test_an_assumed_fact_a_check_relied_on_gets_a_stable_confirm_question() -> None:
    """INIT > Evidence tags and decision 026: a check's assumed fact (E3's assumed EU link) is
    asked to be confirmed, with an id from its text, the same on every run; a fact the facts
    node extracted already has its own question."""
    extracted = Fact(text="The tool is bought in", evidence=EvidenceTag.ASSUMED)
    scope = CheckOutcome(step=step(StepName.SCOPE, EU_USE, extracted))
    facts = FactsOutcome(facts=(extracted,))
    first, again = (run({StepName.SCOPE: scope}, facts) for _ in range(2))
    confirm = FollowUpQuestion(
        id="confirm_the_system_is_used_in_the_eu",
        text="Please confirm: The system is used in the EU",
        options=YES_NO,
    )
    assert first.follow_up_questions == (confirm,)
    assert again.follow_up_questions == first.follow_up_questions


def test_a_confirm_question_never_takes_an_id_already_asked() -> None:
    taken = FollowUpQuestion(id="confirm_the_system_is_used_in_the_eu", text="Another question?")
    scope = CheckOutcome(step=step(StepName.SCOPE, EU_USE), follow_up_questions=(taken,))
    result = run({StepName.SCOPE: scope})
    assert question_ids(result) == [taken.id, f"{taken.id}_2"]


@pytest.mark.parametrize("point", ["annex:III:6:a", "annex:III:7:b"])
def test_an_assumed_public_authority_user_is_asked_once(point: str) -> None:
    """Annex III 6 and 7: the high-risk check assumes a public-authority user and asks
    `public_authority_user` itself, so finalize adds no confirm question for that fact."""
    assumed = annex_iii(point, YES, public_authority=Answer.UNKNOWN)
    hr = high_risk_outcome(high_risk_answer(assumed))
    result = run({StepName.HIGH_RISK: hr})
    assert any(f.evidence is EvidenceTag.ASSUMED for f in result.steps[2].facts_used)
    assert question_ids(result) == ["public_authority_user"]


# --- High-risk findings: the Annex point, both routes, Section B ----------------------------------


@pytest.mark.parametrize(
    ("outcome", "point"),
    [
        (high_risk("annex:III:5:b"), "annex:III:5:b"),
        (high_risk("annex:I:A:11", HighRiskRoute.ANNEX_I), "annex:I:A:11"),
        (CheckOutcome(step=step(StepName.HIGH_RISK, RANKS)), None),
    ],
)
def test_the_annex_point_is_copied_into_the_result(
    outcome: CheckOutcome, point: str | None
) -> None:
    assert run({StepName.HIGH_RISK: outcome}).annex_point == point


def test_both_routes_report_annex_iii_and_keep_annex_i_in_the_deciding_facts() -> None:
    """User, 2026-09-30: Annex III is reported (its duties apply first, Art. 16(i)); the Annex I
    route stays in the deciding facts."""
    medical_device = annex_i("annex:I:A:11", YES, YES, YES)
    both = high_risk_outcome(
        high_risk_answer(annex_iii("annex:III:5:d", YES), art_6_3(), medical_device)
    )
    role = real_role(role_answer(Role.DEPLOYER, legacy=legacy_answer()))
    result = run({StepName.HIGH_RISK: both, StepName.ROLE_OBLIGATIONS: role})
    assert result.risk_class is RiskClass.HIGH_RISK
    assert result.annex_point == "annex:III:5:d"
    routed = [o for o in result.obligations if o.high_risk_route is not None]
    assert routed
    assert {(o.high_risk_route, o.applies_from) for o in routed} == {
        (HighRiskRoute.ANNEX_III, CHAPTER_III_DATES[HighRiskRoute.ANNEX_III])
    }
    assert {"Annex III: annex:III:5:d", "Annex I: annex:I:A:11"} <= set(
        texts(result.deciding_facts)
    )


CHATTY = CheckOutcome(step=step(StepName.TRANSPARENCY, NO_CHAT), transparency_duties=("art:50:1",))


@pytest.mark.parametrize("language", [Language.EN, Language.DE])
def test_a_decided_section_b_result_lists_no_ai_act_obligations(language: Language) -> None:
    """Art. 2(2) (user, 2026-09-30): a product the high-risk check decided is high-risk under
    Annex I Section B gets only Art. 6(1), 60a and 102 to 112 of the AI Act, so neither duties
    nor Art. 50 duties are listed; the role step says why and cites Art. 2(2)."""
    machinery = high_risk_outcome(high_risk_answer(one=annex_i("annex:I:B:21", YES, YES, YES)))
    assert machinery.step.status is Status.DECIDED
    role = real_role(role_answer(Role.PROVIDER, legacy=legacy_answer(placed_before=YES)))
    checks = {StepName.HIGH_RISK: machinery, StepName.TRANSPARENCY: CHATTY,
              StepName.ROLE_OBLIGATIONS: role}  # fmt: skip
    result = run(checks, language=language)
    assert (result.risk_class, result.annex_point) == (RiskClass.HIGH_RISK, "annex:I:B:21")
    assert (result.role, result.obligations, result.transparency_duties) == (Role.PROVIDER, (), ())
    role_step = result.steps[-1]
    assert "art:2:2" in [c.provision_id for c in role_step.citations]
    assert ("Section B" if language is Language.EN else "Abschnitt B") in role_step.decision
    assert not any(q.id == "significant_design_change" for q in result.follow_up_questions)


def test_an_assumed_section_b_result_keeps_every_duty_and_names_art_2_2_as_possible() -> None:
    """Orchestrator's ruling (E8 review round 1): the stricter reading keeps the duties while the
    high-risk step is uncertain; the role step states the Art. 2(2) outcome as a possibility."""
    open_assessment = annex_i("annex:I:B:21", YES, YES, Answer.UNKNOWN)
    machinery = high_risk_outcome(high_risk_answer(one=open_assessment))
    assert machinery.step.status is Status.NEEDS_MORE_INFORMATION
    role = real_role(role_answer(Role.PROVIDER, legacy=legacy_answer()))
    checks = {StepName.HIGH_RISK: machinery, StepName.TRANSPARENCY: CHATTY,
              StepName.ROLE_OBLIGATIONS: role}  # fmt: skip
    result = run(checks)
    assert (result.risk_class, result.annex_point) == (RiskClass.HIGH_RISK, "annex:I:B:21")
    assert {"art:4:1", "art:9", "art:50:1"} <= {o.article for o in result.obligations}
    assert result.transparency_duties == ("art:50:1",)
    decision = result.steps[-1].decision
    assert "If the system is high-risk as a product" in decision
    assert "No AI Act duties listed" not in decision


def test_a_prohibited_assumption_over_a_section_b_product_keeps_its_duties() -> None:
    """Art. 2(2) is read for a high-risk class only: when an uncertain Art. 5 match keeps
    prohibited as the class, the prohibition rows stay listed."""
    machinery = high_risk_outcome(high_risk_answer(one=annex_i("annex:I:B:21", YES, YES, YES)))
    role = real_role(role_answer(Role.PROVIDER, risk_class=RiskClass.PROHIBITED, route=None))
    checks = {StepName.PROHIBITED: prohibited_match(Status.LEGALLY_AMBIGUOUS),
              StepName.HIGH_RISK: machinery, StepName.ROLE_OBLIGATIONS: role}  # fmt: skip
    result = run(checks)
    assert (result.risk_class, result.annex_point) == (RiskClass.PROHIBITED, "annex:I:B:21")
    assert any(o.article.startswith("art:5:") for o in result.obligations)


def test_a_section_a_product_keeps_its_duties() -> None:
    device = high_risk_outcome(high_risk_answer(one=annex_i("annex:I:A:11", YES, YES, YES)))
    role = real_role(role_answer(Role.PROVIDER, legacy=legacy_answer()))
    result = run({StepName.HIGH_RISK: device, StepName.ROLE_OBLIGATIONS: role})
    assert result.annex_point == "annex:I:A:11"
    assert "art:9" in [o.article for o in result.obligations]


# --- A broken contract ---------------------------------------------------------------------------


def test_a_result_that_breaks_the_contract_raises_without_user_text() -> None:
    """A role step without its finding can't make a result; the error names the rule, never the
    description or the facts."""
    no_finding = CheckOutcome(step=step(StepName.ROLE_OBLIGATIONS, BOUGHT))
    with pytest.raises(FinalizeOutputError, match="role is set exactly") as raised:
        run({StepName.ROLE_OBLIGATIONS: no_finding}, FactsOutcome(facts=(RANKS,)))
    message = str(raised.value)
    assert message == (
        "the result breaks its contract: answer: Value error, role is set exactly when the "
        "role_obligations step is present"
    )  # describe_validation_error's output: location and message, no input values
    assert "input_value" not in message
    assert DESCRIPTION not in message
    assert RANKS.text not in message
    assert raised.value.__cause__ is None


# --- A provider refusal (decision 029; X2b's DoD addition) ---------------------------------------


def test_a_refused_prohibited_step_keeps_prohibited_and_names_the_step() -> None:
    check = ProhibitedCheck(settings(), chat=filtered(), library=ProhibitedLibrary())
    result = run({StepName.PROHIBITED: check})
    assert result.risk_class is RiskClass.PROHIBITED
    assert result.status in (Status.NEEDS_MORE_INFORMATION, Status.LEGALLY_AMBIGUOUS)
    assert result.not_assessed == (StepName.PROHIBITED,)
    assert [s.step for s in result.steps] == list(STEP_ORDER)  # the run goes on
    assert "person_review" in question_ids(result)
    assert result.legal_review == LEGAL_REVIEW[Language.EN][RiskClass.PROHIBITED]


def test_a_refused_high_risk_step_assumes_high_risk_and_names_the_step() -> None:
    check = HighRiskCheck(settings(), chat=filtered(), library=HighRiskLibrary())
    role = real_role(role_answer(Role.DEPLOYER, legacy=legacy_answer()))
    result = run({StepName.HIGH_RISK: check, StepName.ROLE_OBLIGATIONS: role})
    assert (result.risk_class, result.status) == (
        RiskClass.HIGH_RISK,
        Status.NEEDS_MORE_INFORMATION,
    )
    assert result.not_assessed == (StepName.HIGH_RISK,)
    assert result.annex_point is None
    assert "high_risk_person_review" in question_ids(result)
    assert "art:26:1" in [o.article for o in result.obligations]


def test_every_refused_step_is_named_in_check_order() -> None:
    def refused(name: StepName) -> CheckOutcome:
        review = FollowUpQuestion(id=f"{name.value}_person_review", text="Please review it.")
        refusal = StepResult(
            step=name,
            decision="The model provider's content filter blocked this description.",
            status=Status.NEEDS_MORE_INFORMATION,
            missing_fact=review,
            error="provider_refusal",
        )
        return CheckOutcome(step=refusal, follow_up_questions=(review,))

    transparency = refused(StepName.TRANSPARENCY).model_copy(
        update={"transparency_duties": ("art:50:1", "art:50:2", "art:50:3", "art:50:4")}
    )
    result = run({StepName.SCOPE: refused(StepName.SCOPE), StepName.TRANSPARENCY: transparency})
    assert result.not_assessed == (StepName.SCOPE, StepName.TRANSPARENCY)
    assert result.risk_class is RiskClass.LIMITED_RISK  # every Art. 50 duty assumed
    assert result.status is Status.NEEDS_MORE_INFORMATION
