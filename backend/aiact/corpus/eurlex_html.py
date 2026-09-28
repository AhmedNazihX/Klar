"""Read EUR-Lex XHTML into a small tree of text lines and labelled list items.

Cellar serves the laws in two layouts (docs/decisions/008-cellar-source.md):
- Official Journal acts (`oj-*` classes): a point is a two-cell table (label, content); a numbered
  paragraph is a `<div id="005.001">` whose first line starts with its number.
- The consolidated text (CONVEX `clg` classes): a point is a `div.grid-list` (label column, content
  column); a numbered paragraph is a `div.norm` holding `span.no-parag`; `p.modref` lines mark which
  act changed the text that follows, and are dropped here.
Both are reduced to the same `Block` tree, so the rest of the parser doesn't care which layout it
reads. Articles, annexes and recitals are found by their language-independent ids (`art_5`,
`anx_III`, `rct_53`), which both layouts share.
"""

import re
from dataclasses import dataclass, replace
from typing import Literal

from lxml import html
from lxml.html import HtmlElement

POINT_LABEL_RE = re.compile(r"^\(?(\d+(?:\.\d+)*[a-z]{0,2}|[a-z]{1,4})\)?\.?$")
"""A point label once quotes are stripped: (a), a), (ba), (iv), (14a), 1., 3.1."""
OPENING_QUOTES = "\u2018\u201e"
"""The quotes that open amending text: English single quote, German low double quote."""
QUOTES = OPENING_QUOTES + "\u2019\u201c\u201d\u201a'\""
PARAGRAPH_PREFIX_RE = re.compile("^[" + OPENING_QUOTES + r"]?\(?(\d+[a-z]{0,2})(?:\.|\))\s+")
"""The number that opens a paragraph: `1.   ` in English, `(1)   ` in German, maybe quoted."""
HANGING_LABEL_RE = re.compile(r"^(\(?\d+(?:\.\d+)*[a-z]{0,2}[.)])\s+(.*)$", re.DOTALL)
"""A numbered line typeset with a hanging indent instead of a list (consolidated Annex I)."""
EMPTY_PARENS_RE = re.compile(r"\(\s*\)")
SPACE_BEFORE_PUNCTUATION_RE = re.compile(r"\s+([,.;:])")
"""Left behind where a footnote reference stood: `Council (¹),` → `Council ,`."""
PARAGRAPH_DIV_RE = re.compile(r"^\d{3}\.(\d{3})$")

SKIPPED_P_CLASSES = frozenset({"modref", "arrow", "oj-note", "footnote"})
"""Amendment markers (`▼M1`) and footnote bodies."""
TITLE_P_CLASSES = frozenset({"oj-ti-art", "title-article-norm"})
"""`Article 5`: the article's own title, or one inside quoted text (`'Article 4a`)."""
HEADING_P_CLASSES = frozenset({"oj-doc-ti", "title-annex-1", "title-annex-2"})
GROUP_P_CLASSES = frozenset({"oj-ti-grseq-1", "title-gr-seq-level-1"})
"""Group titles inside an annex: `Section A — …`, `1.   Introduction`."""
DELETION_MARK = "—————"
BLOCK_TAGS = frozenset({"p", "div", "table"})
MAX_LABEL_LENGTH = 8
"""Longer first cells are table data, not list labels (`(iv)`, `„14a.`, `—` all fit)."""

TextRole = Literal["text", "heading", "title", "group"]


@dataclass(frozen=True)
class Text:
    """One line of running text. `role` is `text`, or for title lines `heading` (an annex's),
    `title` (an article's number line) or `group` (a section title inside an annex)."""

    text: str
    role: TextRole = "text"


@dataclass(frozen=True)
class Item:
    """A labelled list entry: a paragraph (`1.`/`(1)`) or a point (`(a)`, `a)`, `14.`)."""

    raw_label: str
    """The label as printed, for example `(a)` or `a)`."""
    label: str | None
    """The normalised label used in provision ids (`a`, `14a`); None for dashes and bullets."""
    children: tuple["Block", ...]
    is_paragraph: bool = False
    is_open: bool = False
    """True where the layout is flat: the blocks that follow belong to this item, up to the next
    open item (consolidated paragraphs, hanging-indent points)."""


Block = Text | Item


def normalise_space(text: str) -> str:
    return " ".join(text.split())


def normalise_label(raw: str) -> str | None:
    """`(a)` → `a`, `„14.` → `14`, `iv)` → `iv`; anything that isn't a point label → None."""
    match = POINT_LABEL_RE.match(raw.strip().strip(QUOTES).strip())
    return match.group(1) if match else None


def _classes(element: HtmlElement) -> set[str]:
    return set((element.get("class") or "").split())


def element_text(element: HtmlElement) -> str:
    """The visible text of an element, without footnote references like `(1)`."""
    parts: list[str] = []
    _collect_text(element, parts)
    text = normalise_space(EMPTY_PARENS_RE.sub("", "".join(parts)))
    return SPACE_BEFORE_PUNCTUATION_RE.sub(r"\1", text)


def _collect_text(element: HtmlElement, parts: list[str]) -> None:
    if element.text:
        parts.append(element.text)
    for child in element:
        if not isinstance(child.tag, str):  # comments and processing instructions
            pass
        elif child.tag == "a" and (child.get("href") or "").startswith("#"):
            pass  # a footnote reference; its tail text is kept below
        elif child.tag == "br":
            parts.append(" ")
        else:
            _collect_text(child, parts)
        if child.tail:
            parts.append(child.tail)


def parse_html(content: bytes) -> HtmlElement:
    """Cellar serves UTF-8; decode as such rather than trust a `<meta>` that may be missing."""
    return html.fromstring(content, parser=html.HTMLParser(encoding="utf-8"))


def blocks_of(element: HtmlElement) -> tuple[Block, ...]:
    """The text lines and list items directly inside `element`, in document order."""
    if not any(child.tag in BLOCK_TAGS for child in element):
        text = element_text(element)
        return (Text(text),) if text else ()
    blocks: list[Block] = []
    if element.text and element.text.strip():
        blocks.append(Text(normalise_space(element.text)))
    for child in element:
        if isinstance(child.tag, str):
            blocks.extend(_blocks_of_child(child))
    return _fold_into_open_items(blocks)


def _fold_into_open_items(blocks: list[Block]) -> tuple[Block, ...]:
    """Attach the blocks that follow an open item to it, up to the next open item or group title.

    The consolidated layout puts only a paragraph's first subparagraph inside its `div.norm`;
    the further subparagraphs and lists follow as siblings (Art. 6(3), points (a)-(d)). Hanging
    points do the same (Annex VII, point 3.1 and its points (a)-(f)).
    """
    folded: list[Block] = []
    for block in blocks:
        last = folded[-1] if folded else None
        is_boundary = (isinstance(block, Item) and block.is_open) or (
            isinstance(block, Text) and block.role != "text"
        )
        if isinstance(last, Item) and last.is_open and not is_boundary:
            folded[-1] = replace(last, children=(*last.children, block))
        else:
            folded.append(block)
    return tuple(folded)


def _blocks_of_child(child: HtmlElement) -> tuple[Block, ...]:
    tag, classes = child.tag, _classes(child)
    if tag == "p":
        return _paragraph_line(child, classes)
    if tag == "table":
        return _table_blocks(child)
    if tag != "div":
        text = element_text(child)
        return (Text(text),) if text else ()
    if "eli-title" in classes:
        return ()
    if "grid-list" in classes:
        return (_grid_item(child),)
    if "oj-enumeration-spacing" in classes:
        return _enumeration_item(child)
    numbered = child.find("span[@class='no-parag']")
    if numbered is not None:
        return (_consolidated_paragraph(child, numbered),)
    if PARAGRAPH_DIV_RE.match(child.get("id") or ""):
        return (_oj_paragraph(child),)
    if "text-indent" in (child.get("style") or ""):
        return _hanging_item(child)
    return blocks_of(child)


def _paragraph_line(p: HtmlElement, classes: set[str]) -> tuple[Block, ...]:
    if classes & SKIPPED_P_CLASSES:
        return ()
    text = element_text(p)
    if not text or text == DELETION_MARK:
        return ()
    if classes & HEADING_P_CLASSES:
        return (Text(text, "heading"),)
    if classes & TITLE_P_CLASSES:
        return (Text(text, "title"),)
    if classes & GROUP_P_CLASSES:
        return (Text(text, "group"),)
    return (Text(text),)


def _item(
    raw_label: str, children: tuple[Block, ...], is_paragraph: bool = False, is_open: bool = False
) -> Item:
    raw = normalise_space(raw_label)
    return Item(raw, normalise_label(raw), children, is_paragraph, is_open)


def _table_blocks(table: HtmlElement) -> tuple[Block, ...]:
    """Rows of two cells whose first cell is a label are list items; any other table is text."""
    rows: list[HtmlElement] = table.xpath("./tr|./tbody/tr")  # not the rows of nested lists
    items = [_label_row(row) for row in rows]
    if rows and all(item is not None for item in items):
        return tuple(item for item in items if item is not None)
    lines = (" | ".join(element_text(cell) for cell in row.findall("td")) for row in rows)
    text = "\n".join(line for line in lines if line.strip(" |"))
    return (Text(text),) if text else ()


def _label_row(row: HtmlElement) -> Item | None:
    cells = row.findall("td")
    while len(cells) > 2 and not element_text(cells[0]):
        cells = cells[1:]  # an empty indentation cell (Annex I)
    if len(cells) != 2:
        return None
    label = element_text(cells[0])
    if len(label) > MAX_LABEL_LENGTH:
        return None
    return _item(label, blocks_of(cells[1]))


def _grid_item(div: HtmlElement) -> Item:
    columns = div.findall("div")
    label = element_text(columns[0]) if columns else ""
    content = columns[1] if len(columns) > 1 else div
    return _item(label, blocks_of(content))


def _enumeration_item(div: HtmlElement) -> tuple[Block, ...]:
    """An OJ numbered line typeset as an inline label `<p>` and a content `<p>` (Annex VI)."""
    parts = [child for child in div if isinstance(child.tag, str)]
    label = element_text(parts[0]) if parts else ""
    if len(parts) < 2 or len(label) > MAX_LABEL_LENGTH:
        return blocks_of(div)
    children: list[Block] = []
    for part in parts[1:]:
        children.extend(_blocks_of_child(part))
    return (_item(label, tuple(children)),)


def _consolidated_paragraph(div: HtmlElement, numbered: HtmlElement) -> Item:
    children: list[Block] = []
    for child in div:
        if child is not numbered and isinstance(child.tag, str):
            children.extend(_blocks_of_child(child))
    return _item(element_text(numbered), tuple(children), is_paragraph=True, is_open=True)


def _oj_paragraph(div: HtmlElement) -> Item:
    """An Official Journal paragraph: strip the number from its first line and use it as label."""
    children = list(blocks_of(div))
    first = children[0] if children else None
    if isinstance(first, Text) and (match := PARAGRAPH_PREFIX_RE.match(first.text)):
        children[0] = Text(first.text[match.end() :])
        return _item(match.group(0), tuple(children), is_paragraph=True)
    number = PARAGRAPH_DIV_RE.match(div.get("id") or "")
    label = str(int(number.group(1))) if number else ""
    return _item(label, tuple(children), is_paragraph=True)


def _hanging_item(div: HtmlElement) -> tuple[Block, ...]:
    blocks = blocks_of(div)
    if len(blocks) == 1 and isinstance(blocks[0], Text):
        match = HANGING_LABEL_RE.match(blocks[0].text)
        if match:
            return (_item(match.group(1), (Text(match.group(2)),), is_open=True),)
    return blocks


def render(blocks: tuple[Block, ...]) -> str:
    """Blocks as plain text, one line per text block, list items prefixed with their label."""
    lines: list[str] = []
    for block in blocks:
        if isinstance(block, Text):
            lines.append(block.text)
        else:
            body = render(block.children)
            lines.append(f"{block.raw_label} {body}" if body else block.raw_label)
    return "\n".join(lines)
