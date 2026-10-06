"""LangSmith tracing of a classification (E10; INIT > Tech stack: "Production traces carry
metadata only").

A run is traced when `LANGSMITH_API_KEY` is set: one trace per classification, its id the run id
the caller gets back (`trace_id`), with every node and model call nested under it. Outside
development (`AIACT_ENV`, production by default) the client hides every run's inputs and outputs,
so a trace keeps only its metadata: node names, timings, model ids, the run's settings (law
version, language, date, counts), never a description, prompt or answer. Errors are kept: the
engine's error messages name fields and steps, never input values.
"""

from functools import cache

from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client

from aiact.settings import Settings


@cache
def _client(api_key: str, *, is_metadata_only: bool) -> Client:
    """One client per key and mode, so its background batching is shared by every run."""
    return Client(
        api_key=api_key,
        hide_inputs=is_metadata_only,
        hide_outputs=is_metadata_only,
    )


def is_metadata_only(settings: Settings) -> bool:
    return settings.aiact_env != "development"


def langsmith_tracer(settings: Settings) -> LangChainTracer | None:
    """The run's LangSmith tracer, or None when no key is set (tracing off)."""
    key = settings.langsmith_api_key
    if key is None or not key.get_secret_value():
        return None
    client = _client(key.get_secret_value(), is_metadata_only=is_metadata_only(settings))
    return LangChainTracer(project_name=settings.langsmith_project, client=client)
