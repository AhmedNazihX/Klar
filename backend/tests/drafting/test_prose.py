"""A skeleton's answers written up as sentences (P9): no word added, changed or moved."""

import re
import sys
from pathlib import Path

import pytest

from aiact.drafting.prose import BLANK, without_blank, write_up


@pytest.mark.parametrize(
    ("answer", "written"),
    [
        ("fine-tuned an open model on our own CVs", "Fine-tuned an open model on our own CVs."),
        ("  Access control and yearly tests.  ", "Access control and yearly tests."),
        ("Is it logged?", "Is it logged?"),
        ("Recall per group!", "Recall per group!"),
        ("Three steps:", "Three steps:"),
        ("Uses ISO/IEC 42001 (draft)", "Uses ISO/IEC 42001 (draft)."),
        ('It says "stop."', 'It says "stop."'),
        ("wir prüfen „jede Woche“", "Wir prüfen „jede Woche“."),
        ("übersetzt von Hand", "Übersetzt von Hand."),
        ("ßtraße", "ßtraße."),
        ("42 test runs", "42 test runs."),
        ("iOS app for field staff", "iOS app for field staff."),
        ("eBay listings are screened", "eBay listings are screened."),
        ("pH values from the line", "pH values from the line."),
        ("iPhones only", "iPhones only."),
        ("a DPO reviews it", "A DPO reviews it."),
        ("first line\nsecond line", "First line\nsecond line."),
        ("", ""),
        (" \n ", ""),
    ],
)
def test_an_answer_is_written_up_as_a_sentence(answer: str, written: str) -> None:
    assert write_up(answer) == written


def test_only_the_first_letter_and_the_closing_full_stop_change() -> None:
    answer = "the vendor's DPO, dpo@example.com, reviews it"
    assert write_up(answer) == "The vendor's DPO, dpo@example.com, reviews it."
    assert write_up(answer)[1:-1] == answer[1:]


def test_blank_is_pythons_whitespace_and_the_byte_order_mark() -> None:
    """The one definition of blank; `interview.ts` lists the same characters."""
    whitespace = {chr(code) for code in range(sys.maxunicode + 1) if chr(code).isspace()}
    assert set(BLANK) == whitespace | {"\ufeff"}
    assert len(BLANK) == len(set(BLANK))


def test_a_blank_answer_writes_up_as_nothing_and_an_answer_loses_its_blank_space() -> None:
    assert write_up("\ufeff \x1c\x85") == ""
    assert without_blank("\ufeff both\u3000") == "both"


INTERVIEW_TS = Path(__file__).parents[3] / "frontend/src/features/documents/interview.ts"
"""Where the Documents screen counts the questions left, with its own copy of `BLANK`."""


def test_the_documents_screen_reads_blank_with_the_same_characters() -> None:
    """The screen's "Needs N answers" agrees with the drafter's unanswered count."""
    match = re.search(r"BLANK_CODE_POINTS = \[([^\]]*)\]", INTERVIEW_TS.read_text())
    assert match is not None, "interview.ts lists the blank characters as BLANK_CODE_POINTS"
    code_points = [int(point, 16) for point in match.group(1).replace(",", " ").split()]
    assert "".join(map(chr, code_points)) == BLANK
