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

A high-risk system also gets the Art. 111(2) key facts (C7b, decision 022): placed on the market
or put into service before its route's Chapter III date, a significant change to its design or
intended purpose from then on (a substantial modification, Art. 3(23)), and use by public
authorities. A legacy system keeps its class; `list_obligations` marks its high-risk duties. An
unknown answer keeps the duties as they are and becomes a follow-up question. The facts are
asked only for a high-risk system, so the request for any other class is unchanged.

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
from pydantic import Field, ValidationError

from aiact.dates import long_date
from aiact.engine.nodes.common import answers_section, facts_section
from aiact.engine.nodes.key_facts import Answer, KeyFact, facts_used
from aiact.engine.nodes.role_texts import (
    BUILDS_ON_GPAI,
    OPERATOR_ROLE,
    OWN_NAME,
    OWN_NAME_QUESTION,
    OWN_NAME_READINGS,
    ROLE_ARTICLES,
    ROLE_NAMES,
    SWITCHES,
    TEXTS,
    KeyQuestion,
    legacy_questions,
)
from aiact.engine.state import CheckOutcome, EngineState, RoleFinding
from aiact.llm import engine_chat_model
from aiact.llm.structured import describe_validation_error, json_schema_format
from aiact.obligations.list import (
    CHAPTER_III_DATES,
    LEGACY_ARTICLE,
    PUBLIC_AUTHORITY_DEADLINE,
    SUBSTANTIAL_MODIFICATION_ARTICLE,
    ObligationTable,
    UnknownLawVersionError,
    default_table,
    legacy_status,
    list_obligations,
)
from aiact.schemas import (
    Citation,
    EvidenceTag,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    LegacyStatus,
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

MAX_OUTPUT_TOKENS = 3000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005)."""

TRANSPARENCY_PREFIX = "art:50:"
GPAI_FLAG_ARTICLE = "art:53:1:b"
DOWNSTREAM_PROVIDER_ARTICLE = "art:3:68"
EXEMPTION_ARTICLE = "art:6:4"
PROHIBITION_ARTICLE = "art:5:1"
"""Rows whose condition is settled by another finding, not asked of the model."""

OWN_NAME_CLASSES = frozenset({RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK})
"""The classes where own-name placement makes the role legally ambiguous under Art. 3(3)."""

ACT_DOCUMENTS: Mapping[LawVersion, str] = {
    LawVersion.ORIGINAL: "ai-act",
    LawVersion.AMENDED: "ai-act-consolidated",
}
"""The manifest key of each AI Act text, as a citation's `document_id`."""


class RoleFact(ContractModel):
    """The company's own role before any switch; None when the description doesn't say."""

    role: Role | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]

    @property
    def is_known(self) -> bool:
        """Always shown: an unknown role is itself a fact the step rests on."""
        return True


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


class LegacyAnswer(ContractModel):
    """The Art. 111(2) key facts of a high-risk system."""

    placed_before: KeyFact
    significant_design_change: KeyFact
    for_public_authority: KeyFact


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
    is_ambiguous: bool = False
    """Own name on a system that isn't high-risk: Art. 3(3) doesn't settle the role."""

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
        ambiguous = (ROLE_ARTICLES[Role.PROVIDER],) if self.is_ambiguous else ()
        cited = (*(ROLE_ARTICLES[r] for r in bases), *ambiguous, *made, *waiting)
        return tuple(dict.fromkeys(cited))

    def open_question(self, language: Language) -> OpenQuestion | None:
        """The Art. 3(3) question an ambiguous own-name placement leaves open."""
        if not self.is_ambiguous or self.base is None:
            return None
        base = ROLE_NAMES[language][self.base]
        stricter, lenient = OWN_NAME_READINGS[language]
        readings = (stricter, lenient.format(base=base[:1].upper() + base[1:]))
        return OpenQuestion(question=OWN_NAME_QUESTION[language], readings=readings)


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
    is_ambiguous: bool = False,
) -> RoleSettlement:
    base = answer.role.role
    is_assumed = bool(missing) or is_ambiguous
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
        is_ambiguous=is_ambiguous,
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
    elif risk_class in OWN_NAME_CLASSES:
        # Limited or minimal risk: Art. 25(1) can't make a provider, but own-name placement bears
        # on Art. 3(3), which the law leaves open (user decisions on own-d-05, 2026-09-29). A
        # prohibited system keeps its base role: Art. 5 bans it whoever the operator is.
        used = (*used, answer.own_brand)
        if answer.own_brand.answer is Answer.YES:
            return _settlement(answer, Role.PROVIDER, used, missing=gpai_open, is_ambiguous=True)
        if answer.own_brand.answer is Answer.UNKNOWN:
            unknown = (OWN_NAME,)
    missing = (*gpai_open, *unknown)
    if missing:
        return _settlement(answer, Role.PROVIDER, used, missing=missing)
    return _settlement(answer, base, used)


# --- Art. 111(2): high-risk systems already on the market -------------------------------------


@dataclass(frozen=True)
class LegacySettlement:
    """What Art. 111(2) gives: the marking for the duties (None: they apply as usual), whether
    to check again at launch (not yet on the market or in use), the answers it rests on, and the
    unknown ones to ask."""

    status: LegacyStatus | None = None
    route: HighRiskRoute | None = None
    used: tuple[KeyFact, ...] = ()
    questions: tuple[KeyQuestion, ...] = ()
    check_at_launch: bool = False

    @property
    def articles(self) -> tuple[str, ...]:
        """What the step cites for Art. 111(2): the article for the check-again sentence, and
        with a marking also Art. 3(23), the substantial modification a significant change is
        read as (recital 177, which the consolidated text doesn't carry)."""
        if self.status is not None:
            return (LEGACY_ARTICLE, SUBSTANTIAL_MODIFICATION_ARTICLE)
        return (LEGACY_ARTICLE,) if self.check_at_launch else ()


def _settled_answer(key_fact: KeyFact) -> Answer:
    """An assumed answer settles nothing under Art. 111(2): it counts as unknown and is asked."""
    return Answer.UNKNOWN if key_fact.evidence is EvidenceTag.ASSUMED else key_fact.answer


def settle_legacy(answer: RoleAnswer, route: HighRiskRoute | None) -> LegacySettlement:
    """Apply Art. 111(2) to the answers, as of the assessment date (user decision, 2026-10-01):
    only a system already on the market or in use counts as placed before the route's date. One
    that isn't yet keeps its duties as usual, with a note to check again at launch (the model
    can't tell a planned launch from a new system, so every "no" gets it, assumed or not). One
    whose design changes keeps its duties too, and the launch and public-use facts aren't relied
    on or asked. Otherwise an assumed answer counts as unknown, so only stated or inferred facts
    can mark duties, and an unknown fact counts the stricter way (not placed before the date,
    changed, for public authorities: the earlier deadline) and is asked as a follow-up question."""
    if not isinstance(answer, HighRiskRoleAnswer) or route is None:
        return LegacySettlement()
    legacy, keys = answer.legacy, legacy_questions(CHAPTER_III_DATES[route], LEGACY_ARTICLE)
    if legacy.placed_before.answer is Answer.NO:
        return LegacySettlement(route=route, used=(legacy.placed_before,), check_at_launch=True)
    placed = _settled_answer(legacy.placed_before)
    changed = _settled_answer(legacy.significant_design_change)
    public = _settled_answer(legacy.for_public_authority)
    chain = (
        (legacy.placed_before, placed, keys.placed_before),
        (legacy.significant_design_change, changed, keys.design_change),
        (legacy.for_public_authority, public, keys.public_authority),
    )
    if changed is Answer.YES:
        # The duties apply as usual whatever the launch or public use: ask neither.
        chain = tuple(link for link in chain[:2] if link[1] is not Answer.UNKNOWN)
    status = legacy_status(
        placed_before=placed is Answer.YES,
        significantly_changed=changed is not Answer.NO,
        for_public_authority=public is not Answer.NO,
    )
    return LegacySettlement(
        status=status,
        route=route,
        used=tuple(fact for fact, settled, _ in chain if settled is not Answer.UNKNOWN),
        questions=tuple(question for _, settled, question in chain if settled is Answer.UNKNOWN),
    )


PER_PRODUCT_ROLES = frozenset({Role.PROVIDER, Role.IMPORTER, Role.DISTRIBUTOR})
"""The roles that supply the system: placing on the market counts per product supplied (the New
Legislative Framework reading), so new copies may be fully covered. A deployer uses its copy."""


def _legacy_summary(
    kept: Sequence[Obligation], legacy: LegacySettlement, language: Language, roles: Sequence[Role]
) -> tuple[str, ...]:
    """One sentence per Art. 111(2) marking the kept duties carry, then the per-product caveat
    for a role that supplies the system; or the check-again sentence for a system not yet on the
    market or in use."""
    if not legacy.articles or legacy.route is None:
        return ()
    texts = TEXTS[language]
    since = long_date(CHAPTER_III_DATES[legacy.route], language)
    if legacy.check_at_launch:
        return (texts["legacy_check_at_launch"].format(date=since),)
    deadline = long_date(PUBLIC_AUTHORITY_DEADLINE, language)
    counts = {status: sum(o.legacy is status for o in kept) for status in LegacyStatus}
    marked = tuple(
        texts[status.value].format(count=count, date=since, deadline=deadline)
        for status, count in counts.items()
        if count
    )
    supplies = any(role in PER_PRODUCT_ROLES for role in roles)
    caveat = (texts["legacy_per_product"].format(date=since),) if marked and supplies else ()
    return (*marked, *caveat)


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


def _question(key: KeyQuestion, language: Language) -> FollowUpQuestion:
    return FollowUpQuestion(id=key.id, text=key.question[language], about=key.article)


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
    if settled.made_by and settled.made_by.reason:
        sentences.append(settled.made_by.reason[language])
    if settled.is_ambiguous and settled.base is not None:
        # The ambiguity states the working assumption; a pending question doesn't settle it.
        sentences.append(texts["ambiguous"].format(base=names[settled.base]))
        sentences.extend(
            texts["still_asked"].format(question=q.question[language]) for q in settled.missing
        )
    elif settled.missing:
        question = settled.missing[0].question[language]
        if settled.missing[0] is OWN_NAME and settled.base is not None:
            base = names[settled.base]
            sentences.append(texts["assumption_own_name"].format(base=base, question=question))
        elif settled.made_by is BUILDS_ON_GPAI and also is not None:
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
    # Decided once: without duties for this law version, Art. 111(2) says nothing either.
    holds_version = source_table.law_version is state["law_version"]
    legacy = settle_legacy(answer, route) if holds_version else LegacySettlement()
    missing = settled.missing[0] if settled.missing else None
    obligations, summary = select_obligations(answer, state, settled, source_table, legacy)
    source = data_dir or get_settings().aiact_data_dir
    cited = (*settled.cited_articles(), *legacy.articles)
    step = StepResult(
        step=StepName.ROLE_OBLIGATIONS,
        decision=_decision(settled, language, summary),
        facts_used=facts_used((*settled.used, *legacy.used), state.get("facts", ())),
        citations=citations(cited, state["law_version"], language, source),
        status=_status(settled),
        missing_fact=_question(missing, language) if missing else None,
        open_question=settled.open_question(language),
    )
    finding = RoleFinding(
        role=settled.role,
        also_role=settled.also_role,
        role_switch_reason=settled.switch_reason(language),
        obligations=obligations,
    )
    asked = (*settled.questions(), *legacy.questions)
    questions = tuple(_question(key, language) for key in asked)
    return CheckOutcome(step=step, role=finding, follow_up_questions=questions)


def select_obligations(
    answer: RoleAnswer,
    state: EngineState,
    settled: RoleSettlement,
    table: ObligationTable,
    legacy: LegacySettlement | None = None,
) -> tuple[tuple[Obligation, ...], tuple[str, ...]]:
    """The duties of the settled role and the role it keeps, less those whose condition doesn't
    apply, marked as Art. 111(2) leaves them, and the sentences that summarise them for the
    step's decision. None when `table` doesn't hold the state's law version."""
    language, law_version = state["language"], state["law_version"]
    risk_class, route = working_class(state)
    texts = TEXTS[language]
    roles = (settled.role, *((settled.also_role,) if settled.also_role else ()))
    legacy = legacy or LegacySettlement()
    if table.law_version is not law_version:
        held = table.law_version.value
        return (), (texts["no_table"].format(version=held, asked=law_version.value),)
    lists = [
        list_obligations(role, risk_class, route, law_version, table, legacy=legacy.status)
        for role in roles
    ]
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
        *_legacy_summary(kept, legacy, language, roles),
    )
    return kept, summary


# --- The model call -----------------------------------------------------------------------------


ROLE_RESPONSE_FORMAT = json_schema_format("role_answer", RoleAnswer)
HIGH_RISK_RESPONSE_FORMAT = json_schema_format("role_answer", HighRiskRoleAnswer)


def answer_model(state: EngineState) -> type[RoleAnswer]:
    """The answer the model gives: with the Art. 111(2) facts for a high-risk system."""
    risk_class, _ = working_class(state)
    return HighRiskRoleAnswer if risk_class is RiskClass.HIGH_RISK else RoleAnswer


def _legacy_section(state: EngineState) -> str:
    """The Art. 111(2) instructions for a high-risk system, or nothing (other classes' requests
    stay as they were). `working_class` gives a route only for a high-risk system."""
    _, route = working_class(state)
    if route is None:
        return ""
    since = long_date(CHAPTER_III_DATES[route], Language.EN)
    return f"Launch and design:\n{LEGACY_INSTRUCTIONS.format(date=since)}\n"


def role_messages(state: EngineState, conditions: Sequence[str]) -> list[BaseMessage]:
    """The fixed instructions first; the per-case context next; the description last (005)."""
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
            f"{_legacy_section(state)}"
            f"Answers to earlier questions:\n{answers_section(state)}\n\n"
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
        """Raises `RoleOutputError` when the reply doesn't fit `RoleAnswer`."""
        risk_class, route = working_class(state)
        conditions = conditions_to_ask(risk_class, route, state["law_version"], self._table)
        model = answer_model(state)
        response_format = (
            HIGH_RISK_RESPONSE_FORMAT if model is HighRiskRoleAnswer else ROLE_RESPONSE_FORMAT
        )
        reply = self._model.invoke(
            role_messages(state, conditions), response_format=response_format
        )
        try:
            answer = model.model_validate_json(reply.text)
        except ValidationError as exc:
            message = f"role answer doesn't fit the schema: {describe_validation_error(exc)}"
            raise RoleOutputError(message) from exc
        return to_outcome(answer, state, self._table, self._data_dir)
