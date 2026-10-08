"""PDF files, drawn with fpdf2: A4, the flat lockup, the fonts embedded (P9; P25's report reuses
`KlarPdf`).

Every text goes through `multi_cell` as plain text (fpdf2's markdown is off), after `printable`.
A visible character the embedded fonts can't draw (an emoji, a CJK character) is shown as "?",
never dropped unseen, and only the count is logged: fpdf2 would log the characters themselves.
Invisible format characters are left out, and spaces and the non-breaking hyphen the fonts lack
are drawn as the plain ones (`_drawable`): this is the PDF's own step, after `printable`, which
both formats share and which keeps them (a Word file can hold them). The page line is written
last, once the page count is known (`KlarPdf.finish`).
"""

import logging
import unicodedata
from collections.abc import Mapping

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import TTFFont

from aiact.export.paper import Block, FillMarker, Heading, Note, Paper, Paragraph, Quote
from aiact.export.style import (
    FILL_TINT,
    FONTS,
    INK,
    INK_2,
    LENS_BLUE,
    LOGO_HEIGHT_MM,
    LOGO_PNG,
    LOGO_WIDTH_MM,
    MARGIN_MM,
    QUOTE_TINT,
    SLATE,
    STAMP,
    rgb,
)
from aiact.export.text import printable

logger = logging.getLogger(__name__)

SERIF, SANS = "Newsreader", "Geist"
UNDRAWABLE = "?"
"""What stands in for a character the font has no glyph for."""
KEPT_CONTROLS = frozenset("\n\t")
INVISIBLE = "Cf"
"""Unicode's format characters (U+200B-U+200D, U+2060, U+FEFF, the soft hyphen U+00AD): never
drawn, so never shown as "?" either."""
SPACE = "Zs"
"""Unicode's space separators (the narrow no-break space in "z. B.", the thin space): drawn as a
plain space when the font has no glyph for them."""
STAND_INS = {"\u2011": "-"}
"""Visible characters drawn as their plain twin when the font lacks them: the non-breaking
hyphen."""
FOOTER_FROM_BOTTOM_MM = 22.0
BOTTOM_MARGIN_MM = 30.0
"""Where a page breaks: above the footer, which holds the disclaimer and the page line."""
PADDING_MM = 3
LOGO_GAP_MM = 8.0
HEADING_KEEP_MM = 24.0
"""The room a heading needs below it for a few lines of its section; otherwise it starts the
next page."""


class KlarPdf(FPDF):
    """An A4 page in Klar's paper style, its footer on every page: `footer_text` (the
    disclaimer) and the page line (`page_of`, with `{page}` and `{pages}`). Renderers draw on it
    with the `write_*` methods (P25's report adds its own), then call `finish` for the file,
    which writes the footers."""

    def __init__(self, footer_text: str, page_of: str) -> None:
        super().__init__(orientation="portrait", unit="mm", format="A4")
        self.footer_text = printable(footer_text)
        self.page_of = page_of
        self.undrawable_count = 0
        # The page line is written once the page count is known (`finish`), so no alias for it
        # is reserved in the text: fpdf2 would swap its own alias wherever a user wrote it.
        self.alias_nb_pages(None)  # pyright: ignore[reportArgumentType]: fpdf2 documents None
        self.set_margins(MARGIN_MM, MARGIN_MM, MARGIN_MM)
        self.set_auto_page_break(auto=True, margin=BOTTOM_MARGIN_MM)
        self.add_font(SERIF, "", FONTS / "Newsreader-Regular.ttf")
        self.add_font(SERIF, "B", FONTS / "Newsreader-Medium.ttf")
        self.add_font(SANS, "", FONTS / "Geist-Regular.ttf")
        self.add_font(SANS, "B", FONTS / "Geist-SemiBold.ttf")

    def finish(self) -> bytes:
        """The file, once each page's footer is written with the page count, known now: the
        page line ends at the right margin."""
        pages = self.pages_count
        self.set_auto_page_break(auto=False)
        for number in range(1, pages + 1):
            self.page = number
            # fpdf2 skips selecting the font it last selected, but that was on another page:
            # forget it, so this page's text selects its own.
            self.font_family = ""
            self.set_y(-FOOTER_FROM_BOTTOM_MM)
            self._style(SANS, "", 8, SLATE)
            self.write_text(self.footer_text, 3.6)
            page_line = self.page_of.format(page=number, pages=pages)
            self.cell(0, 5, page_line, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return bytes(self.output())

    def write_text(self, text: str, line_height: float, *, fill: str | None = None) -> None:
        """`text` as given, wrapped to the page, on a `fill` ground when one is given; then the
        next line, at the left margin."""
        if fill is not None:
            self.set_fill_color(*rgb(fill))
        self.multi_cell(
            0,
            line_height,
            self._drawable(printable(text)),
            align="L",
            fill=fill is not None,
            padding=PADDING_MM if fill is not None else 0,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    def _drawable(self, text: str) -> str:
        """`text` as the current font can draw it: an invisible format character (a zero-width
        space, a soft hyphen, a byte order mark) left out, a space or hyphen the font has no
        glyph for as the plain one, and any other character it can't draw as `UNDRAWABLE`,
        counted."""
        font = self.current_font
        if not isinstance(font, TTFFont):
            return text
        drawn = [self._glyph(char, font.cmap) for char in text]
        self.undrawable_count += drawn.count(UNDRAWABLE) - text.count(UNDRAWABLE)
        return "".join(drawn)

    @staticmethod
    def _glyph(char: str, cmap: Mapping[int, object]) -> str:
        category = unicodedata.category(char)
        if category == INVISIBLE:
            return ""
        if char in KEPT_CONTROLS or ord(char) in cmap:
            return char
        if category == SPACE:
            return " "
        return STAND_INS.get(char, UNDRAWABLE)

    def write_logo(self) -> None:
        self.image(LOGO_PNG, x=MARGIN_MM, y=MARGIN_MM, w=LOGO_WIDTH_MM)
        self.set_y(MARGIN_MM + LOGO_HEIGHT_MM + LOGO_GAP_MM)

    def write_title(self, title: str, stamp: str | None, lines: tuple[str, ...]) -> None:
        if stamp is not None:
            self._style(SANS, "B", 9, STAMP)
            self.write_text(stamp, 5)
            self.ln(1)
        self._style(SERIF, "B", 22, INK)
        self.write_text(title, 9.5)
        self._style(SANS, "", 9, SLATE)
        for line in lines:
            self.write_text(line, 4.6)
        self.ln(4)

    def write_block(self, block: Block) -> None:
        match block:
            case Heading(text=text):
                if self.will_page_break(HEADING_KEEP_MM):
                    self.add_page()  # never a heading alone at the foot of a page
                self.ln(3)
                self._style(SANS, "B", 11, INK)
                self.write_text(text, 6)
                self.ln(1)
            case Paragraph(text=text):
                self._style(SERIF, "", 11.5, INK_2)
                self.write_text(text, 5.8)
                self.ln(1.5)
            case Quote(text=text, source=source):
                self._style(SERIF, "", 10.5, INK_2)
                self.write_text(text, 5.2, fill=QUOTE_TINT)
                self._style(SANS, "", 8, SLATE)
                self.write_text(source, 4.4)
                self.ln(1.5)
            case FillMarker(text=text):
                self._style(SANS, "B", 10, LENS_BLUE)
                self.write_text(text, 5, fill=FILL_TINT)
                self.ln(1.5)
            case Note(text=text):
                self._style(SANS, "", 9.5, INK_2)
                self.write_text(text, 4.8, fill=QUOTE_TINT)
                self.ln(2)

    def _style(self, family: str, style: str, size: float, colour: str) -> None:
        self.set_font(family, style, size)
        self.set_text_color(*rgb(colour))


def render_pdf(paper: Paper) -> bytes:
    """`paper` as a PDF file."""
    pdf = KlarPdf(paper.footer, paper.page_of)
    pdf.set_lang(paper.language.value)
    pdf.set_title(printable(paper.title))
    pdf.add_page()
    pdf.write_logo()
    pdf.write_title(paper.title, paper.stamp, paper.lines)
    for block in paper.blocks:
        pdf.write_block(block)
    content = pdf.finish()
    if pdf.undrawable_count:
        logger.warning("PDF: %d characters no font can draw shown as ?", pdf.undrawable_count)
    return content
