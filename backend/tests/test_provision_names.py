"""How results and drafts name provisions (moved out of the engine's texts unchanged)."""

import pytest

from aiact.provision_names import annex_point_name, article_provision_name
from aiact.schemas import Language

EN, DE = Language.EN, Language.DE


@pytest.mark.parametrize(
    ("provision", "language", "name"),
    [
        ("art:50:1", EN, "Art. 50(1)"),
        ("art:50:1", DE, "Art. 50 Abs. 1"),
        ("art:26:11", DE, "Art. 26 Abs. 11"),
        ("art:5:1:ba", EN, "Art. 5(1)(ba)"),
        ("art:5:1:ba", DE, "Art. 5 Abs. 1 Buchst. ba"),
        ("art:5:1:c:i", EN, "Art. 5(1)(c)(i)"),
        ("art:5:1:c:i", DE, "Art. 5 Abs. 1 Buchst. c Ziff. i"),
    ],
)
def test_article_provision_names(provision: str, language: Language, name: str) -> None:
    assert article_provision_name(provision, language) == name


@pytest.mark.parametrize(
    ("point", "language", "name"),
    [
        ("annex:III:4:a", EN, "Annex III point 4(a)"),
        ("annex:III:4:a", DE, "Anhang III Nummer 4 Buchstabe a"),
        ("annex:III:1", EN, "Annex III point 1"),
        ("annex:I:A:11", EN, "Annex I Section A point 11"),
        ("annex:I:A:11", DE, "Anhang I Abschnitt A Nummer 11"),
    ],
)
def test_annex_point_names(point: str, language: Language, name: str) -> None:
    assert annex_point_name(point, language) == name
