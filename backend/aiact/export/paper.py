"""A document to print, in the blocks both renderers draw (`pdf.py`, `word.py`).

A caller builds a `Paper` from its own content (a drafted document, P9; the report for a lawyer
and the inventory report, P25) and hands it to a renderer. Every text is plain text: a renderer
writes it as given and never reads markup in it, so the user's words can't change the file's
layout or content.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from aiact.schemas import Language

EN, DE = Language.EN, Language.DE


@dataclass(frozen=True)
class Heading:
    """A section's heading, in the product's sans-serif voice."""

    text: str


@dataclass(frozen=True)
class Paragraph:
    """Body text, in the documents' serif voice."""

    text: str


@dataclass(frozen=True)
class Quote:
    """A provision quoted word for word, and where it comes from."""

    text: str
    source: str


@dataclass(frozen=True)
class FillMarker:
    """What is still to be filled in, marked so it can't pass for content."""

    text: str


@dataclass(frozen=True)
class Note:
    """A line set apart from the content, such as the simplified-form note."""

    text: str


@dataclass(frozen=True)
class Fields:
    """A row of labelled values, each label above its value: the report's Class, Status, Role
    and Duties-from grid."""

    items: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Table:
    """A table: its header row, then its rows, each with one text per column. `widths` are the
    columns' shares of the page's width."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    widths: tuple[float, ...]

    def __post_init__(self) -> None:
        columns = len(self.header)
        if len(self.widths) != columns or any(len(row) != columns for row in self.rows):
            raise ValueError("every row of a table and its widths have one entry per column")


@dataclass(frozen=True)
class SignOff:
    """A box for a person to sign: its heading, a line to write on above each label ("Reviewed
    by", "Date"), then a text."""

    heading: str
    labels: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class PageBreak:
    """What follows starts a new page."""


Block = Heading | Paragraph | Quote | FillMarker | Note | Fields | Table | SignOff | PageBreak


def block_texts(block: Block) -> tuple[str, ...]:
    """Every text a block draws, for counting a paper's length before it is rendered."""
    match block:
        case Quote(text=text, source=source):
            return (text, source)
        case Fields(items=items):
            return tuple(text for item in items for text in item)
        case Table(header=header, rows=rows):
            return (*header, *(text for row in rows for text in row))
        case SignOff(heading=heading, labels=labels, text=text):
            return (heading, *labels, text)
        case PageBreak():
            return ()
        case Heading(text=text) | Paragraph(text=text) | FillMarker(text=text) | Note(text=text):
            return (text,)


PAGE_OF: Mapping[Language, str] = MappingProxyType(
    {EN: "Page {page} of {pages}", DE: "Seite {page} von {pages}"}
)
"""The page line on every page; `{page}` and `{pages}` are filled in by the renderer."""


@dataclass(frozen=True)
class Paper:
    """One document: the flat lockup, an optional stamp (DRAFT) or kicker (the kind of document
    and its ID), the title and the lines under it, then the blocks in order. `footer` (the
    disclaimer) and the page line close every page."""

    language: Language
    title: str
    blocks: tuple[Block, ...]
    footer: str
    stamp: str | None = None
    kicker: str | None = None
    lines: tuple[str, ...] = ()

    @property
    def page_of(self) -> str:
        return PAGE_OF[self.language]
