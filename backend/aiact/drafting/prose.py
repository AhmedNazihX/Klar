"""Writing an interview answer up as prose for a skeleton's section (INIT > Documentation
drafting: "the answers are written up as prose").

No model is involved and no word is added or changed: the answer is written in as given, as a
sentence. Its first letter becomes a capital and, unless it already ends a sentence, a full stop
closes it. The "No content you didn't supply" check compares a section with the answers written
up this way, not with the bare answers, which is the looser comparison P8b asked for. The short
deployer documents keep each answer exactly as given ("Written into the notice as you give it").
"""

SENTENCE_ENDS = frozenset(".!?…:;")
"""Marks an answer may already end with; it gets no full stop after them."""

CLOSING_MARKS = "\"'\u201d\u2019\u201c\u2018\u00bb\u00ab)]"
"""Closing quotes (straight, curly, and the German and French ones) and brackets, looked past
for the mark that ends the sentence inside them."""


def write_up(answer: str) -> str:
    """`answer` as a sentence: without surrounding blank space, its first letter a capital, and
    a full stop at the end unless it already ends a sentence. A blank answer stays empty."""
    text = answer.strip()
    if not text:
        return ""
    first = text[0].upper()
    if len(first) == 1:  # "ß".upper() is "SS": such a letter stays as written
        text = first + text[1:]
    ending = text.rstrip(CLOSING_MARKS)[-1:]
    return text if ending in SENTENCE_ENDS else f"{text}."
