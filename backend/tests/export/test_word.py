"""Word files (P9): every block as plain text, the logo, and the footer with the page fields."""

from io import BytesIO
from zipfile import ZipFile

from aiact.export import render_docx
from aiact.schemas import Language
from tests.export.papers import FOOTER, LONG, MARKUP, sample_paper
from tests.export.reading import read_docx


def test_every_block_is_written_as_given_in_order() -> None:
    word = read_docx(render_docx(sample_paper()))
    texts = [text for text in word.paragraphs if text]
    assert texts == [
        "DRAFT",
        "Größere Dokumentation: a test",
        "AI Act text: CELEX 02024R1689-20260727, as it applies on 7 October 2026.",
        "A simplified form is expected.",
        "The system",
        MARKUP,
        "Line one\nline two",
        "the methods and steps performed for the development",
        "Annex IV, point 2",
        "To fill in.",
        LONG,
    ]


def test_markup_is_escaped_into_the_file_never_read_as_markup() -> None:
    with ZipFile(BytesIO(render_docx(sample_paper()))) as archive:
        body = archive.read("word/document.xml").decode()
    assert "&lt;b&gt;Not bold&lt;/b&gt; **not starred** {nb} &amp;amp;" in body
    assert "<script>" not in body


def test_the_footer_holds_the_notice_and_the_page_fields() -> None:
    word = read_docx(render_docx(sample_paper()))
    assert word.footer[0] == FOOTER
    assert word.footer[1] == "Page  of "
    assert 'w:instr="PAGE"' in word.footer_xml
    assert 'w:instr="NUMPAGES"' in word.footer_xml


def test_a_german_paper_is_marked_german_and_numbers_its_pages_in_german() -> None:
    word = read_docx(render_docx(sample_paper(Language.DE)))
    assert (word.language, word.footer[1]) == ("de", "Seite  von ")
    assert word.title == "Größere Dokumentation: a test"


def test_the_flat_lockup_is_the_only_picture() -> None:
    with ZipFile(BytesIO(render_docx(sample_paper()))) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    assert len(media) == 1
    assert media[0].endswith(".png")
