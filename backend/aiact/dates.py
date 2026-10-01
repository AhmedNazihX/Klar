"""Month names and long dates as the AI Act writes them, in English and German.

Shared by the corpus parser (C1, reading dates out of the Omnibus) and the engine's texts (C7b,
writing them), so neither imports the other. Keyed by language code: `aiact.schemas.Language`
values and the corpus's language literals are both these strings.
"""

from collections.abc import Mapping
from datetime import date

EN_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August")
EN_MONTHS += ("September", "October", "November", "December")
DE_MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August")
DE_MONTHS += ("September", "Oktober", "November", "Dezember")

MONTHS: Mapping[str, tuple[str, ...]] = {"en": EN_MONTHS, "de": DE_MONTHS}


def long_date(day: date, language: str) -> str:
    """`day` as the Act writes it: "2 December 2027" (en), "2. Dezember 2027" (de). Raises
    KeyError for a language without month names."""
    month = MONTHS[language][day.month - 1]
    separator = ". " if language == "de" else " "
    return f"{day.day}{separator}{month} {day.year}"
