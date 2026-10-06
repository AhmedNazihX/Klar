"""LangSmith tracing of a classification (E10; INIT > Tech stack: "Production traces carry
metadata only").

A run is traced only through the tracer built here, and only when `LANGSMITH_API_KEY` is set:
one trace per classification, its id the run id the caller gets back (`trace_id`), with every
node and model call nested under it. Without a key nothing is traced: the run switches off
langchain-core's own tracer too, which `LANGSMITH_TRACING` in the environment would otherwise
add with the full content (`tracing_switch`).

Outside development (`AIACT_ENV`, production by default) a trace keeps only its metadata: node
names, timings, model ids and the run's settings (law version, language, date, counts). The
client hides every run's inputs and outputs, and cuts every run's error down to its exception
type (`withheld_error`): an error's text and traceback may quote what a model returned, which
quotes the description, or what a provider or the database echoed back.
"""

import re
from contextlib import AbstractContextManager
from functools import cache
from typing import TYPE_CHECKING

from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client
from langsmith.run_helpers import tracing_context

from aiact.settings import Settings

if TYPE_CHECKING:
    import requests

WITHHELD = "{error_type} (details withheld: traces carry metadata only)"
"""A run's error in a metadata-only trace."""

ERROR_TYPE = re.compile(r"[A-Za-z_][\w.]*(?=[(:]|$)")
"""The exception type an error string starts with: `repr(exc)` or `Type: message`."""


def is_metadata_only(settings: Settings) -> bool:
    return settings.aiact_env != "development"


def withheld_error(error: object) -> str:
    """`error` cut down to the exception type it names first ("Error" when none is found)."""
    lines = str(error).strip().splitlines()
    match = ERROR_TYPE.match(lines[0].strip()) if lines else None
    return WITHHELD.format(error_type=match.group(0) if match else "Error")


def scrub_errors(payload: dict[str, object]) -> dict[str, object]:
    """The client's anonymizer in metadata-only mode. The client hands it each run's error
    wrapped as `{"error": …}`, which comes back withheld; any other payload (run metadata: the
    inputs and outputs are already hidden) comes back as it is."""
    if set(payload) != {"error"}:
        return payload
    return {"error": withheld_error(payload["error"])}


def build_client(
    api_key: str,
    *,
    is_metadata_only: bool,
    api_url: str | None = None,
    session: "requests.Session | None" = None,
    auto_batch_tracing: bool = True,
) -> Client:
    """A LangSmith client; in metadata-only mode it hides inputs and outputs and withholds
    errors. `api_url`, `session` and `auto_batch_tracing` select another endpoint or transport
    (tests read each post through a session, unbatched)."""
    return Client(
        api_key=api_key,
        api_url=api_url,
        session=session,
        auto_batch_tracing=auto_batch_tracing,
        hide_inputs=is_metadata_only,
        hide_outputs=is_metadata_only,
        anonymizer=scrub_errors if is_metadata_only else None,
    )


@cache
def _client(api_key: str, *, is_metadata_only: bool) -> Client:
    """One client per key and mode, so its background batching is shared by every run."""
    return build_client(api_key, is_metadata_only=is_metadata_only)


def langsmith_tracer(settings: Settings) -> LangChainTracer | None:
    """The run's LangSmith tracer, or None when no key is set (tracing off)."""
    key = settings.langsmith_api_key
    if key is None or not key.get_secret_value():
        return None
    client = _client(key.get_secret_value(), is_metadata_only=is_metadata_only(settings))
    return LangChainTracer(project_name=settings.langsmith_project, client=client)


def tracing_switch(tracer: LangChainTracer | None) -> AbstractContextManager[object]:
    """The tracing context a run's graph runs in: with no tracer of ours, tracing is switched
    off, so no default tracer from the environment joins in. With ours, langchain-core adds no
    second tracer (it adds one only when none is present)."""
    return tracing_context(enabled=False) if tracer is None else tracing_context()
