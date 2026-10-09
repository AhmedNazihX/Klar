"""PDF files, drawn with fpdf2: A4, the flat lockup, the fonts embedded (P9; P25's reports add
the field grid, tables and the sign-off box).

Every text goes through `multi_cell`, or a table cell, as plain text (fpdf2's markdown is off),
after `printable`.
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
from fpdf.enums import TableBordersLayout, XPos, YPos
from fpdf.fonts import FontFace, TTFFont

from aiact.export.paper import (
    Block,
    Fields,
    FillMarker,
    Heading,
    Note,
    PageBreak,
    Paper,
    Paragraph,
    Quote,
    SignOff,
    SmallText,
    Table,
)
from aiact.export.style import (
    FILL_TINT,
    FONTS,
    HAIRLINE,
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
TABLE_FONT_PT = 8.0
CELL_PADDING_MM = 1.0
TABLE_LINE_MM = 3.6
SIGN_OFF_KEEP_MM = 50.0
"""The room the sign-off box needs; otherwise it starts the next page, whole."""
SIGNATURE_ROOM_MM = 10.0
"""The space above the signature lines, to write in."""
SIGNATURE_GAP_MM = 10.0
"""Between two signature lines side by side."""


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

    def write_title(
        self, title: str, stamp: str | None, lines: tuple[str, ...], kicker: str | None = None
    ) -> None:
        if stamp is not None:
            self._style(SANS, "B", 9, STAMP)
            self.write_text(stamp, 5)
            self.ln(1)
        if kicker is not None:
            self._style(SANS, "B", 9, SLATE)
            self.write_text(kicker, 5)
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
            case SmallText(text=text):
                self._style(SANS, "", 9.5, INK_2)
                self.write_text(text, 4.6)
                self.ln(1)
            case Note(text=text):
                self._style(SANS, "", 9.5, INK_2)
                self.write_text(text, 4.8, fill=QUOTE_TINT)
                self.ln(2)
            case Fields(items=items):
                self._write_fields(items)
            case Table():
                self._write_table(block)
            case SignOff():
                self._write_sign_off(block)
            case PageBreak():
                self.add_page()

    def _write_fields(self, items: tuple[tuple[str, str], ...]) -> None:
        """Each label above its value, side by side, between two hairlines."""
        self._style(SANS, "B", 11, INK)
        labels = FontFace(family=SANS, emphasis="", size_pt=8, color=rgb(SLATE))
        self._table_rows(
            (tuple(label for label, _ in items), tuple(value for _, value in items)),
            widths=(1.0,) * len(items),
            headings=labels,
        )
        self.ln(3)

    def _write_table(self, table: Table) -> None:
        self._style(SANS, "", TABLE_FONT_PT, INK_2)
        header = FontFace(family=SANS, emphasis="B", size_pt=TABLE_FONT_PT, color=rgb(SLATE))
        self._table_rows(
            (table.header, *table.rows),
            widths=table.widths,
            headings=header,
        )
        self.ln(3)

    def _table_rows(
        self,
        rows: tuple[tuple[str, ...], ...],
        *,
        widths: tuple[float, ...],
        headings: FontFace,
    ) -> None:
        """`rows` as a table across the page, the first one its header (repeated on a new
        page); each text as the current font can draw it."""
        self.set_draw_color(*rgb(HAIRLINE))
        with self.table(
            col_widths=widths,
            width=self.epw,
            align="LEFT",
            v_align="TOP",
            text_align="LEFT",
            borders_layout=TableBordersLayout.HORIZONTAL_LINES,
            headings_style=headings,
            line_height=TABLE_LINE_MM,
            padding=CELL_PADDING_MM,
            markdown=False,
        ) as table:
            for texts in rows:
                row = table.row()
                for text in texts:
                    row.cell(self._drawable(printable(text)))

    def _write_sign_off(self, sign_off: SignOff) -> None:
        """The heading, the lines to sign on side by side, each above its label, then the text;
        kept on one page."""
        if self.will_page_break(SIGN_OFF_KEEP_MM):
            self.add_page()
        self.ln(3)
        self._style(SANS, "B", 11, INK)
        self.write_text(sign_off.heading, 6)
        self.set_draw_color(*rgb(SLATE))
        self._style(SANS, "", 8, SLATE)
        count = len(sign_off.labels)
        width = (self.epw - SIGNATURE_GAP_MM * (count - 1)) / max(count, 1)
        self.ln(SIGNATURE_ROOM_MM)
        y = self.get_y()
        for number, label in enumerate(sign_off.labels):
            x = self.l_margin + number * (width + SIGNATURE_GAP_MM)
            self.line(x, y, x + width, y)
            self.set_xy(x, y)
            self.cell(width, 4.4, self._drawable(printable(label)))
        self.set_xy(self.l_margin, y + 4.4)
        self.ln(3)
        self._style(SANS, "", 9.5, INK_2)
        self.write_text(sign_off.text, 4.8, fill=QUOTE_TINT)

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
    pdf.write_title(paper.title, paper.stamp, paper.lines, paper.kicker)
    for block in paper.blocks:
        pdf.write_block(block)
    content = pdf.finish()
    if pdf.undrawable_count:
        logger.warning("PDF: %d characters no font can draw shown as ?", pdf.undrawable_count)
    return content
