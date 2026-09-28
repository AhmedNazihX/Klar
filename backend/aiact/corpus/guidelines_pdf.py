"""Read a guideline PDF with Docling and flatten it into `Block`s in reading order.

Docling finds the layout (headings, paragraphs, list items, footnotes, tables) and the page of each
item. This module turns that into a flat, normalised sequence the chunker can walk:
- page furniture (running headers, page numbers) is left out, and so are pictures and the
  table of contents;
- a list marker that Docling left inside the text ("- Facial …", "(196) An AI …", "o AI …") or
  mislabelled (a bold bullet title read as a heading) becomes the block's `marker`;
- a paragraph that runs over a page break is joined back: a block that opens a new page with a
  lower-case letter continues the previous body block (footnotes in between are skipped).
"""

import re
from dataclasses import dataclass, replace
from io import BytesIO
from typing import Literal

from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.table.table import TableItem
from docling_core.types.doc.items.text import ListItem, TextItem
from docling_core.types.doc.labels import DocItemLabel

BlockKind = Literal["heading", "paragraph", "list_item", "footnote", "table"]

BULLET_MARKERS = frozenset({"-", "\u2013", "\u2022"})
"""Top-level bullets: hyphen, en dash, bullet. `o` marks a sub-bullet; a middle dot or a
lettered marker belongs to another kind of list."""
SUB_BULLET_MARKER = "o"
INLINE_BULLET_RE = re.compile("^([-\u2013\u2022])\\s+(?=\\S)")
INLINE_SUB_BULLET_RE = re.compile(r"^o\s+(?=[A-Z])")
INLINE_PARAGRAPH_RE = re.compile(r"^(\(\d+\))\s+(?=\S)")
PARAGRAPH_MARKER_RE = re.compile(r"^\(\d+\)$")
"""A numbered paragraph of the guidelines, such as `(43)`."""
DOT_LEADER_RE = re.compile(r"\.{5,}")
MIN_TOC_LEADERS = 3
"""A table with this many dot leaders ("Introduction ...... 1") is a table of contents."""
TABLE_PADDING_RE = re.compile(r"[ \t]{2,}")
TABLE_RULE_RE = re.compile(r"-{4,}")
SKIPPED_LABELS = frozenset(
    {DocItemLabel.PICTURE, DocItemLabel.DOCUMENT_INDEX, DocItemLabel.PAGE_HEADER}
)
KIND_OF_LABEL: dict[DocItemLabel, BlockKind] = {
    DocItemLabel.SECTION_HEADER: "heading",
    DocItemLabel.TITLE: "heading",
    DocItemLabel.LIST_ITEM: "list_item",
    DocItemLabel.FOOTNOTE: "footnote",
    DocItemLabel.TABLE: "table",
}


@dataclass(frozen=True)
class Block:
    """One layout item of a guideline PDF, in reading order."""

    kind: BlockKind
    text: str
    """The item's text, without its list marker."""
    page: int
    """The physical PDF page (1-based) the item starts on."""
    marker: str = ""
    """The list marker: `-`, `o`, `(43)`, `a.` …; empty for other blocks."""

    @property
    def rendered(self) -> str:
        """The text as printed, marker included."""
        return f"{self.marker} {self.text}" if self.marker else self.text

    @property
    def is_bullet(self) -> bool:
        return self.kind == "list_item" and self.marker in BULLET_MARKERS

    @property
    def is_sub_bullet(self) -> bool:
        return self.kind == "list_item" and self.marker == SUB_BULLET_MARKER

    @property
    def is_numbered_paragraph(self) -> bool:
        return self.kind == "list_item" and PARAGRAPH_MARKER_RE.match(self.marker) is not None


def convert_pdf(content: bytes, name: str) -> DoclingDocument:
    """Run Docling's PDF pipeline on the PDF bytes `content` (`name` is the file name).

    The PDFs have a text layer, so OCR is off. Docling downloads its layout and table models on
    first use and caches them.
    """
    # Imported here: the converter pulls in torch, which the rest of the corpus code never needs.
    from docling.datamodel.base_models import DocumentStream, InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    return converter.convert(DocumentStream(name=name, stream=BytesIO(content))).document


def blocks_of(document: DoclingDocument) -> tuple[Block, ...]:
    """The body of `document` as normalised blocks, page breaks inside paragraphs joined."""
    raw = (_block(document, item) for item, _level in document.iterate_items())
    return _join_page_breaks([block for block in raw if block is not None and block.text])


def _block(document: DoclingDocument, item: object) -> Block | None:
    if isinstance(item, TableItem):
        return _table(item.export_to_markdown(document), _page(item))
    if not isinstance(item, TextItem) or item.label in SKIPPED_LABELS:
        return None
    kind = KIND_OF_LABEL.get(item.label, "paragraph")
    marker = item.marker.strip() if isinstance(item, ListItem) else ""
    return _normalise(Block(kind, _clean(item.text), _page(item), marker))


def _table(markdown: str, page: int) -> Block | None:
    """A table as compact markdown; a table of contents (dot leaders) is left out."""
    if len(DOT_LEADER_RE.findall(markdown)) >= MIN_TOC_LEADERS:
        return None
    compact = TABLE_RULE_RE.sub("---", TABLE_PADDING_RE.sub(" ", markdown))
    return Block("table", compact.strip(), page)


def _page(item: TextItem | TableItem) -> int:
    return item.prov[0].page_no if item.prov else 0


def _clean(text: str) -> str:
    return " ".join(text.split())


def _normalise(block: Block) -> Block:
    """Move a list marker that Docling left in the text, or missed, into `marker`.

    A heading only ever hides a bullet (a bold bullet title); other blocks can also hide a
    paragraph number or an `o` sub-bullet.
    """
    if block.kind == "footnote" or block.marker:
        return block
    patterns = (INLINE_BULLET_RE,)
    if block.kind != "heading":
        patterns = (INLINE_BULLET_RE, INLINE_PARAGRAPH_RE, INLINE_SUB_BULLET_RE)
    for pattern in patterns:
        match = pattern.match(block.text)
        if match is not None:
            marker = SUB_BULLET_MARKER if pattern is INLINE_SUB_BULLET_RE else match.group(1)
            return replace(block, kind="list_item", marker=marker, text=block.text[match.end() :])
    return block


def _join_page_breaks(blocks: list[Block]) -> tuple[Block, ...]:
    """Join a block that opens a page with a lower-case letter to the body block before it."""
    joined: list[Block] = []
    last_body: int | None = None
    last_page = 0
    for block in blocks:
        if block.kind == "footnote":
            joined.append(block)
            continue
        is_page_start = block.page > last_page
        last_page = max(last_page, block.page)
        if is_page_start and last_body is not None and _continues(block):
            previous = joined[last_body]
            joined[last_body] = replace(previous, text=_join(previous.text, block.text))
            continue
        last_body = len(joined)
        joined.append(block)
    return tuple(joined)


def _continues(block: Block) -> bool:
    return (
        block.kind in ("paragraph", "list_item") and not block.marker and block.text[:1].islower()
    )


def _join(first: str, second: str) -> str:
    """Join two halves of a paragraph; a word hyphenated over the break is closed up."""
    if first.endswith("-") and first[-2:-1].isalpha():
        return first[:-1] + second
    return f"{first} {second}"
