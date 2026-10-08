"""`classify_system` and its streamed form (E10), over stub and fake-model nodes: answers appended
to the description (decision 019), the gap run's opt-in reaching every retrieval call (decision
012), the streamed events, no class after a failed check, and the cost per node. No model,
database or network is used. INIT's worked example end to end is in
`test_classify_worked_example.py`."""

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr, ValidationError

from aiact.engine import (
    ClassificationFailedError,
    ClassifyRequest,
    ErrorEvent,
    FactsEvent,
    ResultEvent,
    StepEvent,
    StepStartedEvent,
    classify_system,
    extended_description,
    run_classification,
    stream_classification,
)
from aiact.engine import classify as classify_module
from aiact.engine.citations import CitationValidator, OmnibusChanges
from aiact.engine.classify import ANSWERS_HEADING, NodeBuilder, engine_nodes
from aiact.engine.clients import NODE_TOKENS
from aiact.engine.graph import CheckNode, EngineNodes
from aiact.engine.nodes.common import lookup_for
from aiact.engine.nodes.facts import (
    ExtractedFact,
    FactExtractor,
    FactsAnswer,
    description_questions,
)
from aiact.engine.nodes.finalize import finalize
from aiact.engine.nodes.role_texts import legacy_questions
from aiact.engine.scripted import Script, no_match, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome, RoleFinding
from aiact.engine.usage import UsageMeter
from aiact.llm import LLMConfigError
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.schemas import (
    DESCRIPTION_QUESTION_IDS,
    STEP_ORDER,
    Citation,
    ClassificationResult,
    EvidenceTag,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    RiskClass,
    Role,
    StepName,
    StepResult,
)
from aiact.settings import Settings

AS_OF = date(2026, 10, 6)
DESCRIPTION = (
    "We're a 40-person logistics company. We use a tool that reads incoming job applications, "
    "scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't "
    "change it."
)
EU_ANSWER = "Yes, we use it at our depot in Leipzig."
EU_QUOTE = "we use it at our depot in Leipzig"

SETTINGS = Settings(_env_file=None, openrouter_api_key=SecretStr("k"))  # pyright: ignore[reportCallIssue]
"""No LangSmith key, so nothing is traced; the key only lets a node build its fake model."""


def request(**changes: object) -> ClassifyRequest:
    values: dict[str, object] = {
        "description": DESCRIPTION,
        "language": Language.EN,
        "as_of": AS_OF,
        **changes,
    }
    return ClassifyRequest.model_validate(values)


def given(nodes: EngineNodes) -> NodeBuilder:
    return lambda _settings, _meter: nodes


enough_answer = partial(FactsAnswer, says_what_it_decides=True, says_who_it_affects=True)
"""A facts answer for a description that says what the system decides and whom it affects."""


def chat(*replies: AIMessage) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter(replies))


def facts_reply(*facts: ExtractedFact) -> AIMessage:
    return AIMessage(content=enough_answer(facts=facts, questions=()).model_dump_json())


EU_FACT = ExtractedFact(
    text="The tool is used in the EU.", evidence=EvidenceTag.STATED, quote=EU_QUOTE, question=None
)


# --- Answers enter as text (decision 019) -------------------------------------------------------


def test_the_answers_are_appended_under_a_heading_one_line_each() -> None:
    answers = {"eu_use": EU_ANSWER, "vendor_changes": "None at all,\nnot even settings."}
    assert extended_description(DESCRIPTION, answers, Language.EN) == (
        f"{DESCRIPTION}\n\nAnswers to follow-up questions:\n"
        f"- eu_use: {EU_ANSWER}\n- vendor_changes: None at all, not even settings."
    )
    german = extended_description("Wir prüfen Bewerbungen.", {"eu_use": "Ja."}, Language.DE)
    assert german == f"Wir prüfen Bewerbungen.\n\n{ANSWERS_HEADING[Language.DE]}\n- eu_use: Ja."
    assert extended_description(DESCRIPTION, {}, Language.EN) == DESCRIPTION


class Captured:
    """Stub checks that keep the state each check was given."""

    def __init__(self) -> None:
        self.states: dict[StepName, EngineState] = {}

    def checks(self) -> dict[StepName, CheckNode]:
        return {name: self._check(name) for name in STEP_ORDER}

    def _check(self, name: StepName) -> CheckNode:
        def run(state: EngineState) -> CheckOutcome:
            self.states[name] = state
            return no_match(name)

        return run


def facts_run(answers: dict[str, str]) -> tuple[ClassificationResult, Captured, list[str]]:
    """A run whose facts node is the real one over a fake model that states the EU fact with
    `EU_QUOTE`; the checks are stubs. Returns the result, the checks' states and the
    descriptions the facts node read."""
    extractor = FactExtractor(SETTINGS, chat=chat(facts_reply(EU_FACT)))
    read: list[str] = []

    def facts_node(state: EngineState) -> FactsOutcome:
        read.append(state["description"])
        return extractor(state)

    captured = Captured()
    stub = scripted_nodes(Script())
    nodes = EngineNodes(facts=facts_node, checks=captured.checks(), finalize=stub.finalize)
    run = run_classification(request(answers=answers), settings=SETTINGS, build_nodes=given(nodes))
    return run.result, captured, read


def test_an_answer_turns_a_fact_into_stated_with_a_span_in_the_extended_text() -> None:
    result, captured, read = facts_run({"eu_use": EU_ANSWER})
    extended = extended_description(DESCRIPTION, {"eu_use": EU_ANSWER}, Language.EN)
    assert read == [extended]

    [fact] = result.facts
    assert fact.evidence is EvidenceTag.STATED
    span = fact.source_span
    assert span is not None
    assert extended[span.start : span.end] == EU_QUOTE
    assert span.start > len(DESCRIPTION)  # the span lies in the appended answer

    for state in captured.states.values():  # every check reads the same text, and no second path
        assert state["description"] == extended
        assert "answers" not in state


def test_without_the_answer_the_same_quote_is_not_stated() -> None:
    result, _, _ = facts_run({})
    [fact] = result.facts
    assert fact.evidence is EvidenceTag.INFERRED
    assert fact.source_span is None


def test_the_art_111_2_questions_pass_through_and_their_answers_enter_like_any_other() -> None:
    legacy = legacy_questions(date(2027, 12, 2), "art:111:2")
    keys = (legacy.placed_before, legacy.design_change, legacy.public_authority)
    questions = tuple(
        FollowUpQuestion(id=k.id, text=k.question[Language.EN], about=k.article) for k in keys
    )
    role_step = StepResult(step=StepName.ROLE_OBLIGATIONS, decision="Role: deployer.")
    role = CheckOutcome(
        step=role_step, role=RoleFinding(role=Role.DEPLOYER), follow_up_questions=questions
    )
    captured = Captured()
    checks = {**captured.checks(), StepName.ROLE_OBLIGATIONS: lambda _state: role}
    nodes = EngineNodes(facts=lambda _state: FactsOutcome(), checks=checks, finalize=finalize)
    answers = {"placed_before_chapter_iii": "No, we launch in 2028.", "for_public_authority": "No."}

    result = run_classification(
        request(answers=answers), settings=SETTINGS, build_nodes=given(nodes)
    ).result

    asked = {question.id for question in result.follow_up_questions}
    assert {"placed_before_chapter_iii", "significant_design_change", "for_public_authority"} <= (
        asked
    )
    seen = captured.states[StepName.SCOPE]["description"]
    assert seen == extended_description(DESCRIPTION, answers, Language.EN)


@pytest.mark.parametrize(
    "changes",
    [
        {"description": "   "},
        {"answers": {"eu_use": " "}},
        {"answers": {"Not An Id": "yes"}},
        {"language": "fr"},
        {"law_version": "2025"},
    ],
)
def test_a_bad_request_is_rejected_before_anything_runs(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        request(**changes)


def test_classify_system_builds_the_request_with_today_and_no_held_out_examples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[ClassifyRequest] = []
    stub = run_classification(request(), settings=SETTINGS, build_nodes=given(stub_nodes()))

    options: list[dict[str, object]] = []

    def fake_run(req: ClassifyRequest, **kwargs: object) -> object:
        seen.append(req)
        options.append(kwargs)
        return stub

    monkeypatch.setattr(classify_module, "run_classification", fake_run)
    result = classify_system(DESCRIPTION, "de", answers={"eu_use": "Ja."})
    assert result == stub.result
    [req] = seen
    assert req.as_of == date.today()
    assert req.language is Language.DE
    assert req.law_version is LawVersion.AMENDED
    assert dict(req.answers) == {"eu_use": "Ja."}
    assert options == [{"exclude_source_example_ids": (), "include_held_out": False}]


def test_the_request_body_has_no_retrieval_options() -> None:
    """What retrieval leaves out is never part of the body P1 and P2b accept (decision 012)."""
    assert {"include_held_out", "exclude_source_example_ids"}.isdisjoint(
        ClassifyRequest.model_fields
    )
    with pytest.raises(ValidationError):
        request(include_held_out=True)


@pytest.mark.parametrize(
    "changes",
    [
        {"description": "x" * (ClassifyRequest.MAX_DESCRIPTION_CHARS + 1)},
        {"answers": {"eu_use": "y" * (ClassifyRequest.MAX_ANSWER_CHARS + 1)}},
        {"answers": {f"q_{n}": "yes" for n in range(ClassifyRequest.MAX_ANSWERS + 1)}},
    ],
    ids=["description", "answer", "answer_count"],
)
def test_oversize_input_is_rejected_before_any_model_call(
    changes: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_run(*args: object, **kwargs: object) -> object:
        raise AssertionError("the run started")

    monkeypatch.setattr(classify_module, "run_classification", no_run)
    values = {"description": DESCRIPTION, "answers": None, **changes}
    with pytest.raises(ValidationError):
        classify_system(
            str(values["description"]),
            Language.EN,
            answers=values["answers"],  # pyright: ignore[reportArgumentType]
        )


def test_input_at_the_limits_is_accepted() -> None:
    limits = request(
        description="x" * ClassifyRequest.MAX_DESCRIPTION_CHARS,
        answers={
            f"q_{n}": "y" * ClassifyRequest.MAX_ANSWER_CHARS
            for n in range(ClassifyRequest.MAX_ANSWERS)
        },
    )
    assert len(limits.answers) == ClassifyRequest.MAX_ANSWERS


# --- The gap run's opt-in (decision 012) ----------------------------------------------------------


class HeldOutProbe:
    """Check nodes that note the `include_held_out` of their run's lookup and cite a provision,
    and a citation source that notes the flag it is asked with (the validator's corpus calls)."""

    def __init__(self) -> None:
        self.check_flags: list[tuple[StepName, bool]] = []
        self.source_flags: list[bool] = []

    def checks(self) -> dict[StepName, CheckNode]:
        return {name: self._check(name) for name in STEP_ORDER}

    def _check(self, name: StepName) -> CheckNode:
        def run(state: EngineState) -> CheckOutcome:
            self.check_flags.append((name, lookup_for(state).include_held_out))
            citation = Citation(
                provision_id="art:5",
                document_id="ai-act-consolidated",
                law_version=LawVersion.AMENDED,
                language=Language.EN,
                quote="As quoted.",
            )
            return CheckOutcome(step=StepResult(step=name, decision="Probe", citations=(citation,)))

        return run

    def provision(
        self,
        provision_id: str,
        language: Language,
        law_version: LawVersion | None,
        as_of: date | None,
        *,
        include_held_out: bool = False,
    ) -> Provision:
        self.source_flags.append(include_held_out)
        raise ProvisionNotFoundError(provision_id)

    def omnibus(self, provision_id: str, language: Language, as_of: date | None) -> Provision:
        raise ProvisionNotFoundError(provision_id)


def held_out_run(*, include_held_out: bool = False) -> HeldOutProbe:
    probe = HeldOutProbe()
    validator = CitationValidator(
        source=probe, omnibus=OmnibusChanges(in_force_from=AS_OF, targets=frozenset())
    )
    stub = scripted_nodes(Script())
    nodes = EngineNodes(
        facts=stub.facts, checks=validator.checks(probe.checks()), finalize=stub.finalize
    )
    run_classification(
        request(), settings=SETTINGS, build_nodes=given(nodes), include_held_out=include_held_out
    )
    return probe


def test_include_held_out_reaches_every_check_and_the_citation_check() -> None:
    probe = held_out_run(include_held_out=True)
    assert {name for name, _ in probe.check_flags} == set(STEP_ORDER)
    assert all(flag for _, flag in probe.check_flags)
    assert probe.source_flags  # (every step's citation, and again on its retry)
    assert all(probe.source_flags)


def test_by_default_no_check_and_no_citation_check_sees_held_out_examples() -> None:
    probe = held_out_run()
    assert {name for name, _ in probe.check_flags} == set(STEP_ORDER)
    assert not any(flag for _, flag in probe.check_flags)
    assert probe.source_flags
    assert not any(probe.source_flags)


def recording_nodes(states: list[tuple[str, EngineState]]) -> EngineNodes:
    """Stub nodes that keep the state every node (facts, each check, finalize) was given."""
    stub = scripted_nodes(Script())

    def kept[T](name: str, node: Callable[[EngineState], T]) -> Callable[[EngineState], T]:
        def run(state: EngineState) -> T:
            states.append((name, state))
            return node(state)

        return run

    return EngineNodes(
        facts=kept("facts", stub.facts),
        checks={name: kept(name.value, check) for name, check in stub.checks.items()},
        finalize=kept("finalize", stub.finalize),
    )


@pytest.mark.parametrize("include_held_out", [None, True])
def test_the_stream_gives_every_node_the_runs_opt_in(include_held_out: bool | None) -> None:
    """Without the opt-in, every node's state says False; with it, True (decision 012)."""
    states: list[tuple[str, EngineState]] = []
    builder = given(recording_nodes(states))
    events = (
        stream_classification(request(), settings=SETTINGS, build_nodes=builder)
        if include_held_out is None
        else stream_classification(
            request(), settings=SETTINGS, build_nodes=builder, include_held_out=include_held_out
        )
    )
    assert isinstance(list(events)[-1], ResultEvent)
    assert [name for name, _ in states] == ["facts", *STEP_ORDER, "finalize"]
    expected = include_held_out is True
    assert all(state.get("include_held_out") is expected for _, state in states)


@pytest.mark.parametrize("run", ["run_classification", "stream_classification"])
def test_a_single_string_of_example_ids_is_rejected(run: str) -> None:
    """A bare string would be split into characters and exclude nothing."""
    function = getattr(classify_module, run)
    with pytest.raises(TypeError, match="not one string"):
        function(
            request(),
            settings=SETTINGS,
            build_nodes=given(stub_nodes()),
            exclude_source_example_ids="hr-ex-001",
        )


def test_classify_system_rejects_a_single_string_of_example_ids() -> None:
    with pytest.raises(TypeError, match="not one string"):
        classify_system(DESCRIPTION, Language.EN, exclude_source_example_ids="hr-ex-001")


def test_example_ids_reach_every_node_as_given() -> None:
    states: list[tuple[str, EngineState]] = []
    run_classification(
        request(),
        settings=SETTINGS,
        build_nodes=given(recording_nodes(states)),
        exclude_source_example_ids=["hr-ex-001", "hr-ex-002"],
    )
    assert {state["exclude_source_example_ids"] for _, state in states} == {
        ("hr-ex-001", "hr-ex-002")
    }


# --- Streaming ------------------------------------------------------------------------------------


ANNEX_POINT = "annex:III:4:a"


def high_risk_outcome() -> CheckOutcome:
    cited = Citation(
        provision_id=ANNEX_POINT,
        document_id="ai-act-consolidated",
        law_version=LawVersion.AMENDED,
        language=Language.EN,
        quote="Employment: recruitment or selection.",
    )
    step = StepResult(step=StepName.HIGH_RISK, decision="High-risk.", citations=(cited,))
    return CheckOutcome(step=step, high_risk_route=HighRiskRoute.ANNEX_III, annex_point=ANNEX_POINT)


def stub_nodes(fail_at: StepName | None = None, spend: UsageMeter | None = None) -> EngineNodes:
    """Stub nodes for a high-risk run; `fail_at` raises in that check after a paid model call
    counted by `spend`."""
    script = Script(
        checks={StepName.HIGH_RISK: high_risk_outcome()}, risk_class=RiskClass.HIGH_RISK
    )
    stub = scripted_nodes(script)
    if fail_at is None:
        return stub

    def failing(_state: EngineState) -> CheckOutcome:
        if spend is not None:
            paid = AIMessage(
                content="{",
                response_metadata={"cost": 0.004},
                usage_metadata={"input_tokens": 900, "output_tokens": 100, "total_tokens": 1000},
            )
            model = GenericFakeChatModel(
                messages=iter([paid]), callbacks=[spend.chat_callback(fail_at)]
            )
            model.invoke("a broken answer follows")
        raise ValueError("high-risk answer doesn't fit the schema: annex_iii.point: bad")

    return EngineNodes(
        facts=stub.facts, checks={**stub.checks, fail_at: failing}, finalize=stub.finalize
    )


def test_the_stream_sends_the_facts_each_check_as_it_starts_and_ends_then_the_result() -> None:
    events = list(
        stream_classification(request(), settings=SETTINGS, build_nodes=given(stub_nodes()))
    )
    kinds = [event.event for event in events]
    assert kinds == ["facts", *(["step_started", "step"] * len(STEP_ORDER)), "result"]
    started = [e.step for e in events if isinstance(e, StepStartedEvent)]
    finished = [e.step.step for e in events if isinstance(e, StepEvent)]
    assert started == finished == list(STEP_ORDER)
    matches = {e.step.step: e.matches for e in events if isinstance(e, StepEvent)}
    assert matches[StepName.HIGH_RISK] == (ANNEX_POINT,)
    assert all(not found for name, found in matches.items() if name is not StepName.HIGH_RISK)
    assert isinstance(events[0], FactsEvent)
    result = events[-1]
    assert isinstance(result, ResultEvent)
    assert result.result.risk_class is RiskClass.HIGH_RISK


def test_a_thin_description_streams_the_facts_then_a_result_with_no_class_and_no_step() -> None:
    thin = FactsOutcome(
        follow_up_questions=description_questions(Language.EN), needs_description=True
    )
    builder = given(scripted_nodes(Script(facts=thin)))
    events = list(stream_classification(request(), settings=SETTINGS, build_nodes=builder))
    assert [event.event for event in events] == ["facts", "result"]
    result = events[-1]
    assert isinstance(result, ResultEvent)
    assert result.result.risk_class is None
    assert result.result.steps == ()
    assert [q.id for q in result.result.follow_up_questions] == list(DESCRIPTION_QUESTION_IDS)


def test_a_failed_check_ends_the_stream_with_an_error_that_names_it_and_no_class() -> None:
    builder = given(stub_nodes(fail_at=StepName.HIGH_RISK))
    events = list(stream_classification(request(), settings=SETTINGS, build_nodes=builder))
    assert not any(isinstance(event, ResultEvent) for event in events)
    last = events[-1]
    assert isinstance(last, ErrorEvent)
    assert last.step == "high_risk"
    assert "high_risk" in last.message
    assert DESCRIPTION not in last.message
    finished = [e.step.step for e in events if isinstance(e, StepEvent)]
    assert finished == [StepName.SCOPE, StepName.PROHIBITED]


def test_a_failed_check_raises_with_its_name_and_what_was_spent() -> None:
    def builder(_settings: Settings, meter: UsageMeter) -> EngineNodes:
        return stub_nodes(fail_at=StepName.TRANSPARENCY, spend=meter)

    with pytest.raises(ClassificationFailedError) as raised:
        run_classification(request(), settings=SETTINGS, build_nodes=builder)
    error = raised.value
    assert error.step == "transparency"
    assert error.usage.cost_usd == pytest.approx(0.004)
    assert error.usage.tokens == 1000
    assert isinstance(error.__cause__, ValueError)
    assert error.trace_id is None  # no LangSmith key, no trace


def test_the_run_reports_and_logs_its_cost_per_node(caplog: pytest.LogCaptureFixture) -> None:
    def builder(_settings: Settings, meter: UsageMeter) -> EngineNodes:
        stub = stub_nodes()
        paid = AIMessage(
            content=enough_answer(facts=(), questions=()).model_dump_json(),
            response_metadata={"cost": 0.0021},
            usage_metadata={"input_tokens": 1500, "output_tokens": 500, "total_tokens": 2000},
        )
        model = GenericFakeChatModel(
            messages=iter([paid]), callbacks=[meter.chat_callback("facts")]
        )
        return EngineNodes(
            facts=FactExtractor(SETTINGS, chat=model), checks=stub.checks, finalize=stub.finalize
        )

    with caplog.at_level(logging.INFO, logger=classify_module.__name__):
        run = run_classification(request(), settings=SETTINGS, build_nodes=builder)
    assert run.usage.cost_usd == pytest.approx(0.0021)
    assert run.usage.by_node["facts"].tokens == 2000
    [line] = [r.getMessage() for r in caplog.records if "classification cost" in r.getMessage()]
    assert "$0.002100" in line
    assert "'facts': 0.0021" in line
    assert DESCRIPTION not in line


# --- The engine's own nodes ---------------------------------------------------------------------


def engine_settings(**values: object) -> Settings:
    configured: dict[str, object] = {
        "openrouter_api_key": SecretStr("k"),
        "engine_model": "openai/gpt-6-luna-20260922",
        "engine_provider": "azure/eu",
        "embedding_model": "qwen/qwen3-embedding-8b",
        "embedding_provider": "nebius",
        **values,
    }
    return Settings(_env_file=None, **configured)  # pyright: ignore[reportCallIssue]


def test_the_engine_nodes_meter_their_models_under_their_own_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paid = AIMessage(
        content=enough_answer(facts=(), questions=()).model_dump_json(),
        response_metadata={"cost": 0.002},
        usage_metadata={"input_tokens": 90, "output_tokens": 10, "total_tokens": 100},
    )

    def fake_engine_chats(settings: Settings) -> dict[str, GenericFakeChatModel]:
        return {node: GenericFakeChatModel(messages=iter([paid])) for node in NODE_TOKENS}

    monkeypatch.setattr(classify_module, "engine_chats", fake_engine_chats)
    meter = UsageMeter()
    nodes = engine_nodes(engine_settings(), meter)
    assert set(nodes.checks) == set(STEP_ORDER)
    assert nodes.finalize is finalize

    nodes.facts(stub_state())
    usage = meter.usage()
    assert set(usage.by_node) == {"facts"}
    assert usage.by_node["facts"].cost_usd == pytest.approx(0.002)


def stub_state() -> EngineState:
    return {
        "description": DESCRIPTION,
        "language": Language.EN,
        "law_version": LawVersion.AMENDED,
        "as_of": AS_OF,
        "exclude_source_example_ids": (),
    }


@pytest.mark.parametrize("missing", ["engine_model", "engine_provider", "embedding_model"])
def test_the_engine_nodes_need_their_model_settings(missing: str) -> None:
    with pytest.raises(LLMConfigError):
        engine_nodes(engine_settings(**{missing: None}), UsageMeter())


def test_a_setup_error_raises_when_the_stream_is_asked_for_not_as_an_event() -> None:
    def unconfigured(_settings: Settings, _meter: UsageMeter) -> EngineNodes:
        raise LLMConfigError("ENGINE_MODEL is not set")

    with pytest.raises(LLMConfigError):
        stream_classification(request(), settings=SETTINGS, build_nodes=unconfigured)
