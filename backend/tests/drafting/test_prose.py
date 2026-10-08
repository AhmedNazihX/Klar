"""A skeleton's answers written up as sentences (P9): no word added, changed or moved."""

import pytest

from aiact.drafting.prose import write_up


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
