"""Writing an interview answer up as prose for a skeleton's section (INIT > Documentation
drafting: "the answers are written up as prose").

No model is involved and no word is added or changed: the answer is written in as given, as a
sentence. Its first letter becomes a capital (unless the first word is a name written with an
inner capital, such as "iOS") and, unless it already ends a sentence, a full stop
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
    a full stop at the end unless it already ends a sentence. A first word written with a capital
    after its first letter ("iOS", "eBay", "pH") is a name and stays as written. A blank answer
    stays empty."""
    text = answer.strip()
    if not text:
        return ""
    first = text[0].upper()
    # "ß".upper() is "SS": such a letter stays as written.
    if len(first) == 1 and not _is_cased_name(text.split(maxsplit=1)[0]):
        text = first + text[1:]
    ending = text.rstrip(CLOSING_MARKS)[-1:]
    return text if ending in SENTENCE_ENDS else f"{text}."


def _is_cased_name(word: str) -> bool:
    """Whether `word` has a capital after its first character, as a name like "iOS" does."""
    return any(character.isupper() for character in word[1:])
