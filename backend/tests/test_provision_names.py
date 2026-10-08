"""How results and drafts name provisions (moved out of the engine's texts unchanged)."""

import pytest

from aiact.provision_names import annex_point_name, article_provision_name, provision_name
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
        ("art:9", EN, "Art. 9"),
        ("art:9", DE, "Art. 9"),
        ("art:16:a", EN, "Art. 16(a)"),
        ("art:16:a", DE, "Art. 16 Buchst. a"),
        ("art:113:c:i", EN, "Art. 113(c)(i)"),
        ("art:113:c:i", DE, "Art. 113 Buchst. c Ziff. i"),
        # An empty paragraph segment is named as before the article-point branch, not an error.
        ("art:5:", EN, "Art. 5()"),
        ("art:5:", DE, "Art. 5 Abs. "),
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


@pytest.mark.parametrize(
    ("provision", "language", "name"),
    [
        ("annex:IV", EN, "Annex IV"),
        ("annex:IV", DE, "Anhang IV"),
        ("annex:IV:2", EN, "Annex IV 2"),
        ("annex:IV:2", DE, "Anhang IV Nr. 2"),
        ("annex:III:4:a", EN, "Annex III 4(a)"),
        ("annex:III:4:a", DE, "Anhang III Nr. 4 Buchst. a"),
        ("annex:I:A:11", EN, "Annex I Section A point 11"),
        ("annex:I:A:11", DE, "Anhang I Abschnitt A Nr. 11"),
        ("art:9:2", EN, "Art. 9(2)"),
        ("art:9:2", DE, "Art. 9 Abs. 2"),
    ],
)
def test_provision_names_as_the_screens_write_them(
    provision: str, language: Language, name: str
) -> None:
    """The frontend's `provisionName` wording, so a file names a requirement as the screen does."""
    assert provision_name(provision, language) == name
