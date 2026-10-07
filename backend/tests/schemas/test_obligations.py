"""`Obligation`: a duty stored before C9, without its labels and German duty, still loads."""

from datetime import date

import pytest
from pydantic import ValidationError

from aiact.schemas import ClassificationResult, Obligation
from aiact.schemas.obligations import STORED_TEXT_FIELDS
from tests.schemas.worked_example import worked_example_result

ANNEX_III_FROM = "2027-12-02"
DISTRIBUTOR_DUTY = (
    "This system can't lawfully be placed on the EU market or used (Art. 5). The Act doesn't "
    "name distributors in Art. 5, but don't supply it."
)


def _stored(article: str, duty: str) -> dict[str, object]:
    return {"duty": duty, "article": article, "applies_from": ANNEX_III_FROM}


def test_a_result_stored_before_c9_still_loads() -> None:
    """As `aiact evaluate report` re-validates a stored prediction (aiact/eval/report.py)."""
    stored = worked_example_result().model_dump(mode="json")
    for duty in stored["obligations"]:
        for field in (*STORED_TEXT_FIELDS, "group", "document"):
            del duty[field]
    result = ClassificationResult.model_validate(stored)
    logs = next(duty for duty in result.obligations if duty.article == "art:26:6")
    assert logs.label_en == "Keep the logs it creates for at least six months"
    assert (
        logs.label_de == "Die automatisch erzeugten Protokolle mindestens sechs Monate aufbewahren"
    )
    assert logs.duty_de.startswith("Die vom System automatisch erzeugten Protokolle")
    assert logs.duty == "Keep the logs the system generates"  # the stored wording stays


def test_a_shared_article_is_matched_by_its_english_duty() -> None:
    """Art. 5(1) is listed for providers and, as information, for distributors."""
    duty = Obligation.model_validate(_stored("art:5:1", DISTRIBUTOR_DUTY))
    assert duty.label_en == "Don't supply it: it can't lawfully be sold or used in the EU"


def test_a_duty_the_table_no_longer_lists_falls_back_to_its_english_text() -> None:
    """E.g. the Art. 16(a) bundle, split into Art. 9 to 15 in C9."""
    duty = Obligation.model_validate(_stored("art:16:a", "Meet the high-risk requirements."))
    assert (duty.duty_de, duty.label_en, duty.label_de) == ("Meet the high-risk requirements.",) * 3


def test_texts_that_are_present_are_kept() -> None:
    given = _stored("art:26:6", "Keep the logs.") | {"label_en": "Mine"}
    duty = Obligation.model_validate(given)
    assert duty.label_en == "Mine"
    assert (
        duty.label_de == "Die automatisch erzeugten Protokolle mindestens sechs Monate aufbewahren"
    )


def test_an_empty_label_is_still_rejected() -> None:
    with pytest.raises(ValidationError, match="label_de"):
        Obligation(
            duty="Keep the logs.",
            duty_de="Protokolle aufbewahren.",
            label_en="Keep the logs",
            label_de="",
            article="art:26:6",
            applies_from=date(2027, 12, 2),
        )
