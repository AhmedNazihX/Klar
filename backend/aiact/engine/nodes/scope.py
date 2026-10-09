"""The scope node: is it an AI system under Art. 3(1), and does an Art. 2 rule take it out of the
Act's scope (E3; INIT > How it works, Risk classes)?

The node fetches Art. 3(1) and Art. 2 by number (`get_provision`) and searches the Commission's
definition guidelines by meaning (`search_ai_act`) with the description. The engine model reads
the fixed instructions (`prompts/scope.md`) and the law first, then the guideline passages, the
facts and the description last, so the shared prefix is cached (decision 005). It only answers
fixed key-fact questions; the Act's rules are applied here, in code:

- Not an AI system (Art. 3(1)), or an Art. 2 exclusion applies: out of scope, decided, and the
  run ends. The exclusions are no link to the Union (2(1)), exclusively military, defence or
  national security (2(3)), scientific research only (2(6)), purely personal use by a natural
  person (2(10)), and a free and open-source release that isn't put on the market as high-risk
  or under Art. 5 or 50 (2(12)).
- Art. 2(8) is a note, never an exclusion (user, 2026-09-30): it exempts today's research,
  testing and development, and a system being built for a planned launch is classified as the
  system it will be once placed on the market or put into service. The note is named in the
  decision and cited.
- The definition question is contested (the facts are known, but Art. 3(1) and the guidelines
  point different ways): legally ambiguous, with in scope as the stricter working assumption.
- A deciding fact the description hints at but doesn't settle: needs more information, again
  with in scope as the working assumption. Every unknown fact becomes a follow-up question.

`matched` is True only for a decided out-of-scope finding: an uncertain scope question keeps the
run going (decision 010), and its working assumption is in scope, the stricter reading. A reply
the provider's content filter refused (decision 029) is not assessed: in scope is assumed until
a person reviews the description, and the step cites what the reviewer checks it against, Art.
3(1) and Art. 2(1). Citations name paragraphs, never the whole of Art. 2 (E16).

Guideline searches pass `max_distance=None` (a signal, not a filter), and pass the caller's
`exclude_source_example_ids` and the run's `include_held_out` (False except in V8's gap run)
through. A German search falls back to
English when no German passage of the definition guidelines is found.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import Field, ValidationError

from aiact.engine.nodes.common import (
    Lookup,
    cited_provisions,
    facts_section,
    guidance_citation,
    lookup_for,
    named_passages,
    refused_check,
)
from aiact.engine.nodes.corpus import CorpusReader, CorpusReading
from aiact.engine.nodes.key_facts import Answer, CitedFact, KeyFact, facts_used
from aiact.engine.nodes.questions import follow_up, hint, open_question
from aiact.engine.nodes.reading_side import ReadingSide
from aiact.engine.nodes.scope_texts import (
    AI_SYSTEM,
    EU_LINK,
    EXCLUSIONS,
    GUIDED_LENIENT_READING,
    OPEN_QUESTION,
    OPEN_SOURCE,
    OPEN_SOURCE_EXCEPTION,
    PERSON_REVIEW,
    PRE_MARKET_DEVELOPMENT,
    READING_SIDES,
    READINGS,
    REFUSAL_CITATIONS,
    TEXTS,
    ScopeQuestion,
)
from aiact.engine.state import CheckOutcome, EngineState
from aiact.llm import engine_chat_model
from aiact.llm.replies import OpenQuestion as ReplyOpenQuestion
from aiact.llm.structured import (
    ProviderRefusalError,
    describe_validation_error,
    json_schema_format,
    parse_reply,
)
from aiact.retrieval.provisions import Provision
from aiact.retrieval.search import QueryEmbedder, SearchHit
from aiact.schemas import (
    Citation,
    EvidenceTag,
    FollowUpQuestion,
    Language,
    OpenQuestion,
    RiskClass,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.base import ContractModel
from aiact.settings import Settings

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "scope.md"
SCOPE_INSTRUCTIONS = PROMPT_PATH.read_text(encoding="utf-8")

MAX_OUTPUT_TOKENS = 3000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005)."""

DEFINITION_ARTICLE = "art:3:1"
SCOPE_ARTICLE = "art:2"
LAW_IN_PROMPT = (DEFINITION_ARTICLE, SCOPE_ARTICLE)
"""The provisions the model always reads: the definition and the whole of Art. 2."""

GUIDANCE_DOC_KEYS = frozenset({"guide-definition"})
"""The manifest key of the Commission's guidelines on the AI system definition; the search is
limited to it inside the SQL, so the other guidelines never crowd it out."""
GUIDANCE_PASSAGES = 5
"""How many definition-guideline passages the model reads."""
GUIDANCE_QUERY = "Is this an AI system under the AI system definition? {description}"
"""The search query: the description, framed as the definition question."""


class Definition(StrEnum):
    """The answer to the Art. 3(1) question; `contested` means the law leaves it open."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"
    CONTESTED = "contested"


class DefinitionFact(ContractModel):
    """The Art. 3(1) answer, with the guideline passages it rests on. Enum fields carry no
    description: strict structured output rejects keywords next to a `$ref`."""

    answer: Definition
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]
    guidance_numbers: tuple[int, ...]

    @property
    def is_known(self) -> bool:
        return self.answer is not Definition.UNKNOWN


class GuidanceFact(KeyFact):
    """Whether a guideline passage the model read names the system's technique among those
    outside the AI system definition, and which passages do."""

    guidance_numbers: tuple[int, ...]


class ScopeAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill. Each Art. 2 field is named
    after its `ScopeQuestion.id`."""

    ai_system: DefinitionFact
    guidance_excludes_technique: GuidanceFact
    eu_link: KeyFact
    military_only: KeyFact
    research_only: KeyFact
    pre_market_development: KeyFact
    personal_use: KeyFact
    open_source: KeyFact
    open_source_exception: KeyFact


SCOPE_RESPONSE_FORMAT = json_schema_format("scope_answer", ScopeAnswer)


class ScopeOutputError(ValueError):
    """The model's answer doesn't fit `ScopeAnswer` (a broken output)."""


# --- Retrieval ----------------------------------------------------------------------------------


class ScopeLibrary(Protocol):
    """Where the node reads the law and the guidance from (`CorpusLibrary`, or a replay)."""

    def provision(self, provision_id: str, lookup: Lookup) -> Provision: ...

    def definition_guidance(self, query: str, lookup: Lookup) -> tuple[SearchHit, ...]: ...


class CorpusLibrary(CorpusReader):
    """The corpus over one connection and one embedder (`ScopeCheck` opens the connection once
    per use), its guidance searches limited to the definition guidelines."""

    def definition_guidance(self, query: str, lookup: Lookup) -> tuple[SearchHit, ...]:
        """The best passages of the definition guidelines in the language asked for, else in
        English (most guidance exists only in English)."""
        for language in dict.fromkeys((lookup.language, Language.EN)):
            hits = self.passages(
                query,
                lookup,
                language=language,
                doc_keys=GUIDANCE_DOC_KEYS,
                limit=GUIDANCE_PASSAGES,
            )
            if hits:
                return hits
        return ()


def retrieve(
    state: EngineState, library: ScopeLibrary
) -> tuple[tuple[Provision, ...], tuple[SearchHit, ...]]:
    """The law the prompt quotes (Art. 3(1) and Art. 2) by lookup, then the definition guidance
    closest to the description. Raises `ProvisionNotFoundError` when the corpus lacks a
    provision."""
    lookup = lookup_for(state)
    law = tuple(library.provision(pid, lookup) for pid in LAW_IN_PROMPT)
    query = GUIDANCE_QUERY.format(description=state["description"])
    return law, library.definition_guidance(query, lookup)


# --- Settling scope -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Verdict:
    """Whether one rule takes the system out of scope, what to ask when that is unknown, and
    the answers it rests on."""

    excludes: Answer
    ask: ScopeQuestion
    used: tuple[KeyFact, ...]


def _verdict(rule: ScopeQuestion, answer: ScopeAnswer) -> Verdict:
    if rule is EU_LINK:
        link = answer.eu_link
        flipped = {Answer.YES: Answer.NO, Answer.NO: Answer.YES, Answer.UNKNOWN: Answer.UNKNOWN}
        return Verdict(flipped[link.answer], EU_LINK, (link,))
    if rule is OPEN_SOURCE:
        return _open_source_verdict(answer.open_source, answer.open_source_exception)
    key_fact: KeyFact = getattr(answer, rule.id)
    return Verdict(key_fact.answer, rule, (key_fact,))


def _open_source_verdict(licence: KeyFact, exception: KeyFact) -> Verdict:
    """Art. 2(12) excludes an open-source system unless it is put on the market as high-risk
    or under Art. 5 or 50; either "no" settles it, whatever the other answer."""
    if licence.answer is Answer.NO:
        return Verdict(Answer.NO, OPEN_SOURCE, (licence,))
    if exception.answer is Answer.YES:
        return Verdict(Answer.NO, OPEN_SOURCE_EXCEPTION, (licence, exception))
    if licence.answer is Answer.UNKNOWN:
        return Verdict(Answer.UNKNOWN, OPEN_SOURCE, (licence,))
    if exception.answer is Answer.UNKNOWN:
        return Verdict(Answer.UNKNOWN, OPEN_SOURCE_EXCEPTION, (licence, exception))
    return Verdict(Answer.YES, OPEN_SOURCE, (licence, exception))


def _is_raised(verdict: Verdict) -> bool:
    """The description spoke to the rule: some answer it rests on isn't just the default."""
    return any(fact.evidence is not EvidenceTag.ASSUMED for fact in verdict.used)


@dataclass(frozen=True)
class ScopeSettlement:
    """What the rules give: the rules that take the system out of scope, the rules the
    description raised that don't apply, the deciding facts still missing, whether the
    definition is contested, and the answers relied on."""

    excluded_by: tuple[ScopeQuestion, ...]
    raised: tuple[ScopeQuestion, ...]
    missing: tuple[ScopeQuestion, ...]
    is_contested: bool
    used: tuple[CitedFact, ...]
    notes: tuple[ScopeQuestion, ...] = ()
    """Rules named in the result that never decide it: Art. 2(8) for a system still in
    development, which is classified as it will be placed on the market or put into service."""
    against: tuple[str, ...] = ()
    """The guideline passages that place the technique outside the definition, when the model
    reads Art. 3(1) as covering it (so the definition is contested)."""

    @property
    def is_out_of_scope(self) -> bool:
        return bool(self.excluded_by)

    @property
    def status(self) -> Status:
        if self.is_out_of_scope:
            return Status.DECIDED
        if self.is_contested:
            return Status.LEGALLY_AMBIGUOUS
        return Status.NEEDS_MORE_INFORMATION if self.missing else Status.DECIDED

    def cited_articles(self) -> tuple[str, ...]:
        """Art. 3(1) always (recital 12 when the definition decided or is open); then the rules
        that take the system out, or, in scope, Art. 2(1) and every rule raised or asked; and
        the notes."""
        definition = (DEFINITION_ARTICLE,)
        if AI_SYSTEM in (*self.excluded_by, *self.missing) or self.is_contested:
            definition = (DEFINITION_ARTICLE, *AI_SYSTEM.recitals)
        rules = (*(self.excluded_by or (EU_LINK, *self.raised, *self.missing)), *self.notes)
        cited = (*definition, *(pid for rule in rules for pid in (rule.article, *rule.recitals)))
        return tuple(dict.fromkeys(cited))


def excluding_passages(answer: ScopeAnswer, guidance: Sequence[SearchHit]) -> tuple[SearchHit, ...]:
    """The passages that, by the model's answer, name the system's technique among those outside
    the definition; none unless it answered yes and cited at least one passage it was given."""
    named = answer.guidance_excludes_technique
    return named_passages(named.guidance_numbers, guidance) if named.answer is Answer.YES else ()


def settle_scope(answer: ScopeAnswer, guidance: Sequence[SearchHit] = ()) -> ScopeSettlement:
    """Apply Art. 3(1) and the Art. 2 exclusions to the model's answers.

    A guideline passage that places the system's technique outside the definition, while the
    model reads Art. 3(1) as covering it, makes the definition contested: an open question of
    law, never a reading the model picks (user, 2026-09-30). A "no" to Art. 3(1) stays a decided
    out-of-scope finding."""
    definition = answer.ai_system
    excluded: list[ScopeQuestion] = [AI_SYSTEM] if definition.answer is Definition.NO else []
    missing: list[ScopeQuestion] = [AI_SYSTEM] if definition.answer is Definition.UNKNOWN else []
    raised: list[ScopeQuestion] = []
    used: list[CitedFact] = [definition]
    against = excluding_passages(answer, guidance)
    is_covered = definition.answer in (Definition.YES, Definition.CONTESTED)
    is_contested = definition.answer is Definition.CONTESTED or (is_covered and bool(against))
    if is_covered and against:
        used.append(answer.guidance_excludes_technique)
    for rule in EXCLUSIONS:
        verdict = _verdict(rule, answer)
        if verdict.excludes is Answer.YES:
            excluded.append(rule)
            used.extend(verdict.used)
        elif verdict.excludes is Answer.UNKNOWN:
            missing.append(verdict.ask)
        elif rule is EU_LINK:
            used.extend(verdict.used)  # the territorial fact is always shown; Art. 2(1) is cited
        elif _is_raised(verdict):
            raised.append(rule)
            used.extend(verdict.used)
    in_development = answer.pre_market_development
    is_noted = in_development.answer is Answer.YES
    return ScopeSettlement(
        excluded_by=tuple(excluded),
        raised=tuple(raised),
        missing=tuple(missing),
        is_contested=is_contested,
        used=(*used, *((in_development,) if is_noted else ())),
        notes=(PRE_MARKET_DEVELOPMENT,) if is_noted else (),
        against=tuple(hit.provision_id for hit in against) if is_covered else (),
    )


# --- The step -----------------------------------------------------------------------------------


def _decision(settled: ScopeSettlement, answer: ScopeAnswer, language: Language) -> str:
    """The finding, then the notes (Art. 2(8)), which never change it."""
    notes = tuple(rule.reason[language] for rule in settled.notes if rule.reason)
    return " ".join((_finding(settled, answer, language), *notes))


def _finding(settled: ScopeSettlement, answer: ScopeAnswer, language: Language) -> str:
    texts = TEXTS[language]
    if settled.is_out_of_scope:
        reasons = (rule.reason[language] for rule in settled.excluded_by if rule.reason)
        return " ".join((texts["out_of_scope"], *reasons))
    questions = [rule.asked(language) for rule in settled.missing]
    if settled.is_contested:
        asked = (texts["still_asked"].format(question=q) for q in questions)
        return " ".join((texts["ambiguous"], answer.ai_system.fact, *asked))
    if questions:
        return texts["assumption"].format(question=questions[0])
    return " ".join((texts["in_scope"], answer.ai_system.fact, answer.eu_link.fact))


def _question(rule: ScopeQuestion, language: Language) -> FollowUpQuestion:
    why = hint(StepName.SCOPE, rule.article, language)
    return follow_up(rule.id, rule.asked(language), rule.article, why, is_yes_no=rule.is_yes_no)


def _open_question(
    settled: ScopeSettlement, language: Language, citations: Sequence[Citation]
) -> OpenQuestion | None:
    """Both readings, stricter first, quoting Art. 3(1) from the step's `citations`; the lenient
    one names, and quotes, the guideline passages behind it."""
    if settled.status is not Status.LEGALLY_AMBIGUOUS:
        return None
    stricter, lenient = READINGS[language]
    if settled.against:
        passages = ", ".join(settled.against)
        lenient = GUIDED_LENIENT_READING[language].format(passages=passages)
    plain = ReplyOpenQuestion(question=OPEN_QUESTION[language], readings=(stricter, lenient))
    words = READING_SIDES[language]
    is_ai = ReadingSide(
        words["ai_system"], words["ai_system_consequence"], None, DEFINITION_ARTICLE
    )
    not_ai = ReadingSide(
        words["not_ai_system"],
        words["not_ai_system_consequence"],
        RiskClass.OUT_OF_SCOPE,
        settled.against[0] if settled.against else DEFINITION_ARTICLE,
    )
    return open_question(plain, is_ai, not_ai, citations)


def _guidance_used(answer: ScopeAnswer, guidance: Sequence[SearchHit]) -> tuple[SearchHit, ...]:
    """The passages the definition answer rests on, then those that place the technique outside
    the definition, each once."""
    named = (*named_passages(answer.ai_system.guidance_numbers, guidance),
             *excluding_passages(answer, guidance))  # fmt: skip
    return tuple(dict.fromkeys(named))


def to_outcome(
    answer: ScopeAnswer,
    state: EngineState,
    guidance: Sequence[SearchHit],
    library: ScopeLibrary,
) -> CheckOutcome:
    """The scope step and whether it ends the run, from the model's answer and the passages it
    read. The cited provisions are fetched from `library`."""
    language = state["language"]
    settled = settle_scope(answer, guidance)
    cited = (
        *cited_provisions(settled.cited_articles(), state, library),
        *(guidance_citation(hit, language) for hit in _guidance_used(answer, guidance)),
    )
    missing = settled.missing if not settled.is_out_of_scope else ()
    step = StepResult(
        step=StepName.SCOPE,
        decision=_decision(settled, answer, language),
        facts_used=facts_used(settled.used, state.get("facts", ())),
        citations=cited,
        status=settled.status,
        missing_fact=_question(missing[0], language) if missing else None,
        open_question=_open_question(settled, language, cited),
    )
    questions = tuple(_question(rule, language) for rule in missing)
    return CheckOutcome(step=step, matched=settled.is_out_of_scope, follow_up_questions=questions)


def refusal_outcome(
    state: EngineState, law: Sequence[Provision], library: ScopeLibrary
) -> CheckOutcome:
    """The step for a reply the provider's content filter refused (decisions 029, 030): not
    assessed, and no class until a person reviews it. It cites what the reviewer checks the
    description against (`REFUSAL_CITATIONS`, E16): Art. 3(1) as the model read it in `law`, and
    Art. 2(1), fetched from `library`. The review question is a missing fact."""
    language = state["language"]
    return refused_check(
        StepName.SCOPE,
        language,
        cited_provisions(REFUSAL_CITATIONS, state, library, known=law),
        _question(PERSON_REVIEW, language),
    )


# --- The model call -----------------------------------------------------------------------------


def _law_section(provisions: Sequence[Provision]) -> str:
    return "\n\n".join(
        f"[{p.provision_id}] {p.heading or ''}\n{p.text}".strip() for p in provisions
    )


def _guidance_section(guidance: Sequence[SearchHit]) -> str:
    listed = (f"{n}. [{hit.provision_id}] {hit.text}" for n, hit in enumerate(guidance, 1))
    return "\n\n".join(listed) or "-"


def scope_messages(
    state: EngineState, law: Sequence[Provision], guidance: Sequence[SearchHit]
) -> list[BaseMessage]:
    """The fixed instructions and the law first; the guideline passages, the per-case context and
    the description last, so the shared prefix is cached (005)."""
    version = state["law_version"].value
    return [
        SystemMessage(SCOPE_INSTRUCTIONS),
        HumanMessage(
            f"The AI Act ({version} text):\n\n{_law_section(law)}\n\n"
            f"Definition guidelines passages:\n\n{_guidance_section(guidance)}\n\n"
            f"Language for facts: {state['language'].value}\n\n"
            f"Facts:\n{facts_section(state)}\n\n"
            f"Description:\n{state['description']}"
        ),
    ]


class ScopeCheck:
    """The scope node for the graph: `checks={StepName.SCOPE: ScopeCheck(), …}`."""

    def __init__(
        self,
        settings: Settings | None = None,
        chat: BaseChatModel | None = None,
        library: ScopeLibrary | None = None,
        embedder: QueryEmbedder | None = None,
    ) -> None:
        """`chat` replaces the OpenRouter model and `library` the corpus (tests). Raises
        `LLMConfigError` when `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set: the
        model is always pinned to its EU endpoint with fallbacks off (decision 005). Without a
        `library`, the query embedder is `embedder` (shared by a run, E10) or is built here
        from the same settings, so `EMBEDDING_MODEL` and `EMBEDDING_PROVIDER` must be set too;
        each step then reads the corpus over a short connection before the model call, and
        another for the citations after it."""
        self._model = chat or engine_chat_model(max_tokens=MAX_OUTPUT_TOKENS, settings=settings)
        self._reading = CorpusReading(library, CorpusLibrary, embedder=embedder, settings=settings)

    def __call__(self, state: EngineState) -> CheckOutcome:
        """A reply the provider's content filter refused gives `refusal_outcome`. Raises
        `ScopeOutputError` when any other reply doesn't fit `ScopeAnswer`, and
        `ProvisionNotFoundError` when the corpus lacks a provision the step reads or cites."""
        law, guidance = self._reading(lambda library: retrieve(state, library))
        reply = self._model.invoke(
            scope_messages(state, law, guidance), response_format=SCOPE_RESPONSE_FORMAT
        )
        try:
            answer = parse_reply(reply, ScopeAnswer)
        except ProviderRefusalError:
            return self._reading(lambda library: refusal_outcome(state, law, library))
        except ValidationError as exc:
            message = f"scope answer doesn't fit the schema: {describe_validation_error(exc)}"
            raise ScopeOutputError(message) from None
        return self._reading(lambda library: to_outcome(answer, state, guidance, library))
