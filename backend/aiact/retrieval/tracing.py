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
- **No handles.** The connection and the embedder are dropped from the inputs: a connection's
  text names its host and user.
"""

import inspect
from collections.abc import Callable, Collection, Mapping
from functools import wraps

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

PROVISION_ID = "lookup_provision_id"
"""Metadata: the provision id a `get_provision` or `get_omnibus_provision` run looked up."""
DOC_KEYS = "lookup_doc_keys"
"""Metadata: the manifest keys a `search_ai_act` run was limited to (absent: every document)."""
DOC_TYPES = "lookup_doc_types"
"""Metadata: the document types a `search_ai_act` run was limited to (absent: every type)."""

HANDLES = frozenset({"connection", "embedder"})
"""Arguments that are objects, not values: never part of a run's inputs."""

RUN_TYPE = "tool"

MetadataOf = Callable[[Mapping[str, object]], Mapping[str, object]]


def provision_metadata(inputs: Mapping[str, object]) -> Mapping[str, object]:
    """A provision lookup's metadata: the id looked up."""
    return {PROVISION_ID: inputs.get("provision_id")}


def search_metadata(inputs: Mapping[str, object]) -> Mapping[str, object]:
    """A search's metadata: the documents and types it was limited to (never the query)."""
    return {DOC_KEYS: _names(inputs.get("doc_keys")), DOC_TYPES: _names(inputs.get("doc_types"))}


def _names(value: object) -> list[str] | None:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Collection):
        return sorted(str(item) for item in value)
    return None


def _without_handles(inputs: dict[str, object]) -> dict[str, object]:
    return {name: value for name, value in inputs.items() if name not in HANDLES}


def traced_lookup[**P, R](metadata_of: MetadataOf) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """A lookup traced as a run under the current trace, with `metadata_of(inputs)` as metadata;
    with no current trace, the plain lookup."""

    def decorate(lookup: Callable[P, R]) -> Callable[P, R]:
        traced = traceable(run_type=RUN_TYPE, process_inputs=_without_handles)(lookup)
        signature = inspect.signature(lookup)

        @wraps(lookup)
        def call(*args: P.args, **kwargs: P.kwargs) -> R:
            if get_current_run_tree() is None:
                return lookup(*args, **kwargs)
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            metadata = {k: v for k, v in metadata_of(bound.arguments).items() if v is not None}
            return traced(*args, langsmith_extra={"metadata": metadata}, **kwargs)

        return call

    return decorate
