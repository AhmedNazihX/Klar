"""The frontend's documents fixture (P9) still matches the backend drafter (P11).

`frontend/src/test/fixtures/documents.drafts.json` holds what `POST /documents/list` and
`POST /documents/draft` return for three results, dumped from the drafter
(`aiact.drafting.documents`) with no model call: the frontend's recorded worked example
(`worked-example.events.json`, a deployer), the backend tests' provider result for an SME and a
limited-risk result with the Art. 50(3) disclosure. The
Documents screen's tests read it, so German titles, questions and drafts the screen shows come
from it. Nothing regenerated it: this test fails when the drafter's texts move away from it.
Replay only: no model, database or network (the corpus is the one built from `data/parsed/`).

When the drafter changes on purpose, re-dump the sets this test names (`DRAFT_SETS`, with
`ANSWERS`) and commit the fixture with the change.
"""

import json
from pathlib import Path

import pytest

from aiact.drafting.documents import checked_draft, listed_documents
from aiact.drafting.models import SizeClass
from aiact.schemas import ClassificationResult, Language
from tests.drafting.vendor_builders import corpus_quotes

FIXTURES = Path(__file__).resolve().parents[3] / "frontend" / "src" / "test" / "fixtures"
FIXTURE = FIXTURES / "documents.drafts.json"
WORKED_EXAMPLE_EVENTS = FIXTURES / "worked-example.events.json"

ANSWERS = {
    "deployer": {"tool_and_supplier": "TalentRank, supplied by Rank GmbH."},
    "provider": {"intended_purpose": "scores drivers for bonuses"},
    "limited": {"recognises": "both"},
}
"""The answers the `en_answered` drafts were drafted with (documents-fixtures.ts names them)."""
DRAFT_SETS = [
    ("deployer", "en"),
    ("deployer", "de"),
    ("deployer", "en_answered"),
    ("provider", "en"),
    ("provider", "en_answered"),
    ("limited", "en"),
    ("limited", "de"),
    ("limited", "en_answered"),
    ("limited", "de_answered"),
]
"""Every draft set the fixture holds (the provider's German drafts aren't in it; the German
Art. 50(3) disclosure with its choice made is, P31)."""
SIZE_CLASS = {"deployer": None, "provider": SizeClass.SME, "limited": None}


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _recorded_worked_example() -> ClassificationResult:
    """The result the frontend's worked-example stream ends with."""
    events = json.loads(WORKED_EXAMPLE_EVENTS.read_text(encoding="utf-8"))
    last = events[-1]
    assert last["event"] == "result"
    return ClassificationResult.model_validate(last["result"])


def _results(fixture: dict[str, object]) -> dict[str, ClassificationResult]:
    return {
        "deployer": _recorded_worked_example(),
        "provider": ClassificationResult.model_validate(fixture["provider_result"]),
        "limited": ClassificationResult.model_validate(fixture["limited_result"]),
    }


def _section(fixture: dict[str, object], name: str) -> dict[str, object]:
    section = fixture[name]
    assert isinstance(section, dict)
    return section


@pytest.mark.parametrize("name", ["deployer", "provider", "limited"])
@pytest.mark.parametrize("language", [Language.EN, Language.DE])
def test_the_document_lists_match_the_drafter(name: str, language: Language) -> None:
    fixture = _fixture()
    result = _results(fixture)[name]
    listed = [document.model_dump(mode="json") for document in listed_documents(result, language)]
    lists = _section(fixture, name)["list"]
    assert isinstance(lists, dict)
    assert lists[language.value]["documents"] == listed


def test_the_fixture_holds_exactly_these_draft_sets() -> None:
    fixture = _fixture()
    held = [
        (name, set_name)
        for name in ("deployer", "provider", "limited")
        for set_name in _section(fixture, name)
        if set_name != "list"
    ]
    assert sorted(held) == sorted(DRAFT_SETS)


@pytest.mark.parametrize(("name", "set_name"), DRAFT_SETS)
def test_the_drafts_match_the_drafter(name: str, set_name: str) -> None:
    fixture = _fixture()
    drafts = _section(fixture, name)[set_name]
    assert isinstance(drafts, dict) and drafts
    result = _results(fixture)[name]
    language = Language(set_name.removesuffix("_answered"))
    answers = ANSWERS[name] if set_name.endswith("_answered") else {}
    for template_id, stored in drafts.items():
        drafted = checked_draft(
            template_id, result, answers, language, SIZE_CLASS[name], corpus_quotes()
        )
        assert stored == drafted.model_dump(mode="json"), template_id


def test_the_fixture_has_german_lists_and_drafts() -> None:
    """German completeness (P11): the screen's German tests read German titles and drafts."""
    fixture = _fixture()
    for name in ("deployer", "provider", "limited"):
        lists = _section(fixture, name)["list"]
        assert isinstance(lists, dict)
        assert lists["de"]["documents"], name
