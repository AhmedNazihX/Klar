"""Text as a file can hold it (P9): nothing changes but line breaks and unprintable characters."""

import pytest

from aiact.export.text import printable


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("Größe, „Zitat“ \u2013 42 €", "Größe, „Zitat“ \u2013 42 €"),
        ("<b>bold</b> **star** {nb} &amp;", "<b>bold</b> **star** {nb} &amp;"),
        ("one\r\ntwo\rthree\nfour\tfive", "one\ntwo\nthree\nfour\tfive"),
        ("bell\x07 null\x00 escape\x1b delete\x7f", "bell null escape delete"),
        ("lone \ud800 surrogate \uffff", "lone  surrogate "),
    ],
)
def test_only_unprintable_characters_and_line_breaks_change(text: str, kept: str) -> None:
    assert printable(text) == kept
