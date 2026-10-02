"""The prohibited node: does the system match a practice Art. 5 prohibits (E4; INIT > How it works,
Risk classes)?

Retrieval comes first and involves no model (`prohibited_retrieval`): the whole of Art. 5 by
lookup, always, and the guidelines on prohibited practices by search. The engine model then
answers fixed key facts for every practice (the prompt in `prompts/prohibited.md` first, then
Art. 5 and the passages, the description last, so the prefix is cached: decision 005), and the
Act's rules are applied here, in code:
- **Each practice** is met when all its conditions are, and none of its exceptions applies:
  (a) and (b) need a significant harm, a deciding fact like any other (B12); (ba) and (bb) need
  one of the Art. 5(1a) routes (the intended purpose, a foreseeable outcome without safeguards,
  or a deployer's own use for that purpose), and Art. 5(1b) takes a manipulation that shows no
  more out of (ba); (f) at work or in education asks whether the system infers emotions (B12).
- **Art. 5(1)(h)** bans real-time remote biometric identification for law enforcement unless the
  use serves one of the listed objectives and meets Art. 5(2), (3) and (5): national law allows
  it, each use is authorised in advance, it only confirms a targeted person within set limits,
  and the impact assessment and registration are done (C7's follow-up). A permitted use names
  the Art. 5(4) notification duty. A private operator's use is not law enforcement.
- **Dates (Art. 113(a)).** Points (ba) and (bb), with Art. 5(1a) and (1b), apply from 2 December
  2026; the rest of Art. 5 from 2 February 2025. A practice is read against the run's `as_of`: one
  not yet applicable never makes the system prohibited, and the decision says when it starts.
  The original text has no points (ba) or (bb), so they are not read for it.
- **Uncertain answers.** A practice the law leaves open makes the step `legally_ambiguous`, a
  deciding fact left open makes it `needs_more_information`; either way prohibited is the
  labelled working assumption, `matched` is set, and the run goes on (decision 010).

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
from aiact.engine.nodes import prohibited_texts as texts
from aiact.engine.nodes.common import (
    answers_section,
    clipped,
    facts_section,
    guidance_citation,
    key_question,
    lookup_for,
    named_passages,
    provision_citation,
)
from aiact.engine.nodes.key_facts import Answer, facts_used
from aiact.engine.nodes.prohibited_practices import (
    APPLICATION_DATES,
    Practice,
    ProhibitedAnswer,
    practices,
)
from aiact.engine.nodes.prohibited_retrieval import (
    ProhibitedCorpus,
    ProhibitedLibrary,
    Retrieved,
    retrieve,
)
from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.engine.state import CheckOutcome, EngineState
from aiact.llm import OpenRouterEmbeddings, engine_chat_model
from aiact.llm.structured import describe_validation_error, json_schema_format
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.retrieval.search import SearchHit
from aiact.schemas import (
    Fact,
    Language,
    LawVersion,
    OpenQuestion,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import Settings

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "prohibited.md"
PROHIBITED_INSTRUCTIONS = PROMPT_PATH.read_text(encoding="utf-8")

MAX_OUTPUT_TOKENS = 6000
"""Bounds a runaway answer; the engine model also spends reasoning tokens (decision 005), and
the answer covers every Art. 5 practice."""

NO_MATCH_CITATION = "art:5:1"
"""What a step that found no practice raised cites: the list of prohibited practices."""


class ProhibitedOutputError(ValueError):
    """The model's answer doesn't fit `ProhibitedAnswer` (a broken output)."""


# --- Applying Art. 5 to the answer --------------------------------------------------------------


@dataclass(frozen=True)
class Settlement:
    """What Art. 5 gives on `as_of`: the step's status and whether it matched (prohibited, or
    assumed so), the practices that decide it, those raised but ruled out, and those that would
    apply but only from a later date."""

    status: Status
    matched: bool
    deciding: tuple[Practice, ...] = ()
    """The practices met (decided), open in law (ambiguous) or open on a fact (missing)."""
    considered: tuple[Practice, ...] = ()
    not_yet: tuple[Practice, ...] = ()
    missing: tuple[KeyQuestion, ...] = ()
    """Every open fact of a practice in force, in the order of the Act, each once."""


def settle(answer: ProhibitedAnswer, law_version: LawVersion, as_of: date) -> Settlement:
    """Apply Art. 5 to the model's answers on `as_of`. A practice met, with no question of law
    open on it, decides prohibited; otherwise one the law leaves open, then one open on a fact,
    keeps prohibited as the working assumption; otherwise no practice matches."""
    read = practices(answer, law_version)
    in_force = [p for p in read if as_of >= p.applies_from]
    not_yet = tuple(
        p
        for p in read
        if as_of < p.applies_from and (p.is_open or p.reading.answer is not Answer.NO)
    )
    met = tuple(p for p in in_force if p.reading.answer is Answer.YES and not p.is_open)
    opened = tuple(p for p in in_force if p.is_open)
    unknown = tuple(p for p in in_force if p.reading.answer is Answer.UNKNOWN and not p.is_open)
    asked = (p.reading.missing for p in unknown if p.reading.missing)
    questions = tuple({key.id: key for key in asked}.values())
    if met:
        return Settlement(Status.DECIDED, matched=True, deciding=met, not_yet=not_yet)
    if opened:
        return Settlement(
            Status.LEGALLY_AMBIGUOUS,
            matched=True,
            deciding=(*opened, *unknown),
            not_yet=not_yet,
            missing=questions,
        )
    if unknown:
        return Settlement(
            Status.NEEDS_MORE_INFORMATION,
            matched=True,
            deciding=unknown,
            not_yet=not_yet,
            missing=questions,
        )
    considered = tuple(p for p in in_force if p.is_raised)
    return Settlement(Status.DECIDED, matched=False, considered=considered, not_yet=not_yet)


# --- The step -----------------------------------------------------------------------------------


def _open_question(practice: Practice, language: Language) -> OpenQuestion:
    """The model's open question for the practice, or a fixed one when it gave none."""
    if practice.summary.open_question is not None:
        return practice.summary.open_question
    point = texts.point_name(practice.point, language)
    question, stricter, lenient = (t.format(point=point) for t in texts.OPEN_FALLBACK[language])
    return OpenQuestion(question=question, readings=(stricter, lenient))


def _not_yet_sentence(practice: Practice, language: Language, as_of: date) -> str:
    verb = "not_yet_verb_met" if practice.reading.answer is Answer.YES else "not_yet_verb_open"
    return texts.TEXTS[language]["not_yet"].format(
        point=texts.point_name(practice.point, language),
        start=long_date(practice.applies_from, language.value),
        as_of=long_date(as_of, language.value),
        verb=texts.TEXTS[language][verb],
        fact=practice.summary.fact,
    )


def _finding(settled: Settlement, language: Language, question: str) -> tuple[str, ...]:
    """The sentences of the finding itself, before the practices that apply only later."""
    words = texts.TEXTS[language]
    deciding = settled.deciding
    if settled.status is Status.DECIDED and settled.matched:
        points = ", ".join(texts.point_name(p.point, language) for p in deciding)
        return (words["prohibited"].format(points=points), *(p.summary.fact for p in deciding))
    if settled.matched:
        key = "ambiguous" if settled.status is Status.LEGALLY_AMBIGUOUS else "missing"
        first = texts.point_name(deciding[0].point, language)
        return (deciding[0].summary.fact, words[key].format(point=first, question=question))
    considered = (
        words["considered"].format(point=texts.point_name(p.point, language), fact=p.summary.fact)
        for p in settled.considered
    )
    notify = (words["notify"],) if any(p.is_permitted_use for p in settled.considered) else ()
    return (words["none"], *considered, *notify)


def _decision(settled: Settlement, language: Language, as_of: date, question: str) -> str:
    later = (_not_yet_sentence(p, language, as_of) for p in settled.not_yet)
    return " ".join((*_finding(settled, language, question), *later))


def _cited_ids(settled: Settlement) -> tuple[tuple[str, bool], ...]:
    """Each provision the step cites, once, with whether it may be missing from the text read:
    a point that applies only later may postdate it (before 27 July 2026 the text has no (ba))."""
    now = (pid for p in (*settled.deciding, *settled.considered) for pid in p.cited)
    cited: dict[str, bool] = dict.fromkeys(now, False)
    for practice in settled.not_yet:
        for pid in practice.cited:
            cited.setdefault(pid, pid != APPLICATION_DATES)
    return tuple(cited.items()) or ((NO_MATCH_CITATION, False),)


def _provisions(
    settled: Settlement, state: EngineState, library: ProhibitedLibrary
) -> tuple[Provision, ...]:
    """The cited provisions, fetched; a later point the text read lacks is left out."""
    lookup = lookup_for(state)
    found: list[Provision] = []
    for pid, may_be_missing in _cited_ids(settled):
        try:
            found.append(library.provision(pid, lookup))
        except ProvisionNotFoundError:
            if not may_be_missing:
                raise
    return tuple(found)


def _facts_used(settled: Settlement, facts: Sequence[Fact]) -> tuple[Fact, ...]:
    """The facts the answer parts of the practices shown rest on, each part once."""
    shown = (*settled.deciding, *settled.considered, *settled.not_yet)
    parts = tuple({id(p.summary): p.summary for p in shown}.values())
    return facts_used(parts, facts)


def to_outcome(
    answer: ProhibitedAnswer, state: EngineState, retrieved: Retrieved, library: ProhibitedLibrary
) -> CheckOutcome:
    """The prohibited step and whether it matched, from the model's answer and the passages
    retrieved. The cited provisions are fetched from `library`."""
    language, as_of = state["language"], state["as_of"]
    settled = settle(answer, state["law_version"], as_of)
    is_ambiguous = settled.status is Status.LEGALLY_AMBIGUOUS
    open_question = _open_question(settled.deciding[0], language) if is_ambiguous else None
    questions = tuple(key_question(key, language) for key in settled.missing)
    is_missing = settled.status is Status.NEEDS_MORE_INFORMATION
    missing_fact = questions[0] if is_missing else None
    asked = open_question.question if open_question else missing_fact.text if missing_fact else ""
    step = StepResult(
        step=StepName.PROHIBITED,
        decision=_decision(settled, language, as_of, asked),
        facts_used=_facts_used(settled, state.get("facts", ())),
        citations=(
            *(provision_citation(p) for p in _provisions(settled, state, library)),
            *(
                guidance_citation(hit, language)
                for hit in named_passages(answer.guidance_numbers, retrieved.guidance)
            ),
        ),
        status=settled.status,
        missing_fact=missing_fact,
        open_question=open_question,
    )
    return CheckOutcome(step=step, matched=settled.matched, follow_up_questions=questions)


# --- The model call -----------------------------------------------------------------------------


PROHIBITED_RESPONSE_FORMAT = json_schema_format("prohibited_answer", ProhibitedAnswer)


def _guidance_section(guidance: Sequence[SearchHit]) -> str:
    listed = (f"{n}. [{hit.provision_id}] {clipped(hit.text)}" for n, hit in enumerate(guidance, 1))
    return "\n\n".join(listed) or "-"


def prohibited_messages(state: EngineState, retrieved: Retrieved) -> list[BaseMessage]:
    """The fixed instructions and Art. 5 first; the passages, the per-case context and the
    description last, so the shared prefix is cached (005)."""
    version = state["law_version"].value
    return [
        SystemMessage(PROHIBITED_INSTRUCTIONS),
        HumanMessage(
            f"The AI Act, Article 5 ({version} text):\n\n{retrieved.article.text}\n\n"
            f"Guidelines on prohibited practices, passages:\n\n"
            f"{_guidance_section(retrieved.guidance)}\n\n"
            f"Language for facts and questions: {state['language'].value}\n\n"
            f"Answers to earlier questions:\n{answers_section(state)}\n\n"
            f"Facts:\n{facts_section(state)}\n\n"
            f"Description:\n{state['description']}"
        ),
    ]


class ProhibitedCheck:
    """The prohibited node for the graph: `checks={StepName.PROHIBITED: ProhibitedCheck(), …}`."""

    def __init__(
        self,
        settings: Settings | None = None,
        chat: BaseChatModel | None = None,
        library: ProhibitedLibrary | None = None,
    ) -> None:
        """`chat` replaces the OpenRouter model and `library` the corpus (tests). Raises
        `LLMConfigError` when `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set: the
        model is always pinned to its EU endpoint with fallbacks off (decision 005). Without a
        `library`, the query embedder is built here from the same settings, so
        `EMBEDDING_MODEL` and `EMBEDDING_PROVIDER` must be set too; each step then reads the
        corpus over a short connection before the model call, and another for the citations
        after it."""
        self._model = chat or engine_chat_model(max_tokens=MAX_OUTPUT_TOKENS, settings=settings)
        self._library = library
        self._embedder = None if library else OpenRouterEmbeddings(settings=settings)

    def _reading[T](self, use: Callable[[ProhibitedLibrary], T]) -> T:
        """`use` applied to the corpus: the given library, or one over a fresh connection that
        is closed before this returns (none stays open during the model call)."""
        if self._library is not None:
            return use(self._library)
        assert self._embedder is not None  # built whenever no library is given
        with connect() as connection:
            return use(ProhibitedCorpus(connection, self._embedder))

    def __call__(self, state: EngineState) -> CheckOutcome:
        """Raises `ProhibitedOutputError` when the reply doesn't fit `ProhibitedAnswer`, and
        `ProvisionNotFoundError` when the corpus lacks a provision the step reads or cites."""
        retrieved = self._reading(lambda library: retrieve(state, library))
        reply = self._model.invoke(
            prohibited_messages(state, retrieved), response_format=PROHIBITED_RESPONSE_FORMAT
        )
        try:
            answer = ProhibitedAnswer.model_validate_json(reply.text)
        except ValidationError as exc:
            message = f"prohibited answer doesn't fit the schema: {describe_validation_error(exc)}"
            raise ProhibitedOutputError(message) from exc
        return self._reading(lambda library: to_outcome(answer, state, retrieved, library))
