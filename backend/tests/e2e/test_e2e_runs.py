"""The end-to-end runs beyond INIT's worked example in English (P13), recorded here and replayed by
the e2e API (`replay_server.py`): the worked example answered on its result screen (its Art. 3(1)
answer and the company profile's EU answer), and the worked example in German, recorded on
2026-10-13; and (P31) the worked example with No to a Yes/No question (not for public
authorities, Art. 111(2)), a German prohibited result (emotion recognition at work) and that
ban re-run after a Confirm (`prohibited_de_confirmed`, once runs.json has it). Each
request is the exact body the app sends, from `frontend/e2e/runs.json`, so the browser's run
finds it.

Recording calls the engine model, the query embeddings and the local test database's corpus:
`RECORD_COMMAND` (in `runs.py`), the orchestrator's paid step, after the reviews. Until then a new
run is a strict "recording pending" xfail; drop the mark once it is recorded.
"""

from collections.abc import Iterator

import pytest

from aiact.engine import run_classification
from aiact.engine.classify import NodeBuilder
from aiact.schemas import Language, RiskClass, Status, StepName
from aiact.settings import Settings
from tests.e2e.runs import E2E_RECORDINGS, RECORD_COMMAND, e2e_runs
from tests.engine.nodes.corpus_recording import (
    RecordingPendingError,
    corpus_recording,
    require_recording,
)
from tests.engine.nodes.known_gaps import stale_recording_pending
from tests.engine.replayed_engine import live_corpus, luna_settings, replayed_nodes

RUNS = e2e_runs()
ANNEX_III_4_A = "annex:III:4:a"
ART_5_1_F = "art:5:1:f"
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


@pytest.fixture(name="luna_settings")
def luna_settings_fixture(openrouter_settings: Settings) -> Settings:
    """As the worked example was recorded, and as the e2e API replays (`replayed_engine`)."""
    return luna_settings(openrouter_settings)


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
        lambda: live_corpus(luna_settings),
    ) as recording:
        yield replayed_nodes(recording)


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


@PENDING
@pytest.mark.vcr
@pytest.mark.parametrize("name", ["worked_example_not_for_authorities"])
def test_a_no_to_a_yes_no_question_is_not_asked_again(
    name: str, luna_settings: Settings, run_nodes: NodeBuilder
) -> None:
    """The worked example answered No on "Is the system meant for use by public authorities?" (with
    the profile's EU answer): neither answered question is asked again, and the class stays
    high-risk under Annex III 4(a)."""
    with stale_recording_pending():
        run = run_classification(RUNS[name], settings=luna_settings, build_nodes=run_nodes)
    result = run.result
    asked = {question.id for question in result.follow_up_questions}
    assert result.risk_class is RiskClass.HIGH_RISK
    assert result.annex_point == ANNEX_III_4_A
    assert not asked & {"for_public_authority", "eu_link"}, asked


@PENDING
@pytest.mark.vcr
@pytest.mark.parametrize("name", ["prohibited_de"])
def test_emotion_recognition_at_work_in_german_is_prohibited(
    name: str, luna_settings: Settings, run_nodes: NodeBuilder
) -> None:
    """Staff moods read from their faces at work, run in German: a decided ban under
    Art. 5(1)(f), which the German result names."""
    assert RUNS[name].language is Language.DE
    with stale_recording_pending():
        run = run_classification(RUNS[name], settings=luna_settings, build_nodes=run_nodes)
    result = run.result
    assert result.risk_class is RiskClass.PROHIBITED
    assert result.status is Status.DECIDED
    prohibited = next(step for step in result.steps if step.step is StepName.PROHIBITED)
    assert ART_5_1_F in {citation.provision_id for citation in prohibited.citations}


CONFIRMED_BAN = "prohibited_de_confirmed"
CONFIRMED_RUNS = [name for name in (CONFIRMED_BAN,) if name in RUNS]
"""The ban re-run after a Confirm (P31, P13 note 4d). Its body answers with the recorded ban's own
assumed fact, so `runs.json` gets it only once `prohibited_de` is recorded (german.spec.ts says
which body to add); until then this test has no run to record."""


@PENDING
@pytest.mark.vcr
@pytest.mark.parametrize("name", CONFIRMED_RUNS)
def test_a_confirmed_fact_keeps_the_german_ban(
    name: str, luna_settings: Settings, run_nodes: NodeBuilder
) -> None:
    """The German ban with its assumed fact confirmed: still a decided ban under Art. 5(1)(f), and
    the confirmed fact is not asked about again."""
    assert RUNS[name].language is Language.DE
    with stale_recording_pending():
        run = run_classification(RUNS[name], settings=luna_settings, build_nodes=run_nodes)
    result = run.result
    asked = {question.id for question in result.follow_up_questions}
    assert result.risk_class is RiskClass.PROHIBITED
    assert result.status is Status.DECIDED
    assert not asked & set(RUNS[name].answers), asked


def _parametrised_runs() -> set[str]:
    """The runs this module's recording tests are parametrised with (`name`)."""
    return {
        value
        for test in globals().values()
        for mark in getattr(test, "pytestmark", ())
        if mark.name == "parametrize" and mark.args[0] == "name"
        for value in mark.args[1]
    }


def test_every_run_has_its_recording_test() -> None:
    """A run added to `runs.json` gets a recording test here, or the e2e API never replays it;
    and every recording test records a run the flows make."""
    assert RUNS, "runs.json names no run"
    assert set(RUNS) == _parametrised_runs()
