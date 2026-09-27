import pytest
from pydantic import ValidationError

from aiact.schemas import DISCLAIMER, DISCLAIMER_DE, DISCLAIMER_EN, Language, OpenQuestion
from aiact.schemas.evidence import SourceSpan


def test_open_question_needs_exactly_two_readings() -> None:
    with pytest.raises(ValidationError):
        OpenQuestion.model_validate({"question": "Profiling?", "readings": ["Yes"]})
    with pytest.raises(ValidationError):
        OpenQuestion.model_validate({"question": "Profiling?", "readings": ["Yes", "No", "Maybe"]})


def test_source_span_end_must_follow_start() -> None:
    with pytest.raises(ValidationError, match="greater than start"):
        SourceSpan(start=5, end=5)


def test_disclaimer_exists_per_language() -> None:
    assert DISCLAIMER[Language.EN] == DISCLAIMER_EN
    assert DISCLAIMER[Language.DE] == DISCLAIMER_DE
    assert set(DISCLAIMER) == set(Language)
    assert "not legal advice" in DISCLAIMER_EN
    assert "keine Rechtsberatung" in DISCLAIMER_DE
