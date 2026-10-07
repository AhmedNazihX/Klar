"""Text as a Word or PDF file can hold it."""

import re

UNPRINTABLE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff￾￿]")
"""Characters XML 1.0 (and so a .docx) can't hold, which a PDF can't draw either: the control
characters other than tab and line breaks, lone surrogates, and the two non-characters."""

LINE_BREAK = re.compile("\r\n?")


def printable(text: str) -> str:
    """`text` with every line break as `\\n` and the characters a file can't hold left out.
    Nothing else changes: the text is never read as markup."""
    return UNPRINTABLE.sub("", LINE_BREAK.sub("\n", text))
