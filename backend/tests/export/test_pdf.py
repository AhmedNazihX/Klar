"""PDF files (P9): every block as plain text, the fonts embedded, the footer and page line on
every page."""

from io import BytesIO
from typing import cast

from pypdf import PdfReader
from pypdf.generic import DictionaryObject

from aiact.export import render_pdf
from aiact.schemas import Language
from tests.export.papers import FOOTER, MARKUP, sample_paper
from tests.export.reading import one_line, pdf_pages


def test_every_block_is_written_as_given() -> None:
    first = pdf_pages(render_pdf(sample_paper()))[0]
    for text in (
        "DRAFT",
        "Größere Dokumentation: a test",
        "AI Act text: CELEX 02024R1689-20260727, as it applies on 7 October 2026.",
        "A simplified form is expected.",
        "The system",
        "the methods and steps performed for the development",
        "Annex IV, point 2",
        "To fill in.",
    ):
        assert text in first


def test_markup_in_a_text_stays_text() -> None:
    first = pdf_pages(render_pdf(sample_paper()))[0]
    assert one_line(MARKUP) in first
    assert "{nb}" in first, "fpdf2's default page-count alias is never filled into the text"


def test_unprintable_characters_are_left_out_and_line_breaks_kept() -> None:
    first = pdf_pages(render_pdf(sample_paper()))[0]
    assert "Line one line two" in first
    assert "\x07" not in first


def test_every_page_carries_the_footer_and_its_number() -> None:
    pages = pdf_pages(render_pdf(sample_paper(paragraphs=12)))
    assert len(pages) >= 2
    for number, page in enumerate(pages, start=1):
        assert FOOTER in page
        assert f"Page {number} of {len(pages)}" in page


def test_a_german_paper_numbers_its_pages_in_german() -> None:
    pages = pdf_pages(render_pdf(sample_paper(Language.DE)))
    assert f"Seite 1 von {len(pages)}" in pages[0]


def test_the_fonts_are_embedded_and_the_logo_drawn() -> None:
    reader = PdfReader(BytesIO(render_pdf(sample_paper())))
    resources = cast(DictionaryObject, reader.pages[0]["/Resources"])
    font_list = cast(DictionaryObject, resources["/Font"])
    fonts = {str(font.get_object()["/BaseFont"]) for font in font_list.values()}
    assert any("Newsreader" in name for name in fonts)
    assert any("Geist" in name for name in fonts)
    assert len(cast(DictionaryObject, resources["/XObject"])) == 1, "the flat lockup"
    assert reader.metadata is not None
    assert reader.metadata.title == "Größere Dokumentation: a test"
