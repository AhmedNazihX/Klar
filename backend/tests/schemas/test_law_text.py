"""The law-text label on a result (E12): CELEX number and date of the text it was checked
against, always matching its law version."""

from datetime import date

import pytest
from pydantic import ValidationError

from aiact.corpus.sources import SOURCES
from aiact.retrieval.provisions import AI_ACT_DOC_KEYS
from aiact.schemas import LAW_TEXTS, ClassificationResult, LawText, LawVersion
from tests.schemas.worked_example import worked_example_result


@pytest.mark.parametrize("law_version", list(LawVersion))
def test_each_label_is_the_text_the_corpus_fetched(law_version: LawVersion) -> None:
    label = LAW_TEXTS[law_version]
    assert label.document_id == AI_ACT_DOC_KEYS[law_version]
    fetched = {(s.celex, s.version) for s in SOURCES if s.id == label.document_id}
    assert fetched == {(label.celex, label.version_date.isoformat())}


def test_the_amended_label_is_the_consolidation_of_27_july_2026() -> None:
    assert LAW_TEXTS[LawVersion.AMENDED] == LawText(
        document_id="ai-act-consolidated",
        celex="02024R1689-20260727",
        version_date=date(2026, 7, 27),
    )


@pytest.mark.parametrize("law_version", list(LawVersion))
def test_a_result_labels_its_law_version_without_being_told(law_version: LawVersion) -> None:
    dumped = worked_example_result().model_dump(exclude={"law_text"})
    result = ClassificationResult.model_validate({**dumped, "law_version": law_version})
    assert result.law_text == LAW_TEXTS[law_version]
    assert result.model_dump(mode="json")["law_text"]["celex"] == LAW_TEXTS[law_version].celex


def test_a_label_of_the_other_text_is_rejected() -> None:
    dumped = worked_example_result().model_dump()
    original = LAW_TEXTS[LawVersion.ORIGINAL].model_dump()
    with pytest.raises(ValidationError, match="law_text must label the amended text"):
        ClassificationResult.model_validate({**dumped, "law_text": original})


def test_a_result_without_a_law_version_fails_on_it_not_on_the_label() -> None:
    dumped = worked_example_result().model_dump(exclude={"law_version", "law_text"})
    with pytest.raises(ValidationError, match="law_version"):
        ClassificationResult.model_validate(dumped)
