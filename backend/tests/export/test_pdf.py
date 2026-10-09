"""PDF files (P9): every block as plain text, the fonts embedded, the footer and page line on
every page."""

import logging
from io import BytesIO
from typing import cast

import pytest
from pypdf import PdfReader
from pypdf.generic import DictionaryObject

from aiact.export import Paper, Paragraph, Table, render_docx, render_pdf
from aiact.export.pdf import SANS, KlarPdf
from aiact.export.pool import RenderTooLong
from aiact.export.text import printable
from aiact.schemas import Language
from tests.export.papers import FOOTER, MARKUP, report_paper, sample_paper
from tests.export.reading import one_line, pdf_pages, read_docx

A4_WIDTH_PT = 595.28
RIGHT_MARGIN_PT = A4_WIDTH_PT - 20.0 * 72 / 25.4
"""Where the text ends on the right: A4's width less the 20 mm margin, in points."""


def test_every_block_is_written_as_given() -> None:
    first = pdf_pages(render_pdf(sample_paper()))[0]
    for text in (
        "DRAFT",
        "Größere Dokumentation: a test",
        "AI Act text: CELEX 02024R1689-20260727, as it applies on 7 October 2026.",
        "A simplified form is expected.",
        "The system",
        "the methods and steps performed for the development",
        "Annex IV 2",
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


def test_a_character_no_font_can_draw_shows_as_a_question_mark_and_only_its_count_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    paper = Paper(
        language=Language.EN,
        title="Undrawable",
        blocks=(Paragraph("Ship it \U0001f600 to Łódź 漢"),),
        footer=FOOTER,
    )
    with caplog.at_level(logging.DEBUG):
        page = pdf_pages(render_pdf(paper))[0]
    assert "Ship it ? to Łódź ?" in page
    assert "PDF: 2 characters no font can draw shown as ?" in caplog.text
    assert "\U0001f600" not in caplog.text
    assert "漢" not in caplog.text


def test_the_users_own_question_marks_are_not_counted_as_undrawable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    paper = Paper(
        language=Language.EN, title="Asked", blocks=(Paragraph("Why? \U0001f600"),), footer=FOOTER
    )
    with caplog.at_level(logging.DEBUG):
        page = pdf_pages(render_pdf(paper))[0]
    assert "Why? ?" in page
    assert "PDF: 1 characters no font can draw shown as ?" in caplog.text


def _page_lines(data: bytes) -> list[tuple[str, float]]:
    """Each page's "Page N of M" line and the x, in points, where it starts."""
    lines: list[tuple[str, float]] = []
    for page in PdfReader(BytesIO(data)).pages:

        def visit(text: str, _cm: object, tm: list[float], _font: object, _size: object) -> None:
            if text.startswith("Page "):
                lines.append((text, tm[4]))

        page.extract_text(visitor_text=visit)
    return lines


def test_the_page_line_ends_at_the_right_margin_on_every_page() -> None:
    lines = _page_lines(render_pdf(sample_paper(paragraphs=12)))
    measure = KlarPdf("", "")
    measure.set_font(SANS, "", 8)
    assert [text for text, _ in lines] == [f"Page {n} of {len(lines)}" for n in (1, 2, 3, 4)]
    for text, start in lines:
        # A cell keeps its text `c_margin` (1 mm) inside its edge.
        end = start + (measure.get_string_width(text) + measure.c_margin) * 72 / 25.4
        assert abs(end - RIGHT_MARGIN_PT) < 0.5, (text, start, end)


INVISIBLE_AND_SPACES = "z.\u202fB. Soft\u00adhyphen \ufeffBOM zero\u200bwidth thin\u2009space"


def test_invisible_characters_and_spaces_the_fonts_lack_never_print_as_question_marks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    paper = Paper(
        language=Language.DE,
        title="Hinweis",
        blocks=(Paragraph(INVISIBLE_AND_SPACES), Paragraph("non\u2011breaking")),
        footer=FOOTER,
    )
    with caplog.at_level(logging.WARNING):
        page = pdf_pages(render_pdf(paper))[0]
    assert "z. B. Softhyphen BOM zerowidth thin space" in page
    assert "non-breaking" in page
    assert "?" not in page
    assert "characters no font can draw" not in caplog.text


def test_the_pdf_alone_replaces_what_its_fonts_cannot_draw() -> None:
    """`printable`, which both formats share, keeps every visible and invisible character; only
    the PDF's own step draws them its way, so the Word file keeps them as the user wrote them."""
    text = f"{INVISIBLE_AND_SPACES} \U0001f600"
    assert printable(text) == text
    paper = Paper(language=Language.EN, title="T", blocks=(Paragraph(text),), footer=FOOTER)
    assert text in read_docx(render_docx(paper)).paragraphs
    assert "zerowidth thin space ?" in pdf_pages(render_pdf(paper))[0]


def test_the_reports_blocks_are_drawn_as_given_and_the_page_break_starts_a_page() -> None:
    first, second = pdf_pages(render_pdf(report_paper()))
    for text in (
        "Classification report · Report KR-0000ABCD Applicant screening",
        "Class Status High-risk Decided",
        f"Facts Fact Source {one_line(MARKUP)} Stated by the user",
    ):
        assert text in first, text
    assert "Duties" not in first
    assert (
        "Duties Points for legal review. For the reviewer Reviewed by Date Not legal advice."
        in second
    )
    for number, page in enumerate((first, second), start=1):
        assert FOOTER in page
        assert f"Page {number} of 2" in page


def test_a_table_cell_draws_what_no_font_can_as_a_question_mark(
    caplog: pytest.LogCaptureFixture,
) -> None:
    paper = Paper(
        language=Language.EN,
        title="Cells",
        blocks=(Table(("Fact",), (("Ship it \U0001f600",),), (1.0,)),),
        footer=FOOTER,
    )
    with caplog.at_level(logging.DEBUG):
        page = pdf_pages(render_pdf(paper))[0]
    assert "Ship it ?" in page
    assert "PDF: 1 characters no font can draw shown as ?" in caplog.text


def _one_cell(text: str, header: str = "Duties apply from") -> Paper:
    table = Table((header,), ((text,),), (1.0,))
    return Paper(language=Language.EN, title="Cells", blocks=(table,), footer=FOOTER)


def test_a_cell_as_tall_as_a_page_moves_to_a_page_of_its_own() -> None:
    pages = pdf_pages(render_pdf(_one_cell("a\n" * 59 + "a")))
    assert pages[-1].count("a") >= 60


def test_a_cell_taller_than_a_page_is_too_long() -> None:
    """fpdf2 can't break a row across pages: its error is raised as `RenderTooLong`."""
    with pytest.raises(RenderTooLong):
        render_pdf(_one_cell("a\n" * 79 + "a"))


def test_another_table_error_stays_a_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only fpdf2's "row too high" is the text's fault: any other error drawing a table is
    raised as it is, a renderer bug, not `RenderTooLong`."""

    def broken(*_args: object, **_kwargs: object) -> None:
        raise ValueError("something else")

    monkeypatch.setattr(KlarPdf, "_table", broken)
    with pytest.raises(ValueError, match=r"^something else$"):
        render_pdf(_one_cell("a"))


def test_a_long_cell_of_words_is_too_long_however_it_wraps() -> None:
    """Words that wrap, not line breaks: the renderer's own measure decides."""
    with pytest.raises(RenderTooLong):
        render_pdf(_one_cell(" ".join(["word"] * 3_000)))
