"""The frontend's ambiguous-result fixture (P22) still matches the backend.

`frontend/src/test/fixtures/ambiguous.json` holds what the ambiguous result screen reads: the
recorded legally ambiguous result (`recorded_ambiguous_result`, own-e-09, whose Annex I
safety-component question the law leaves open) and the request `POST /documents/vendor-letter`
drafts from it in English and German with the tool's name the screen sends (`TOOL_ANSWERS`).
Replay only: no model, database or network (the corpus is the one built from `data/parsed/`).

When the engine, the drafter or the corpus changes on purpose, rewrite the fixture with
`AIACT_WRITE_FRONTEND_FIXTURES=1 uv run pytest tests/drafting/test_frontend_ambiguous_fixture.py`
and commit it with the change.
"""

import json
import os
from pathlib import Path

import pytest

from aiact.api.documents import VendorLetter
from aiact.schemas import ClassificationResult, Language, Status
from aiact.settings import Settings
from tests.drafting.recorded_results import (
    AMBIGUOUS_CASSETTE,
    AMBIGUOUS_DIR,
    recorded_ambiguous_result,
)
from tests.drafting.vendor_builders import letter, letter_checks

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "test"
    / "fixtures"
    / "ambiguous.json"
)
WRITE_FLAG = "AIACT_WRITE_FRONTEND_FIXTURES"
TOOL_ANSWERS = {"tool_name": "Ropeway wear forecast"}
"""What the screen answers for the letter: the tool's name in the frontend tests' inventory
(`ResultScreen.ambiguous.test.tsx`). The recipient and the sender stay to fill in."""


@pytest.fixture
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def default_cassette_name(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def replay_settings(openrouter_settings: Settings, record_mode: str) -> Settings:
    if record_mode != "none":
        pytest.skip("replay only: record the node tests' replays instead")
    return openrouter_settings


def _letters(result: ClassificationResult) -> dict[str, object]:
    """The request as the route answers it, given the tool's name, by language."""
    letters: dict[str, object] = {}
    for language in Language:
        document = letter(result, TOOL_ANSWERS, language)
        checks = letter_checks(document, result, TOOL_ANSWERS)
        letters[language.value] = VendorLetter(document=document, checks=checks).model_dump(
            mode="json"
        )
    return letters


@pytest.mark.vcr
@pytest.mark.parametrize(
    ("vcr_cassette_dir", "default_cassette_name"),
    [(AMBIGUOUS_DIR, AMBIGUOUS_CASSETTE)],
    indirect=True,
)
def test_the_frontend_ambiguous_fixture_matches_the_backend(
    vcr_cassette_dir: str, default_cassette_name: str, replay_settings: Settings, record_mode: str
) -> None:
    """Replays `default_cassette_name` from `vcr_cassette_dir`."""
    result = recorded_ambiguous_result(replay_settings, record_mode)
    assert result.status is Status.LEGALLY_AMBIGUOUS
    expected = {"result": result.model_dump(mode="json"), "letters": _letters(result)}
    if os.environ.get(WRITE_FLAG) == "1":
        FIXTURE.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
    stored = json.loads(FIXTURE.read_text())
    assert stored == expected, f"{FIXTURE.name} is stale: rewrite it with {WRITE_FLAG}=1"
