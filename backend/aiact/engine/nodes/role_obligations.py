"""The role and obligations node: Art. 25 switches, GPAI-based systems, importer and distributor,
and the duties `list_obligations` returns for the settled role and class (E7; INIT > Roles).

The engine model only answers fixed key-fact questions (the prompt in `prompts/role_obligations.md`
comes first, the description last, so the prefix is cached: decision 005). The Act's rules are
applied here, in code:

- A company that builds its own system on a general-purpose AI model is that system's provider,
  and the model provider's own duties are flagged (the informational Art. 53(1)(b) row).
- A deployer, importer or distributor of a high-risk system becomes its provider under Art. 25(1)
  when it rebrands (a), substantially modifies (b) or repurposes it into high-risk (c). Every
  switch that applies is reported with its citation, next to the GPAI rule too; (b) and (c)
  exclude each other by the original system's class, (a) joins either (user, 2026-10-06).
- A deciding fact the model can't settle makes the step `needs_more_information`. The labelled
  working assumption is provider plus the base role (deployer when the role itself is unknown),
  so no duty that may apply is dropped. Every unknown fact becomes a follow-up question.
- A question the law leaves open with the facts known makes the step `legally_ambiguous`, with
  the same working assumption: own name on a system that isn't high-risk (Art. 3(3), own-d-05),
  or a change whose description says what the provider's documentation foresees but which may or
  may not be a substantial modification (Art. 3(23), user, 2026-10-06, own-d-12).
- A system that is high-risk as an Annex I Section B product gets no AI Act duties (Art. 2(2)).
- Under the original text the duties are not modelled (decision 020, E11): the step says so and
  lists none, and asks neither the conditions nor the Art. 111(2) facts.
- A reply the provider's content filter refused (decision 029) is not assessed: provider, keeping
  the deployer duties, is the working assumption until a person reviews the description.

Conditional duties are filtered by their `applies_if`. Rows another finding settles are never
asked of the model: Art. 50 by the transparency step's duties, Art. 5 by the prohibited class,
Art. 6(4) by the high-risk step's Art. 6(3) exemption, the GPAI flag by the GPAI answer. Every
other condition goes to the model. A duty whose condition is "no" is dropped; "yes" and
"unknown" keep it, with its condition shown.

A high-risk system also gets the Art. 111(2) key facts (C7b, decision 022; `role_legacy`), asked
only for a high-risk system. Each step cites the provisions its role rests on (Art. 3, the Art.
25(1) switches, Art. 53(1)(b)), quoted from the parsed AI Act until `get_provision` (C5).
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import Field, ValidationError

from aiact.dates import long_date
from aiact.engine.nodes.common import facts_section, refused_check
from aiact.engine.nodes.high_risk import SECTION_B_PREFIX
from aiact.engine.nodes.key_facts import Answer, KeyFact, ShortTexts, facts_used
from aiact.engine.nodes.questions import ask, open_question
from aiact.engine.nodes.role_legacy import (
    LegacyAnswer,
    LegacySettlement,
    legacy_summary,
    settle_legacy,
)
from aiact.engine.nodes.role_texts import (
    BUILDS_ON_GPAI,
    OPERATOR_ROLE,
    OWN_NAME,
    OWN_NAME_OPEN,
    PERSON_REVIEW,
    ROLE_ARTICLES,
    ROLE_NAMES,
    SUBSTANTIAL_MODIFICATION_OPEN,
    SWITCHES,
    TEXTS,
    KeyQuestion,
    OpenInLaw,
    open_in_law_parts,
)
from aiact.engine.state import CheckOutcome, EngineState, RoleFinding
from aiact.llm import engine_chat_model
from aiact.llm.structured import (
    ProviderRefusalError,
    describe_validation_error,
    json_schema_format,
    parse_reply,
)
from aiact.obligations.list import (
    CHAPTER_III_DATES,
    ObligationTable,
    UnknownLawVersionError,
    default_table,
    list_obligations,
)
from aiact.schemas import (
    Citation,
    EvidenceTag,
    HighRiskRoute,
    Language,
    LawVersion,
    Obligation,
    OpenQuestion,
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
LEGACY_PROMPT_PATH = PROMPT_PATH.with_name("role_obligations_legacy.md")
LEGACY_INSTRUCTIONS = LEGACY_PROMPT_PATH.read_text(encoding="utf-8")
"""The Art. 111(2) section of the per-case message, for a high-risk system; `{date}` is its
route's Chapter III date."""

MAX_OUTPUT_TOKENS = 4000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005). E7's
recordings used up to 2206 of 3000 (1549 on reasoning, own-d-08), and E8's contested answer
adds a question of law to weigh, so the cap was raised before re-recording (X2's note)."""

TRANSPARENCY_PREFIX = "art:50:"
GPAI_FLAG_ARTICLE = "art:53:1:b"
DOWNSTREAM_PROVIDER_ARTICLE = "art:3:68"
EXEMPTION_ARTICLE = "art:6:4"
PROHIBITION_ARTICLE = "art:5:1"
"""Rows whose condition is settled by another finding, not asked of the model."""

OWN_NAME_CLASSES = frozenset({RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK})
"""The classes where own-name placement makes the role legally ambiguous under Art. 3(3)."""

SECTION_B_ARTICLE = "art:2:2"
"""Cited when an Annex I Section B product gets no AI Act duties."""
MODIFICATION_FIELD = "substantial_modification"
"""The `RoleAnswer` field of Art. 25(1)(b), the switch whose answer can be contested."""

ACT_DOCUMENTS: Mapping[LawVersion, str] = {
    LawVersion.ORIGINAL: "ai-act",
    LawVersion.AMENDED: "ai-act-consolidated",
}
"""The manifest key of each AI Act text, as a citation's `document_id`."""


class RoleFact(ShortTexts):
    """The company's own role before any switch; None when the description doesn't say."""

    role: Role | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]

    @property
    def is_known(self) -> bool:
        """Always shown: an unknown role is itself a fact the step rests on."""
        return True


class Modification(StrEnum):
    """The Art. 25(1)(b) answer; `contested` means the facts are known but the law leaves open
    whether the change is a substantial modification."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"
    CONTESTED = "contested"


class ModificationFact(ShortTexts):
    """The Art. 25(1)(b) key fact. Enum fields carry no description: strict structured output
    rejects keywords next to a `$ref`; the prompt explains every field instead."""

    answer: Modification
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]

    @property
    def is_known(self) -> bool:
        return self.answer is not Modification.UNKNOWN


class ConditionAnswer(ContractModel):
    id: str
    answer: Answer


class RoleAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill."""

    role: RoleFact
    builds_on_gpai: KeyFact
    own_brand: KeyFact
    substantial_modification: ModificationFact
    changed_purpose: KeyFact
    conditions: tuple[ConditionAnswer, ...]


class HighRiskRoleAnswer(RoleAnswer):
    """The answer for a high-risk system: the role facts and the Art. 111(2) facts."""

    legacy: LegacyAnswer


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
    """What the rules give: the role and a role kept next to it, the key questions that made the
    company a provider (the Art. 25(1) switches that apply, or GPAI), the deciding facts still
    missing (the role is then the working assumption), other open questions, the question the
    law leaves open (the role is then the working assumption too), and the answers relied on."""

    base: Role | None
    role: Role
    also_role: Role | None
    gpai: Answer
    used: tuple[KeyFact | ModificationFact | RoleFact, ...]
    made_by: tuple[KeyQuestion, ...] = ()
    missing: tuple[KeyQuestion, ...] = ()
    open_questions: tuple[KeyQuestion, ...] = ()
    open_in_law: OpenInLaw | None = None

    @property
    def is_ambiguous(self) -> bool:
        return self.open_in_law is not None

    def switch_reason(self, language: Language) -> str | None:
        """Why the Art. 25 switches to provider apply, one sentence each, when any does."""
        reasons = (q.reason[language] for q in self.made_by if q is not BUILDS_ON_GPAI and q.reason)
        return " ".join(reasons) or None

    def questions(self) -> tuple[KeyQuestion, ...]:
        """Every unknown fact worth asking, the deciding ones first."""
        return (*self.missing, *self.open_questions)

    def cited_articles(self) -> tuple[str, ...]:
        """The provisions the role rests on: the base role's definition (provider and deployer
        when it is unknown), the provisions of an open question of law, what made a provider
        (each Art. 25(1) point that applies, or for a system built on a GPAI model the provider
        and downstream-provider definitions), and the facts an assumption waits on."""
        bases = (self.base,) if self.base else (Role.PROVIDER, Role.DEPLOYER)
        gpai = (ROLE_ARTICLES[Role.PROVIDER], DOWNSTREAM_PROVIDER_ARTICLE)
        made = tuple(q.article for q in self.made_by if q is not BUILDS_ON_GPAI)
        made = (*made, *(gpai if BUILDS_ON_GPAI in self.made_by else ()))
        waiting = tuple(q.article for q in self.missing if q is not OPERATOR_ROLE)
        opened = self.open_in_law.articles if self.open_in_law else ()
        cited = (*(ROLE_ARTICLES[r] for r in bases), *opened, *made, *waiting)
        return tuple(dict.fromkeys(cited))

    def open_question(self, language: Language, cited: Sequence[Citation]) -> OpenQuestion | None:
        """The question the law leaves open, both readings quoting the step's `cited`."""
        if self.open_in_law is None or self.base is None:
            return None
        return open_question(*open_in_law_parts(self.open_in_law, self.base, language), cited)


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
    used: tuple[KeyFact | ModificationFact | RoleFact, ...],
    made_by: tuple[KeyQuestion, ...] = (),
    missing: tuple[KeyQuestion, ...] = (),
    open_questions: tuple[KeyQuestion, ...] = (),
    open_in_law: OpenInLaw | None = None,
) -> RoleSettlement:
    base = answer.role.role
    is_assumed = bool(missing) or open_in_law is not None
    kept = None if role is base else _kept_role(base, is_assumed=is_assumed)
    return RoleSettlement(
        base=base,
        role=role,
        also_role=kept,
        gpai=answer.builds_on_gpai.answer,
        used=used,
        made_by=made_by,
        missing=missing,
        open_questions=open_questions,
        open_in_law=open_in_law,
    )


def settle_role(answer: RoleAnswer, risk_class: RiskClass) -> RoleSettlement:
    """Apply the GPAI rule and the Art. 25(1) switches to the model's answers."""
    gpai, base = answer.builds_on_gpai.answer, answer.role.role
    used: tuple[KeyFact | ModificationFact | RoleFact, ...] = (answer.role, answer.builds_on_gpai)
    gpai_open = (BUILDS_ON_GPAI,) if gpai is Answer.UNKNOWN else ()
    if gpai is Answer.YES:
        # The provider role is settled; with an unknown base, whether it also deploys is not.
        # A high-risk system's Art. 25(1) switches are reported too (own-d-03: a repurposed GPAI
        # system is a provider under (c), and the model provider's duties are flagged).
        unsettled = (OPERATOR_ROLE,) if base is None else ()
        switched = base not in (None, Role.PROVIDER) and risk_class is RiskClass.HIGH_RISK
        facts = _switch_facts(answer) if switched else {}
        fired = {f: fact for f, fact in facts.items() if _as_switch(fact) is Answer.YES}
        made_by = (*(SWITCHES[f] for f in fired), BUILDS_ON_GPAI)
        shown = (*used, *fired.values())
        return _settlement(answer, Role.PROVIDER, shown, made_by=made_by, missing=unsettled)
    if base is None:
        return _settlement(answer, Role.PROVIDER, used, missing=(OPERATOR_ROLE, *gpai_open))
    if base is Role.PROVIDER:
        return _settlement(answer, Role.PROVIDER, used, open_questions=gpai_open)
    if risk_class is RiskClass.HIGH_RISK:
        return _settle_switches(answer, base, used, gpai_open)
    unknown: tuple[KeyQuestion, ...] = ()
    if risk_class in OWN_NAME_CLASSES:
        # Limited or minimal risk: Art. 25(1) can't make a provider, but own-name placement bears
        # on Art. 3(3), which the law leaves open (user decisions on own-d-05, 2026-09-29). A
        # prohibited system keeps its base role: Art. 5 bans it whoever the operator is.
        used = (*used, answer.own_brand)
        if answer.own_brand.answer is Answer.YES:
            return _settlement(
                answer, Role.PROVIDER, used, missing=gpai_open, open_in_law=OWN_NAME_OPEN
            )
        if answer.own_brand.answer is Answer.UNKNOWN:
            unknown = (OWN_NAME,)
    missing = (*gpai_open, *unknown)
    if missing:
        return _settlement(answer, Role.PROVIDER, used, missing=missing)
    return _settlement(answer, base, used)


def _switch_facts(answer: RoleAnswer) -> dict[str, KeyFact | ModificationFact]:
    """The key fact of each Art. 25(1) switch that can apply, by `SWITCHES` field.

    (b) and (c) exclude each other by the original system's class (user, 2026-10-06): (b) needs
    a system that was already high-risk, (c) one that only its new purpose made high-risk. A
    "yes" to (c) says the new purpose is what made it high-risk, so (b) can't apply and is
    neither relied on nor asked. (a) can join either."""
    facts: dict[str, KeyFact | ModificationFact] = {
        field: getattr(answer, field) for field in SWITCHES
    }
    if answer.changed_purpose.answer is Answer.YES:
        return {field: fact for field, fact in facts.items() if field != MODIFICATION_FIELD}
    return facts


def _as_switch(fact: KeyFact | ModificationFact) -> Answer:
    """A switch's answer: a contested (b) is neither met nor a missing fact (`NO` here), and
    `_settle_switches` reads it as an open question of law instead."""
    if not isinstance(fact, ModificationFact):
        return fact.answer
    return Answer.NO if fact.answer is Modification.CONTESTED else Answer(fact.answer.value)


def _settle_switches(
    answer: RoleAnswer,
    base: Role,
    used: tuple[KeyFact | ModificationFact | RoleFact, ...],
    gpai_open: tuple[KeyQuestion, ...],
) -> RoleSettlement:
    """A deployer, importer or distributor of a high-risk system: every Art. 25(1) switch that
    applies makes it the provider; otherwise an open (b) question of law, then an unknown switch,
    keeps provider as the working assumption; otherwise it keeps its own role."""
    facts = _switch_facts(answer)
    shown = (*used, *facts.values())
    given = {field: _as_switch(fact) for field, fact in facts.items()}
    fired = tuple(SWITCHES[field] for field, value in given.items() if value is Answer.YES)
    if fired:
        return _settlement(answer, Role.PROVIDER, shown, made_by=fired, open_questions=gpai_open)
    unknown = tuple(SWITCHES[field] for field, value in given.items() if value is Answer.UNKNOWN)
    missing = (*gpai_open, *unknown)
    modification = facts.get(MODIFICATION_FIELD)
    if isinstance(modification, ModificationFact) and (
        modification.answer is Modification.CONTESTED
    ):
        return _settlement(
            answer, Role.PROVIDER, shown, missing=missing, open_in_law=SUBSTANTIAL_MODIFICATION_OPEN
        )
    if missing:
        return _settlement(answer, Role.PROVIDER, shown, missing=missing)
    return _settlement(answer, base, shown)


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
    """The check that settles the row is absent from the run (a scripted or partial run). When
    it ran and didn't report the row, it decided the row doesn't apply: `CONDITION_NOT_MET`."""


def _found(is_found: bool, settled_by: StepName, state: EngineState) -> Kept:
    """A row another check settles: kept when reported; otherwise not met if that check ran."""
    if is_found:
        return Kept.YES
    ran = any(step.step is settled_by for step in state.get("steps", ()))
    return Kept.CONDITION_NOT_MET if ran else Kept.NOT_FOUND


def _kept(
    obligation: Obligation, answers: Mapping[str, Answer], state: EngineState, gpai: Answer
) -> Kept:
    if obligation.applies_if is None:
        return Kept.YES
    article = obligation.article
    if article.startswith(TRANSPARENCY_PREFIX):
        return _found(article in state.get("transparency_duties", ()), StepName.TRANSPARENCY, state)
    if article == EXEMPTION_ARTICLE:
        return _found(state.get("annex_iii_exempt", False), StepName.HIGH_RISK, state)
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
    except UnicodeDecodeError as error:
        raise ProvisionTextError(f"{path} is not valid UTF-8") from error
    except json.JSONDecodeError as error:
        raise ProvisionTextError(f"{path}: line {error.lineno} is not valid JSON") from error
    except (KeyError, TypeError) as error:
        raise ProvisionTextError(f"{path}: a row lacks provision_id or text ({error})") from error


def citations(
    articles: Sequence[str], law_version: LawVersion, language: Language, data_dir: Path
) -> tuple[Citation, ...]:
    """Citations quoting `articles` from the parsed AI Act text of `law_version`.

    The citation validator (E9, `aiact.engine.citations`) then resolves each one through
    `get_provision` and re-quotes it from the corpus slice of the run's date. The document id is
    the manifest key, which the citation checks expect (V2, E9).
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


def _status(settled: RoleSettlement) -> Status:
    if settled.is_ambiguous:
        return Status.LEGALLY_AMBIGUOUS
    return Status.NEEDS_MORE_INFORMATION if settled.missing else Status.DECIDED


def _decision(settled: RoleSettlement, language: Language, summary: Sequence[str]) -> str:
    names, texts = ROLE_NAMES[language], TEXTS[language]
    also = settled.also_role
    sentences = [
        texts["role"].format(role=names[settled.role])
        if also is None
        else texts["role_also"].format(role=names[settled.role], also=names[also])
    ]
    sentences.extend(q.reason[language] for q in settled.made_by if q.reason)
    if settled.open_in_law is not None and settled.base is not None:
        # The ambiguity states the working assumption; a pending question doesn't settle it.
        sentence = texts[settled.open_in_law.sentence]
        sentences.append(sentence.format(base=names[settled.base]))
        sentences.extend(
            texts["still_asked"].format(question=q.question[language]) for q in settled.missing
        )
    elif settled.missing:
        question = settled.missing[0].question[language]
        if settled.missing[0] is OWN_NAME and settled.base is not None:
            base = names[settled.base]
            sentences.append(texts["assumption_own_name"].format(base=base, question=question))
        elif BUILDS_ON_GPAI in settled.made_by and also is not None:
            # The GPAI rule settled the provider role; only the kept role is assumed.
            sentences.append(texts["assumption_also"].format(also=names[also], question=question))
        else:
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
    risk_class, route = working_class(state)
    settled = settle_role(answer, risk_class)
    source_table = table or default_table()
    given = answer.legacy if isinstance(answer, HighRiskRoleAnswer) else None
    legacy = settle_legacy(given, route) if has_duties(state, source_table) else LegacySettlement()
    missing = settled.missing[0] if settled.missing else None
    obligations, summary = select_obligations(
        answer.conditions, state, settled, source_table, legacy
    )
    source = data_dir or get_settings().aiact_data_dir
    cited = (*settled.cited_articles(), *legacy.articles, *_section_b_articles(state))
    quotes = citations(cited, state["law_version"], language, source)
    step = StepResult(
        step=StepName.ROLE_OBLIGATIONS,
        decision=_decision(settled, language, summary),
        facts_used=facts_used((*settled.used, *legacy.used), state.get("facts", ())),
        citations=quotes,
        status=_status(settled),
        missing_fact=ask(missing, language, StepName.ROLE_OBLIGATIONS) if missing else None,
        open_question=settled.open_question(language, quotes),
    )
    finding = RoleFinding(
        role=settled.role,
        also_role=settled.also_role,
        role_switch_reason=settled.switch_reason(language),
        obligations=obligations,
    )
    asked = (*settled.questions(), *legacy.questions)
    questions = tuple(ask(key, language, StepName.ROLE_OBLIGATIONS) for key in asked)
    return CheckOutcome(step=step, role=finding, follow_up_questions=questions)


def refusal_outcome(
    state: EngineState, table: ObligationTable | None = None, data_dir: Path | None = None
) -> CheckOutcome:
    """The step for a reply the provider's content filter refused (decision 029): not assessed,
    provider keeping the deployer duties assumed (the stricter reading, as for an unknown role)
    until a person reviews it, with every duty whose condition is open, citing both
    definitions. The review question is a missing fact."""
    language = state["language"]
    settled = RoleSettlement(
        base=None, role=Role.PROVIDER, also_role=Role.DEPLOYER, gpai=Answer.UNKNOWN, used=()
    )
    obligations, summary = select_obligations((), state, settled, table or default_table())
    source = data_dir or get_settings().aiact_data_dir
    cited = (*settled.cited_articles(), *_section_b_articles(state))
    return refused_check(
        StepName.ROLE_OBLIGATIONS,
        language,
        " ".join((TEXTS[language]["refusal"], *summary)),
        citations(cited, state["law_version"], language, source),
        ask(PERSON_REVIEW, language, StepName.ROLE_OBLIGATIONS),
        role=RoleFinding(role=settled.role, also_role=settled.also_role, obligations=obligations),
    )


def _is_section_b_point(state: EngineState) -> bool:
    """High-risk, decided or assumed, on an Annex I Section B point. An Art. 5 match that keeps
    prohibited as the class keeps its prohibition rows."""
    risk_class, _ = working_class(state)
    is_high_risk = risk_class is RiskClass.HIGH_RISK
    return is_high_risk and state.get("annex_point", "").startswith(SECTION_B_PREFIX)


def _is_high_risk_decided(state: EngineState) -> bool:
    steps = state.get("steps", ())
    return any(s.step is StepName.HIGH_RISK and s.status is Status.DECIDED for s in steps)


def is_section_b(state: EngineState) -> bool:
    """Decided high-risk as an Annex I Section B product: Art. 2(2) leaves it no AI Act duties.
    An uncertain high-risk step only makes it possible (`may_be_section_b`): the duties stay,
    the stricter reading (orchestrator's ruling, E8 review round 1)."""
    return _is_section_b_point(state) and _is_high_risk_decided(state)


def may_be_section_b(state: EngineState) -> bool:
    """Assumed, not decided, high-risk on an Annex I Section B point: Art. 2(2) is a possibility
    the step names, and every duty that may apply stays listed."""
    return _is_section_b_point(state) and not _is_high_risk_decided(state)


def _section_b_articles(state: EngineState) -> tuple[str, ...]:
    return (SECTION_B_ARTICLE,) if _is_section_b_point(state) else ()


def has_duties(state: EngineState, table: ObligationTable | None = None) -> bool:
    """Whether the step lists duties at all: the table holds the run's law version (the amended
    text only: the original's are not modelled, decision 020) and the system is no decided
    Section B product (none under Art. 2(2)). Without duties, Art. 111(2) says nothing either."""
    source = table or default_table()
    return source.law_version is state["law_version"] and not is_section_b(state)


def select_obligations(
    conditions: Sequence[ConditionAnswer],
    state: EngineState,
    settled: RoleSettlement,
    table: ObligationTable,
    legacy: LegacySettlement | None = None,
) -> tuple[tuple[Obligation, ...], tuple[str, ...]]:
    """The duties of the settled role and the role it keeps, less those whose condition the
    model's `conditions` answers rule out, marked as Art. 111(2) leaves them, and the sentences
    that summarise them for the step's decision. None when `table` doesn't hold the state's law
    version, or for a decided Annex I Section B product (Art. 2(2), user, 2026-09-30); an
    assumed one keeps them, and the summary names Art. 2(2) as a possibility."""
    language, law_version = state["language"], state["law_version"]
    risk_class, route = working_class(state)
    texts = TEXTS[language]
    roles = (settled.role, *((settled.also_role,) if settled.also_role else ()))
    legacy = legacy or LegacySettlement()
    if is_section_b(state):
        return (), (texts["section_b"],)
    if table.law_version is not law_version:
        held = table.law_version.value
        return (), (texts["not_modelled"].format(version=held, asked=law_version.value),)
    lists = [
        list_obligations(role, risk_class, route, law_version, table, legacy=legacy.status)
        for role in roles
    ]
    listed = tuple(dict.fromkeys(o for duties in lists for o in duties.obligations))
    ids = condition_ids(conditions_to_ask(risk_class, route, law_version, table))
    by_id = {given.id: given.answer for given in conditions}
    answers = {condition: by_id.get(cid, Answer.UNKNOWN) for condition, cid in ids.items()}
    verdicts = [(o, _kept(o, answers, state, settled.gpai)) for o in listed]
    kept = tuple(o for o, verdict in verdicts if verdict is Kept.YES)
    version = lists[0].law_version.value
    counts = {v: sum(verdict is v for _, verdict in verdicts) for v in Kept if v is not Kept.YES}
    summary = (
        texts["duties"].format(count=len(kept), risk_class=risk_class.value, version=version),
        *(texts[verdict.value].format(count=count) for verdict, count in counts.items() if count),
        *legacy_summary(kept, legacy, language, roles),
        *((texts["section_b_possible"],) if may_be_section_b(state) else ()),
    )
    return kept, summary


# --- The model call -----------------------------------------------------------------------------


ROLE_RESPONSE_FORMAT = json_schema_format("role_answer", RoleAnswer)
HIGH_RISK_RESPONSE_FORMAT = json_schema_format("role_answer", HighRiskRoleAnswer)


def answer_model(state: EngineState, table: ObligationTable | None = None) -> type[RoleAnswer]:
    """The answer the model gives: with the Art. 111(2) facts for a high-risk system that has
    duties for them to mark (`has_duties`: not under the original text, nor for a decided
    Section B product)."""
    risk_class, _ = working_class(state)
    if risk_class is RiskClass.HIGH_RISK and has_duties(state, table):
        return HighRiskRoleAnswer
    return RoleAnswer


def asked_conditions(state: EngineState, table: ObligationTable | None = None) -> tuple[str, ...]:
    """The conditions the model is asked: none for a decided Section B product (no duties)."""
    if is_section_b(state):
        return ()
    risk_class, route = working_class(state)
    return conditions_to_ask(risk_class, route, state["law_version"], table)


def _legacy_section(state: EngineState, table: ObligationTable | None) -> str:
    """The Art. 111(2) instructions for a high-risk system, or nothing (other classes' requests
    stay as they were, and without duties there is nothing to mark). `working_class` gives a
    route only for a high-risk system."""
    _, route = working_class(state)
    if route is None or not has_duties(state, table):
        return ""
    since = long_date(CHAPTER_III_DATES[route], Language.EN)
    return f"Launch and design:\n{LEGACY_INSTRUCTIONS.format(date=since)}\n"


def role_messages(
    state: EngineState, conditions: Sequence[str], table: ObligationTable | None = None
) -> list[BaseMessage]:
    """The fixed instructions first; the per-case context next; the description last (005).
    `table` is the obligations table the step reads (default: the committed one)."""
    risk_class, route = working_class(state)
    shown_class = risk_class.value + (f" ({route.value} route)" if route else "")
    steps = "\n".join(f"- {s.step.value}: {s.decision}" for s in state.get("steps", ())) or "-"
    listed = "\n".join(f"{cid}: {text}" for text, cid in condition_ids(conditions).items()) or "-"
    return [
        SystemMessage(ROLE_INSTRUCTIONS),
        HumanMessage(
            f"Language for facts: {state['language'].value}\n\n"
            f"Risk class so far: {shown_class}\n\n"
            f"Earlier checks:\n{steps}\n\n"
            f"Conditions:\n{listed}\n\n"
            f"{_legacy_section(state, table)}"
            f"Facts:\n{facts_section(state)}\n\n"
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
        self._model = chat or engine_chat_model(max_tokens=MAX_OUTPUT_TOKENS, settings=settings)
        self._table = table
        self._data_dir = settings.aiact_data_dir

    def __call__(self, state: EngineState) -> CheckOutcome:
        """A reply the provider's content filter refused gives `refusal_outcome`. Raises
        `RoleOutputError` when any other reply doesn't fit `RoleAnswer`."""
        conditions = asked_conditions(state, self._table)
        model = answer_model(state, self._table)
        response_format = (
            HIGH_RISK_RESPONSE_FORMAT if model is HighRiskRoleAnswer else ROLE_RESPONSE_FORMAT
        )
        reply = self._model.invoke(
            role_messages(state, conditions, self._table), response_format=response_format
        )
        try:
            answer = parse_reply(reply, model)
        except ProviderRefusalError:
            return refusal_outcome(state, self._table, self._data_dir)
        except ValidationError as exc:
            message = f"role answer doesn't fit the schema: {describe_validation_error(exc)}"
            raise RoleOutputError(message) from None
        return to_outcome(answer, state, self._table, self._data_dir)
