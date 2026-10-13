"""How the scope step varies from run to run on INIT's worked example (E14).

The engine runs at temperature 0, but the pinned model reasons before it answers, so two runs on
the same request can differ. On the worked example the scope step once paused to ask whether the
tool infers (Art. 3(1)) and once decided it was in scope (user's live check, 2026-10-07). INIT >
Worked example accepts both: the description doesn't say how the tool works, so the engine may
ask, or assume it is an AI system. No run may pause on any other question.

The replay asks the scope step `RUNS` times with the same request and replays the replies in the
order they were recorded; the corpus answers come from the `.corpus.json` next to the cassette.
Record it with `RECORD_COMMAND` (paid, the orchestrator's step, after the user's go-ahead).
"""

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import pytest

from aiact.db import connect
from aiact.engine.nodes.key_facts import Answer, KeyFact
from aiact.engine.nodes.scope import (
    CorpusLibrary,
    Definition,
    DefinitionFact,
    ScopeCheck,
    to_outcome,
)
from aiact.engine.nodes.scope_texts import AI_SYSTEM
from aiact.engine.state import CheckOutcome
from aiact.eval.experiments.matchers import WORKED_EXAMPLE, replay_state
from aiact.llm import OpenRouterEmbeddings
from aiact.schemas import Status
from aiact.settings import Settings
from tests.engine.built_corpus import unresolved_citations, whole_articles
from tests.engine.nodes.corpus_recording import (
    RecordingPendingError,
    corpus_recording,
    require_recording,
)
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


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@contextmanager
def _live_corpus(settings: Settings) -> Iterator[CorpusLibrary]:
    with connect() as connection:
        yield CorpusLibrary(connection, OpenRouterEmbeddings(settings=settings))


@pytest.mark.vcr
@pytest.mark.xfail(
    strict=True,
    raises=RecordingPendingError,
    reason="recording pending (orchestrator, after the user's go-ahead on the cost): E14's "
    f"{RUNS} runs of the scope step on the worked example",
)
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
    run_state = replay_state(WORKED_EXAMPLE, AS_OF)
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
    readings = Counter(accepted_reading(outcome) for outcome in outcomes)
    assert None not in readings, [(o.step.status, o.follow_up_questions) for o in outcomes]
