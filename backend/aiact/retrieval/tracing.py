"""The lookups as LangSmith runs (V7): `get_provision`, `get_omnibus_provision` and
`search_ai_act` each become a run of their own, nested under the engine step that called them, so
tool-call correctness (`aiact.eval.tool_calls`) can read from a trace which lookups a step made.

- **Only inside a trace.** A lookup is traced only while a traced run is current (the engine's
  run, `aiact.engine.tracing`), and then through that run's client: metadata only outside
  development. Called from the API, the MCP server or a script, it is the plain function, so
  `LANGSMITH_TRACING` in the environment never traces a lookup on its own.
- **What the check reads is metadata.** The provision id looked up, or the documents and document
  types a search was limited to, go into the run's metadata, which a metadata-only trace keeps.
  The search query (the description) never does: it is an input, and the engine's client hides
  inputs outside development.
- **What a search found, in benchmark runs only.** Inside `benchmark_run()` (the benchmark's
  engine classifier enters it per case), a search's run also records the provision ids it
  returned (`HIT_IDS`), corpus ids only, so the gap run (V8) can show from its traces that a
  held-out example was retrieved, and the reported run that none was. A real user's
  classification (API, MCP) never records them.
- **Recorded only once resolved.** The metadata is set when the lookup returns. A provision id
  can come from a model (the citation validator looks up whatever a step cited), so an id that
  resolved nowhere could carry the description's words: a failed lookup records no id, only its
  name and its error (cut down to the exception type outside development). A recorded id is
  therefore always a corpus id; the id length cap (`MAX_PROVISION_ID_CHARS`) is enforced where
  ids come in, at the API and MCP boundaries.
- **No handles.** The connection and the embedder are dropped from the inputs: a connection's
  text names its host and user.
"""

import inspect
from collections.abc import Callable, Collection, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

PROVISION_ID = "lookup_provision_id"
"""Metadata: the provision id a `get_provision` or `get_omnibus_provision` run looked up."""
DOC_KEYS = "lookup_doc_keys"
"""Metadata: the manifest keys a `search_ai_act` run was limited to (absent: every document)."""
DOC_TYPES = "lookup_doc_types"
"""Metadata: the document types a `search_ai_act` run was limited to (absent: every type)."""
HIT_IDS = "lookup_hit_ids"
"""Metadata: the provision ids a `search_ai_act` run returned, in rank order."""

HANDLES = frozenset({"connection", "embedder"})
"""Arguments that are objects, not values: never part of a run's inputs."""

RUN_TYPE = "tool"

_IN_BENCHMARK_RUN: ContextVar[bool] = ContextVar("aiact_in_benchmark_run", default=False)
"""Set by `benchmark_run()`; the engine's node threads inherit it, as they inherit the trace."""

MetadataOf = Callable[[Mapping[str, object]], Mapping[str, object]]


def provision_metadata(inputs: Mapping[str, object]) -> Mapping[str, object]:
    """A provision lookup's metadata: the id looked up."""
    provision_id = inputs.get("provision_id")
    if not isinstance(provision_id, str):
        return {}
    return {PROVISION_ID: provision_id}


def search_metadata(inputs: Mapping[str, object]) -> Mapping[str, object]:
    """A search's metadata: the documents and types it was limited to (never the query)."""
    return {DOC_KEYS: _names(inputs.get("doc_keys")), DOC_TYPES: _names(inputs.get("doc_types"))}


def _names(value: object) -> list[str] | None:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Collection):
        return sorted(str(item) for item in value)
    return None


@contextmanager
def benchmark_run() -> Iterator[None]:
    """Mark the lookups made inside as a benchmark run's: only they record what they returned."""
    token = _IN_BENCHMARK_RUN.set(True)
    try:
        yield
    finally:
        _IN_BENCHMARK_RUN.reset(token)


def is_benchmark_run() -> bool:
    return _IN_BENCHMARK_RUN.get()


def _without_handles(inputs: dict[str, object]) -> dict[str, object]:
    return {name: value for name, value in inputs.items() if name not in HANDLES}


def traced_lookup[**P, R](
    metadata_of: MetadataOf, result_metadata_of: Callable[[R], Mapping[str, object]] | None = None
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """A lookup traced as a run under the current trace, with `metadata_of(inputs)` (and, in a
    benchmark run, `result_metadata_of(result)` when given) set as its metadata once it returns;
    with no current trace, the plain lookup."""

    def decorate(lookup: Callable[P, R]) -> Callable[P, R]:
        signature = inspect.signature(lookup)

        @wraps(lookup)
        def recorded(*args: P.args, **kwargs: P.kwargs) -> R:
            result = lookup(*args, **kwargs)
            run = get_current_run_tree()  # the lookup's own run, inside `traceable`
            if run is not None:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                found = result_metadata_of if is_benchmark_run() else None
                metadata = {**metadata_of(bound.arguments), **(found(result) if found else {})}
                run.add_metadata({k: v for k, v in metadata.items() if v is not None})
            return result

        traced = traceable(run_type=RUN_TYPE, process_inputs=_without_handles)(recorded)

        @wraps(lookup)
        def call(*args: P.args, **kwargs: P.kwargs) -> R:
            if get_current_run_tree() is None:
                return lookup(*args, **kwargs)
            return traced(*args, **kwargs)

        return call

    return decorate
