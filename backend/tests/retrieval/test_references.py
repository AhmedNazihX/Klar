"""Exact references read from a search query (X1b), in English and German."""

import pytest

from aiact.retrieval.references import exact_references


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Article 50", ("art:50",)),
        ("What does Article 5(1)(f) prohibit?", ("art:5:1:f",)),
        ("Art. 6(3)", ("art:6:3",)),
        ("Art. 4a", ("art:4a",)),
        ("Articles 50 and 52", ("art:50",)),
        ("Annex III point 5(b)", ("annex:III:5:b",)),
        ("Annex I, Section A, point 11", ("annex:I:A:11",)),
        ("recital 27", ("recital:27",)),
    ],
)
def test_english_references_become_provision_ids(query: str, ids: tuple[str, ...]) -> None:
    assert exact_references(query) == ids


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Artikel 50", ("art:50",)),
        ("Was verlangt Artikel 26 Absatz 2?", ("art:26:2",)),
        ("Art. 5 Abs. 1 Buchst. f", ("art:5:1:f",)),
        ("Artikel 43 Absatz 1 Unterabsatz 2 Buchstabe a", ("art:43:1",)),
        ("Anhang III Nummer 4", ("annex:III:4",)),
        ("Anhang III Nr. 5 Buchstabe b", ("annex:III:5:b",)),
        ("Erwägungsgrund 27", ("recital:27",)),
    ],
)
def test_german_references_become_provision_ids(query: str, ids: tuple[str, ...]) -> None:
    assert exact_references(query) == ids


@pytest.mark.parametrize(
    "query",
    ["Annex III", "Is our Annex III system high-risk?", "Hochrisiko-Systeme nach Anhang III"],
)
def test_a_whole_annex_is_no_reference(query: str) -> None:
    assert exact_references(query) == ()


@pytest.mark.parametrize(
    "query", ["tell me a joke", "state of the art 5", "emotion recognition in the workplace"]
)
def test_a_query_without_references_names_none(query: str) -> None:
    assert exact_references(query) == ()


def test_references_keep_the_order_named_and_appear_once() -> None:
    query = "Annex III point 4(a), Article 6(3) and again Annex III point 4(a)"
    assert exact_references(query) == ("annex:III:4:a", "art:6:3")


@pytest.mark.parametrize(
    "query",
    [
        "Article 22 GDPR",
        "Article 22(1) GDPR",
        "GDPR Article 22",
        "Article 101 TFEU",
        "Article 21 of the Charter",
        "Article 6 of Regulation (EU) 2016/679",
        "Article 10 of the General Data Protection Regulation",
        "Article 4 of Directive 2001/95/EC",
        "recital 71 GDPR",
        "Annex II point 1 of Regulation (EU) 2017/745",
    ],
)
def test_an_english_reference_to_another_act_is_no_reference(query: str) -> None:
    assert exact_references(query) == ()


@pytest.mark.parametrize(
    "query",
    [
        "Art. 17 DSGVO",
        "Art. 22 DS-GVO",
        "Art. 5 Abs. 1 lit. a DSGVO",
        "DSGVO Art. 9",
        "Artikel 101 AEUV",
        "Artikel 9 der Datenschutz-Grundverordnung",
        "Artikel 6 der Verordnung (EU) 2016/679",
        "Artikel 10 der Richtlinie (EU) 2016/680",
        "Erwägungsgrund 71 DSGVO",
    ],
)
def test_a_german_reference_to_another_act_is_no_reference(query: str) -> None:
    assert exact_references(query) == ()


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Article 22(1) GDPR and Article 50", ("art:50",)),
        ("Does Article 50 apply under the GDPR too?", ("art:50",)),
        ("Article 6 of Regulation (EU) 2024/1689", ("art:6",)),
        ("Artikel 6 der Verordnung (EU) 2024/1689", ("art:6",)),
        ("Art. 17 DSGVO und Artikel 26 Absatz 2", ("art:26:2",)),
    ],
)
def test_only_the_reference_next_to_another_act_is_skipped(
    query: str, ids: tuple[str, ...]
) -> None:
    assert exact_references(query) == ids
