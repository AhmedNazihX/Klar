"""The finalize node: the checks' steps and findings aggregated into one result (E8; INIT > How it
works, Ethical considerations). No model is called.

- **Class.** A decided out-of-scope step that ended the run gives `out_of_scope`. Otherwise the
  class is the stricter reading the checks left (`working_class`, which the role check reads
  too): an Art. 5 match, decided or uncertain, keeps `prohibited` (decision 010); then high-risk
  on its route (Annex III when both routes apply: the high-risk check reports it, user,
  2026-09-30); then Art. 50 duties; else minimal risk. When the status is uncertain the class
  is the labelled working assumption: the status says so, and the legal-review line names it.
- **Status** follows the steps (`derived_status`); a refused step (decision 029) is
  `needs_more_information`, and `not_assessed` names it.
- **Findings** are copied as the checks set them: the Annex point whatever the final class
  (F7b: the metrics read the basis from it), the Art. 50 duties, the role, the role kept next
  to it (`also_role`, shown as "You also use it", decision 026) and its duties. A product the
  high-risk check decided is high-risk under Annex I Section B keeps no Art. 50 duty either:
  Art. 2(2) applies only Art. 6(1), 60a and 102 to 112 to it (the original text: Art. 6(1), 102
  to 109 and 112), and the role check lists no duties.
  Only assumed so, it keeps every duty that may apply (the stricter reading).
- **Deciding facts** are the facts of the steps the outcome rests on: the step that set the
  class (for limited and minimal risk, the high-risk and transparency checks), every uncertain
  step, and the role step; each fact once.
- **Follow-up questions**: every step's missing fact first (in check order), then the facts
  node's and the checks' questions, then a "please confirm" question for every assumed fact a
  step relied on that neither the facts node extracted nor a check already asks about (INIT >
  Evidence tags; decision 026); each id once, the first one kept, so a missing fact is listed
  with its own text.
- **Legal review** is recommended for high-risk, prohibited and legally ambiguous results (INIT
  > Ethical considerations, decision 026 item 12), in the result's language: the class's own
  sentence, then what each open question of law leaves assumed.
"""

from collections.abc import Iterable, Mapping, Sequence

from pydantic import ValidationError

from aiact.engine.graph import run_ends_after
from aiact.engine.nodes.facts import confirm_question
from aiact.engine.nodes.role_obligations import is_section_b, working_class
from aiact.engine.nodes.role_texts import ROLE_NAMES
from aiact.engine.state import EngineState
from aiact.llm.structured import describe_validation_error
from aiact.schemas import (
    DISCLAIMER,
    ClassificationResult,
    EvidenceTag,
    Fact,
    FollowUpQuestion,
    Language,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.result import derived_status, refused_steps

CLASS_STEPS: Mapping[RiskClass, tuple[StepName, ...]] = {
    RiskClass.OUT_OF_SCOPE: (StepName.SCOPE,),
    RiskClass.PROHIBITED: (StepName.PROHIBITED,),
    RiskClass.HIGH_RISK: (StepName.HIGH_RISK,),
    RiskClass.LIMITED_RISK: (StepName.HIGH_RISK, StepName.TRANSPARENCY),
    RiskClass.MINIMAL_RISK: (StepName.HIGH_RISK, StepName.TRANSPARENCY),
}
"""The steps whose facts set each class; limited and minimal risk fall through the high-risk
check, and the transparency check settles which of the two."""

CLASS_CHECKS = frozenset({StepName.PROHIBITED, StepName.HIGH_RISK})
"""The checks whose open question of law leaves the class itself as the stricter reading; the
transparency check does so only for a limited-risk result."""

LEGAL_REVIEW_CLASSES = frozenset({RiskClass.HIGH_RISK, RiskClass.PROHIBITED})
"""The classes whose results recommend legal review whatever their status (decision 026)."""

CLASS_NAMES: Mapping[Language, Mapping[RiskClass, str]] = {
    Language.EN: {
        RiskClass.OUT_OF_SCOPE: "out of scope",
        RiskClass.PROHIBITED: "prohibited",
        RiskClass.HIGH_RISK: "high-risk",
        RiskClass.LIMITED_RISK: "limited risk",
        RiskClass.MINIMAL_RISK: "minimal risk",
    },
    Language.DE: {
        RiskClass.OUT_OF_SCOPE: "außerhalb des Anwendungsbereichs",
        RiskClass.PROHIBITED: "verboten",
        RiskClass.HIGH_RISK: "Hochrisiko",
        RiskClass.LIMITED_RISK: "begrenztes Risiko",
        RiskClass.MINIMAL_RISK: "minimales Risiko",
    },
}
LEGAL_REVIEW: Mapping[Language, Mapping[str, str]] = {
    Language.EN: {
        "lead": "Have this result reviewed by a lawyer.",
        RiskClass.PROHIBITED: "Have this result reviewed by a lawyer before you use or supply "
        "the system: it is, or is assumed to be, a practice Art. 5 prohibits.",
        RiskClass.HIGH_RISK: "Have this result reviewed by a lawyer: a high-risk system carries "
        "duties with legal consequences.",
        "scope_open": "The law and guidance don't settle whether the AI Act applies, so it is "
        "assumed to apply until a lawyer has reviewed it.",
        "class_open": "The law and guidance don't settle part of the classification, so the "
        "stricter reading ({risk_class}) is assumed until a lawyer has reviewed it.",
        "transparency_open": "The law and guidance don't settle whether an Art. 50 transparency "
        "duty applies, so it is assumed until a lawyer has reviewed it.",
        "role_open": "The law doesn't settle the company's role, so the {role} role is assumed "
        "until a lawyer has reviewed it.",
    },
    Language.DE: {
        "lead": "Lassen Sie dieses Ergebnis anwaltlich prüfen.",
        RiskClass.PROHIBITED: "Lassen Sie dieses Ergebnis anwaltlich prüfen, bevor Sie das "
        "System nutzen oder bereitstellen: Es ist eine nach Art. 5 verbotene Praktik, oder dies "
        "wird angenommen.",
        RiskClass.HIGH_RISK: "Lassen Sie dieses Ergebnis anwaltlich prüfen: Ein "
        "Hochrisiko-System bringt Pflichten mit rechtlicher Tragweite mit sich.",
        "scope_open": "Recht und Leitlinien klären nicht, ob die KI-Verordnung gilt, daher wird "
        "bis zur anwaltlichen Prüfung angenommen, dass sie gilt.",
        "class_open": "Recht und Leitlinien klären einen Teil der Einstufung nicht, daher wird "
        "bis zur anwaltlichen Prüfung die strengere Lesart ({risk_class}) angenommen.",
        "transparency_open": "Recht und Leitlinien klären nicht, ob eine Transparenzpflicht nach "
        "Art. 50 gilt, daher wird sie bis zur anwaltlichen Prüfung angenommen.",
        "role_open": "Das Recht klärt die Rolle des Unternehmens nicht, daher wird bis zur "
        "anwaltlichen Prüfung die Rolle {role} angenommen.",
    },
}
"""The legal-review line: the class's own sentence for a prohibited or high-risk result (or the
plain lead), then one sentence per open question of law naming what is assumed."""


class FinalizeOutputError(ValueError):
    """The steps and findings don't make a contract-valid result (a node broke its contract)."""


def final_class(state: EngineState) -> RiskClass:
    """Out of scope when the scope step ended the run; otherwise the stricter reading the checks
    left (`working_class`)."""
    steps = state.get("steps", ())
    if steps and steps[-1].step is StepName.SCOPE and run_ends_after(state, StepName.SCOPE):
        return RiskClass.OUT_OF_SCOPE
    risk_class, _ = working_class(state)
    return risk_class


def deciding_facts(steps: Sequence[StepResult], risk_class: RiskClass) -> tuple[Fact, ...]:
    """The facts of the steps the outcome rests on (the class's steps, every uncertain step,
    the role step), in check order, each fact once."""
    deciding = {*CLASS_STEPS[risk_class], StepName.ROLE_OBLIGATIONS}
    rests_on = (s for s in steps if s.step in deciding or s.status is not Status.DECIDED)
    by_text = {fact.text: fact for step in rests_on for fact in step.facts_used}
    return tuple(by_text.values())


def _unique_by_id(questions: Iterable[FollowUpQuestion]) -> dict[str, FollowUpQuestion]:
    by_id: dict[str, FollowUpQuestion] = {}
    for question in questions:
        by_id.setdefault(question.id, question)
    return by_id


def follow_up_questions(state: EngineState) -> tuple[FollowUpQuestion, ...]:
    """Every step's missing fact, then the questions the facts node and the checks asked, then
    a confirm question for each assumed fact a step relied on that neither the facts node
    extracted nor a check already asks about (`asked_facts`); each id once (the first kept),
    each confirm question once per fact."""
    steps = state.get("steps", ())
    missing = (step.missing_fact for step in steps if step.missing_fact)
    by_id = _unique_by_id((*missing, *state.get("follow_up_questions", ())))
    asked = {fact.text for fact in state.get("facts", ())} | set(state.get("asked_facts", ()))
    assumed = {
        fact.text: fact
        for step in steps
        for fact in step.facts_used
        if fact.evidence is EvidenceTag.ASSUMED and fact.text not in asked
    }
    for fact in assumed.values():
        question = confirm_question(fact, state["language"], set(by_id))
        by_id[question.id] = question
    return tuple(by_id.values())


def legal_review(
    steps: Sequence[StepResult], risk_class: RiskClass, role: Role | None, language: Language
) -> str | None:
    """The recommendation of legal review for a high-risk, prohibited or legally ambiguous
    result: the class's sentence, then what each open question of law leaves assumed (in check
    order: that the Act applies, the stricter class, an Art. 50 duty, the role)."""
    texts = LEGAL_REVIEW[language]
    opened = {step.step for step in steps if step.status is Status.LEGALLY_AMBIGUOUS}
    # An open Art. 50 question sets the class only for a limited-risk result; on a higher class
    # it leaves a duty assumed, not the class.
    sets_class = CLASS_CHECKS | (
        {StepName.TRANSPARENCY} if risk_class is RiskClass.LIMITED_RISK else set()
    )
    duty_open = StepName.TRANSPARENCY in opened - sets_class
    clauses = (
        *((texts["scope_open"],) if StepName.SCOPE in opened else ()),
        *(
            (texts["class_open"].format(risk_class=CLASS_NAMES[language][risk_class]),)
            if opened & sets_class
            else ()
        ),
        *((texts["transparency_open"],) if duty_open else ()),
        *(
            (texts["role_open"].format(role=ROLE_NAMES[language][role]),)
            if StepName.ROLE_OBLIGATIONS in opened and role is not None
            else ()
        ),
    )
    if risk_class in LEGAL_REVIEW_CLASSES:
        return " ".join((texts[risk_class], *clauses))
    return " ".join((texts["lead"], *clauses)) if clauses else None


def finalize(state: EngineState) -> ClassificationResult:
    """The result of one run: the finalize node for the graph (`EngineNodes(finalize=finalize,
    …)`). Raises `FinalizeOutputError` when the steps and findings break the result contract (a
    check skipped, a missing fact not asked); its message names the fields, never their values."""
    steps: tuple[StepResult, ...] = state.get("steps", ())
    language = state["language"]
    risk_class = final_class(state)
    role = state.get("role")
    is_out = risk_class is RiskClass.OUT_OF_SCOPE
    duties = () if is_out or is_section_b(state) else state.get("transparency_duties", ())
    try:
        return ClassificationResult(
            facts=state.get("facts", ()),
            steps=steps,
            risk_class=risk_class,
            status=derived_status(steps),
            role=role.role if role else None,
            also_role=role.also_role if role else None,
            role_switch_reason=role.role_switch_reason if role else None,
            annex_point=state.get("annex_point"),
            transparency_duties=duties,
            deciding_facts=deciding_facts(steps, risk_class),
            obligations=role.obligations if role else (),
            law_version=state["law_version"],
            as_of=state["as_of"],
            disclaimer=DISCLAIMER[language],
            legal_review=legal_review(steps, risk_class, role.role if role else None, language),
            not_assessed=refused_steps(steps),
            follow_up_questions=follow_up_questions(state),
        )
    except ValidationError as exc:
        message = f"the result breaks its contract: {describe_validation_error(exc)}"
        raise FinalizeOutputError(message) from None
