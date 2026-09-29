"""Find the Commission's worked examples in the high-risk guidelines and number them `hr-ex-NNN`.

The rules are those of docs/decisions/001-commission-example-count.md, applied to the PDF alone
(this code never reads the benchmark's copy of the examples):
1. Sources: in the Annex I part, the named systems of paras. (43), (45), (46), (47) and (49);
   in the Annex III part, every list under a heading that begins with `a)`, `b)` or `c)` and
   contains "Practical example", plus exactly two named lists (the cybersecurity list of section
   3.2.1 and the list of para. (372)). Nothing else is an example.
2. One top-level bullet is one example; a bullet with `o` sub-bullets gives one example per
   sub-bullet, with the bullet's own sentence as the `lead_in`. A list without bullets (the gas,
   heating and electricity headings) gives one example per paragraph. Para. (43) holds two
   examples, split at "Conversely,"; para. (49) is one.
3. IDs run through the Annex I part, then the Annex III part, in document order.

The result is checked against 001's anchor table: the number of examples in every counted list,
in order (79 lists, 307 examples). A list that comes out with a different size stops the parse:
an example that can't be numbered is a hole in the benchmark isolation.
"""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace

from aiact.corpus.guidelines_pdf import Block

ANNEX_I_DOC = "guide-high-risk-annex-i"
ANNEX_III_DOC = "guide-high-risk-annex-iii"
EXAMPLE_DOCS = (ANNEX_I_DOC, ANNEX_III_DOC)
"""The parts that hold examples, in numbering order."""
EXAMPLE_ID_FORMAT = "hr-ex-{:03d}"

LIST_SIZES: dict[str, tuple[int, ...]] = {
    ANNEX_I_DOC: (2, 4, 3, 2, 1),
    ANNEX_III_DOC: (
        *(7, 20, 2, 4, 5, 2, 4, 1, 1, 5, 2, 2, 1, 1, 2, 7, 4, 2, 3, 2, 3, 3, 3, 2, 2),
        *(3, 2, 2, 9, 6, 5, 5, 5, 2, 10, 4, 4, 2, 7, 2, 2, 8, 7, 2, 3, 5, 1, 3, 4, 7),
        *(2, 4, 1, 2, 3, 3, 9, 2, 2, 1, 8, 5, 5, 1, 9, 5, 5, 1, 4, 6, 5, 3, 8, 1),
    ),
}
"""Decision 001's anchor table: the examples in each counted list, in document order."""

PRACTICAL_HEADING_RE = re.compile(r"^[abc]\)\s*.*\bpractical examples?\b", re.IGNORECASE)
NAMED_LIST_INTROS = (
    "Examples of AI systems used solely for cybersecurity purposes, thus falling outside the use "
    "case of point 2 of Annex III",
    "Below are some examples of AI systems used by law enforcement authorities that would not "
    "generally be classified as high-risk",
)
"""Decision 001, rule 1: the only two lists without a "Practical example" heading."""
NUMBERED_HEADING_RE = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[ivxIVX]+\.|[a-z]\)|\([ivx]+\))\s")
"""A section heading: `3.5.3.`, `2.2.2`, `ii.`, `IV.`, `a)`, `(i)`."""
SECTION_MARKER_RE = re.compile(r"^(?:[IVX]+|[ivx]+|\d+(?:\.\d+)*)\.$")
"""A list marker that numbers a section rather than a bullet: `V.`, `ii.`, `3.`."""
ANNEX_I_LIST_PARAGRAPHS = frozenset({"(45)", "(46)", "(47)"})
"""Annex I paragraphs whose bullets are the examples."""
ANNEX_I_WHOLE_PARAGRAPHS = frozenset({"(49)"})
ANNEX_I_SPLIT_PARAGRAPHS: dict[str, str] = {"(43)": "Conversely,"}
"""Annex I paragraphs that hold two examples, and the words the second one begins with."""


class ExampleCountError(Exception):
    """The examples found don't match decision 001's anchor table."""


@dataclass(frozen=True)
class Example:
    """One worked example: its verbatim text, where it starts, and its number once assigned."""

    text: str
    page: int
    lead_in: str | None = None
    subheading: str | None = None
    """An unnumbered heading inside the list that groups this example with the next ones."""
    example_id: str | None = None


@dataclass(frozen=True)
class ExampleList:
    """A counted list: its heading (or introducing text) and its examples, in order."""

    heading: str
    page: int
    examples: tuple[Example, ...]


Segment = Block | ExampleList
"""A document after example extraction: prose blocks and example lists, in reading order."""


def extract_examples(doc: str, blocks: Sequence[Block]) -> tuple[Segment, ...]:
    """Take the examples of `doc` out of its blocks. Other documents come back unchanged."""
    if doc == ANNEX_I_DOC:
        return tuple(_annex_i(blocks))
    if doc == ANNEX_III_DOC:
        return tuple(_annex_iii(blocks))
    return tuple(blocks)


def number_examples(documents: dict[str, tuple[Segment, ...]]) -> dict[str, tuple[Segment, ...]]:
    """Give every example its `hr-ex-NNN`, after checking each list's size against the anchors.

    `documents` maps a doc id to its segments and must hold both example documents.
    """
    missing = [doc for doc in EXAMPLE_DOCS if doc not in documents]
    if missing:
        raise ExampleCountError(f"examples are numbered across both parts; missing {missing}")
    numbered = dict(documents)
    counter = 0
    for doc in EXAMPLE_DOCS:
        _check_sizes(doc, documents[doc])
        segments: list[Segment] = []
        for segment in documents[doc]:
            if isinstance(segment, ExampleList):
                examples = []
                for example in segment.examples:
                    counter += 1
                    examples.append(replace(example, example_id=EXAMPLE_ID_FORMAT.format(counter)))
                segment = replace(segment, examples=tuple(examples))
            segments.append(segment)
        numbered[doc] = tuple(segments)
    return numbered


def _check_sizes(doc: str, segments: tuple[Segment, ...]) -> None:
    lists = [s for s in segments if isinstance(s, ExampleList)]
    found = tuple(len(s.examples) for s in lists)
    expected = LIST_SIZES[doc]
    for index, (list_, size) in enumerate(zip(lists, expected, strict=False), start=1):
        if len(list_.examples) != size:
            raise ExampleCountError(
                f"{doc}: list {index} ({list_.heading[:60]!r}, p. {list_.page}) has "
                f"{len(list_.examples)} examples, decision 001 counts {size}"
            )
    if len(found) != len(expected):
        raise ExampleCountError(
            f"{doc}: found {len(found)} example lists, decision 001 counts {len(expected)}"
        )


def _annex_iii(blocks: Sequence[Block]) -> Iterator[Segment]:
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if block.kind == "heading" and PRACTICAL_HEADING_RE.match(block.text):
            examples, footnotes, index = _collect(blocks, index + 1)
            yield ExampleList(block.text, block.page, examples)
            yield from footnotes
            continue
        yield block
        index += 1
        if block.text.startswith(NAMED_LIST_INTROS):
            examples, footnotes, index = _collect(blocks, index)
            yield ExampleList(block.text, block.page, examples)
            yield from footnotes


def _annex_i(blocks: Sequence[Block]) -> Iterator[Segment]:
    index = 0
    while index < len(blocks):
        block = blocks[index]
        index += 1
        heading = f"para. {block.marker}"
        if not block.is_numbered_paragraph:
            yield block
        elif block.marker in ANNEX_I_WHOLE_PARAGRAPHS:
            yield ExampleList(heading, block.page, (Example(block.text, block.page),))
        elif block.marker in ANNEX_I_SPLIT_PARAGRAPHS:
            yield ExampleList(heading, block.page, _split_paragraph(block))
        else:
            yield block
            if block.marker in ANNEX_I_LIST_PARAGRAPHS:
                examples, footnotes, index = _collect(blocks, index)
                yield ExampleList(heading, block.page, examples)
                yield from footnotes


def _split_paragraph(block: Block) -> tuple[Example, ...]:
    second_start = ANNEX_I_SPLIT_PARAGRAPHS[block.marker]
    first, found, second = block.text.partition(second_start)
    if not found:
        raise ExampleCountError(f"para. {block.marker}: {second_start!r} not found")
    return (Example(first.strip(), block.page), Example(found + second, block.page))


def _ends_list(block: Block) -> bool:
    """A numbered heading (also one Docling read as a list item, `V. Entry into application`),
    a table or a numbered paragraph ends a list. An unnumbered heading ("Prioritisation") only
    groups the examples under it."""
    if block.kind == "heading":
        return NUMBERED_HEADING_RE.match(block.text) is not None
    if block.kind == "list_item" and SECTION_MARKER_RE.match(block.marker):
        return True
    return block.kind == "table" or block.is_numbered_paragraph


def _collect(
    blocks: Sequence[Block], start: int
) -> tuple[tuple[Example, ...], tuple[Block, ...], int]:
    """The examples of the list starting at `start`, the footnotes met on the way, and the index
    of the first block after the list."""
    end = start
    while end < len(blocks) and not _ends_list(blocks[end]):
        end += 1
    body = [b for b in blocks[start:end] if b.kind != "footnote"]
    footnotes = tuple(b for b in blocks[start:end] if b.kind == "footnote")
    is_bulleted = any(b.is_bullet or b.is_sub_bullet for b in body)
    examples = _bulleted(body) if is_bulleted else _unbulleted(body)
    return examples, footnotes, end


def _unbulleted(body: list[Block]) -> tuple[Example, ...]:
    """Decision 001, rule 2: a verdict heading without bullets has one example per paragraph."""
    examples: list[Example] = []
    subheading: str | None = None
    for block in body:
        if block.kind == "heading":
            subheading = block.text
        else:
            examples.append(Example(block.rendered, block.page, subheading=subheading))
    return tuple(examples)


def _bulleted(body: list[Block]) -> tuple[Example, ...]:
    """One example per top-level bullet, or per `o` sub-bullet (the bullet becomes the lead-in).

    Paragraphs after a bullet (its body text, or text Docling split off) belong to that bullet.
    """
    examples: list[Example] = []
    lead_in: str | None = None
    subheading: str | None = None
    for block in body:
        if block.kind == "heading":
            subheading, lead_in = block.text, None
        elif block.is_bullet:
            lead_in = None
            examples.append(Example(block.text, block.page, subheading=subheading))
        elif block.is_sub_bullet:
            if lead_in is None:
                if not examples:
                    raise ExampleCountError(f"p. {block.page}: a sub-bullet without a bullet")
                lead_in = examples.pop().text
            examples.append(Example(block.text, block.page, lead_in, subheading))
        elif examples:
            last = examples[-1]
            examples[-1] = replace(last, text=f"{last.text}\n{block.rendered}")
        else:
            raise ExampleCountError(f"p. {block.page}: text before the first bullet of a list")
    return tuple(examples)
