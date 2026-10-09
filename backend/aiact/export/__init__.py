"""Word and PDF files, drawn in Klar's paper style from a `Paper` (P9): the drafted documents
(P9), the report for a lawyer and the inventory report (P25). The files are made in Python (INIT >
Tech stack: Document files), and every text in them is plain text."""

from aiact.export.paper import (
    PAGE_OF,
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
    block_texts,
)
from aiact.export.pdf import KlarPdf, render_pdf
from aiact.export.word import render_docx

__all__ = [
    "PAGE_OF",
    "Block",
    "Fields",
    "FillMarker",
    "Heading",
    "KlarPdf",
    "Note",
    "PageBreak",
    "Paper",
    "Paragraph",
    "Quote",
    "SignOff",
    "SmallText",
    "Table",
    "block_texts",
    "render_docx",
    "render_pdf",
]
