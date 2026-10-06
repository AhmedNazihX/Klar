"""The transparency node: which Art. 50 duties the system carries (E6; INIT > How it works, Risk
classes).

Retrieval comes first and involves no model (`guideline_retrieval`): the whole of Art. 50 by
lookup, always, and the Commission's Art. 50 guidelines by search. The engine model then answers
fixed key facts for every duty (the prompt in `prompts/transparency.md` first, then Art. 50 and
the passages, the description last, so the prefix is cached: decision 005), and the Act's rules
are applied here, in code:
- **The duties stack.** The list is the system's, whoever bears each duty (the provider for
  Art. 50(1) and (2), the deployer for (3) and (4)), and it is kept whatever class the other
  checks find: a high-risk chatbot is high-risk and has its Art. 50(1) duty. The role step lists
  an Art. 50 duty only when it is here, so every duty that may apply is listed, assumed ones
  included.
- **Each duty** applies when the system is the kind its paragraph names and none of the
  paragraph's exceptions takes it out.
- **Uncertain answers.** A duty the law leaves open makes the step `legally_ambiguous`, a deciding
  fact left open makes it `needs_more_information`; either way the duty is listed as the
  working assumption.
- **The grace period (Art. 111(4)).** A system generating synthetic content that was placed on
  the market before 2 August 2026 has until 2 December 2026 to mark its outputs. The duty is
  listed either way; on a date before that deadline the decision gives it and cites Art. 111(4).
  A system only put into service before then gets the Act's wording (no grace) with the
  guidelines' wider reading noted, and an unknown date is asked. The original text has no
  Art. 111(4).

Every citation is fetched through `get_provision`, or is a retrieved guideline passage.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from aiact.dates import long_date
from aiact.db import connect
from aiact.engine.nodes import transparency_texts as texts
from aiact.engine.nodes.common import (
    facts_section,
    guidance_citation,
    guidance_section,
    lookup_for,
    named_passages,
    provision_citation,
    refused_check,
)
from aiact.engine.nodes.guideline_retrieval import (
    GuidelineCorpus,
    GuidelineLibrary,
    GuidelineSource,
    Retrieved,
    retrieve,
)
from aiact.engine.nodes.key_facts import Answer, facts_used
from aiact.engine.nodes.questions import ReadingSide, ask, open_question
from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.engine.nodes.transparency_duties import (
    Duty,
    MarketTiming,
    TransparencyAnswer,
    duties,
)
from aiact.engine.state import CheckOutcome, EngineState
from aiact.llm import OpenRouterEmbeddings, engine_chat_model
from aiact.llm.replies import OpenQuestion as ReplyOpenQuestion
from aiact.llm.structured import (
    ProviderRefusalError,
    describe_validation_error,
    json_schema_format,
    parse_reply,
)
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.retrieval.search import QueryEmbedder
from aiact.schemas import (
    Citation,
    FollowUpQuestion,
    Language,
    LawVersion,
    OpenQuestion,
    RiskClass,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import Settings

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "transparency.md"
TRANSPARENCY_INSTRUCTIONS = PROMPT_PATH.read_text(encoding="utf-8")

SOURCE = GuidelineSource(article="art:50", doc_keys=frozenset({"guide-art50"}), passages=8)
"""Art. 50, read whole, and the Commission's guidelines on the Art. 50 transparency obligations
(8 passages: Art. 50 has four duties, each with exceptions)."""

MAX_OUTPUT_TOKENS = 4000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005)."""

MARKING = "art:50:2"
GRACE_PERIOD = "art:111:4"
MARKING_DEADLINE = date(2026, 12, 2)
"""Art. 111(4): systems placed on the market before 2 August 2026 mark their outputs by then."""
ALL_DUTIES = ("art:50:1", "art:50:2", "art:50:3", "art:50:4")
"""Every duty Art. 50 places on a provider or a deployer."""

GRACE_TEXTS: dict[MarketTiming, str] = {
    MarketTiming.PLACED_BEFORE: "grace",
    MarketTiming.IN_SERVICE_BEFORE: "grace_in_service",
    MarketTiming.UNKNOWN: "grace_unknown",
}
"""The decision sentence for each launch date the grace period may concern."""
PLACED_BEFORE_SENTENCE = GRACE_TEXTS[MarketTiming.PLACED_BEFORE]
"""The only sentence that gives the grace period outright."""


class TransparencyOutputError(ValueError):
    """The model's answer doesn't fit `TransparencyAnswer` (a broken output)."""


# --- Applying Art. 50 to the answer -------------------------------------------------------------


@dataclass(frozen=True)
class Settlement:
    """What Art. 50 gives: the step's status, the duties listed (applying, assumed or open), those
    raised but ruled out (unless their paragraph is listed through its other part: Art. 50(4) has
    two), those open in law, those open on a fact, and the questions to ask."""

    status: Status
    listed: tuple[Duty, ...]
    considered: tuple[Duty, ...]
    opened: tuple[Duty, ...]
    unknown: tuple[Duty, ...]
    missing: tuple[KeyQuestion, ...]

    @property
    def provisions(self) -> tuple[str, ...]:
        """The listed duties' paragraphs, each once, in the order of Art. 50."""
        return tuple(dict.fromkeys(duty.provision for duty in self.listed))


def settle(answer: TransparencyAnswer) -> Settlement:
    """Apply Art. 50 to the model's answers. A duty the law leaves open makes the step ambiguous,
    then one open on a fact makes it miss a fact; otherwise it is decided."""
    read = duties(answer)
    opened = tuple(d for d in read if d.is_open)
    unknown = tuple(d for d in read if d.reading.answer is Answer.UNKNOWN and not d.is_open)
    asked = (d.reading.missing for d in unknown if d.reading.missing)
    if opened:
        status = Status.LEGALLY_AMBIGUOUS
    elif unknown:
        status = Status.NEEDS_MORE_INFORMATION
    else:
        status = Status.DECIDED
    listed = tuple(d for d in read if d.is_listed)
    in_force = {d.provision for d in listed}
    return Settlement(
        status=status,
        listed=listed,
        considered=tuple(
            d for d in read if d.is_raised and not d.is_listed and d.provision not in in_force
        ),
        opened=opened,
        unknown=unknown,
        missing=tuple({key.id: key for key in asked}.values()),
    )


def grace_text(
    settled: Settlement, timing: MarketTiming, law_version: LawVersion, as_of: date
) -> str | None:
    """The key of the grace-period sentence, when Art. 111(4) bears on the marking duty on
    `as_of`: it is listed, the text read is the amended one, the deadline hasn't passed, and the
    system may have been on the market before 2 August 2026."""
    if MARKING not in settled.provisions or law_version is LawVersion.ORIGINAL:
        return None
    if as_of >= MARKING_DEADLINE:
        return None
    return GRACE_TEXTS.get(timing)


def grace_sentence(key: str, language: Language) -> str:
    """The grace-period sentence `key` (one of `GRACE_TEXTS`' values), with the deadline."""
    return texts.TEXTS[language][key].format(deadline=long_date(MARKING_DEADLINE, language.value))


# --- The step -----------------------------------------------------------------------------------


def _stricter_class(state: EngineState) -> RiskClass | None:
    """The class a duty's stricter reading gives: limited risk, unless an earlier check already
    holds a higher class (a duty then changes no class)."""
    is_higher = StepName.PROHIBITED in state.get("matches", ()) or "high_risk_route" in state
    return None if is_higher else RiskClass.LIMITED_RISK


def _open_question(duty: Duty, state: EngineState, citations: Sequence[Citation]) -> OpenQuestion:
    """The model's open question for the duty, or a fixed one when it gave none, with its two
    readings quoting the duty's paragraph from the step's `citations`."""
    language = state["language"]
    point = texts.provision_name(duty.provision, language)
    plain = duty.summary.open_question
    if plain is None:
        question, stricter, lenient = (t.format(point=point) for t in texts.OPEN_FALLBACK[language])
        plain = ReplyOpenQuestion(question=question, readings=(stricter, lenient))
    words = {key: text.format(point=point) for key, text in texts.READINGS[language].items()}
    applies = ReadingSide(
        words["applies"], words["applies_consequence"], _stricter_class(state), duty.provision
    )
    does_not = ReadingSide(
        words["does_not_apply"], words["does_not_apply_consequence"], None, duty.provision
    )
    return open_question(plain, applies, does_not, citations)


def _finding(settled: Settlement, language: Language, question: str) -> tuple[str, ...]:
    """The sentences of the finding: the duties and their facts, why a duty is only assumed, and
    the duties raised but ruled out."""
    words = texts.TEXTS[language]
    considered = tuple(
        words["considered"].format(
            point=texts.provision_name(d.provision, language), fact=d.summary.fact
        )
        for d in settled.considered
    )
    if not settled.listed:
        return (words["none"], *considered)
    points = ", ".join(texts.provision_name(pid, language) for pid in settled.provisions)
    facts = tuple(dict.fromkeys(d.summary.fact for d in settled.listed))
    uncertain = settled.opened or settled.unknown
    why: tuple[str, ...] = ()
    if uncertain:
        key = "ambiguous" if settled.opened else "missing"
        point = texts.provision_name(uncertain[0].provision, language)
        why = (words[key].format(point=point, question=question),)
    return (words["duties"].format(points=points), *facts, *why, *considered)


@dataclass(frozen=True)
class Grace:
    """What Art. 111(4) adds to the step: its sentence, the provision as fetched, and the
    question about the launch date when that is unknown."""

    sentence: str
    provision: Provision
    questions: tuple[FollowUpQuestion, ...]


def _grace(
    settled: Settlement,
    answer: TransparencyAnswer,
    state: EngineState,
    library: GuidelineLibrary,
) -> Grace | None:
    """The grace period as it bears on this run; None when it doesn't, or when the text read has
    no Art. 111(4)."""
    timing, language = answer.market_timing, state["language"]
    key = grace_text(settled, timing, state["law_version"], state["as_of"])
    if key is None:
        return None
    try:
        provision = library.provision(GRACE_PERIOD, lookup_for(state))
    except ProvisionNotFoundError:
        return None
    is_unknown = timing is MarketTiming.UNKNOWN
    return Grace(
        sentence=grace_sentence(key, language),
        provision=provision,
        questions=(ask(texts.MARKET_DATE, language, StepName.TRANSPARENCY),) if is_unknown else (),
    )


def _cited(
    settled: Settlement, state: EngineState, retrieved: Retrieved, library: GuidelineLibrary
) -> tuple[Provision, ...]:
    """The paragraphs of every duty shown, fetched in the order of Art. 50; Art. 50 as a whole
    when none is raised."""
    shown = {duty.provision for duty in (*settled.listed, *settled.considered)}
    if not shown:
        return (retrieved.article,)
    lookup = lookup_for(state)
    return tuple(library.provision(pid, lookup) for pid in ALL_DUTIES if pid in shown)


def to_outcome(
    answer: TransparencyAnswer,
    state: EngineState,
    retrieved: Retrieved,
    library: GuidelineLibrary,
) -> CheckOutcome:
    """The transparency step and the duties it lists, from the model's answer and the passages
    retrieved. The cited provisions are fetched from `library`."""
    language = state["language"]
    settled = settle(answer)
    grace = _grace(settled, answer, state, library)
    citations = (
        *(provision_citation(p) for p in _cited(settled, state, retrieved, library)),
        *((provision_citation(grace.provision),) if grace else ()),
        *(
            guidance_citation(hit, language)
            for hit in named_passages(answer.guidance_numbers, retrieved.guidance)
        ),
    )
    is_ambiguous = settled.status is Status.LEGALLY_AMBIGUOUS
    opened = settled.opened[0] if is_ambiguous else None
    open_question = _open_question(opened, state, citations) if opened else None
    questions = tuple(ask(key, language, StepName.TRANSPARENCY) for key in settled.missing)
    is_missing = settled.status is Status.NEEDS_MORE_INFORMATION
    missing_fact = questions[0] if is_missing else None
    asked = open_question.question if open_question else missing_fact.text if missing_fact else ""
    shown = tuple(d.summary for d in (*settled.listed, *settled.considered))
    step = StepResult(
        step=StepName.TRANSPARENCY,
        decision=" ".join(
            (*_finding(settled, language, asked), *((grace.sentence,) if grace else ()))
        ),
        facts_used=facts_used(shown, state.get("facts", ())),
        citations=citations,
        status=settled.status,
        missing_fact=missing_fact,
        open_question=open_question,
    )
    return CheckOutcome(
        step=step,
        transparency_duties=settled.provisions,
        follow_up_questions=(*questions, *(grace.questions if grace else ())),
    )


def refusal_outcome(state: EngineState, retrieved: Retrieved) -> CheckOutcome:
    """The step for a reply the provider's content filter refused (decision 029): not assessed,
    every Art. 50 duty assumed until a person reviews it (the stricter reading), citing Art. 50
    as fetched. The review question is a missing fact."""
    language = state["language"]
    return refused_check(
        StepName.TRANSPARENCY,
        language,
        texts.REFUSAL[language],
        (provision_citation(retrieved.article),),
        ask(texts.PERSON_REVIEW, language, StepName.TRANSPARENCY),
        transparency_duties=ALL_DUTIES,
    )


# --- The model call -----------------------------------------------------------------------------


TRANSPARENCY_RESPONSE_FORMAT = json_schema_format("transparency_answer", TransparencyAnswer)


def transparency_messages(state: EngineState, retrieved: Retrieved) -> list[BaseMessage]:
    """The fixed instructions and Art. 50 first; the passages, the per-case context and the
    description last, so the shared prefix is cached (005)."""
    version = state["law_version"].value
    return [
        SystemMessage(TRANSPARENCY_INSTRUCTIONS),
        HumanMessage(
            f"The AI Act, Article 50 ({version} text):\n\n{retrieved.article.text}\n\n"
            f"Guidelines on the transparency obligations under Article 50, passages:\n\n"
            f"{guidance_section(retrieved.guidance)}\n\n"
            f"Language for facts and questions: {state['language'].value}\n\n"
            f"Facts:\n{facts_section(state)}\n\n"
            f"Description:\n{state['description']}"
        ),
    ]


class TransparencyCheck:
    """The transparency node for the graph: `checks={StepName.TRANSPARENCY: TransparencyCheck(),
    …}`."""

    def __init__(
        self,
        settings: Settings | None = None,
        chat: BaseChatModel | None = None,
        library: GuidelineLibrary | None = None,
        embedder: QueryEmbedder | None = None,
    ) -> None:
        """`chat` replaces the OpenRouter model and `library` the corpus (tests). Raises
        `LLMConfigError` when `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set: the
        model is always pinned to its EU endpoint with fallbacks off (decision 005). Without a
        `library`, the query embedder is `embedder` (shared by a run, E10) or is built here
        from the same settings, so
        `EMBEDDING_MODEL` and `EMBEDDING_PROVIDER` must be set too; each step then reads the
        corpus over a short connection before the model call, and another for the citations
        after it."""
        self._model = chat or engine_chat_model(max_tokens=MAX_OUTPUT_TOKENS, settings=settings)
        self._library = library
        self._embedder = None if library else embedder or OpenRouterEmbeddings(settings=settings)

    def _reading[T](self, use: Callable[[GuidelineLibrary], T]) -> T:
        """`use` applied to the corpus: the given library, or one over a fresh connection that
        is closed before this returns (none stays open during the model call)."""
        if self._library is not None:
            return use(self._library)
        assert self._embedder is not None  # built whenever no library is given
        with connect() as connection:
            return use(GuidelineCorpus(connection, self._embedder, SOURCE))

    def __call__(self, state: EngineState) -> CheckOutcome:
        """A reply the provider's content filter refused gives `refusal_outcome`. Raises
        `TransparencyOutputError` when any other reply doesn't fit `TransparencyAnswer`, and
        `ProvisionNotFoundError` when the corpus lacks a provision the step reads or cites."""
        retrieved = self._reading(lambda library: retrieve(state, library, SOURCE.article))
        reply = self._model.invoke(
            transparency_messages(state, retrieved),
            response_format=TRANSPARENCY_RESPONSE_FORMAT,
        )
        try:
            answer = parse_reply(reply, TransparencyAnswer)
        except ProviderRefusalError:
            return refusal_outcome(state, retrieved)
        except ValidationError as exc:
            message = (
                f"transparency answer doesn't fit the schema: {describe_validation_error(exc)}"
            )
            raise TransparencyOutputError(message) from None
        return self._reading(lambda library: to_outcome(answer, state, retrieved, library))
