"""The runner's `engine` classifier over `run_classification` (E10, V1's adapter): it reports cost,
tokens and the trace id, reads the case's date (B5c), and raises `ClassifierFailedError` when a
run fails after spending. Stub nodes only: no model, database or network."""

from datetime import date

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.engine import ClassificationFailedError
from aiact.engine.graph import EngineNodes
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import EngineState, FactsOutcome
from aiact.engine.usage import UsageMeter
from aiact.eval import engine_classifier, runner
from aiact.eval.engine_classifier import EngineClassifier
from aiact.eval.runner import ClassifierFailedError, ClassifierInput
from aiact.llm import LLMConfigError
from aiact.schemas import Language
from aiact.settings import Settings

CASE_DATE = date(2027, 3, 1)


def settings(**values: object) -> Settings:
    configured: dict[str, object] = {
        "openrouter_api_key": SecretStr("k"),
        "engine_model": "openai/gpt-6-luna-20260922",
        "engine_provider": "azure/eu",
        "embedding_model": "qwen/qwen3-embedding-8b",
        "embedding_provider": "nebius",
        **values,
    }
    return Settings(_env_file=None, **configured)  # pyright: ignore[reportCallIssue]


def paid_reply(content: str) -> AIMessage:
    return AIMessage(
        content=content,
        response_metadata={"cost": 0.003},
        usage_metadata={"input_tokens": 400, "output_tokens": 100, "total_tokens": 500},
    )


class Builder:
    """Stub nodes whose facts node makes one paid call (or fails after it), keeping the
    states it was given."""

    def __init__(self, *, fail: bool = False, spend: bool = True) -> None:
        self.fail = fail
        self.spend = spend
        self.states: list[EngineState] = []

    def __call__(self, _settings: Settings, meter: UsageMeter) -> EngineNodes:
        stub = scripted_nodes(Script())
        model = GenericFakeChatModel(
            messages=iter([paid_reply("{}")]), callbacks=[meter.chat_callback("facts")]
        )

        def facts(state: EngineState) -> FactsOutcome:
            self.states.append(state)
            if self.spend:
                model.invoke("describe")
            if self.fail:
                raise ValueError("facts answer doesn't fit the schema")
            return FactsOutcome()

        return EngineNodes(facts=facts, checks=stub.checks, finalize=stub.finalize)


def request(as_of: date | None = CASE_DATE) -> ClassifierInput:
    return ClassifierInput(
        description="A tool that ranks job applicants.",
        language=Language.EN,
        exclude_source_example_ids=("hr-ex-002",),
        as_of=as_of,
    )


def test_a_case_reports_its_cost_and_tokens_and_runs_on_its_own_date() -> None:
    builder = Builder()
    answer = EngineClassifier(settings(), build_nodes=builder).classify(request())
    assert answer.cost_usd == pytest.approx(0.003)
    assert answer.tokens == 500
    assert answer.trace_id is None  # no LangSmith key in these settings
    [state] = builder.states
    assert state["as_of"] == CASE_DATE
    assert answer.result.as_of == CASE_DATE
    assert state["exclude_source_example_ids"] == ("hr-ex-002",)
    assert state.get("include_held_out", False) is False


def test_a_case_without_a_date_runs_on_the_run_date() -> None:
    builder = Builder()
    EngineClassifier(settings(), build_nodes=builder).classify(request(as_of=None))
    assert builder.states[0]["as_of"] == date.today()


def test_a_run_that_fails_after_spending_carries_its_cost() -> None:
    classifier = EngineClassifier(settings(), build_nodes=Builder(fail=True))
    with pytest.raises(ClassifierFailedError) as raised:
        classifier.classify(request())
    assert raised.value.cost_usd == pytest.approx(0.003)
    assert raised.value.tokens == 500
    assert isinstance(raised.value.cause, ClassificationFailedError)


def test_a_run_that_fails_before_spending_raises_its_own_error() -> None:
    classifier = EngineClassifier(settings(), build_nodes=Builder(fail=True, spend=False))
    with pytest.raises(ClassificationFailedError):
        classifier.classify(request())


def test_the_classifier_records_the_engine_settings() -> None:
    info = EngineClassifier(settings()).info
    assert (info.model, info.provider) == ("openai/gpt-6-luna-20260922", "azure/eu")
    assert info.embedding == {
        "model": "qwen/qwen3-embedding-8b",
        "provider": "nebius",
        "dimensions": 1536,
    }


def test_the_runner_builds_the_engine_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_classifier, "get_settings", settings)
    assert isinstance(runner.build_classifier("engine"), EngineClassifier)


@pytest.mark.parametrize("missing", ["engine_model", "embedding_provider"])
def test_a_missing_setting_makes_it_unavailable(missing: str) -> None:
    with pytest.raises(LLMConfigError):
        EngineClassifier(settings(**{missing: None}))
