"""The frontend's prohibited-result fixture (P21) still matches the backend.

`frontend/src/test/fixtures/prohibited.json` holds what the prohibited result screen reads: the
recorded prohibited result (`recorded_prohibited_result`, own-c-08 decided under Art. 5(1)(f)),
the vendor message `POST /documents/vendor-letter` drafts from it in English and German, and the
`GET /provisions/{id}` answers for the deciding point and Art. 99(3) and 99(6) in both languages,
at the result's law version and date. Replay only: no model, database or network (the corpus is
the one built from `data/parsed/`).

When the engine, the drafter or the corpus changes on purpose, rewrite the fixture with
`AIACT_WRITE_FRONTEND_FIXTURES=1 uv run pytest tests/drafting/test_frontend_prohibited_fixture.py`
and commit it with the change.
"""

import json
import os
from pathlib import Path

import pytest

from aiact.api.documents import VendorLetter
from aiact.schemas import ClassificationResult, Language, LawVersion, RiskClass, Status
from aiact.settings import Settings
from tests.drafting.recorded_results import (
    PROHIBITED_CASSETTE,
    PROHIBITED_DIR,
    recorded_prohibited_result,
)
from tests.drafting.vendor_builders import letter, letter_checks
from tests.engine.built_corpus import built_corpus

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "test"
    / "fixtures"
    / "prohibited.json"
)
WRITE_FLAG = "AIACT_WRITE_FRONTEND_FIXTURES"
PROVISIONS = ("art:5:1:f", "art:99:3", "art:99:6")
"""The deciding point and the two paragraphs the fine tile quotes."""


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


def _provisions(result: ClassificationResult) -> dict[str, dict[str, object]]:
    """Each provision as `GET /provisions/{id}` answers it, by id and language."""
    as_of = result.as_of if result.law_version is LawVersion.AMENDED else None
    corpus = built_corpus()
    return {
        pid: {
            language.value: corpus.provision(pid, language, result.law_version, as_of).model_dump(
                mode="json"
            )
            for language in Language
        }
        for pid in PROVISIONS
    }


def _letters(result: ClassificationResult) -> dict[str, object]:
    """The vendor message as the route answers it, with no answers given, by language."""
    letters: dict[str, object] = {}
    for language in Language:
        document = letter(result, {}, language)
        checks = letter_checks(document, result, {})
        letters[language.value] = VendorLetter(document=document, checks=checks).model_dump(
            mode="json"
        )
    return letters


@pytest.mark.vcr
@pytest.mark.parametrize(
    ("vcr_cassette_dir", "default_cassette_name"),
    [(PROHIBITED_DIR, PROHIBITED_CASSETTE)],
    indirect=True,
)
def test_the_frontend_prohibited_fixture_matches_the_backend(
    vcr_cassette_dir: str, default_cassette_name: str, replay_settings: Settings, record_mode: str
) -> None:
    """Replays `default_cassette_name` from `vcr_cassette_dir`."""
    result = recorded_prohibited_result(replay_settings, record_mode)
    assert (result.risk_class, result.status) == (RiskClass.PROHIBITED, Status.DECIDED)
    expected = {
        "result": result.model_dump(mode="json"),
        "letters": _letters(result),
        "provisions": _provisions(result),
    }
    if os.environ.get(WRITE_FLAG) == "1":
        FIXTURE.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
    stored = json.loads(FIXTURE.read_text())
    assert stored == expected, f"{FIXTURE.name} is stale: rewrite it with {WRITE_FLAG}=1"
