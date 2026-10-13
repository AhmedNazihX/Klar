"""How the scope step varies from run to run on INIT's worked example (E14).

The engine runs at temperature 0, but the pinned model reasons before it answers, so two runs on
the same request can differ. On the worked example the scope step once paused to ask whether the
tool infers (Art. 3(1)) and once decided it was in scope (user's live check, 2026-10-07). INIT >
Worked example accepts both: the description doesn't say how the tool works, so the engine may
ask, or assume it is an AI system. No run may pause on any other question.

The replay asks the scope step `RUNS` times with the request a whole run sends it: the
description with the four facts the facts node extracted from it (not the replay state's empty
facts), and replays the replies in the order they were recorded; the corpus answers come from the
`.corpus.json` next to the cassette. A free check holds that request to the whole run's recorded
one. Record it with `RECORD_COMMAND` (paid, the orchestrator's step, after the user's go-ahead).
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import pytest
import yaml
from langchain_core.messages import BaseMessage

from aiact.db import connect
from aiact.engine.nodes.facts import find_span
from aiact.engine.nodes.key_facts import Answer, KeyFact
from aiact.engine.nodes.scope import (
    SCOPE_INSTRUCTIONS,
    CorpusLibrary,
    Definition,
    DefinitionFact,
    ScopeCheck,
    scope_messages,
    to_outcome,
)
from aiact.engine.nodes.scope_texts import AI_SYSTEM
from aiact.engine.state import CheckOutcome, EngineState
from aiact.eval.experiments.matchers import WORKED_EXAMPLE, replay_state
from aiact.llm import OpenRouterEmbeddings
from aiact.schemas import EvidenceTag, Fact, Status
from aiact.settings import Settings
from tests.conftest import RECORDINGS_DIR
from tests.engine.built_corpus import unresolved_citations, whole_articles
from tests.engine.nodes.corpus_recording import corpus_recording, require_recording
from tests.engine.nodes.known_gaps import STALE_RECORDING_ERRORS
from tests.engine.nodes.test_scope import (
    LUNA,
    LUNA_PROVIDER,
    FakeLibrary,
    RecordedScopeLibrary,
    definition,
    key_fact,
    scope_answer,
    state,
)

RUNS = 5
"""How many times the replay asks the scope step (BACKLOG > E14: about five)."""
AS_OF = date(2026, 10, 13)
RECORD_COMMAND = "uv run pytest tests/engine/nodes/test_scope_variance.py --record-mode=once"
WHOLE_RUN_CASSETTE = (
    RECORDINGS_DIR / "engine" / "test_classify_worked_example" / "test_replay_worked_example.yaml"
)
"""The whole-run recording whose scope request the five runs repeat."""
CASE_CONTEXT = "Language for facts:"
"""Where the scope request's per-case context starts, after the law and the guideline passages."""


def _fact(text: str, evidence: EvidenceTag, quote: str | None = None) -> Fact:
    span = find_span(WORKED_EXAMPLE.description, quote) if quote else None
    return Fact(text=text, evidence=evidence, source_span=span)


WORKED_EXAMPLE_FACTS = (
    _fact(
        "The tool scores job applications and presents HR with a ranked shortlist of applicants.",
        EvidenceTag.STATED,
        "reads incoming job applications, scores them, and shows HR a ranked shortlist.",
    ),
    _fact(
        "The company bought the tool from a vendor and says it did not change it.",
        EvidenceTag.STATED,
        "We bought it from a vendor and didn't change it.",
    ),
    _fact(
        "The scores appear to evaluate individual applicants using information in their "
        "applications.",
        EvidenceTag.INFERRED,
    ),
    _fact(
        "The tool is assumed to be used in or placed on the market in the EU.",
        EvidenceTag.ASSUMED,
    ),
)
"""The facts the facts node extracted from the worked example in the whole-run recording
(`WHOLE_RUN_CASSETTE`'s first reply: each fact's text, evidence tag and quote), as E20's
re-record of the whole run gave them."""

WHOLE_RUN_FACTS_PENDING = pytest.mark.xfail(
    strict=True,
    raises=STALE_RECORDING_ERRORS,
    reason="recording pending (orchestrator): E20 re-recorded the whole run, whose facts the "
    "five runs repeat (WORKED_EXAMPLE_FACTS), so their recorded request is stale; delete and "
    "re-record",
)
"""The five scope runs, until the orchestrator records them on the new whole run's facts."""

DECIDED = "in scope, decided"
ASKS_AI_SYSTEM = "in scope as the working assumption, asks whether the tool infers"
"""INIT's two accepted readings of the worked example's scope step."""


def accepted_reading(outcome: CheckOutcome) -> str | None:
    """Which of INIT's two readings the outcome is, or None for any other: out of scope, a
    contested definition, or a pause on any question but Art. 3(1)'s."""
    if outcome.matched:
        return None
    asked = [question.id for question in outcome.follow_up_questions]
    if outcome.step.status is Status.DECIDED and not asked:
        return DECIDED
    if outcome.step.status is Status.NEEDS_MORE_INFORMATION and asked == [AI_SYSTEM.id]:
        return ASKS_AI_SYSTEM
    return None


def _outcome(ai_system: DefinitionFact | None = None, **key_facts: KeyFact) -> CheckOutcome:
    return to_outcome(scope_answer(ai_system, **key_facts), state(), (), FakeLibrary())


UNKNOWN_LINK = key_fact(Answer.UNKNOWN)


def test_both_of_inits_readings_are_accepted() -> None:
    assert accepted_reading(_outcome()) == DECIDED
    assert accepted_reading(_outcome(definition(Definition.UNKNOWN))) == ASKS_AI_SYSTEM


@pytest.mark.parametrize(
    ("ai_system", "key_facts"),
    [
        pytest.param(definition(Definition.NO), {}, id="not-an-ai-system"),
        pytest.param(definition(Definition.CONTESTED), {}, id="contested"),
        pytest.param(None, {"eu_link": UNKNOWN_LINK}, id="asks-the-eu-link"),
        pytest.param(
            definition(Definition.UNKNOWN), {"eu_link": UNKNOWN_LINK}, id="asks-the-eu-link-too"
        ),
    ],
)
def test_any_other_reading_is_not(
    ai_system: DefinitionFact | None, key_facts: dict[str, KeyFact]
) -> None:
    assert accepted_reading(_outcome(ai_system, **key_facts)) is None


def worked_example_state() -> EngineState:
    """The state the scope step gets in a whole run: the replay state plus the facts."""
    return {**replay_state(WORKED_EXAMPLE, AS_OF), "facts": WORKED_EXAMPLE_FACTS}


def _case_context(message: BaseMessage | dict[str, object]) -> str:
    """A scope request's text from its per-case context on: the language, the facts and the
    description. The law and the guideline passages before it come from the corpus."""
    content = message.content if isinstance(message, BaseMessage) else message["content"]
    assert isinstance(content, str)
    return content[content.index(CASE_CONTEXT) :]


def _whole_run_scope_request() -> dict[str, object]:
    """The human message of the whole run's scope request: the one sent with the scope prompt."""
    cassette = yaml.safe_load(WHOLE_RUN_CASSETTE.read_text(encoding="utf-8"))
    for interaction in cassette["interactions"]:
        messages = json.loads(interaction["request"]["body"]).get("messages", [])
        if messages and messages[0]["content"] == SCOPE_INSTRUCTIONS:
            return messages[-1]
    raise AssertionError(
        f"{WHOLE_RUN_CASSETTE.name} has no request with the current scope prompt: the prompt "
        "changed or the whole run was re-recorded; recheck WORKED_EXAMPLE_FACTS against it"
    )


def test_the_runs_repeat_the_whole_runs_scope_request() -> None:
    """The five runs measure the input that wavered: the request with the facts node's facts."""
    sent = scope_messages(worked_example_state(), (), ())
    assert _case_context(sent[-1]) == _case_context(_whole_run_scope_request())
    assert "Facts:\n1. [stated] The tool scores job applications" in _case_context(sent[-1])


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@contextmanager
def _live_corpus(settings: Settings) -> Iterator[CorpusLibrary]:
    with connect() as connection:
        yield CorpusLibrary(connection, OpenRouterEmbeddings(settings=settings))


@WHOLE_RUN_FACTS_PENDING
@pytest.mark.vcr
def test_worked_example_scope_varies_only_between_inits_readings(
    luna_settings: Settings,
    record_mode: str,
    vcr_cassette_dir: str,
    default_cassette_name: str,
) -> None:
    """Every run reads the worked example one of INIT's two ways: no run pauses on any other
    question, and none ends out of scope or contested. How many runs ask is E14's diagnosis,
    read from the recorded replies' `ai_system` answers."""
    require_recording(vcr_cassette_dir, default_cassette_name, record_mode)
    run_state = worked_example_state()
    with corpus_recording(
        vcr_cassette_dir,
        default_cassette_name,
        record_mode,
        RECORD_COMMAND,
        lambda: _live_corpus(luna_settings),
    ) as recording:
        check = ScopeCheck(luna_settings, library=RecordedScopeLibrary(recording))
        outcomes = [check(run_state) for _ in range(RUNS)]
    for outcome in outcomes:
        assert not unresolved_citations(outcome.step, run_state)
        assert not whole_articles(outcome.step)
    readings = [accepted_reading(outcome) for outcome in outcomes]
    assert None not in readings, [(o.step.status, o.follow_up_questions) for o in outcomes]
