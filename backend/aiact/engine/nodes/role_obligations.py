"""The role and obligations node: Art. 25 switches, GPAI-based systems, importer and distributor,
and the duties `list_obligations` returns for the settled role and class (E7; INIT > Roles).

The engine model only answers fixed key-fact questions (the prompt in `prompts/role_obligations.md`
comes first, the description last, so the prefix is cached: decision 005). The Act's rules are
applied here, in code:

- A company that builds its own system on a general-purpose AI model is that system's provider,
  and the model provider's own duties are flagged (the informational Art. 53(1)(b) row).
- A deployer, importer or distributor of a high-risk system becomes its provider under Art. 25(1)
  when it rebrands it (a), substantially modifies it (b) or repurposes it into high-risk (c).
  Art. 25 adds the provider's duties; a deployer still uses the system and keeps its own.
- A deciding fact the model can't settle makes the step `needs_more_information`. The labelled
  working assumption is provider plus the base role (deployer when the role itself is unknown),
  so no duty that may apply is dropped. Every unknown fact becomes a follow-up question.

Conditional duties are filtered by their `applies_if`. Rows another finding settles are never
asked of the model: Art. 50 by the transparency step's duties, Art. 5 by the prohibited class,
Art. 6(4) by the high-risk step's Art. 6(3) exemption, the GPAI flag by the GPAI answer. Every
other condition goes to the model. A duty whose condition is "no" is dropped; "yes" and
"unknown" keep it, with its condition shown.

Each step cites the provisions its role rests on (Art. 3 definitions, the Art. 25(1) switch,
Art. 53(1)(b)), quoted from the parsed AI Act until `get_provision` (C5) serves them.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, JsonValue, ValidationError

from aiact.engine.nodes.role_texts import (
    BUILDS_ON_GPAI,
    OPERATOR_ROLE,
    ROLE_ARTICLES,
    ROLE_NAMES,
    SWITCHES,
    TEXTS,
    KeyQuestion,
)
from aiact.engine.state import CheckOutcome, EngineState, RoleFinding
from aiact.llm import chat_model
from aiact.llm.routing import require_setting
from aiact.obligations.list import (
    ObligationTable,
    UnknownLawVersionError,
    default_table,
    list_obligations,
)
from aiact.schemas import (
    Citation,
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
DOWNSTREAM_PROVIDER_ARTICLE = "art:3:68"
EXEMPTION_ARTICLE = "art:6:4"
PROHIBITION_ARTICLE = "art:5:1"
"""Rows whose condition is settled by another finding, not asked of the model."""

ACT_DOCUMENTS: Mapping[LawVersion, str] = {
    LawVersion.ORIGINAL: "ai-act",
    LawVersion.AMENDED: "ai-act-consolidated",
}
"""The manifest key of each AI Act text, as a citation's `document_id`."""


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
    """What the rules give: the role and a role kept next to it, the key question that made the
    company a provider (a switch or GPAI), the deciding facts still missing (the role is then the
    working assumption), other open questions, and the answers relied on."""

    base: Role | None
    role: Role
    also_role: Role | None
    gpai: Answer
    used: tuple[KeyFact | RoleFact, ...]
    made_by: KeyQuestion | None = None
    missing: tuple[KeyQuestion, ...] = ()
    open_questions: tuple[KeyQuestion, ...] = ()

    def switch_reason(self, language: Language) -> str | None:
        """Why the Art. 25 switch to provider applies, when one does."""
        if self.made_by is None or self.made_by is BUILDS_ON_GPAI or self.made_by.reason is None:
            return None
        return self.made_by.reason[language]

    def questions(self) -> tuple[KeyQuestion, ...]:
        """Every unknown fact worth asking, the deciding ones first."""
        return (*self.missing, *self.open_questions)

    def cited_articles(self) -> tuple[str, ...]:
        """The provisions the role rests on: the base role's definition (provider and deployer
        when it is unknown), what made a provider (the Art. 25(1) point, or for a system built on
        a GPAI model the provider and downstream-provider definitions), and the facts an
        assumption waits on."""
        bases = (self.base,) if self.base else (Role.PROVIDER, Role.DEPLOYER)
        if self.made_by is BUILDS_ON_GPAI:
            made: tuple[str, ...] = (ROLE_ARTICLES[Role.PROVIDER], DOWNSTREAM_PROVIDER_ARTICLE)
        else:
            made = (self.made_by.article,) if self.made_by else ()
        waiting = tuple(q.article for q in self.missing if q is not OPERATOR_ROLE)
        return tuple(dict.fromkeys((*(ROLE_ARTICLES[r] for r in bases), *made, *waiting)))


def _kept_role(base: Role | None, *, is_assumed: bool) -> Role | None:
    """The role a company that became (or is assumed to be) the provider keeps: a deployer still
    uses the system, and so is assumed to when its role is unknown; under a working assumption
    an importer or distributor keeps its own duties too."""
    if base is None or base is Role.DEPLOYER:
        return Role.DEPLOYER
    return base if is_assumed else None


def _settlement(
    answer: RoleAnswer,
    role: Role,
    used: tuple[KeyFact | RoleFact, ...],
    made_by: KeyQuestion | None = None,
    missing: tuple[KeyQuestion, ...] = (),
    open_questions: tuple[KeyQuestion, ...] = (),
) -> RoleSettlement:
    base = answer.role.role
    kept = None if role is base else _kept_role(base, is_assumed=bool(missing))
    return RoleSettlement(
        base=base,
        role=role,
        also_role=kept,
        gpai=answer.builds_on_gpai.answer,
        used=used,
        made_by=made_by,
        missing=missing,
        open_questions=open_questions,
    )


def settle_role(answer: RoleAnswer, risk_class: RiskClass) -> RoleSettlement:
    """Apply the GPAI rule and the Art. 25(1) switches to the model's answers."""
    gpai, base = answer.builds_on_gpai.answer, answer.role.role
    used: tuple[KeyFact | RoleFact, ...] = (answer.role, answer.builds_on_gpai)
    gpai_open = (BUILDS_ON_GPAI,) if gpai is Answer.UNKNOWN else ()
    if gpai is Answer.YES:
        # The provider role is settled; with an unknown base, whether it also deploys is not.
        unsettled = (OPERATOR_ROLE,) if base is None else ()
        return _settlement(answer, Role.PROVIDER, used, made_by=BUILDS_ON_GPAI, missing=unsettled)
    if base is None:
        return _settlement(answer, Role.PROVIDER, used, missing=(OPERATOR_ROLE, *gpai_open))
    if base is Role.PROVIDER:
        return _settlement(answer, Role.PROVIDER, used, open_questions=gpai_open)
    unknown: tuple[KeyQuestion, ...] = ()
    if risk_class is RiskClass.HIGH_RISK:
        for field, switch in SWITCHES.items():
            key_fact: KeyFact = getattr(answer, field)
            used = (*used, key_fact)
            if key_fact.answer is Answer.YES:
                return _settlement(
                    answer, Role.PROVIDER, used, made_by=switch, open_questions=gpai_open
                )
            if key_fact.answer is Answer.UNKNOWN:
                unknown = (*unknown, switch)
    missing = (*gpai_open, *unknown)
    if missing:
        return _settlement(answer, Role.PROVIDER, used, missing=missing)
    return _settlement(answer, base, used)


# --- Conditional duties -------------------------------------------------------------------------


def _is_art_5(article: str) -> bool:
    return article == PROHIBITION_ARTICLE or article.startswith(f"{PROHIBITION_ARTICLE}:")


def _is_settled_elsewhere(obligation: Obligation) -> bool:
    """Rows another finding settles: Art. 50 (transparency), Art. 53(1)(b) (the GPAI answer),
    Art. 5 (the class: E4 found the practice) and Art. 6(4) (E5's Art. 6(3) exemption)."""
    article = obligation.article
    return (
        article.startswith(TRANSPARENCY_PREFIX)
        or article in (GPAI_FLAG_ARTICLE, EXEMPTION_ARTICLE)
        or _is_art_5(article)
    )


def conditions_to_ask(
    risk_class: RiskClass,
    route: HighRiskRoute | None,
    law_version: LawVersion,
    table: ObligationTable | None = None,
) -> tuple[str, ...]:
    """The distinct conditions of every role's duties at this class, in table order, less those
    another finding settles; empty when the table doesn't hold `law_version`. Asked before the
    role is known, in one call."""
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


class Kept(StrEnum):
    """Whether a listed duty stays, and why not when it doesn't."""

    YES = "yes"
    CONDITION_NOT_MET = "condition_not_met"
    NOT_FOUND = "not_found"
    """Another check settles the row and didn't report it (or hasn't run: E5, E6)."""


def _found(is_found: bool) -> Kept:
    return Kept.YES if is_found else Kept.NOT_FOUND


def _kept(
    obligation: Obligation, answers: Mapping[str, Answer], state: EngineState, gpai: Answer
) -> Kept:
    if obligation.applies_if is None:
        return Kept.YES
    article = obligation.article
    if article.startswith(TRANSPARENCY_PREFIX):
        return _found(article in state.get("transparency_duties", ()))
    if article == EXEMPTION_ARTICLE:
        return _found(state.get("annex_iii_exempt", False))
    if article == GPAI_FLAG_ARTICLE:
        is_met = gpai is not Answer.NO
    elif _is_art_5(article):
        is_met = True  # listed only for the prohibited class, which E4's finding settled
    else:
        is_met = answers.get(obligation.applies_if, Answer.UNKNOWN) is not Answer.NO
    return Kept.YES if is_met else Kept.CONDITION_NOT_MET


# --- Citations ----------------------------------------------------------------------------------


class ProvisionTextError(LookupError):
    """A provision the step cites has no text in the parsed AI Act."""


@cache
def _provision_texts(path: Path) -> Mapping[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line.strip()]
        return {row["provision_id"]: row["text"] for row in rows}
    except OSError as error:
        raise ProvisionTextError(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ProvisionTextError(f"{path}: line {error.lineno} is not valid JSON") from error
    except (KeyError, TypeError) as error:
        raise ProvisionTextError(f"{path}: a row lacks provision_id or text ({error})") from error


def citations(
    articles: Sequence[str], law_version: LawVersion, language: Language, data_dir: Path
) -> tuple[Citation, ...]:
    """Citations quoting `articles` from the parsed AI Act text of `law_version`.

    A stopgap until `get_provision` (C5) serves the same text from the corpus. The document id is
    the manifest key, which the citation check expects (V2).
    """
    doc_key = ACT_DOCUMENTS[law_version]
    texts = _provision_texts(data_dir / "parsed" / f"{doc_key}.{language.value}.jsonl")
    missing = [article for article in articles if article not in texts]
    if missing:
        raise ProvisionTextError(f"{doc_key}.{language.value} has no {', '.join(missing)}")
    return tuple(
        Citation(
            provision_id=article,
            document_id=doc_key,
            law_version=law_version,
            language=language,
            quote=texts[article],
        )
        for article in articles
    )


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


def _decision(settled: RoleSettlement, language: Language, summary: Sequence[str]) -> str:
    names, texts = ROLE_NAMES[language], TEXTS[language]
    also = settled.also_role
    sentences = [
        texts["role"].format(role=names[settled.role])
        if also is None
        else texts["role_also"].format(role=names[settled.role], also=names[also])
    ]
    if settled.made_by and settled.made_by.reason:
        sentences.append(settled.made_by.reason[language])
    if settled.missing:
        question = settled.missing[0].question[language]
        sentences.append(texts["assumption"].format(question=question))
    return " ".join((*sentences, *summary))


def to_outcome(
    answer: RoleAnswer,
    state: EngineState,
    table: ObligationTable | None = None,
    data_dir: Path | None = None,
) -> CheckOutcome:
    """The role_obligations step and its finding, from the model's answer and the state.
    `data_dir` holds the parsed AI Act the citations quote (default: the settings')."""
    language = state["language"]
    risk_class, _ = working_class(state)
    settled = settle_role(answer, risk_class)
    missing = settled.missing[0] if settled.missing else None
    obligations, summary = select_obligations(answer, state, settled, table)
    source = data_dir or get_settings().aiact_data_dir
    step = StepResult(
        step=StepName.ROLE_OBLIGATIONS,
        decision=_decision(settled, language, summary),
        facts_used=_facts_used(settled.used, state.get("facts", ())),
        citations=citations(settled.cited_articles(), state["law_version"], language, source),
        status=Status.NEEDS_MORE_INFORMATION if missing else Status.DECIDED,
        missing_fact=_question(missing, language) if missing else None,
    )
    finding = RoleFinding(
        role=settled.role,
        also_role=settled.also_role,
        role_switch_reason=settled.switch_reason(language),
        obligations=obligations,
    )
    questions = tuple(_question(key, language) for key in settled.questions())
    return CheckOutcome(step=step, role=finding, follow_up_questions=questions)


def select_obligations(
    answer: RoleAnswer,
    state: EngineState,
    settled: RoleSettlement,
    table: ObligationTable | None = None,
) -> tuple[tuple[Obligation, ...], tuple[str, ...]]:
    """The duties of the settled role and the role it keeps, less those whose condition doesn't
    apply, and the sentences that summarise them for the step's decision."""
    language, law_version = state["language"], state["law_version"]
    risk_class, route = working_class(state)
    texts = TEXTS[language]
    roles = (settled.role, *((settled.also_role,) if settled.also_role else ()))
    try:
        lists = [list_obligations(role, risk_class, route, law_version, table) for role in roles]
    except UnknownLawVersionError:
        held = (table or default_table()).law_version.value
        return (), (texts["no_table"].format(version=held, asked=law_version.value),)
    listed = tuple(dict.fromkeys(o for duties in lists for o in duties.obligations))
    ids = condition_ids(conditions_to_ask(risk_class, route, law_version, table))
    by_id = {given.id: given.answer for given in answer.conditions}
    answers = {condition: by_id.get(cid, Answer.UNKNOWN) for condition, cid in ids.items()}
    verdicts = [(o, _kept(o, answers, state, settled.gpai)) for o in listed]
    kept = tuple(o for o, verdict in verdicts if verdict is Kept.YES)
    version = lists[0].law_version.value
    counts = {v: sum(verdict is v for _, verdict in verdicts) for v in Kept if v is not Kept.YES}
    summary = (
        texts["duties"].format(count=len(kept), risk_class=risk_class.value, version=version),
        *(texts[verdict.value].format(count=count) for verdict, count in counts.items() if count),
    )
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
        self._data_dir = settings.aiact_data_dir

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
        return to_outcome(answer, state, self._table, self._data_dir)
