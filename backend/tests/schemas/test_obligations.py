"""`Obligation`: a duty stored before C9, without its labels and German duty, still loads."""

from datetime import date

import pytest
from pydantic import ValidationError

from aiact.obligations.list import default_table, list_obligations
from aiact.schemas import (
    ClassificationResult,
    HighRiskRoute,
    Obligation,
    ObligationGroup,
    RiskClass,
    Role,
)
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
    assert (duty.group, duty.document) == (None, None)


@pytest.mark.parametrize(
    ("article", "group", "document"),
    [
        ("art:9", ObligationGroup.BUILD, "art_9_risk_management"),
        ("art:11:1", ObligationGroup.PROVE, "annex_iv_technical_documentation"),
    ],
)
def test_a_stored_provider_duty_gets_the_tables_group_and_document(
    article: str, group: ObligationGroup, document: str
) -> None:
    duty = Obligation.model_validate(_stored(article, "A duty stored before C9."))
    assert (duty.group, duty.document) == (group, document)


def test_a_stored_group_and_document_are_kept() -> None:
    given = _stored("art:9", "Run a risk management system.") | {
        "group": "after_launch",
        "document": "mine",
    }
    duty = Obligation.model_validate(given)
    assert (duty.group, duty.document) == (ObligationGroup.AFTER_LAUNCH, "mine")


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


def test_a_result_stored_before_the_key_still_loads() -> None:
    """A duty saved before P24 has no `key` (the table's key a tick is saved under)."""
    listed = list_obligations(Role.DEPLOYER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III)
    current = worked_example_result().model_copy(update={"obligations": listed.obligations})
    stored = current.model_dump(mode="json")
    assert all(duty["key"] for duty in stored["obligations"])
    for duty in stored["obligations"]:
        del duty["key"]
    result = ClassificationResult.model_validate(stored)
    assert len(result.obligations) == len(listed.obligations)
    assert {duty.key for duty in result.obligations} == {None}


@pytest.mark.parametrize("key", ["Hr-Logs", "hr_logs", "-hr", "a" * 201])
def test_a_key_that_is_not_a_table_key_is_rejected(key: str) -> None:
    with pytest.raises(ValidationError, match="key"):
        Obligation.model_validate({**_stored("art:26:6", "Keep the logs"), "key": key})


INPUT_DATA_EN = "You control the input data."
INPUT_DATA_DE = "Die Eingabedaten unterliegen Ihrer Kontrolle."


def _stored_after_c9(**fields: object) -> dict[str, object]:
    """A deployer's Art. 26(4) duty as stored between C9 and P11: texts, no German condition."""
    return _stored("art:26:4", "Make sure the input data is relevant.") | {
        "duty_de": "Eingabedaten prüfen.",
        "label_en": "Check the input data",
        "label_de": "Eingabedaten prüfen",
        "applies_if": INPUT_DATA_EN,
        **fields,
    }


def test_a_duty_stored_before_p11_gets_the_tables_german_condition() -> None:
    duty = Obligation.model_validate(_stored_after_c9())
    assert duty.applies_if_de == INPUT_DATA_DE
    assert duty.label_en == "Check the input data"  # the stored texts stay


def test_a_stored_condition_the_table_no_longer_holds_gets_no_german_twin() -> None:
    """The German would not translate the condition the duty was stored with."""
    duty = Obligation.model_validate(_stored_after_c9(applies_if="An older condition."))
    assert (duty.applies_if, duty.applies_if_de) == ("An older condition.", None)


def test_a_stored_german_condition_is_kept() -> None:
    duty = Obligation.model_validate(_stored_after_c9(applies_if_de="Meine Bedingung."))
    assert duty.applies_if_de == "Meine Bedingung."


def test_a_stored_duty_without_a_condition_gets_no_german_condition() -> None:
    duty = Obligation.model_validate(_stored("art:26:4", "Make sure the input data is relevant."))
    assert (duty.applies_if, duty.applies_if_de) == (None, None)


def test_a_stored_relief_gets_its_german_twin() -> None:
    table_entry = next(e for e in default_table().obligations if e.relief_note is not None)
    relief = {"relief_note": table_entry.relief_note}
    given = _stored(table_entry.article, table_entry.duty) | relief
    duty = Obligation.model_validate(given)
    assert duty.relief_note_de == table_entry.relief_note_de
    assert duty.relief_note_de and duty.relief_note_de.startswith("Für KMU")
