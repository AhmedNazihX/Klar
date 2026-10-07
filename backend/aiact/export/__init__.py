"""Word and PDF files, drawn in Klar's paper style from a `Paper` (P9): the drafted documents now,
the report for a lawyer (P25) next. The files are made in Python (INIT > Tech stack: Document
files), and every text in them is plain text."""

from aiact.export.paper import (
    PAGE_OF,
    Block,
    FillMarker,
    Heading,
    Note,
    Paper,
    Paragraph,
    Quote,
)
from aiact.export.pdf import KlarPdf, render_pdf
from aiact.export.word import render_docx

__all__ = [
    "PAGE_OF",
    "Block",
    "FillMarker",
    "Heading",
    "KlarPdf",
    "Note",
    "Paper",
    "Paragraph",
    "Quote",
    "render_docx",
    "render_pdf",
]
