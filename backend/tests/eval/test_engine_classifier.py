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
from aiact.eval.runner import ClassifierFailedError, ClassifierInput, DummyClassifier, run_benchmark
from aiact.llm import LLMConfigError
from aiact.schemas import Language
from aiact.settings import Settings
from tests.eval.test_runner import CASES, SPLIT, MemoryStore, options

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


LUNA = "openai/gpt-6-luna-20260922"
GEMINI = "google/gemini-3.1-flash-lite"


def paid_reply(content: str, model: str | None = None) -> AIMessage:
    """A reply billed at $0.003, served by `model` (OpenRouter's `model`; None: unnamed)."""
    return AIMessage(
        content=content,
        response_metadata={"cost": 0.003, **({"model_name": model} if model else {})},
        usage_metadata={"input_tokens": 400, "output_tokens": 100, "total_tokens": 500},
    )


class Builder:
    """Stub nodes whose facts node makes one paid call per model in `served` (or fails after
    them), keeping the states it was given."""

    def __init__(
        self, *, fail: bool = False, spend: bool = True, served: tuple[str | None, ...] = (None,)
    ) -> None:
        self.fail = fail
        self.spend = spend
        self.served = served
        self.states: list[EngineState] = []

    def __call__(self, _settings: Settings, meter: UsageMeter) -> EngineNodes:
        stub = scripted_nodes(Script())
        model = GenericFakeChatModel(
            messages=iter([paid_reply("{}", served) for served in self.served]),
            callbacks=[meter.chat_callback("facts")],
        )

        def facts(state: EngineState) -> FactsOutcome:
            self.states.append(state)
            if self.spend:
                for _ in self.served:
                    model.invoke("describe")
            if self.fail:
                raise ValueError("facts answer doesn't fit the schema")
            return FactsOutcome()

        return EngineNodes(facts=facts, checks=stub.checks, finalize=stub.finalize)


def request(as_of: date | None = CASE_DATE, *, include_held_out: bool = False) -> ClassifierInput:
    return ClassifierInput(
        description="A tool that ranks job applicants.",
        language=Language.EN,
        exclude_source_example_ids=("hr-ex-002",),
        as_of=as_of,
        include_held_out=include_held_out,
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


def test_the_gap_runs_opt_in_reaches_the_engine() -> None:
    builder = Builder()
    EngineClassifier(settings(), build_nodes=builder).classify(request(include_held_out=True))
    [state] = builder.states
    assert state.get("include_held_out") is True
    assert state["exclude_source_example_ids"] == ("hr-ex-002",)


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


REFUSED_THEN_ANSWERED = (LUNA, GEMINI)
"""The facts request Luna's provider refused and the second model answered (decision 033)."""


def test_a_stored_case_records_which_model_served_each_nodes_calls() -> None:
    """The DoD's "each stored call records which model served it": the case row's scores."""
    store = MemoryStore()
    classifier = EngineClassifier(settings(), build_nodes=Builder(served=REFUSED_THEN_ANSWERED))
    run_benchmark(CASES[:1], classifier, store, options(classifier_name="engine"), SPLIT)
    [(_, record)] = store.cases
    assert record.scores["is_error"] is False
    assert record.scores["models"] == {"facts": {LUNA: 1, GEMINI: 1}}
    assert record.tokens == 1000


def test_a_stored_failed_case_records_which_model_served_each_nodes_calls() -> None:
    store = MemoryStore()
    builder = Builder(fail=True, served=REFUSED_THEN_ANSWERED)
    run_benchmark(
        CASES[:1],
        EngineClassifier(settings(), build_nodes=builder),
        store,
        options(classifier_name="engine"),
        SPLIT,
    )
    [(_, record)] = store.cases
    assert record.scores["is_error"] is True
    assert record.scores["models"] == {"facts": {LUNA: 1, GEMINI: 1}}


def test_a_classifier_that_reports_no_models_stores_none() -> None:
    store = MemoryStore()
    run_benchmark(CASES[:1], DummyClassifier(), store, options(), SPLIT)
    [(_, record)] = store.cases
    assert "models" not in record.scores


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
