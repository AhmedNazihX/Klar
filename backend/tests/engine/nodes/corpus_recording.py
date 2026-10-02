"""Record and replay the corpus calls of a replayed engine node (E3, E4, E5).

A node's replay test replays the model reply from its cassette (`<test>.yaml`, pytest-recording)
and the corpus answers from the `<test>.corpus.json` next to it, so the replay needs neither the
database nor the embeddings. Each corpus call is keyed by what it asked (the call's name, its
arguments and the run's `Lookup`):
- while recording, every call goes to the live corpus and its answer is kept under its key;
- while replaying, a call is served from its key; a call the recording never saw (a changed
  query, filter or exclusion) fails the test, and recorded calls a replay doesn't make are
  ignored.

Each node test wraps a `CorpusRecording` in a small library with the node's own protocol, and
gets one from `corpus_recording`, which skips the test while nothing is recorded.
"""

import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict
from pathlib import Path

import pytest

from aiact.engine.nodes.common import Lookup
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.retrieval.search import SearchHit

CORPUS_SUFFIX = ".corpus.json"
NOT_FOUND = "not_found"
"""The entry of a lookup the corpus had no text for; the replay raises it again."""


def lookup_call(lookup: Lookup) -> dict[str, object]:
    """The run's lookup as part of a call's key."""
    return {**asdict(lookup), "exclude_source_example_ids": list(lookup.exclude_source_example_ids)}


def _key(call: Mapping[str, object]) -> str:
    return json.dumps(call, sort_keys=True, default=str)


def _dumped(result: object) -> object:
    if isinstance(result, tuple | list):
        return [_dumped(item) for item in result]
    assert isinstance(result, SearchHit | Provision)
    return result.model_dump(mode="json")


class CorpusRecording[S]:
    """The corpus answers of one replay: asked of `live` (a node's corpus library) and kept
    while recording, read from `path` while replaying (`live` is None)."""

    def __init__(self, path: Path, live: S | None) -> None:
        self._path = path
        self._live = live
        self._entries: dict[str, object] = (
            {} if live is not None else json.loads(path.read_text(encoding="utf-8"))
        )

    def _answer(self, call: Mapping[str, object], ask: Callable[[S], object]) -> object:
        key = _key(call)
        if self._live is not None:
            try:
                result = ask(self._live)
            except ProvisionNotFoundError:
                self._entries[key] = {NOT_FOUND: True}
                raise
            self._entries[key] = _dumped(result)
            return result
        if key not in self._entries:
            pytest.fail(f"no recorded corpus answer for {key}; record the replay again")
        entry = self._entries[key]
        if isinstance(entry, dict) and entry.get(NOT_FOUND):
            raise ProvisionNotFoundError(f"recorded as not found: {key}")
        return entry

    def provision(
        self, provision_id: str, lookup: Lookup, ask: Callable[[S], Provision]
    ) -> Provision:
        """`get_provision`'s answer for `provision_id`, keyed by the id and the lookup."""
        call = {"lookup": provision_id, **lookup_call(lookup)}
        return Provision.model_validate(self._answer(call, ask))

    def hits(
        self, call: Mapping[str, object], ask: Callable[[S], Sequence[SearchHit]]
    ) -> tuple[SearchHit, ...]:
        """A search's hits, keyed by `call` (the search's name and arguments, and the lookup)."""
        found = self._answer(call, ask)
        assert isinstance(found, tuple | list)
        return tuple(SearchHit.model_validate(hit) for hit in found)

    def save(self) -> None:
        """Write what was recorded; a replay writes nothing."""
        if self._live is None:
            return
        text = json.dumps(self._entries, indent=1, sort_keys=True, ensure_ascii=False)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(text + "\n", encoding="utf-8")


@contextmanager
def corpus_recording[S](
    cassette_dir: str,
    cassette_name: str,
    record_mode: str,
    record_command: str,
    live: Callable[[], AbstractContextManager[S]],
) -> Iterator[CorpusRecording[S]]:
    """The test's `CorpusRecording`: replayed from `<cassette_name>.corpus.json` in record mode
    `none` (the test is skipped while it or the cassette is missing), recorded from `live()`
    otherwise and saved when the test ends, whether it passed or not."""
    cassette = Path(cassette_dir) / f"{cassette_name}.yaml"
    corpus = cassette.with_name(f"{cassette_name}{CORPUS_SUFFIX}")
    if record_mode == "none":
        if not (cassette.exists() and corpus.exists()):
            pytest.skip(f"{cassette_name} has no recording yet; record it with `{record_command}`")
        yield CorpusRecording(corpus, None)
        return
    with live() as source:
        recording = CorpusRecording(corpus, source)
        try:
            yield recording
        finally:
            recording.save()
