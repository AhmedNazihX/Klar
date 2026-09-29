"""The role and obligations node: Art. 25 switches, GPAI-based systems, importer and distributor,
and the duties `list_obligations` returns for the settled role and class (E7; INIT > Roles).

The engine model only answers fixed key-fact questions (the prompt in `prompts/role_obligations.md`
comes first, the description last, so the prefix is cached: decision 005). The Act's rules are
applied here, in code:

- A company that builds its own system on a general-purpose AI model is that system's provider,
  and the model provider's own duties are flagged (the informational Art. 53(1)(b) row).
- A deployer, importer or distributor of a high-risk system becomes its provider under Art. 25(1)
  when it rebrands it (a), substantially modifies it (b) or repurposes it into high-risk (c).
- A deciding fact the model can't settle makes the step `needs_more_information`, with provider,
  the role with the most duties, as the labelled working assumption.

Conditional duties are filtered by their `applies_if`: Art. 50 rows by the transparency step's
findings, the GPAI flag by the GPAI answer, every other condition by the model's answer. A duty
whose condition is "no" is dropped; "yes" and "unknown" keep it, with its condition shown.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, JsonValue, ValidationError

from aiact.engine.state import CheckOutcome, EngineState, RoleFinding
from aiact.llm import chat_model
from aiact.llm.routing import require_setting
from aiact.obligations.list import (
    ObligationTable,
    UnknownLawVersionError,
    list_obligations,
)
from aiact.schemas import (
    EvidenceTag,
    Fact,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    Obligation,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.base import ContractModel
from aiact.settings import Settings, get_settings

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "role_obligations.md"
ROLE_INSTRUCTIONS = PROMPT_PATH.read_text(encoding="utf-8")

MAX_OUTPUT_TOKENS = 3000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005)."""

TRANSPARENCY_PREFIX = "art:50:"
GPAI_FLAG_ARTICLE = "art:53:1:b"
"""Rows whose condition is settled by another finding, not asked of the model."""


class Answer(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class KeyFact(ContractModel):
    """One key-fact answer. Enum fields carry no description: strict structured output rejects
    keywords next to a `$ref`; the prompt explains every field instead."""

    answer: Answer
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class RoleFact(ContractModel):
    """The company's own role before any switch; None when the description doesn't say."""

    role: Role | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class ConditionAnswer(ContractModel):
    id: str
    answer: Answer


class RoleAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill."""

    role: RoleFact
    builds_on_gpai: KeyFact
    own_brand: KeyFact
    substantial_modification: KeyFact
    changed_purpose: KeyFact
    conditions: tuple[ConditionAnswer, ...]


class RoleOutputError(ValueError):
    """The model's answer doesn't fit `RoleAnswer` (a broken output)."""


# --- Fixed texts: stable question ids, EN and DE ------------------------------------------------


@dataclass(frozen=True)
class KeyQuestion:
    """A deciding fact: its follow-up question and, when a "yes" makes a provider, why."""

    id: str
    article: str
    question: Mapping[Language, str]
    reason: Mapping[Language, str] | None = None


OPERATOR_ROLE = KeyQuestion(
    id="operator_role",
    article="art:3:3",
    question={
        Language.EN: "Does your company develop the system, use a system someone else provides, "
        "import it into the EU, or distribute it?",
        Language.DE: "Entwickelt Ihr Unternehmen das System, nutzt es ein System eines anderen "
        "Anbieters, führt es das System in die EU ein oder vertreibt es es?",
    },
)
BUILDS_ON_GPAI = KeyQuestion(
    id="builds_on_gpai",
    article="art:53:1:b",
    question={
        Language.EN: "Is the system built on a general-purpose AI model from another provider "
        "(for example a foundation model integrated through an API)?",
        Language.DE: "Beruht das System auf einem KI-Modell mit allgemeinem Verwendungszweck eines "
        "anderen Anbieters (zum Beispiel ein über eine API eingebundenes Basismodell)?",
    },
    reason={
        Language.EN: "It builds its own system on a general-purpose AI model, so it is the "
        "provider of that system; the model provider's own duties (Art. 53) are flagged.",
        Language.DE: "Es baut ein eigenes System auf einem KI-Modell mit allgemeinem "
        "Verwendungszweck auf und ist daher dessen Anbieter; die eigenen Pflichten des "
        "Modellanbieters (Art. 53) werden ausgewiesen.",
    },
)
SWITCHES: Mapping[str, KeyQuestion] = {
    "own_brand": KeyQuestion(
        id="own_brand",
        article="art:25:1:a",
        question={
            Language.EN: "Do you put your own name or trademark on the system?",
            Language.DE: "Bringen Sie Ihren eigenen Namen oder Ihre Marke auf dem System an?",
        },
        reason={
            Language.EN: "Art. 25(1)(a): it puts its own name or trademark on the high-risk "
            "system, so it is considered its provider.",
            Language.DE: "Art. 25 Abs. 1 Buchst. a: Es bringt seinen Namen oder seine Marke auf "
            "dem Hochrisiko-System an und gilt daher als dessen Anbieter.",
        },
    ),
    "substantial_modification": KeyQuestion(
        id="substantial_modification",
        article="art:25:1:b",
        question={
            Language.EN: "Have you changed the system beyond the provider's configuration "
            "options, for example by retraining it or changing how it decides?",
            Language.DE: "Haben Sie das System über die Einstellmöglichkeiten des Anbieters "
            "hinaus verändert, zum Beispiel neu trainiert oder seine Entscheidungslogik geändert?",
        },
        reason={
            Language.EN: "Art. 25(1)(b): it substantially modifies the high-risk system, so it "
            "is considered its provider.",
            Language.DE: "Art. 25 Abs. 1 Buchst. b: Es nimmt eine wesentliche Veränderung am "
            "Hochrisiko-System vor und gilt daher als dessen Anbieter.",
        },
    ),
    "changed_purpose": KeyQuestion(
        id="changed_purpose",
        article="art:25:1:c",
        question={
            Language.EN: "Do you use the system for a purpose its provider did not intend?",
            Language.DE: "Nutzen Sie das System für einen Zweck, den sein Anbieter nicht "
            "vorgesehen hat?",
        },
        reason={
            Language.EN: "Art. 25(1)(c): it uses the system for a new purpose that makes it "
            "high-risk, so it is considered its provider.",
            Language.DE: "Art. 25 Abs. 1 Buchst. c: Es ändert die Zweckbestimmung so, dass das "
            "System hochriskant wird, und gilt daher als dessen Anbieter.",
        },
    ),
}
"""The Art. 25(1) switches, in the order of the Act; keys are `RoleAnswer` fields."""

ROLE_NAMES: Mapping[Language, Mapping[Role, str]] = {
    Language.EN: {role: role.value for role in Role},
    Language.DE: {
        Role.PROVIDER: "Anbieter",
        Role.DEPLOYER: "Betreiber",
        Role.IMPORTER: "Einführer",
        Role.DISTRIBUTOR: "Händler",
    },
}
TEXTS: Mapping[Language, Mapping[str, str]] = {
    Language.EN: {
        "role": "Role: {role}.",
        "assumption": "Working assumption: provider, pending an answer to: {question}",
        "duties": "{count} duties listed for a {risk_class} system ({version} text).",
        "dropped": "{count} conditional duties left out because their condition doesn't apply.",
        "no_table": "No duties listed: the obligations table covers only the {version} text.",
    },
    Language.DE: {
        "role": "Rolle: {role}.",
        "assumption": "Arbeitsannahme: Anbieter, bis diese Frage beantwortet ist: {question}",
        "duties": "{count} Pflichten für ein System der Klasse {risk_class} ({version} Fassung).",
        "dropped": "{count} bedingte Pflichten entfallen, weil ihre Bedingung nicht erfüllt ist.",
        "no_table": "Keine Pflichten aufgeführt: Die Pflichtentabelle deckt nur die "
        "{version} Fassung ab.",
    },
}


# --- The class the earlier checks settled -----------------------------------------------------


def working_class(state: EngineState) -> tuple[RiskClass, HighRiskRoute | None]:
    """The class so far: an Art. 5 match that didn't end the run keeps prohibited (the stricter
    reading, decision 010); then high-risk on its route; then Art. 50 duties; else minimal."""
    if StepName.PROHIBITED in state.get("matches", ()):
        return RiskClass.PROHIBITED, None
    route = state.get("high_risk_route")
    if route is not None:
        return RiskClass.HIGH_RISK, route
    if state.get("transparency_duties"):
        return RiskClass.LIMITED_RISK, None
    return RiskClass.MINIMAL_RISK, None


# --- Settling the role --------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleSettlement:
    """The role the rules give, the key question that made it (a switch or GPAI), the deciding
    facts still missing (the role is then the working assumption) and the answers relied on."""

    role: Role
    made_by: KeyQuestion | None
    missing: tuple[KeyQuestion, ...]
    used: tuple[KeyFact | RoleFact, ...]

    @property
    def is_gpai_based(self) -> bool:
        return self.made_by is BUILDS_ON_GPAI

    def switch_reason(self, language: Language) -> str | None:
        """Why the Art. 25 switch to provider applies, when one does."""
        if self.made_by is None or self.is_gpai_based or self.made_by.reason is None:
            return None
        return self.made_by.reason[language]


def settle_role(answer: RoleAnswer, risk_class: RiskClass) -> RoleSettlement:
    """Apply the GPAI rule and the Art. 25(1) switches to the model's answers."""
    gpai = answer.builds_on_gpai
    used: tuple[KeyFact | RoleFact, ...] = (answer.role, gpai)
    if gpai.answer is Answer.YES:
        return RoleSettlement(Role.PROVIDER, BUILDS_ON_GPAI, (), used)
    base = answer.role.role
    if base is None:
        return RoleSettlement(Role.PROVIDER, None, (OPERATOR_ROLE,), used)
    missing: tuple[KeyQuestion, ...] = ()
    if base is not Role.PROVIDER and risk_class is RiskClass.HIGH_RISK:
        for field, switch in SWITCHES.items():
            key_fact: KeyFact = getattr(answer, field)
            used = (*used, key_fact)
            if key_fact.answer is Answer.YES:
                return RoleSettlement(Role.PROVIDER, switch, (), used)
            if key_fact.answer is Answer.UNKNOWN:
                missing = (*missing, switch)
    if gpai.answer is Answer.UNKNOWN and base is not Role.PROVIDER:
        missing = (BUILDS_ON_GPAI, *missing)
    return RoleSettlement(Role.PROVIDER if missing else base, None, missing, used)


# --- Conditional duties -------------------------------------------------------------------------


def _is_settled_elsewhere(obligation: Obligation) -> bool:
    return obligation.article.startswith(TRANSPARENCY_PREFIX) or (
        obligation.article == GPAI_FLAG_ARTICLE
    )


def conditions_to_ask(
    risk_class: RiskClass,
    route: HighRiskRoute | None,
    law_version: LawVersion,
    table: ObligationTable | None = None,
) -> tuple[str, ...]:
    """The distinct conditions of every role's duties at this class, in table order; empty when
    the table doesn't hold `law_version`. Asked before the role is known, in one call."""
    try:
        lists = [list_obligations(role, risk_class, route, law_version, table) for role in Role]
    except UnknownLawVersionError:
        return ()
    conditions = (
        o.applies_if
        for listed in lists
        for o in listed.obligations
        if o.applies_if and not _is_settled_elsewhere(o)
    )
    return tuple(dict.fromkeys(conditions))


def condition_ids(conditions: Sequence[str]) -> dict[str, str]:
    """`c1`, `c2`, … for each condition, as the prompt lists them."""
    return {condition: f"c{number}" for number, condition in enumerate(conditions, 1)}


def _applies(
    obligation: Obligation,
    answers: Mapping[str, Answer],
    transparency_duties: tuple[str, ...],
    is_gpai_based: bool,
) -> bool:
    if obligation.applies_if is None:
        return True
    if obligation.article.startswith(TRANSPARENCY_PREFIX):
        return obligation.article in transparency_duties
    if obligation.article == GPAI_FLAG_ARTICLE:
        return is_gpai_based
    return answers.get(obligation.applies_if, Answer.UNKNOWN) is not Answer.NO


# --- The step -----------------------------------------------------------------------------------


def _facts_used(used: Sequence[KeyFact | RoleFact], facts: Sequence[Fact]) -> tuple[Fact, ...]:
    """The extracted facts an answer cites, or the answer itself as an inferred or assumed fact
    (a stated fact must point into the description, and only the facts node sets spans)."""
    result: dict[str, Fact] = {}
    for key_fact in used:
        if isinstance(key_fact, KeyFact) and key_fact.answer is Answer.UNKNOWN:
            continue
        cited = [facts[n - 1] for n in key_fact.fact_numbers if 0 < n <= len(facts)]
        if cited and key_fact.evidence is not EvidenceTag.ASSUMED:
            result.update((fact.text, fact) for fact in cited)
            continue
        is_assumed = key_fact.evidence is EvidenceTag.ASSUMED
        evidence = EvidenceTag.ASSUMED if is_assumed else EvidenceTag.INFERRED
        result.setdefault(key_fact.fact, Fact(text=key_fact.fact, evidence=evidence))
    return tuple(result.values())


def _question(key: KeyQuestion, language: Language) -> FollowUpQuestion:
    return FollowUpQuestion(id=key.id, text=key.question[language], about=key.article)


def to_outcome(
    answer: RoleAnswer, state: EngineState, table: ObligationTable | None = None
) -> CheckOutcome:
    """The role_obligations step and its finding, from the model's answer and the state."""
    language = state["language"]
    risk_class, _ = working_class(state)
    settled = settle_role(answer, risk_class)
    texts = TEXTS[language]
    missing = settled.missing[0] if settled.missing else None
    made_by = settled.made_by
    obligations, summary = select_obligations(answer, state, settled, table)
    decision = (
        texts["role"].format(role=ROLE_NAMES[language][settled.role]),
        *((made_by.reason[language],) if made_by and made_by.reason else ()),
        *((texts["assumption"].format(question=missing.question[language]),) if missing else ()),
        *summary,
    )
    step = StepResult(
        step=StepName.ROLE_OBLIGATIONS,
        decision=" ".join(decision),
        facts_used=_facts_used(settled.used, state.get("facts", ())),
        status=Status.NEEDS_MORE_INFORMATION if missing else Status.DECIDED,
        missing_fact=_question(missing, language) if missing else None,
    )
    finding = RoleFinding(
        role=settled.role,
        role_switch_reason=settled.switch_reason(language),
        obligations=obligations,
    )
    return CheckOutcome(step=step, role=finding)


def select_obligations(
    answer: RoleAnswer,
    state: EngineState,
    settled: RoleSettlement,
    table: ObligationTable | None = None,
) -> tuple[tuple[Obligation, ...], tuple[str, ...]]:
    """The settled role's duties, less those whose condition doesn't apply, and the sentences
    that summarise them for the step's decision."""
    language, law_version = state["language"], state["law_version"]
    risk_class, route = working_class(state)
    texts = TEXTS[language]
    try:
        listed = list_obligations(settled.role, risk_class, route, law_version, table)
    except UnknownLawVersionError:
        return (), (texts["no_table"].format(version=LawVersion.AMENDED.value),)
    ids = condition_ids(conditions_to_ask(risk_class, route, law_version, table))
    by_id = {given.id: given.answer for given in answer.conditions}
    answers = {condition: by_id.get(cid, Answer.UNKNOWN) for condition, cid in ids.items()}
    duties = state.get("transparency_duties", ())
    kept = tuple(
        o for o in listed.obligations if _applies(o, answers, duties, settled.is_gpai_based)
    )
    version = listed.law_version.value
    summary = (
        texts["duties"].format(count=len(kept), risk_class=risk_class.value, version=version),
    )
    dropped = len(listed.obligations) - len(kept)
    if dropped:
        summary = (*summary, texts["dropped"].format(count=dropped))
    return kept, summary


# --- The model call -----------------------------------------------------------------------------


def _all_required(schema: JsonValue) -> JsonValue:
    """`schema` with every object's properties required, as OpenAI-style structured output
    demands; optional fields stay nullable. (Same rule as `aiact.eval.baselines.all_required`.)"""
    if isinstance(schema, list):
        return [_all_required(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    updated = {key: _all_required(value) for key, value in schema.items()}
    properties = schema.get("properties")
    if isinstance(properties, dict):
        updated["required"] = list(properties)
    return updated


def _response_format(name: str, model: type[BaseModel]) -> dict[str, object]:
    schema = _all_required(model.model_json_schema())
    return {"type": "json_schema", "json_schema": {"name": name, "schema": schema}}


ROLE_RESPONSE_FORMAT = _response_format("role_answer", RoleAnswer)


def _describe(exc: ValidationError) -> str:
    """The validation errors by location and message, without the input values they quote."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'answer'}: {error['msg']}"
        for error in exc.errors()
    )


def role_messages(state: EngineState, conditions: Sequence[str]) -> list[BaseMessage]:
    """The fixed instructions first; the per-case context next; the description last (005)."""
    risk_class, route = working_class(state)
    shown_class = risk_class.value + (f" ({route.value} route)" if route else "")
    steps = "\n".join(f"- {s.step.value}: {s.decision}" for s in state.get("steps", ())) or "-"
    listed = "\n".join(f"{cid}: {text}" for text, cid in condition_ids(conditions).items()) or "-"
    given = "\n".join(f"- {qid}: {text}" for qid, text in state["answers"].items()) or "-"
    facts = state.get("facts", ())
    numbered = "\n".join(f"{n}. [{f.evidence.value}] {f.text}" for n, f in enumerate(facts, 1))
    return [
        SystemMessage(ROLE_INSTRUCTIONS),
        HumanMessage(
            f"Language for facts: {state['language'].value}\n\n"
            f"Risk class so far: {shown_class}\n\n"
            f"Earlier checks:\n{steps}\n\n"
            f"Conditions:\n{listed}\n\n"
            f"Answers to earlier questions:\n{given}\n\n"
            f"Facts:\n{numbered or '-'}\n\n"
            f"Description:\n{state['description']}"
        ),
    ]


class RoleObligationsCheck:
    """The role_obligations node for the graph: `checks={StepName.ROLE_OBLIGATIONS: …}`."""

    def __init__(
        self,
        settings: Settings | None = None,
        chat: BaseChatModel | None = None,
        table: ObligationTable | None = None,
    ) -> None:
        """`chat` replaces the OpenRouter model and `table` the committed obligations (tests).
        Raises `LLMConfigError` when `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set:
        the model is always pinned to its EU endpoint with fallbacks off (decision 005)."""
        settings = settings or get_settings()
        model_id = require_setting(settings.engine_model, "ENGINE_MODEL")
        provider = require_setting(settings.engine_provider, "ENGINE_PROVIDER")
        self._model = chat or chat_model(
            model=model_id,
            provider_order=[provider],
            allow_fallbacks=False,
            max_tokens=MAX_OUTPUT_TOKENS,
            settings=settings,
        )
        self._table = table

    def __call__(self, state: EngineState) -> CheckOutcome:
        """Raises `RoleOutputError` when the reply doesn't fit `RoleAnswer`."""
        risk_class, route = working_class(state)
        conditions = conditions_to_ask(risk_class, route, state["law_version"], self._table)
        reply = self._model.invoke(
            role_messages(state, conditions), response_format=ROLE_RESPONSE_FORMAT
        )
        try:
            answer = RoleAnswer.model_validate_json(reply.text)
        except ValidationError as exc:
            message = f"role answer doesn't fit the schema: {_describe(exc)}"
            raise RoleOutputError(message) from exc
        return to_outcome(answer, state, self._table)
