"""INIT's worked example end to end through `classify_system`'s pipeline (E10): live, and replayed
in CI from one recording of the whole run.

The replay runs the engine's own nodes (`engine_nodes`) on the recorded model replies and the
recorded corpus answers of every check (`<test>.corpus.json`, keyed per node), and checks every
citation against the corpus built from `data/parsed/` (E9), so it needs no database. It is
skipped until it is recorded: record it (live model, embedding and local-corpus calls) with
`RECORD_COMMAND`, after the story's reviews, as the orchestrator's paid step.
"""

from collections.abc import Iterator
from datetime import date

import pytest

from aiact.engine import (
    ClassificationRun,
    ClassifyRequest,
    run_classification,
)
from aiact.engine.classify import NodeBuilder
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome
from aiact.eval.experiments.matchers import WORKED_EXAMPLE
from aiact.schemas import (
    DISCLAIMER,
    ClassificationResult,
    EvidenceTag,
    Fact,
    FollowUpQuestion,
    Language,
    LawVersion,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import Settings, get_settings
from tests.engine.built_corpus import unresolved_citations, whole_articles
from tests.engine.nodes.corpus_recording import corpus_recording
from tests.engine.nodes.known_gaps import stale_recording_pending
from tests.engine.replayed_engine import live_corpus, luna_settings, replayed_nodes

AS_OF = date(2026, 10, 6)
"""The replay's date, fixed so the recorded corpus slices stay the ones it reads."""

RECORD_COMMAND = (
    "uv run pytest tests/engine/test_classify_worked_example.py -k replay --record-mode=once"
)
LIVE_COMMAND = "uv run pytest tests/engine/test_classify_worked_example.py -m live"


def worked_example_request() -> ClassifyRequest:
    return ClassifyRequest(
        description=WORKED_EXAMPLE.description, language=Language.EN, as_of=AS_OF
    )


INIT_DUTIES = {
    "art:26:1": "follow the provider's instructions for use",
    "art:26:2": "assign human oversight",
    "art:26:6": "keep the logs",
    "art:26:11": "inform the applicants subject to it",
}
"""The Art. 26 duties INIT's worked example lists, by the obligation table's article ids."""
ANNEX_III_FROM = date(2027, 12, 2)
"""INIT: the duties apply "from 2 December 2027" (the Annex III route's Chapter III date)."""
INIT_BASIS: dict[StepName, set[str]] = {
    StepName.SCOPE: {"art:3:1", "art:2:1"},
    StepName.HIGH_RISK: {"annex:III:4:a", "art:6:3"},
    StepName.TRANSPARENCY: {"art:50:1", "art:50:2", "art:50:3", "art:50:4"},
    StepName.ROLE_OBLIGATIONS: {"art:3:4"},
}
"""The Basis column of INIT's table, as the ids each step cites: Art. 2-3 (the AI system
definition and the territorial scope), Annex III 4(a) and Art. 6(3), Art. 50 (no duty raised,
so each duty paragraph it rules out, Art. 50(1) to (4): E16), and for the role the deployer
definition (INIT names Art. 25, whose switches a deployer that keeps its role doesn't trigger,
so the step cites none of them). Art. 5 is checked apart (`ART_5`): a step that matches no
practice cites either the Art. 5(1) list or the points it considered and set aside. No step
cites a whole article its text splits into paragraphs (`whole_articles`, E16)."""
ART_5 = "art:5"
"""The prohibited step's Basis: every id it cites is a provision of Art. 5."""


SCOPE_QUESTION = "ai_system"
"""The scope step's missing fact when it asks whether the tool infers its outputs (Art. 3(1)),
which the description doesn't say. It may instead assume that the tool is an AI system and
decide (user, 2026-10-06: either outcome is accepted, as long as the system is in scope)."""
DECIDED_STEPS = (
    StepName.PROHIBITED,
    StepName.HIGH_RISK,
    StepName.TRANSPARENCY,
    StepName.ROLE_OBLIGATIONS,
)


def assert_in_scope(result: ClassificationResult) -> None:
    """The scope step's two accepted outcomes: (a) it asks the Art. 3(1) inference question,
    with in scope as the working assumption, and the result needs more information with that
    question among its follow-ups; or (b) it decides in scope, with the fact that the tool is
    an AI system marked assumed, and the result is decided."""
    scope = next(step for step in result.steps if step.step is StepName.SCOPE)
    if scope.status is Status.NEEDS_MORE_INFORMATION:
        assert scope.missing_fact is not None and scope.missing_fact.id == SCOPE_QUESTION
        assert scope.missing_fact.about == "art:3:1"
        assert result.status is Status.NEEDS_MORE_INFORMATION
        assert SCOPE_QUESTION in {question.id for question in result.follow_up_questions}
        return
    assert scope.status is Status.DECIDED, (scope.status, scope.decision)
    assumed = [f.text for f in scope.facts_used if f.evidence is EvidenceTag.ASSUMED]
    assert any("ai system" in text.lower() for text in assumed), assumed
    assert result.status is Status.DECIDED


def assert_the_expected_result(run: ClassificationRun) -> None:
    """`assert_the_expected_classification`, and the run's cost counted for every node."""
    assert_the_expected_classification(run.result)
    assert run.usage.cost_usd > 0
    assert run.usage.tokens > 0
    assert set(run.usage.by_node) >= {"facts", *(name.value for name in StepName)}


def assert_the_expected_classification(result: ClassificationResult) -> None:
    """INIT > Worked example, row by row: in scope, with the scope step either (a) asking
    whether the tool infers (Art. 3(1)), in scope as the working assumption, so the result needs
    more information, or (b) deciding in scope with the AI-system point marked assumed, so the
    result is decided (`assert_in_scope`); no prohibited practice; high-risk under Annex III
    4(a) (ranking applicants is profiling, so Art. 6(3) can't exempt it); no separate Art. 50
    duty; the company stays a deployer, with the Art. 26 duties INIT lists from 2 December 2027;
    each step citing its Basis (`INIT_BASIS`).
    Every citation resolves."""
    steps = {step.step: step for step in result.steps}
    assert list(steps) == list(StepName)  # in scope (assumed), not prohibited: every check ran
    assert_in_scope(result)
    for name in DECIDED_STEPS:
        step = steps[name]
        assert step.status is Status.DECIDED, (name, step.status, step.decision)
    assert result.risk_class is RiskClass.HIGH_RISK, result.risk_class
    assert result.annex_point == "annex:III:4:a"
    for name, basis in INIT_BASIS.items():
        cited = {c.provision_id for c in steps[name].citations}
        assert basis <= cited, (name, sorted(cited))
    prohibited_cites = [c.provision_id for c in steps[StepName.PROHIBITED].citations]
    assert prohibited_cites, "the prohibited step cites nothing"
    assert all(pid == ART_5 or pid.startswith(f"{ART_5}:") for pid in prohibited_cites), (
        prohibited_cites
    )
    assert result.transparency_duties == ()
    assert result.role is Role.DEPLOYER
    duties = {o.article: o for o in result.obligations}
    assert set(INIT_DUTIES) <= set(duties), sorted(duties)
    for article in INIT_DUTIES:
        assert duties[article].applies_from == ANNEX_III_FROM, article
    assert result.law_version is LawVersion.AMENDED
    assert result.as_of == AS_OF
    assert result.disclaimer == DISCLAIMER[Language.EN]
    state = {
        "description": WORKED_EXAMPLE.description,
        "language": Language.EN,
        "law_version": LawVersion.AMENDED,
        "as_of": AS_OF,
        "exclude_source_example_ids": (),
    }
    for step in result.steps:
        assert not unresolved_citations(step, state), step.step  # pyright: ignore[reportArgumentType]
        assert not whole_articles(step), step.step


def stub_result(scope: StepResult) -> ClassificationResult:
    """A stub run whose scope check returns `scope` and whose other checks find nothing."""
    nodes = scripted_nodes(Script(checks={StepName.SCOPE: CheckOutcome(step=scope)}))
    run = run_classification(
        worked_example_request(),
        settings=Settings(_env_file=None),  # pyright: ignore[reportCallIssue]
        build_nodes=lambda _settings, _meter: nodes,
    )
    return run.result


ASKS = StepResult(
    step=StepName.SCOPE,
    decision="Working assumption: in scope.",
    status=Status.NEEDS_MORE_INFORMATION,
    missing_fact=FollowUpQuestion(
        id=SCOPE_QUESTION, text="Is it trained on data, or does it apply rules?", about="art:3:1"
    ),
)


def assumes(fact: str) -> StepResult:
    return StepResult(
        step=StepName.SCOPE,
        decision="In scope.",
        facts_used=(Fact(text=fact, evidence=EvidenceTag.ASSUMED),),
    )


@pytest.mark.parametrize(
    "scope", [ASKS, assumes("The tool is assumed to be an AI system.")], ids=["asks", "assumes"]
)
def test_either_scope_outcome_is_accepted(scope: StepResult) -> None:
    assert_in_scope(stub_result(scope))


@pytest.mark.parametrize(
    "scope",
    [
        assumes("The tool is assumed to be used in the EU."),  # the AI-system point not assumed
        ASKS.model_copy(update={"missing_fact": FollowUpQuestion(id="eu_use", text="EU?")}),
    ],
    ids=["decided_without_the_assumption", "asks_another_question"],
)
def test_any_other_scope_outcome_fails(scope: StepResult) -> None:
    with pytest.raises(AssertionError):
        assert_in_scope(stub_result(scope))


# --- Live ---------------------------------------------------------------------------------------


@pytest.mark.live
def test_live_worked_example() -> None:
    """The real pipeline: the engine model, the query embeddings and the corpus in the local test
    database (needs `backend/.env`'s keys). The run logs its cost per node (run pytest with
    `--log-cli-level=INFO` to see it)."""
    run = run_classification(worked_example_request(), settings=get_settings())
    assert_the_expected_result(run)


# --- Replay -------------------------------------------------------------------------------------


@pytest.fixture(name="luna_settings")
def luna_settings_fixture(openrouter_settings: Settings) -> Settings:
    return luna_settings(openrouter_settings)


@pytest.fixture
def replay_nodes(
    luna_settings: Settings, record_mode: str, vcr_cassette_dir: str, default_cassette_name: str
) -> Iterator[NodeBuilder]:
    """The engine's own nodes over the recorded model and corpus, citations checked against the
    built corpus; skips while nothing is recorded."""
    with corpus_recording(
        vcr_cassette_dir,
        default_cassette_name,
        record_mode,
        RECORD_COMMAND,
        lambda: live_corpus(luna_settings),
    ) as recording:
        yield replayed_nodes(recording)


@pytest.mark.vcr
def test_replay_worked_example(luna_settings: Settings, replay_nodes: NodeBuilder) -> None:
    with stale_recording_pending():
        run = run_classification(
            worked_example_request(), settings=luna_settings, build_nodes=replay_nodes
        )
    assert_the_expected_result(run)
