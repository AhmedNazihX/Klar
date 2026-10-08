"""A document to print, in the blocks both renderers draw (`pdf.py`, `word.py`).

A caller builds a `Paper` from its own content (a drafted document, P9; the report for a lawyer,
P25) and hands it to a renderer. Every text is plain text: a renderer writes it as given and never
reads markup in it, so the user's words can't change the file's layout or content.
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


Block = Heading | Paragraph | Quote | FillMarker | Note


PAGE_OF: Mapping[Language, str] = MappingProxyType(
    {EN: "Page {page} of {pages}", DE: "Seite {page} von {pages}"}
)
"""The page line on every page; `{page}` and `{pages}` are filled in by the renderer."""


@dataclass(frozen=True)
class Paper:
    """One document: the flat lockup, an optional stamp (DRAFT), the title and the lines under it,
    then the blocks in order. `footer` (the disclaimer) and the page line close every page."""

    language: Language
    title: str
    blocks: tuple[Block, ...]
    footer: str
    stamp: str | None = None
    lines: tuple[str, ...] = ()

    @property
    def page_of(self) -> str:
        return PAGE_OF[self.language]
