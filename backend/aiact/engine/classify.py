"""`classify_system`: one description through the staged engine (E10; INIT > How it works).

- **Answers** to follow-up questions are appended to the description, one line each under a
  heading, before the facts node reads it (decision 019), so a fact an answer gives is `stated`
  with a span in the extended text (`extended_description`). There is no second path for
  answers. A request's text is bounded (`ClassifyRequest`) before any paid call.
- **The nodes** are the engine's own, on the engine model pinned to its EU endpoint (decision
  005); every check is wrapped by the citation validator (E9), and finalize builds the result
  (E8). A node that raises stops the run: no class is returned after a failed check
  (`ClassificationFailedError`, or the `error` event when streamed).
- **Held-out examples** stay hidden unless `include_held_out` is set, which only V8's gap run
  does (decision 012); it reaches every lookup, search and citation check through the run's
  `Lookup`. It and `exclude_source_example_ids` are keyword arguments of the run functions,
  never fields of `ClassifyRequest`, the body the API (P1) and the MCP tool (P2b) accept.
- **Cost** is counted per node (`UsageMeter`), the validator's re-runs included, and logged
  once per run with the trace id. **Tracing** goes to LangSmith when a key is set, metadata only
  outside development, and is switched off otherwise (`aiact.engine.tracing`).
"""

import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Annotated, ClassVar, Self, cast
from uuid import UUID, uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from pydantic import Field, StringConstraints, model_validator

from aiact.engine.citations import CitationValidator
from aiact.engine.events import (
    ClassifyEvent,
    FactsEvent,
    ResultEvent,
    StepEvent,
    StepStartedEvent,
    error_event,
    matches,
)
from aiact.engine.graph import FACTS, FINALIZE, CheckNode, EngineNodes, build_graph
from aiact.engine.nodes.facts import MAX_OUTPUT_TOKENS as FACTS_TOKENS
from aiact.engine.nodes.facts import FactExtractor
from aiact.engine.nodes.finalize import finalize
from aiact.engine.nodes.guideline_retrieval import GuidelineLibrary
from aiact.engine.nodes.high_risk import MAX_OUTPUT_TOKENS as HIGH_RISK_TOKENS
from aiact.engine.nodes.high_risk import HighRiskCheck
from aiact.engine.nodes.high_risk_retrieval import HighRiskLibrary
from aiact.engine.nodes.prohibited import MAX_OUTPUT_TOKENS as PROHIBITED_TOKENS
from aiact.engine.nodes.prohibited import ProhibitedCheck
from aiact.engine.nodes.role_obligations import MAX_OUTPUT_TOKENS as ROLE_TOKENS
from aiact.engine.nodes.role_obligations import RoleObligationsCheck
from aiact.engine.nodes.scope import MAX_OUTPUT_TOKENS as SCOPE_TOKENS
from aiact.engine.nodes.scope import ScopeCheck, ScopeLibrary
from aiact.engine.nodes.transparency import MAX_OUTPUT_TOKENS as TRANSPARENCY_TOKENS
from aiact.engine.nodes.transparency import TransparencyCheck
from aiact.engine.state import EngineInput
from aiact.engine.tracing import langsmith_tracer, tracing_switch
from aiact.engine.usage import MeteredEmbedder, RunUsage, UsageMeter
from aiact.llm import OpenRouterEmbeddings, engine_chat_model
from aiact.schemas import (
    ClassificationResult,
    Fact,
    FollowUpQuestion,
    Language,
    LawVersion,
    StepName,
    StepResult,
)
from aiact.schemas.base import ContractModel
from aiact.schemas.questions import SLUG_PATTERN
from aiact.settings import Settings, get_settings

logger = logging.getLogger(__name__)

RUN_NAME = "classify_system"
"""The name of the run's root trace."""

ANSWERS_HEADING: Mapping[Language, str] = {
    Language.EN: "Answers to follow-up questions:",
    Language.DE: "Antworten auf Rückfragen:",
}
"""The line above the appended answers (decision 019)."""

AnswerId = Annotated[str, StringConstraints(pattern=SLUG_PATTERN)]
"""A follow-up question's id, which keys its answer."""


class ClassifyRequest(ContractModel):
    """One classification, as a caller asks for it (the body the API and the MCP tool reuse).
    `as_of` defaults to the run's date. The text is bounded before any paid call: the
    description as the database stores it (`systems.description`), and the answers in number
    and length. What retrieval leaves out is not part of it (see `run_classification`)."""

    MAX_DESCRIPTION_CHARS: ClassVar[int] = 20_000
    """The `systems.description` check (migration 20260928210100_user_data.sql)."""
    MAX_ANSWERS: ClassVar[int] = 40
    """Well above the follow-up questions one run asks."""
    MAX_ANSWER_CHARS: ClassVar[int] = 1_000

    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    language: Language
    law_version: LawVersion = LawVersion.AMENDED
    as_of: date = Field(default_factory=date.today)
    answers: Mapping[AnswerId, Annotated[str, StringConstraints(max_length=MAX_ANSWER_CHARS)]] = (
        Field(default_factory=dict, max_length=MAX_ANSWERS)
    )

    @model_validator(mode="after")
    def _has_text(self) -> Self:
        if not self.description.strip():
            raise ValueError("the description is blank")
        if any(not text.strip() for text in self.answers.values()):
            raise ValueError("an answer is blank; leave the question out instead")
        return self


class ClassificationFailedError(RuntimeError):
    """A node raised, so the run gives no class. Carries the failed node, what the run had spent
    by then and its trace id; the node's own error is the `__cause__`."""

    def __init__(self, step: str, usage: RunUsage, trace_id: str | None) -> None:
        super().__init__(f"the {step} node failed, so the run gives no class")
        self.step = step
        self.usage = usage
        self.trace_id = trace_id


@dataclass(frozen=True)
class ClassificationRun:
    """A finished run: the result, what it cost, and its LangSmith trace (None when untraced)."""

    result: ClassificationResult
    usage: RunUsage
    trace_id: str | None


NodeBuilder = Callable[[Settings, UsageMeter], EngineNodes]
"""Builds a run's nodes, with every paid call counted by the meter."""


# --- The input ----------------------------------------------------------------------------------


def extended_description(description: str, answers: Mapping[str, str], language: Language) -> str:
    """The description with the answers appended, one `- <question id>: <answer>` line each (an
    answer's line breaks become spaces), under `ANSWERS_HEADING`; the description alone when
    there are no answers. Fact spans point into this text."""
    if not answers:
        return description
    lines = (f"- {qid}: {' '.join(text.split())}" for qid, text in answers.items())
    return "\n".join((f"{description}\n", ANSWERS_HEADING[language], *lines))


@dataclass(frozen=True)
class Retrieval:
    """What a run's retrieval leaves out: the examples the caller excludes, and whether the
    held-out ones are included (V8's gap run only, decision 012)."""

    exclude_source_example_ids: tuple[str, ...] = ()
    include_held_out: bool = field(default=False, kw_only=True)

    @classmethod
    def given(cls, exclude_source_example_ids: Sequence[str], *, include_held_out: bool) -> Self:
        """The run functions' keyword arguments as a `Retrieval`. Raises TypeError for a bare
        string of ids, which would otherwise be split into single characters and exclude
        nothing."""
        if isinstance(exclude_source_example_ids, str):
            raise TypeError("exclude_source_example_ids takes a sequence of ids, not one string")
        return cls(tuple(exclude_source_example_ids), include_held_out=include_held_out)


def engine_input(request: ClassifyRequest, retrieval: Retrieval) -> EngineInput:
    """The graph's input: the extended description (decision 019) and the run's retrieval."""
    return {
        "description": extended_description(request.description, request.answers, request.language),
        "language": request.language,
        "law_version": request.law_version,
        "as_of": request.as_of,
        "exclude_source_example_ids": retrieval.exclude_source_example_ids,
        "include_held_out": retrieval.include_held_out,
    }


# --- The nodes ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusLibraries:
    """What each check reads instead of the database (the end-to-end replay)."""

    scope: ScopeLibrary
    prohibited: GuidelineLibrary
    high_risk: HighRiskLibrary
    transparency: GuidelineLibrary


def engine_nodes(
    settings: Settings,
    meter: UsageMeter,
    *,
    libraries: CorpusLibraries | None = None,
    validator: CitationValidator | None = None,
) -> EngineNodes:
    """The engine's own nodes, each check wrapped by the citation validator, every model call
    and query embedding counted by `meter`. Without `libraries`, the checks read the corpus from
    DATABASE_URL and embed their queries with the settings' embedding model; without
    `validator`, citations are checked against the database too. Raises `LLMConfigError` when a
    model setting or the API key is missing."""

    def chat(node: str, max_tokens: int) -> BaseChatModel:
        model = engine_chat_model(max_tokens=max_tokens, settings=settings)
        return model.model_copy(update={"callbacks": [meter.chat_callback(node)]})

    embeddings = OpenRouterEmbeddings(settings=settings) if libraries is None else None

    def embedder(name: StepName) -> MeteredEmbedder | None:
        return meter.embedder(name, embeddings) if embeddings is not None else None

    scope, prohibited = StepName.SCOPE, StepName.PROHIBITED
    high_risk, transparency = StepName.HIGH_RISK, StepName.TRANSPARENCY
    role = StepName.ROLE_OBLIGATIONS
    checks: dict[StepName, CheckNode] = {
        scope: ScopeCheck(
            settings,
            chat=chat(scope, SCOPE_TOKENS),
            library=libraries.scope if libraries else None,
            embedder=embedder(scope),
        ),
        prohibited: ProhibitedCheck(
            settings,
            chat=chat(prohibited, PROHIBITED_TOKENS),
            library=libraries.prohibited if libraries else None,
            embedder=embedder(prohibited),
        ),
        high_risk: HighRiskCheck(
            settings,
            chat=chat(high_risk, HIGH_RISK_TOKENS),
            library=libraries.high_risk if libraries else None,
            embedder=embedder(high_risk),
        ),
        transparency: TransparencyCheck(
            settings,
            chat=chat(transparency, TRANSPARENCY_TOKENS),
            library=libraries.transparency if libraries else None,
            embedder=embedder(transparency),
        ),
        role: RoleObligationsCheck(settings, chat=chat(role, ROLE_TOKENS)),
    }
    return EngineNodes(
        facts=FactExtractor(settings, chat=chat(FACTS, FACTS_TOKENS)),
        checks=(validator or CitationValidator(settings=settings)).checks(checks),
        finalize=finalize,
    )


# --- One run ------------------------------------------------------------------------------------

STEP_NAMES = frozenset(name.value for name in StepName)
"""The graph's check nodes, which get a `step_started` event (facts and finalize don't)."""


class _Run:
    """One classification: its graph, meter, trace id and events. Building it builds the nodes,
    so a setup error (a missing model setting, unreadable amendment records) raises here."""

    def __init__(
        self,
        request: ClassifyRequest,
        retrieval: Retrieval,
        settings: Settings,
        build_nodes: NodeBuilder,
    ) -> None:
        self.request = request
        self._retrieval = retrieval
        self.meter = UsageMeter()
        self._tracer = langsmith_tracer(settings)
        self._run_id: UUID = uuid4()
        self._graph = build_graph(build_nodes(settings, self.meter))

    @property
    def trace_id(self) -> str | None:
        return str(self._run_id) if self._tracer is not None else None

    def _config(self) -> RunnableConfig:
        """The run's id, name and tracer, with metadata only: never the description."""
        request, retrieval = self.request, self._retrieval
        return {
            "run_id": self._run_id,
            "run_name": RUN_NAME,
            "callbacks": [self._tracer] if self._tracer is not None else [],
            "tags": [RUN_NAME],
            "metadata": {
                "law_version": request.law_version.value,
                "language": request.language.value,
                "as_of": request.as_of.isoformat(),
                "answers": len(request.answers),
                "excluded_examples": len(retrieval.exclude_source_example_ids),
                "include_held_out": retrieval.include_held_out,
            },
        }

    def events(self) -> Iterator[ClassifyEvent]:
        """The run's events up to `result`. Raises `ClassificationFailedError` (from the node's
        error) when a node fails. Logs the run's cost either way."""
        running = FACTS
        chunks = self._graph.stream(
            engine_input(self.request, self._retrieval),
            self._config(),
            stream_mode=["tasks", "updates"],
        )
        try:
            for mode, chunk in self._pulled(chunks):
                if mode == "tasks":
                    started = _started(chunk)
                    if started is not None:
                        running = started
                        if started in STEP_NAMES:
                            yield StepStartedEvent(step=StepName(started))
                    continue
                yield from _update_events(chunk)
        except Exception as exc:
            logger.warning("classification stopped in %s: %s", running, type(exc).__name__)
            raise ClassificationFailedError(running, self.meter.usage(), self.trace_id) from exc
        finally:
            _log_usage(self.meter.usage(), self.trace_id)

    def _pulled(self, chunks: Iterator[object]) -> Iterator[tuple[object, object]]:
        """`chunks`, each pulled inside the run's tracing switch. Every pull runs graph steps,
        and a server may run each in a fresh copy of its own context (Starlette's
        StreamingResponse over a sync iterator does), so the switch is set for each pull and
        never left on the caller's context between events."""
        while True:
            with tracing_switch(self._tracer):
                item = next(chunks, _DONE)
            if item is _DONE:
                return
            yield cast(tuple[object, object], item)  # (mode, chunk): two stream modes


_DONE = object()
"""The end of a run's graph stream."""


def _started(chunk: object) -> str | None:
    """The node a `tasks` chunk starts, or None for a chunk that reports a finished task."""
    if not isinstance(chunk, Mapping) or "result" in chunk:
        return None
    name = chunk.get("name")
    return name if isinstance(name, str) else None


def _update_events(chunk: object) -> Iterator[ClassifyEvent]:
    """The events for one node's state update."""
    if not isinstance(chunk, Mapping):
        return
    for node, update in chunk.items():
        if not isinstance(update, Mapping):
            continue
        if node == FACTS:
            yield FactsEvent(
                facts=_typed(update.get("facts", ()), Fact),
                follow_up_questions=_typed(update.get("follow_up_questions", ()), FollowUpQuestion),
            )
        elif node == FINALIZE:
            result = update.get("result")
            if isinstance(result, ClassificationResult):
                yield ResultEvent(result=result)
        else:
            for step in _typed(update.get("steps", ()), StepResult):
                yield StepEvent(step=step, matches=matches(step))


def _typed[T](items: object, kind: type[T]) -> tuple[T, ...]:
    """`items` as a tuple of `kind`; the graph's updates are typed as plain objects."""
    if not isinstance(items, Sequence):
        return ()
    return tuple(item for item in items if isinstance(item, kind))


def _log_usage(usage: RunUsage, trace_id: str | None) -> None:
    """The run's cost, tokens and per-node split: metadata only."""
    per_node = {name: round(node.cost_usd, 6) for name, node in usage.by_node.items()}
    logger.info(
        "classification cost $%.6f%s, %d tokens; per node %s; trace %s",
        usage.cost_usd,
        "" if usage.is_cost_complete else " (a reply had no cost)",
        usage.tokens,
        per_node,
        trace_id or "-",
    )


# --- The public functions -----------------------------------------------------------------------


def run_classification(
    request: ClassifyRequest,
    *,
    settings: Settings | None = None,
    build_nodes: NodeBuilder = engine_nodes,
    exclude_source_example_ids: Sequence[str] = (),
    include_held_out: bool = False,
) -> ClassificationRun:
    """Classify `request`, with what it cost and its trace id. `exclude_source_example_ids`
    keeps those guideline examples out of retrieval; `include_held_out` is V8's gap run only
    (decision 012). Raises `ClassificationFailedError` when a node fails, `LLMConfigError`
    when a model setting is missing, and TypeError when `exclude_source_example_ids` is a single
    string."""
    retrieval = Retrieval.given(exclude_source_example_ids, include_held_out=include_held_out)
    run = _Run(request, retrieval, settings or get_settings(), build_nodes)
    results = [event.result for event in run.events() if isinstance(event, ResultEvent)]
    if len(results) != 1:
        raise RuntimeError(f"the graph returned {len(results)} results instead of one")
    return ClassificationRun(result=results[0], usage=run.meter.usage(), trace_id=run.trace_id)


def stream_classification(
    request: ClassifyRequest,
    *,
    settings: Settings | None = None,
    build_nodes: NodeBuilder = engine_nodes,
    exclude_source_example_ids: Sequence[str] = (),
    include_held_out: bool = False,
) -> Iterator[ClassifyEvent]:
    """Classify `request` as a stream of events (`aiact.engine.events`): the facts, each check as
    it starts and ends, then the result, or an `error` event naming the failed node, after which
    nothing more comes. The run is set up here, at the call: a setup error (`LLMConfigError` for
    a missing model setting, OSError when the amendment records can't be read) raises before
    any event, and only a failed node becomes the `error` event. The keyword arguments are as in
    `run_classification`."""
    retrieval = Retrieval.given(exclude_source_example_ids, include_held_out=include_held_out)
    run = _Run(request, retrieval, settings or get_settings(), build_nodes)
    return _events_or_error(run, request.language)


def _events_or_error(run: _Run, language: Language) -> Iterator[ClassifyEvent]:
    try:
        yield from run.events()
    except ClassificationFailedError as exc:
        yield error_event(exc.step, language)


def classify_system(
    description: str,
    language: Language | str,
    law_version: LawVersion | str = LawVersion.AMENDED,
    as_of: date | None = None,
    answers: Mapping[str, str] | None = None,
    exclude_source_example_ids: Sequence[str] = (),
    *,
    include_held_out: bool = False,
) -> ClassificationResult:
    """Classify one AI system under the AI Act: the staged checks with their citations, the risk
    class (the stricter reading when uncertain), the role and its duties, the law version and
    date used, and the "guidance, not legal advice" notice.

    `as_of` is the date the law is read on (default: today). `answers` maps follow-up question
    ids to the user's answers, which are appended to the description (decision 019).
    `exclude_source_example_ids` keeps those guideline examples out of retrieval.
    `include_held_out` is for V8's gap run only (decision 012).

    Raises pydantic's ValidationError, before any paid call, for a blank or oversized
    description or answer, too many answers, an unknown language or law version, or an answer
    id that isn't in question-id form (snake_case; whether a question with that id was asked is
    not checked); `ClassificationFailedError` when a check fails (no class is given then);
    `LLMConfigError` when a model setting is missing.
    """
    request = ClassifyRequest.model_validate(
        {
            "description": description,
            "language": language,
            "law_version": law_version,
            "answers": dict(answers or {}),
            **({"as_of": as_of} if as_of is not None else {}),
        }
    )
    return run_classification(
        request,
        exclude_source_example_ids=exclude_source_example_ids,
        include_held_out=include_held_out,
    ).result
