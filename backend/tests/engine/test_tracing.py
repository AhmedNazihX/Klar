"""LangSmith tracing of a classification: off without a key, metadata only outside development
(E10; INIT > Tech stack). No trace is sent: the tracer is only built and inspected."""

from typing import Literal

from pydantic import SecretStr

from aiact.engine.tracing import langsmith_tracer
from aiact.settings import Settings

RUN_INPUTS = {"description": "We screen job applicants.", "language": "en"}
RUN_OUTPUTS = {"result": {"risk_class": "high_risk"}}


def _settings(env: Literal["development", "production"] | None, key: str | None) -> Settings:
    values: dict[str, object] = {"langsmith_project": "aiact-test"}
    if env is not None:
        values["aiact_env"] = env
    if key is not None:
        values["langsmith_api_key"] = SecretStr(key)
    return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]


def test_without_a_key_nothing_is_traced() -> None:
    assert langsmith_tracer(_settings("development", None)) is None
    assert langsmith_tracer(_settings("development", "")) is None


def test_production_is_the_default_and_its_traces_carry_metadata_only() -> None:
    tracer = langsmith_tracer(_settings(None, "lsv2-test-key"))
    assert tracer is not None
    assert tracer.project_name == "aiact-test"
    client = tracer.client
    assert client._hide_run_inputs(RUN_INPUTS) == {}  # pyright: ignore[reportPrivateUsage]
    assert client._hide_run_outputs(RUN_OUTPUTS) == {}  # pyright: ignore[reportPrivateUsage]


def test_development_traces_keep_inputs_and_outputs() -> None:
    tracer = langsmith_tracer(_settings("development", "lsv2-test-key"))
    assert tracer is not None
    client = tracer.client
    assert client._hide_run_inputs(RUN_INPUTS) == RUN_INPUTS  # pyright: ignore[reportPrivateUsage]
    assert client._hide_run_outputs(RUN_OUTPUTS) == RUN_OUTPUTS  # pyright: ignore[reportPrivateUsage]
