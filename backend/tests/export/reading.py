"""Reading exported files back, for the tests: a PDF's text per page and a Word file's
paragraphs, each with its runs' fonts, and its footer."""

import re
from dataclasses import dataclass
from io import BytesIO

from docx import Document
from pypdf import PdfReader

BLANK_SPACE = re.compile(r"\s+")


def one_line(text: str) -> str:
    """`text` with every run of blank space (line breaks from wrapping included) as one space."""
    return BLANK_SPACE.sub(" ", text).strip()


def pdf_pages(data: bytes) -> list[str]:
    """Each page's text, on one line."""
    return [one_line(page.extract_text()) for page in PdfReader(BytesIO(data)).pages]


@dataclass(frozen=True)
class WordFile:
    paragraphs: tuple[str, ...]
    """The body's paragraphs, as their text."""
    footer: tuple[str, ...]
    footer_xml: str
    title: str
    language: str


def read_docx(data: bytes) -> WordFile:
    document = Document(BytesIO(data))
    footer = document.sections[0].footer
    return WordFile(
        paragraphs=tuple(paragraph.text for paragraph in document.paragraphs),
        footer=tuple(paragraph.text for paragraph in footer.paragraphs),
        footer_xml=footer._element.xml,  # pyright: ignore[reportPrivateUsage]
        title=document.core_properties.title,
        language=document.core_properties.language,
    )
