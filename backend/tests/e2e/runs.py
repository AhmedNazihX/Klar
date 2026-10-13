"""The classifications the end-to-end tests run (P13), and where their recordings are.

`frontend/e2e/runs.json` names each run beyond INIT's worked example in English: the exact body
the app sends for it, which the Playwright flows type in and `test_e2e_runs.py` records. One file
for both, so a recording always answers the request the browser makes. The English worked
example itself replays E10's recording (`tests/engine/test_classify_worked_example.py`), so it
needs no recording of its own.
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from aiact.engine import ClassifyRequest
from tests.conftest import RECORDINGS_DIR, TESTS_DIR
from tests.engine.nodes.corpus_recording import CORPUS_SUFFIX
from tests.engine.test_classify_worked_example import AS_OF

RUNS_FILE = TESTS_DIR.parents[1] / "frontend" / "e2e" / "runs.json"
E2E_RECORDINGS = RECORDINGS_DIR / "e2e" / "test_e2e_runs"
WORKED_EXAMPLE_RECORDING = (
    RECORDINGS_DIR / "engine" / "test_classify_worked_example" / "test_replay_worked_example"
)
RECORD_COMMAND = "uv run pytest tests/e2e/test_e2e_runs.py --record-mode=once"


@dataclass(frozen=True)
class Recording:
    """A model cassette (`<stem>.yaml`) and its corpus answers (`<stem>.corpus.json`)."""

    stem: Path

    @property
    def cassette(self) -> Path:
        return self.stem.with_suffix(".yaml")

    @property
    def corpus(self) -> Path:
        return self.stem.with_name(f"{self.stem.name}{CORPUS_SUFFIX}")

    @property
    def exists(self) -> bool:
        return self.cassette.exists() and self.corpus.exists()


def run_date() -> date:
    """The date every e2e run is classified on: the worked example's recording date, which
    `runs.json` repeats for the browser's side."""
    pinned = date.fromisoformat(json.loads(RUNS_FILE.read_text(encoding="utf-8"))["as_of"])
    if pinned != AS_OF:
        raise ValueError(f"{RUNS_FILE.name} pins {pinned}, the worked example's recording {AS_OF}")
    return pinned


def e2e_runs() -> dict[str, ClassifyRequest]:
    """Each named run of `runs.json` as the request the API receives (its date pinned)."""
    data = json.loads(RUNS_FILE.read_text(encoding="utf-8"))
    as_of = run_date()
    return {
        name: ClassifyRequest.model_validate({**body, "as_of": as_of})
        for name, body in data["runs"].items()
    }


def recording_of(name: str) -> Recording:
    return Recording(E2E_RECORDINGS / name)


def replayed_recordings() -> list[Recording]:
    """The worked example's recording, then every e2e run's that exists (the rest are pending)."""
    recorded = [recording_of(name) for name in e2e_runs() if recording_of(name).exists]
    return [Recording(WORKED_EXAMPLE_RECORDING), *recorded]
