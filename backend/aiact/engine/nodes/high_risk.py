"""The high-risk node: Annex III matching with the Art. 6(3) filter, and the Annex I product route
(E5; INIT > How it works, Annex I).

Retrieval comes first and involves no model:
- **Annex III by search.** The description is searched in the law (`search_ai_act`, no distance
  cut-off, so a softly worded use still reaches its point: C8), and the Annex III rows among the
  hits are the candidate points.
- **Analogy.** The guidelines are searched the same way; their worked examples (Pile A only: held-
  out examples are never retrievable, decision 012) are shown for reasoning by analogy. The
  caller's `exclude_source_example_ids` go into every search, so a leave-one-out run drops the
  example a case was written from. Guidance is mostly English only, so a German search that finds
  none is repeated in English.
- **Annex I by lookup.** The Annex I list is short and the law says where to look, so each of its
  points is fetched (`get_provision`) and shown as one line with its id and short title: the
  model can only pick an id the text of this law version has.

The engine model then answers fixed key facts (the prompt in `prompts/high_risk.md` comes first,
the retrieved provisions next, the description last, so the prefix is cached: decision 005), and
the Act's rules are applied here, in code:
- **Annex III:** a listed use is high-risk unless an Art. 6(3) condition is met; a system that
  profiles people never is (the last subparagraph of Art. 6(3)). Points that need a public user
  ask about it (5(a), 8(a)) or, for 6 and 7, state it as an assumed fact.
- **Annex I:** high-risk when the product is covered by the listed law, the AI system is the
  product or its safety component (Art. 6(1)(a), 6(1a), 6(1b)), and the product needs a third-
  party conformity assessment (Art. 6(1)(b), 6(1c)). The result names the law, and for Section B
  says that Art. 2(2) leaves the duties to the sector law.
- **Uncertain facts:** a deciding fact left open makes the step `needs_more_information`, a
  question the law leaves open makes it `legally_ambiguous`; either way the stricter reading
  (high-risk) is the labelled working assumption, and the step asks the deciding question.

Every citation is fetched through `get_provision`, or is a retrieved guideline passage.
"""

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import Field, ValidationError

from aiact.engine.nodes.high_risk_texts import (
    ANNEX_I_QUESTIONS,
    ANNEX_III_USE,
    AUTHORITY_ASSUMED,
    DECIDES_ADMISSION,
    JUDICIAL_USE,
    OPEN_FALLBACK,
    PROFILING,
    PUBLIC_AUTHORITY_USER,
    PUBLIC_SCHEME,
    ROUTE_NAMES,
    TEXTS,
    point_name,
)
from aiact.engine.nodes.key_facts import Answer, facts_used
from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.engine.state import CheckOutcome, EngineState
from aiact.llm import engine_chat_model
from aiact.llm.structured import describe_validation_error, json_schema_format
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError, get_provision
from aiact.retrieval.search import SearchHit, SearchResults, search_ai_act
from aiact.schemas import (
    Citation,
    EvidenceTag,
    Fact,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    OpenQuestion,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.base import ContractModel
from aiact.settings import Settings

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "high_risk.md"
HIGH_RISK_INSTRUCTIONS = PROMPT_PATH.read_text(encoding="utf-8")

MAX_OUTPUT_TOKENS = 3000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005)."""

LAW_SEARCH_LIMIT = 50
"""Hits asked of the law search; the Annex III rows among them are the candidates."""
MAX_ANNEX_CANDIDATES = 8
GUIDANCE_SEARCH_LIMIT = 8
MAX_PASSAGE_CHARS = 4000
"""Bounds one retrieved text in the prompt (a parent row holds all its children's text)."""

ANNEX_I_CANDIDATES: tuple[str, ...] = (
    *(f"annex:I:A:{number}" for number in range(1, 13)),
    *(f"annex:I:B:{number}" for number in range(13, 22)),
)
"""Every Annex I point id either text may have: A.1-12 and B.13-21."""
ANNEX_III_PREFIX = "annex:III"
EXAMPLE_MARK = ":ex:"
"""Guideline worked examples have ids like `guide:guide-high-risk-annex-iii:ex:042`."""

ANNEX_III_POINTS: frozenset[str] = frozenset(
    f"annex:III:{point}"
    for point in (
        *("1:a", "1:b", "1:c", "2", "3:a", "3:b", "3:c", "3:d", "4:a", "4:b"),
        *("5:a", "5:b", "5:c", "5:d", "6:a", "6:b", "6:c", "6:d", "6:e"),
        *("7:a", "7:b", "7:c", "7:d", "8:a", "8:b"),
    )
)
"""Every Annex III point a use can fall under (the leaves of the annex)."""
ANNEX_I_POINT = re.compile(r"^annex:I:(A|B):\d{1,2}$")
SECTION_B_PREFIX = "annex:I:B:"

ADMISSION_POINTS = frozenset({"annex:III:3:a", "annex:III:3:c"})


@dataclass(frozen=True)
class AuthorityRule:
    """An Annex III point that names its user: ask who uses it, or assume the authority."""

    question: KeyQuestion
    is_assumed: bool = False


AUTHORITY_RULES: Mapping[str, AuthorityRule] = {
    "annex:III:5:a": AuthorityRule(PUBLIC_SCHEME),
    "annex:III:6": AuthorityRule(PUBLIC_AUTHORITY_USER, is_assumed=True),
    "annex:III:7": AuthorityRule(PUBLIC_AUTHORITY_USER, is_assumed=True),
    "annex:III:8:a": AuthorityRule(JUDICIAL_USE),
}
"""Keyed by the point or its area (`annex:III:6` covers 6(a)-(e))."""

ACT_SHORT_TITLE = re.compile(
    r" (of the European Parliament and of the Council|des Europäischen Parlaments und des Rates)"
    r"( of| vom) \d{1,2}\.? \w+ \d{4}"
)
HARMONISATION_WORDS = re.compile(
    r"on the harmonisation of the laws of the Member States relating to "
    r"(the making available on the market of )?"
    r"|(zur Angleichung|zur Harmonisierung|über die Harmonisierung) der Rechtsvorschriften der "
    r"Mitgliedstaaten (über|für) (die Bereitstellung von )?"
)
GERMAN_ACCUSATIVE: Mapping[str, str] = {"Druckgeräten": "Druckgeräte"}
"""A noun left in the dative once "über die Bereitstellung von" is dropped from a title."""
TITLE_END = re.compile(
    r",| and repealing| und zur Aufhebung| zur Aufhebung| sowie| auf dem Markt| \(OJ| \(ABl"
)


class Art63Condition(StrEnum):
    """The Art. 6(3) condition met, second subparagraph (a)-(d), or none."""

    NONE = "none"
    A = "a"
    B = "b"
    C = "c"
    D = "d"


class RouteSummary(ContractModel):
    """A route's answer as `key_facts.facts_used` reads it: its `fact` sums up the whole route,
    so it always counts as settled (an open fact is asked through the route's question)."""

    @property
    def is_known(self) -> bool:
        return True


class Settled(StrEnum):
    """Whether the Act and guidance settle a route's reading of the facts."""

    YES = "yes"
    NO = "no"


class AnnexIIIAnswer(RouteSummary):
    """The Annex III use. Enum fields carry no description: strict structured output rejects
    keywords next to a `$ref`; the prompt explains every field instead. Each route's
    `settled_in_law` and `open_question` come right after its facts, so the model answers them
    in that order every time."""

    point: str | None
    uses: Answer
    public_authority: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]
    examples: tuple[str, ...]


class Art63Answer(RouteSummary):
    condition: Art63Condition
    profiling: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class AnnexIAnswer(RouteSummary):
    point: str | None
    covered: Answer
    safety_component_or_product: Answer
    third_party_assessment: Answer
    settled_in_law: Settled
    open_question: OpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


RouteAnswer = AnnexIIIAnswer | Art63Answer | AnnexIAnswer


class HighRiskAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill."""

    annex_iii: AnnexIIIAnswer
    art_6_3: Art63Answer
    annex_i: AnnexIAnswer
    question: FollowUpQuestion | None


class HighRiskOutputError(ValueError):
    """The model's answer doesn't fit `HighRiskAnswer` or names an Annex point that doesn't exist
    (a broken output)."""


# --- Retrieval ----------------------------------------------------------------------------------


class Searcher(Protocol):
    """What the node needs from `search_ai_act`."""

    def __call__(
        self,
        query: str,
        language: Language,
        law_version: LawVersion,
        as_of: date | None,
        *,
        doc_types: Collection[str],
        exclude_source_example_ids: Sequence[str],
        max_distance: float | None,
        limit: int,
    ) -> SearchResults: ...


class Lookup(Protocol):
    """What the node needs from `get_provision`."""

    def __call__(
        self, provision_id: str, language: Language, law_version: LawVersion, as_of: date | None
    ) -> Provision: ...


def search_corpus(
    query: str,
    language: Language,
    law_version: LawVersion,
    as_of: date | None,
    *,
    doc_types: Collection[str],
    exclude_source_example_ids: Sequence[str],
    max_distance: float | None,
    limit: int,
) -> SearchResults:
    return search_ai_act(
        query,
        language,
        law_version,
        as_of,
        doc_types=doc_types,
        exclude_source_example_ids=exclude_source_example_ids,
        max_distance=max_distance,
        limit=limit,
    )


def lookup_provision(
    provision_id: str, language: Language, law_version: LawVersion, as_of: date | None
) -> Provision:
    return get_provision(provision_id, language, law_version, as_of)


def slice_date(state: EngineState) -> date | None:
    """The date the texts are read on: the original text has one open slice and takes none."""
    return None if state["law_version"] is LawVersion.ORIGINAL else state["as_of"]


@dataclass(frozen=True)
class Retrieved:
    """What the searches and the lookup found for one description."""

    annex_i: tuple[Provision, ...]
    """Every Annex I point the text of this law version has, in order."""
    annex_iii: tuple[SearchHit, ...]
    guidance: tuple[SearchHit, ...]


def annex_i_points(state: EngineState, lookup: Lookup) -> tuple[Provision, ...]:
    """The Annex I points of the law version read, one lookup each. The candidates cover both
    numberings (the Omnibus moved machinery from A.1 to B.21), and a point the text lacks is
    skipped, so the model is only shown ids that exist."""
    language, version, on = state["language"], state["law_version"], slice_date(state)
    points: list[Provision] = []
    for point in ANNEX_I_CANDIDATES:
        try:
            points.append(lookup(point, language, version, on))
        except ProvisionNotFoundError:
            continue
    return tuple(points)


def retrieve(state: EngineState, search: Searcher, lookup: Lookup) -> Retrieved:
    """The Annex III candidates, the guidance and the Annex I list for the description. Every
    search carries the caller's exclusions and no distance cut-off."""
    language, version, on = state["language"], state["law_version"], slice_date(state)

    def run(doc_type: str, in_language: Language, limit: int) -> tuple[SearchHit, ...]:
        results = search(
            state["description"],
            in_language,
            version,
            on,
            doc_types={doc_type},
            exclude_source_example_ids=state["exclude_source_example_ids"],
            max_distance=None,
            limit=limit,
        )
        return results.hits

    law = run("law", language, LAW_SEARCH_LIMIT)
    annex_iii = tuple(hit for hit in law if hit.provision_id.startswith(ANNEX_III_PREFIX))
    guidance = run("guideline", language, GUIDANCE_SEARCH_LIMIT)
    if not guidance and language is not Language.EN:
        guidance = run("guideline", Language.EN, GUIDANCE_SEARCH_LIMIT)
    return Retrieved(
        annex_i=annex_i_points(state, lookup),
        annex_iii=annex_iii[:MAX_ANNEX_CANDIDATES],
        guidance=guidance,
    )


# --- Applying Art. 6 to the answer --------------------------------------------------------------


@dataclass(frozen=True)
class Route:
    """One route's reading: whether it makes the system high-risk (yes, no, or open on a fact),
    the question that settles an open fact, and the sentences that explain it."""

    answer: Answer
    missing: KeyQuestion | None = None
    sentences: tuple[str, ...] = ()
    cited: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnnexIIIReading:
    listed: Route
    exempt: Answer
    """Whether the Art. 6(3) exemption applies; `NO` when the use isn't listed."""
    exempt_missing: KeyQuestion | None = None
    assumed: tuple[Fact, ...] = ()
    confirm: tuple[KeyQuestion, ...] = ()


def _authority_rule(point: str) -> AuthorityRule | None:
    area = ":".join(point.split(":")[:3])
    return AUTHORITY_RULES.get(point) or AUTHORITY_RULES.get(area)


def read_annex_iii(answer: HighRiskAnswer, language: Language) -> AnnexIIIReading:
    """Whether the use is listed in Annex III and whether Art. 6(3) exempts it."""
    match, art63 = answer.annex_iii, answer.art_6_3
    if match.uses is Answer.NO:
        return AnnexIIIReading(listed=Route(Answer.NO), exempt=Answer.NO)
    point = match.point
    if point not in ANNEX_III_POINTS:
        raise HighRiskOutputError(f"the answer names no Annex III point it can use: {point!r}")
    listed, missing = match.uses, None
    assumed: tuple[Fact, ...] = ()
    confirm: tuple[KeyQuestion, ...] = ()
    rule = _authority_rule(point)
    if rule is not None and match.public_authority is Answer.NO:
        return AnnexIIIReading(listed=Route(Answer.NO), exempt=Answer.NO)
    if rule is not None and match.public_authority is Answer.UNKNOWN:
        if rule.is_assumed:
            assumed = (Fact(text=AUTHORITY_ASSUMED[language], evidence=EvidenceTag.ASSUMED),)
            confirm = (rule.question,)
        else:
            listed, missing = Answer.UNKNOWN, rule.question
    if listed is Answer.UNKNOWN and missing is None:
        missing = DECIDES_ADMISSION if point in ADMISSION_POINTS else ANNEX_III_USE
    exempt, exempt_missing = _exemption(art63)
    return AnnexIIIReading(
        listed=Route(listed, missing, cited=(point, "art:6:2", "art:6:3")),
        exempt=exempt,
        exempt_missing=exempt_missing,
        assumed=assumed,
        confirm=confirm,
    )


def _exemption(art63: Art63Answer) -> tuple[Answer, KeyQuestion | None]:
    """Art. 6(3): a condition met and no profiling exempts; profiling never does."""
    if art63.condition is Art63Condition.NONE or art63.profiling is Answer.YES:
        return Answer.NO, None
    if art63.profiling is Answer.UNKNOWN:
        return Answer.UNKNOWN, PROFILING
    return Answer.YES, None


def read_annex_i(answer: AnnexIAnswer) -> Route:
    """Art. 6(1): covered by the law, the product or its safety component, third-party check."""
    point = answer.point
    if point is None:
        return Route(Answer.NO)
    if not ANNEX_I_POINT.fullmatch(point):
        raise HighRiskOutputError(f"the answer names no Annex I point it can use: {point!r}")
    facts = (answer.covered, answer.safety_component_or_product, answer.third_party_assessment)
    cited = (point, "art:6:1")
    if Answer.NO in facts:
        reason = ("i_not_covered", "i_not_safety", "i_no_third_party")[facts.index(Answer.NO)]
        return Route(Answer.NO, sentences=(reason,), cited=cited)
    if Answer.UNKNOWN in facts:
        return Route(Answer.UNKNOWN, ANNEX_I_QUESTIONS[facts.index(Answer.UNKNOWN)], cited=cited)
    section_b = ("i_section_b",) if point.startswith(SECTION_B_PREFIX) else ()
    extra = ("art:2:2",) if section_b else ()
    return Route(Answer.YES, sentences=("i_high", *section_b), cited=(*cited, *extra))


@dataclass(frozen=True)
class Settlement:
    """What Art. 6 gives: the route (None when not high-risk), the Art. 6(3) exemption, the step's
    status with its missing fact or open question, and what the decision says and cites."""

    route: HighRiskRoute | None
    is_exempt: bool
    status: Status
    point: str | None
    missing: KeyQuestion | None = None
    open_question: OpenQuestion | None = None
    sentences: tuple[str, ...] = ()
    cited: tuple[str, ...] = ()
    questions: tuple[KeyQuestion, ...] = ()
    """Every other open fact worth asking, and the confirm questions for assumed facts."""
    assumed: tuple[Fact, ...] = ()


def _art63_citations(art63: Art63Answer) -> tuple[str, ...]:
    if art63.condition is Art63Condition.NONE:
        return ()
    return (f"art:6:3:{art63.condition.value}", "art:6:4")


def settle(answer: HighRiskAnswer, language: Language) -> Settlement:
    """Apply Art. 6 to the model's answers. A route decided high-risk, with no question of law
    open on it, wins; otherwise an open question of law, then an open fact, keeps high-risk as
    the working assumption; otherwise the system is exempt under Art. 6(3) or not high-risk.
    The key facts answer what the description states, so a route the law leaves open is
    ambiguous even when its facts all read "yes"."""
    iii = read_annex_iii(answer, language)
    annex_i = read_annex_i(answer.annex_i)
    unknowns = (iii.listed.missing, iii.exempt_missing, annex_i.missing)
    base = Settlement(
        route=None,
        is_exempt=False,
        status=Status.DECIDED,
        point=None,
        questions=(*iii.confirm, *(q for q in unknowns if q is not None)),
        assumed=iii.assumed,
    )
    iii_cited = (*iii.listed.cited, *_art63_citations(answer.art_6_3)) if iii.listed.cited else ()
    iii_open, i_open = _open_on_annex_iii(answer), _open_on_annex_i(answer)
    if iii.listed.answer is Answer.YES and iii.exempt is Answer.NO and not iii_open:
        why = "iii_profiling" if answer.art_6_3.profiling is Answer.YES else "iii_no_condition"
        return replace(
            base,
            route=HighRiskRoute.ANNEX_III,
            point=answer.annex_iii.point,
            sentences=("iii_high", why, *annex_i.sentences),
            cited=(*iii_cited, *annex_i.cited),
        )
    if annex_i.answer is Answer.YES and not i_open:
        return replace(
            base,
            route=HighRiskRoute.ANNEX_I,
            point=answer.annex_i.point,
            sentences=annex_i.sentences,
            cited=(*annex_i.cited, *iii_cited),
        )
    if iii_open:
        point = answer.annex_iii.point
        assert point is not None  # _open_on_annex_iii checked it
        is_on_6_3 = answer.annex_iii.settled_in_law is Settled.YES
        part: RouteAnswer = answer.art_6_3 if is_on_6_3 else answer.annex_iii
        cited = iii_cited or (point, "art:6:2", "art:6:3")
        return _ambiguous(base, HighRiskRoute.ANNEX_III, point, part, cited, language)
    if i_open:
        point = answer.annex_i.point
        assert point is not None  # _open_on_annex_i checked it
        route = HighRiskRoute.ANNEX_I
        return _ambiguous(base, route, point, answer.annex_i, annex_i.cited, language)
    return _open_or_settled(answer, base, iii, annex_i, iii_cited)


def _open_on_annex_iii(answer: HighRiskAnswer) -> bool:
    """The law leaves open whether a named Annex III point, or its Art. 6(3) exemption, applies."""
    match = answer.annex_iii
    if match.point not in ANNEX_III_POINTS:
        return False
    exemption_open = match.uses is not Answer.NO and answer.art_6_3.settled_in_law is Settled.NO
    return match.settled_in_law is Settled.NO or exemption_open


def _open_on_annex_i(answer: HighRiskAnswer) -> bool:
    """The law leaves open whether Art. 6(1) is met for a named Annex I point."""
    return answer.annex_i.point is not None and answer.annex_i.settled_in_law is Settled.NO


def _ambiguous(
    base: Settlement,
    route: HighRiskRoute,
    point: str,
    part: RouteAnswer,
    cited: tuple[str, ...],
    language: Language,
) -> Settlement:
    """An open question of law on a route: high-risk on it is the working assumption. When the
    model marks the route unsettled without stating the question, a fixed one stands in."""
    fallback = OPEN_FALLBACK[language][route.value]
    return replace(
        base,
        route=route,
        status=Status.LEGALLY_AMBIGUOUS,
        point=point,
        open_question=part.open_question
        or OpenQuestion(question=fallback[0], readings=(fallback[1], fallback[2])),
        sentences=("ambiguous",),
        cited=cited,
    )


def _open_or_settled(
    answer: HighRiskAnswer,
    base: Settlement,
    iii: AnnexIIIReading,
    annex_i: Route,
    iii_cited: tuple[str, ...],
) -> Settlement:
    """No route is decided high-risk and no question of law is open: an open fact on a route
    keeps high-risk as the assumption; otherwise the system is exempt or not high-risk."""
    listed = iii.listed.answer
    unsure = replace(base, status=Status.NEEDS_MORE_INFORMATION, sentences=("assumed",))
    if listed is Answer.UNKNOWN and iii.exempt is not Answer.YES:
        return replace(
            unsure,
            route=HighRiskRoute.ANNEX_III,
            point=answer.annex_iii.point,
            missing=iii.listed.missing,
            cited=iii_cited,
        )
    if listed is Answer.YES and iii.exempt is Answer.UNKNOWN:
        return replace(
            unsure,
            route=HighRiskRoute.ANNEX_III,
            point=answer.annex_iii.point,
            missing=iii.exempt_missing,
            cited=iii_cited,
        )
    if annex_i.answer is Answer.UNKNOWN:
        return replace(
            unsure,
            route=HighRiskRoute.ANNEX_I,
            point=answer.annex_i.point,
            missing=annex_i.missing,
            cited=annex_i.cited,
        )
    if listed is Answer.YES:  # exempt: a condition is met and it doesn't profile
        return replace(
            base,
            is_exempt=True,
            point=answer.annex_iii.point,
            sentences=("iii_exempt", *annex_i.sentences),
            cited=(*iii_cited, *annex_i.cited),
        )
    if listed is Answer.UNKNOWN:
        # Exempt if listed; whether it is listed still decides the Art. 6(4) duty, so the
        # exemption is the working assumption and the listing question is asked.
        return replace(
            unsure,
            is_exempt=True,
            point=answer.annex_iii.point,
            missing=iii.listed.missing,
            sentences=("assumed_exempt",),
            cited=iii_cited,
        )
    return replace(
        base,
        sentences=("none", *annex_i.sentences),
        cited=("art:6:1", "art:6:2", *annex_i.cited),
    )


# --- The step -----------------------------------------------------------------------------------


def law_title(provision: Provision) -> str:
    """The Annex I legislation's short title: `Regulation (EU) 2017/745 on medical devices`."""
    text = re.sub(r"^\d+\.\s*", "", provision.text.strip())
    short = ACT_SHORT_TITLE.sub("", text, count=1)
    short = HARMONISATION_WORDS.sub(lambda m: "über " if m.group(2) else "on ", short, count=1)
    title = TITLE_END.split(short, maxsplit=1)[0].strip()
    for dative, accusative in GERMAN_ACCUSATIVE.items():
        title = title.replace(f"über {dative}", f"über {accusative}")
    return title


def _law(point: str | None, state: EngineState, lookup: Lookup) -> str:
    """The short title of the Annex I legislation at `point`, or "" without one."""
    if point is None:
        return ""
    try:
        provision = lookup(point, state["language"], state["law_version"], slice_date(state))
    except ProvisionNotFoundError as error:
        raise HighRiskOutputError(
            f"the answer names an Annex I point with no text: {point}"
        ) from error
    return law_title(provision)


def _question(key: KeyQuestion, language: Language, law: str) -> FollowUpQuestion:
    return FollowUpQuestion(
        id=key.id, text=key.question[language].format(law=law), about=key.article
    )


def _missing_question(
    settled: Settlement, answer: HighRiskAnswer, language: Language, law: str
) -> FollowUpQuestion | None:
    """The step's missing fact: the fixed question, except that the model's own question
    replaces the generic Annex III one."""
    if settled.missing is None:
        return None
    if settled.missing is ANNEX_III_USE and answer.question is not None:
        return answer.question
    return _question(settled.missing, language, law)


def _facts_used(
    answer: HighRiskAnswer, settled: Settlement, facts: Sequence[Fact]
) -> tuple[Fact, ...]:
    """The facts each route's answer rests on (`key_facts.facts_used`), plus the facts the rules
    assumed."""
    parts = (answer.annex_iii, answer.art_6_3, answer.annex_i)
    result = {fact.text: fact for fact in facts_used(parts, facts)}
    result.update((fact.text, fact) for fact in settled.assumed)
    return tuple(result.values())


def _examples(answer: HighRiskAnswer, guidance: Sequence[SearchHit]) -> tuple[SearchHit, ...]:
    """The retrieved worked examples the answer compared with; any other id is ignored."""
    named = set(answer.annex_iii.examples)
    return tuple(
        hit for hit in guidance if EXAMPLE_MARK in hit.provision_id and hit.provision_id in named
    )


def _guidance_citation(hit: SearchHit, language: Language) -> Citation:
    return Citation(
        provision_id=hit.provision_id,
        document_id=hit.doc_key,
        law_version=hit.law_version,
        document_status=hit.status,
        language=hit.language,
        quote=hit.text,
        english_only=hit.language is not language,
    )


def _citation(provision: Provision) -> Citation:
    return Citation(
        provision_id=provision.provision_id,
        document_id=provision.doc_key,
        law_version=provision.law_version,
        document_status=provision.status,
        language=provision.language,
        quote=provision.text,
        english_only=provision.english_only,
    )


def _decision(
    settled: Settlement,
    answer: HighRiskAnswer,
    language: Language,
    law: str,
    examples: Sequence[SearchHit],
    question: FollowUpQuestion | None,
) -> str:
    texts = TEXTS[language]
    point = point_name(settled.point, language) if settled.point else ""
    route = ROUTE_NAMES[language][settled.route.value] if settled.route else ""
    asked = settled.open_question.question if settled.open_question else ""
    values = {
        "point": point,
        "law": law,
        "condition": answer.art_6_3.condition.value,
        "route": route,
        "question": question.text if question else asked,
    }
    i_point = answer.annex_i.point
    i_values = {**values, "point": point_name(i_point, language) if i_point else ""}
    sentences = [
        texts[key].format(**(i_values if key.startswith("i_") else values))
        for key in settled.sentences
    ]
    if examples:
        sentences.append(texts["examples"].format(ids=", ".join(h.provision_id for h in examples)))
    return " ".join(sentences)


def to_outcome(
    answer: HighRiskAnswer, state: EngineState, retrieved: Retrieved, lookup: Lookup
) -> CheckOutcome:
    """The high_risk step and its findings, from the model's answer and what was retrieved."""
    language, version, on = state["language"], state["law_version"], slice_date(state)
    settled = settle(answer, language)
    law = _law(answer.annex_i.point, state, lookup)
    missing = _missing_question(settled, answer, language, law)
    examples = _examples(answer, retrieved.guidance)
    provisions = [lookup(pid, language, version, on) for pid in dict.fromkeys(settled.cited)]
    step = StepResult(
        step=StepName.HIGH_RISK,
        decision=_decision(settled, answer, language, law, examples, missing),
        facts_used=_facts_used(answer, settled, state.get("facts", ())),
        citations=(
            *(_citation(p) for p in provisions),
            *(_guidance_citation(hit, language) for hit in examples),
        ),
        status=settled.status,
        missing_fact=missing,
        open_question=settled.open_question,
    )
    questions: dict[str, FollowUpQuestion] = {missing.id: missing} if missing else {}
    for key in settled.questions:
        if key is not settled.missing:
            questions.setdefault(key.id, _question(key, language, law))
    return CheckOutcome(
        step=step,
        high_risk_route=settled.route,
        annex_iii_exempt=settled.is_exempt,
        annex_point=settled.point,
        follow_up_questions=tuple(questions.values()),
    )


# --- The model call -----------------------------------------------------------------------------


HIGH_RISK_RESPONSE_FORMAT = json_schema_format("high_risk_answer", HighRiskAnswer)


def _passage(provision_id: str, text: str, heading: str | None = None) -> str:
    body = text if len(text) <= MAX_PASSAGE_CHARS else f"{text[:MAX_PASSAGE_CHARS]} […]"
    title = f" ({heading})" if heading else ""
    return f"[{provision_id}]{title}\n{body}"


def high_risk_messages(state: EngineState, retrieved: Retrieved) -> list[BaseMessage]:
    """The fixed instructions first; the retrieved provisions next; the per-case context and the
    description last (005)."""
    annex_i = "\n".join(f"[{p.provision_id}] {law_title(p)}" for p in retrieved.annex_i) or "-"
    annex_iii = "\n\n".join(_passage(h.provision_id, h.text) for h in retrieved.annex_iii) or "-"
    guidance = (
        "\n\n".join(_passage(h.provision_id, h.text, h.heading) for h in retrieved.guidance) or "-"
    )
    steps = "\n".join(f"- {s.step.value}: {s.decision}" for s in state.get("steps", ())) or "-"
    given = "\n".join(f"- {qid}: {text}" for qid, text in state["answers"].items()) or "-"
    facts = state.get("facts", ())
    numbered = "\n".join(f"{n}. [{f.evidence.value}] {f.text}" for n, f in enumerate(facts, 1))
    return [
        SystemMessage(HIGH_RISK_INSTRUCTIONS),
        HumanMessage(
            f"Annex I:\n{annex_i}\n\n"
            f"Annex III points found:\n{annex_iii}\n\n"
            f"Guideline passages and examples found:\n{guidance}\n\n"
            f"Language for facts and questions: {state['language'].value}\n\n"
            f"Earlier checks:\n{steps}\n\n"
            f"Answers to earlier questions:\n{given}\n\n"
            f"Facts:\n{numbered or '-'}\n\n"
            f"Description:\n{state['description']}"
        ),
    ]


class HighRiskCheck:
    """The high_risk node for the graph: `checks={StepName.HIGH_RISK: HighRiskCheck(), …}`."""

    def __init__(
        self,
        settings: Settings | None = None,
        chat: BaseChatModel | None = None,
        search: Searcher = search_corpus,
        lookup: Lookup = lookup_provision,
    ) -> None:
        """`chat` replaces the OpenRouter model, `search` and `lookup` the corpus (tests).
        Raises `LLMConfigError` when `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set:
        the model is always pinned to its EU endpoint with fallbacks off (decision 005)."""
        self._model = chat or engine_chat_model(max_tokens=MAX_OUTPUT_TOKENS, settings=settings)
        self._search = search
        self._lookup = lookup

    def __call__(self, state: EngineState) -> CheckOutcome:
        """Raises `HighRiskOutputError` when the reply doesn't fit `HighRiskAnswer`."""
        retrieved = retrieve(state, self._search, self._lookup)
        reply = self._model.invoke(
            high_risk_messages(state, retrieved), response_format=HIGH_RISK_RESPONSE_FORMAT
        )
        try:
            answer = HighRiskAnswer.model_validate_json(reply.text)
        except ValidationError as exc:
            message = f"high-risk answer doesn't fit the schema: {describe_validation_error(exc)}"
            raise HighRiskOutputError(message) from exc
        return to_outcome(answer, state, retrieved, self._lookup)
