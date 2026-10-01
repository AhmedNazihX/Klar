"""Long dates as the Act writes them, shared by the corpus parser and the engine texts."""

from datetime import date

import pytest

from aiact.dates import DE_MONTHS, EN_MONTHS, long_date
from aiact.schemas import Language


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (Language.EN, "2 December 2027"),
        (Language.DE, "2. Dezember 2027"),
        ("de", "2. Dezember 2027"),
    ],
)
def test_long_date_in_each_language(language: str, expected: str) -> None:
    assert long_date(date(2027, 12, 2), language) == expected


def test_twelve_months_each() -> None:
    assert len(EN_MONTHS) == len(DE_MONTHS) == 12
    assert long_date(date(2030, 3, 1), Language.DE) == "1. März 2030"
