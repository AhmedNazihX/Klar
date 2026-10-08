"""Writing an interview answer up as prose for a skeleton's section (INIT > Documentation
drafting: "the answers are written up as prose").

No model is involved and no word is added or changed: the answer is written in as given, as a
sentence. Its first letter becomes a capital (unless the first word is a name written with an
inner capital, such as "iOS") and, unless it already ends a sentence, a full stop
closes it. The "No content you didn't supply" check compares a section with the answers written
up this way, not with the bare answers, which is the looser comparison P8b asked for. The short
deployer documents keep each answer exactly as given ("Written into the notice as you give it").
"""

BLANK = (
    "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)
"""Blank space around an answer: Python's whitespace (`str.isspace`) and the byte order mark.
An answer of nothing else is blank, left to fill in. The Documents screen counts the questions
left with the same characters (`BLANK_CODE_POINTS` in
frontend/src/features/documents/interview.ts, checked by the tests to match)."""

SENTENCE_ENDS = frozenset(".!?…:;")
"""Marks an answer may already end with; it gets no full stop after them."""

CLOSING_MARKS = "\"'\u201d\u2019\u201c\u2018\u00bb\u00ab)]"
"""Closing quotes (straight, curly, and the German and French ones) and brackets, looked past
for the mark that ends the sentence inside them."""


def write_up(answer: str) -> str:
    """`answer` as a sentence: without surrounding blank space, its first letter a capital, and
    a full stop at the end unless it already ends a sentence. A first word written with a capital
    after its first letter ("iOS", "eBay", "pH") is a name and stays as written. A blank answer
    stays empty."""
    text = without_blank(answer)
    if not text:
        return ""
    first = text[0].upper()
    # "ß".upper() is "SS": such a letter stays as written.
    if len(first) == 1 and not _is_cased_name(text.split(maxsplit=1)[0]):
        text = first + text[1:]
    ending = text.rstrip(CLOSING_MARKS)[-1:]
    return text if ending in SENTENCE_ENDS else f"{text}."


def without_blank(answer: str) -> str:
    """`answer` without the `BLANK` space around it."""
    return answer.strip(BLANK)


def _is_cased_name(word: str) -> bool:
    """Whether `word` has a capital after its first character, as a name like "iOS" does."""
    return any(character.isupper() for character in word[1:])
