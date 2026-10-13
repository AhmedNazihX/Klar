"""The end-to-end runs beyond INIT's worked example in English (P13), recorded here and replayed by
the e2e API (`replay_server.py`): the worked example answered on its result screen (its Art. 3(1)
answer and the company profile's EU answer), and the worked example in German. Each request is
the exact body the app sends, from `frontend/e2e/runs.json`, so the browser's run finds it.

Recording calls the engine model, the query embeddings and the local test database's corpus:
`RECORD_COMMAND` (in `runs.py`), the orchestrator's paid step, after the reviews. Until then each
run is a strict "recording pending" xfail; drop the mark once it is recorded.
"""

from collections.abc import Iterator
from functools import partial

import pytest

from aiact.engine import run_classification
from aiact.engine.classify import NodeBuilder, engine_nodes
from aiact.schemas import Language, RiskClass
from aiact.settings import Settings
from tests.e2e.runs import E2E_RECORDINGS, RECORD_COMMAND, e2e_runs
from tests.engine.built_corpus import built_validator
from tests.engine.nodes.corpus_recording import (
    RecordingPendingError,
    corpus_recording,
    require_recording,
)
from tests.engine.nodes.known_gaps import stale_recording_pending
from tests.engine.test_classify_worked_example import (
    LUNA,
    LUNA_PROVIDER,
    _live_corpus,  # pyright: ignore[reportPrivateUsage]
    recorded_libraries,
)

RUNS = e2e_runs()
ANNEX_III_4_A = "annex:III:4:a"
PENDING = pytest.mark.xfail(
    strict=True,
    raises=RecordingPendingError,
    reason=f"recording pending: record it with `{RECORD_COMMAND}`",
)


@pytest.fixture(scope="module")
def vcr_cassette_dir() -> str:
    return str(E2E_RECORDINGS)


@pytest.fixture
def default_cassette_name(name: str) -> str:
    """One recording per run, named as `runs.json` names it (the e2e API finds it by name)."""
    return name


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    """As the worked example was recorded: Luna, and no LangSmith key (no trace is sent)."""
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER, "langsmith_api_key": None}
    )


@pytest.fixture
def run_nodes(
    luna_settings: Settings, record_mode: str, vcr_cassette_dir: str, default_cassette_name: str
) -> Iterator[NodeBuilder]:
    require_recording(vcr_cassette_dir, default_cassette_name, record_mode)
    with corpus_recording(
        vcr_cassette_dir,
        default_cassette_name,
        record_mode,
        RECORD_COMMAND,
        lambda: _live_corpus(luna_settings),
    ) as recording:
        yield partial(
            engine_nodes, libraries=recorded_libraries(recording), validator=built_validator()
        )


@PENDING
@pytest.mark.vcr
@pytest.mark.parametrize("name", ["worked_example_answered"])
def test_the_answered_worked_example_no_longer_asks_its_answer(
    name: str, luna_settings: Settings, run_nodes: NodeBuilder
) -> None:
    """Answered on the result screen (trained on data, used in the EU), the worked example stays
    high-risk under Annex III 4(a), and neither answered question is asked again."""
    with stale_recording_pending():
        run = run_classification(RUNS[name], settings=luna_settings, build_nodes=run_nodes)
    result = run.result
    asked = {question.id for question in result.follow_up_questions}
    assert result.risk_class is RiskClass.HIGH_RISK
    assert result.annex_point == ANNEX_III_4_A
    assert not asked & {"ai_system", "eu_link"}, asked


@PENDING
@pytest.mark.vcr
@pytest.mark.parametrize("name", ["worked_example_de"])
def test_the_worked_example_in_german_is_high_risk(
    name: str, luna_settings: Settings, run_nodes: NodeBuilder
) -> None:
    """The German worked example, run in German: high-risk under Annex III 4(a), as in English."""
    assert RUNS[name].language is Language.DE
    with stale_recording_pending():
        run = run_classification(RUNS[name], settings=luna_settings, build_nodes=run_nodes)
    assert run.result.risk_class is RiskClass.HIGH_RISK
    assert run.result.annex_point == ANNEX_III_4_A


def test_every_run_has_its_recording_test() -> None:
    """A run added to `runs.json` gets a recording test here, or the e2e API never replays it."""
    assert set(RUNS) == {"worked_example_answered", "worked_example_de"}
