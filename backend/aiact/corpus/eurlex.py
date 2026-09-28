"""Parse the EUR-Lex laws into provisions: `raw/<doc>.<lang>.html` → `parsed/<doc>.<lang>.jsonl`.

`aiact corpus parse` reads every HTML entry of `data/manifest.yaml`, checks its sha256 against the
manifest (the raw folder is shared by all worktrees), and writes one JSON line per provision:
article > paragraph > point, annex > (section >) point > letter, and recital. Each provision's
text includes the text of its children, so any level can be quoted on its own.

`provision_id`s come only from the structure and the printed numbers, never from wording, so the
English and German versions of a document get the same ids (German labels such as `a)` or `(1)`
are normalised like the English `(a)` and `1.`):
- `art:5`, `art:5:1`, `art:5:1:a`, `art:5:1:c:ii`; points of an article without numbered
  paragraphs sit right under it (`art:3:14`, `art:113:a`);
- `annex:III`, `annex:III:4`, `annex:III:4:a`; an annex divided into sections puts the section in
  between (`annex:VIII:B`, `annex:VIII:B:7`, `annex:VII:3`), and a dotted point drops its section
  number (point 3.1 of Annex VII is `annex:VII:3:1`);
- `recital:53`;
- a list that restarts its labels in a later subparagraph goes, as a whole, under that
  subparagraph's number (`art:43:1:sub2:a` to `art:43:1:sub2:d`), while the first list keeps
  the ids citations use (`art:43:1:a`, `art:43:1:b`).
The consolidated text has no recitals: consolidations leave out the preamble.

The Digital Omnibus is parsed like any act, but it amends the AI Act: the entries of its amending
article carry an `Amendment` (which AI Act provisions change, how, and from when; see
`aiact.corpus.amendments`), and the quoted replacement text stays inside the entry's text instead
of becoming provisions of the Omnibus.
"""

import logging
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lxml.html import HtmlElement
from pydantic import BaseModel, ConfigDict

from aiact.corpus.amendments import (
    AmendingContext,
    Amendment,
    amending_context,
    amendment_for,
    is_instruction_group,
)
from aiact.corpus.eurlex_html import Block, Item, Text, blocks_of, parse_html, render
from aiact.corpus.fetch import ManifestEntry, load_manifest, sha256_of
from aiact.corpus.files import write_atomic
from aiact.corpus.sources import Language
from aiact.settings import DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)

ProvisionKind = Literal["article", "paragraph", "point", "annex", "section", "recital"]

DEFAULT_PARSED_DIR = DEFAULT_DATA_DIR / "parsed"
"""The committed parse output in this checkout (raw files are read from the shared data dir)."""
AI_ACT_DOC = "ai-act"
"""The original AI Act: its provision ids are what the Omnibus amendments resolve against."""
ARTICLE_ID_RE = re.compile(r"^art_(\d+[a-z]*)$")
ANNEX_ID_RE = re.compile(r"^anx_([IVXL]+)$")
RECITAL_ID_RE = re.compile(r"^rct_(\d+)$")
SECTION_RE = re.compile(r"^(?:Section|Abschnitt|SECTION|ABSCHNITT)\s+([A-Z0-9]+)\b")
NUMBERED_GROUP_RE = re.compile(r"^(\d+)\.\s+\S")


class ParseError(Exception):
    """The HTML doesn't have the structure the parser expects (for example a duplicate id)."""


class RawFileError(Exception):
    """A raw file wasn't fetched, or doesn't match the sha256 the manifest recorded for it."""


class ParsedProvision(BaseModel):
    """One addressable unit of a law in one language: a line of `data/parsed/<doc>.<lang>.jsonl`."""

    model_config = ConfigDict(frozen=True)

    provision_id: str
    """Language-independent id, identical across EN and DE: `art:5:1:a`, `annex:III:4:a`."""
    doc: str
    """The manifest id of the document (`ai-act`, `omnibus`, `ai-act-consolidated`)."""
    language: Language
    kind: ProvisionKind
    parent_id: str | None
    heading: str | None
    """The title of the article or annex the unit belongs to; None for recitals."""
    text: str
    """The unit's full text, its children's text included (their labels kept)."""
    amendment: Amendment | None = None
    """Set on the entries of an amending act (the Omnibus): what they change in the AI Act."""


@dataclass(frozen=True)
class _Scope:
    """Where the units being built sit: their document, heading and how deep to descend."""

    doc: str
    language: Language
    heading: str | None
    descend: Callable[[Item], bool]
    amending: AmendingContext | None = None


def _always(_: Item) -> bool:
    return True


def _row(
    scope: _Scope, pid: str, kind: ProvisionKind, parent: str | None, text: str
) -> ParsedProvision:
    return ParsedProvision(
        provision_id=pid,
        doc=scope.doc,
        language=scope.language,
        kind=kind,
        parent_id=parent,
        heading=scope.heading,
        text=text,
    )


def _units(
    scope: _Scope, parent: str, blocks: tuple[Block, ...], chain: tuple[str, ...] = ()
) -> Iterator[ParsedProvision]:
    """Provisions for the labelled items in `blocks`, depth first, in document order."""
    for pid, block in _item_ids(parent, blocks):
        kind: ProvisionKind = "paragraph" if block.is_paragraph else "point"
        row = _row(scope, pid, kind, parent, render(block.children))
        instruction = _first_text(block.children)
        if scope.amending is not None and not scope.descend(block):
            amendment = amendment_for(scope.amending, (*chain, instruction), block.children)
            yield row.model_copy(update={"amendment": amendment})
            continue
        yield row
        if scope.descend(block):
            yield from _units(scope, pid, block.children, (*chain, instruction))


def _item_ids(parent: str, blocks: tuple[Block, ...]) -> Iterator[tuple[str, Item]]:
    """Each labelled item with its id. A list that restarts its labels in a later subparagraph
    (Art. 43(1) has points (a)-(b), then a second subparagraph with points (a)-(d)) puts the whole
    of that list under the subparagraph's number: `art:43:1:sub2:a` to `art:43:1:sub2:d`. The
    first list keeps the plain ids that citations use (`art:6:3:a`)."""
    seen: set[str] = set()
    for subparagraph, items in _lists(parent, blocks):
        labels = [label for label, _ in items]
        prefix = f"{parent}:sub{subparagraph}" if seen.intersection(labels) else parent
        seen.update(labels)
        for label, item in items:
            yield f"{prefix}:{label}", item


def _lists(parent: str, blocks: tuple[Block, ...]) -> Iterator[tuple[int, list[tuple[str, Item]]]]:
    """The labelled items of `blocks`, grouped into lists: a run of items between text lines.

    Each list comes with the number of the subparagraph it belongs to (text lines so far).
    """
    subparagraph = 0
    items: list[tuple[str, Item]] = []
    for block in blocks:
        if isinstance(block, Text):
            if block.role != "text":
                continue
            if items:
                yield subparagraph, items
                items = []
            subparagraph += 1
        elif block.label is not None:
            items.append((_local_label(parent, block.label), block))
    if items:
        yield subparagraph, items


def _local_label(parent: str, label: str) -> str:
    """`3.1` under `annex:VII:3` is point `1` of that section: `annex:VII:3:1`."""
    head, _, rest = label.partition(".")
    return rest if rest and parent.rsplit(":", 1)[-1] == head else label


def _first_text(blocks: tuple[Block, ...]) -> str:
    return next((b.text for b in blocks if isinstance(b, Text)), "")


def _has_role(block: Block, role: str) -> bool:
    return isinstance(block, Text) and block.role == role


def _article_heading(div: HtmlElement, blocks: tuple[Block, ...], number: str) -> str:
    """`Article 5 — Prohibited AI practices`, from the number line and the `eli-title` div."""
    title = next((b.text for b in blocks if isinstance(b, Text) and b.role == "title"), number)
    subtitle_div = div.find("div[@class='eli-title']")
    subtitle = "" if subtitle_div is None else _first_text(blocks_of(subtitle_div))
    return f"{title} — {subtitle}" if subtitle else title


def _descend_into_instructions(language: Language) -> Callable[[Item], bool]:
    """In an amending article, descend only into items that list further instructions."""

    def descend(item: Item) -> bool:
        return is_instruction_group(_first_text(item.children), item.children, language)

    return descend


def _article(
    div: HtmlElement, number: str, doc: str, language: Language, amended_ids: frozenset[str]
) -> Iterator[ParsedProvision]:
    all_blocks = blocks_of(div)
    blocks = tuple(b for b in all_blocks if not _has_role(b, "title"))
    intro = _first_text(blocks)
    is_amending = is_instruction_group(intro, blocks, language)
    context = amending_context(intro, language, div, amended_ids)
    if context is not None and not amended_ids:
        raise ParseError(
            f"{doc}.{language} amends the AI Act, but no AI Act provision ids were given for "
            f"{language}; parse the AI Act ({AI_ACT_DOC}.{language}) first"
        )
    scope = _Scope(
        doc,
        language,
        _article_heading(div, all_blocks, number),
        _descend_into_instructions(language) if is_amending else _always,
        context,
    )
    pid = f"art:{number}"
    yield _row(scope, pid, "article", None, render(blocks))
    yield from _units(scope, pid, blocks)


def _annex(
    div: HtmlElement, number: str, doc: str, language: Language
) -> Iterator[ParsedProvision]:
    blocks = blocks_of(div)
    titles = [b.text for b in blocks if isinstance(b, Text) and b.role == "heading"]
    body = tuple(b for b in blocks if not _has_role(b, "heading"))
    scope = _Scope(doc, language, " — ".join(titles) or None, _always)
    pid = f"annex:{number}"
    yield _row(scope, pid, "annex", None, render(body))
    for section, section_blocks in _sections(body):
        if section is None:
            yield from _units(scope, pid, section_blocks)
            continue
        section_id = f"{pid}:{section}"
        yield _row(scope, section_id, "section", pid, render(section_blocks))
        yield from _units(scope, section_id, section_blocks)


def _section_label(block: Block) -> str | None:
    if not isinstance(block, Text) or block.role != "group":
        return None
    match = SECTION_RE.match(block.text) or NUMBERED_GROUP_RE.match(block.text)
    return match.group(1) if match else None


def _sections(blocks: tuple[Block, ...]) -> list[tuple[str | None, tuple[Block, ...]]]:
    """Split an annex body at its section titles; blocks before the first title get None."""
    groups: list[tuple[str | None, list[Block]]] = [(None, [])]
    for block in blocks:
        label = _section_label(block)
        if label is not None:
            groups.append((label, []))
        groups[-1][1].append(block)
    return [(label, tuple(items)) for label, items in groups if items]


def _recital(div: HtmlElement, number: str, doc: str, language: Language) -> ParsedProvision:
    blocks = blocks_of(div)
    first = blocks[0] if len(blocks) == 1 else None
    text = render(first.children) if isinstance(first, Item) else render(blocks)
    scope = _Scope(doc, language, None, _always)
    return _row(scope, f"recital:{number}", "recital", None, text)


def parse_document(
    content: bytes, doc: str, language: Language, amended_ids: frozenset[str] = frozenset()
) -> tuple[ParsedProvision, ...]:
    """Every provision of one EUR-Lex XHTML document, in document order.

    `amended_ids` are the AI Act's provision ids in `language`; an amending act resolves its
    targets against them and can't be parsed without them. Raises `ParseError` if they are
    missing for an amending act, if two units get the same id, or if no unit is found.
    """
    root = parse_html(content)
    rows: list[ParsedProvision] = []
    for div in root.iter("div"):
        div_id = div.get("id") or ""
        if match := ARTICLE_ID_RE.match(div_id):
            rows.extend(_article(div, match.group(1), doc, language, amended_ids))
        elif match := ANNEX_ID_RE.match(div_id):
            rows.extend(_annex(div, match.group(1), doc, language))
        elif match := RECITAL_ID_RE.match(div_id):
            rows.append(_recital(div, match.group(1), doc, language))
    _check_unique(rows, f"{doc}.{language}")
    return tuple(rows)


def _check_unique(rows: list[ParsedProvision], label: str) -> None:
    if not rows:
        raise ParseError(f"{label}: no articles, annexes or recitals found")
    seen: set[str] = set()
    for row in rows:
        if row.provision_id in seen:
            raise ParseError(f"{label}: duplicate provision_id {row.provision_id}")
        seen.add(row.provision_id)


def dump_jsonl(rows: tuple[ParsedProvision, ...]) -> str:
    return "".join(row.model_dump_json() + "\n" for row in rows)


def load_jsonl(path: Path) -> tuple[ParsedProvision, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return tuple(ParsedProvision.model_validate_json(line) for line in lines if line)


@dataclass(frozen=True)
class ParseReport:
    counts: tuple[tuple[str, int], ...] = ()
    """`doc.lang` and its number of provisions, in manifest order."""
    written: tuple[str, ...] = ()
    """Output files whose content changed."""


def read_raw(entry: ManifestEntry, raw_dir: Path) -> bytes:
    """The raw file of a downloaded entry, after checking it against the manifest's sha256."""
    if entry.file is None:
        raise RawFileError(f"{entry.id}.{entry.language}: the manifest records no file")
    content = (raw_dir / entry.file).read_bytes()
    if sha256_of(content) != entry.sha256:
        raise RawFileError(
            f"{entry.file}: sha256 differs from the manifest; re-run `aiact corpus fetch`"
        )
    return content


def html_entries(manifest_path: Path) -> tuple[ManifestEntry, ...]:
    """The manifest's HTML entries that exist. A failed fetch (`available: null`) is an error."""
    entries = tuple(e for e in load_manifest(manifest_path).documents if e.kind == "html")
    failed = [f"{e.id}.{e.language}" for e in entries if e.available is None]
    if failed:
        raise RawFileError(f"fetch failed for {', '.join(failed)}; re-run `aiact corpus fetch`")
    return tuple(e for e in entries if e.available)


def _write_if_changed(path: Path, text: str) -> bool:
    """Write `text` via a temporary file and rename, unless the file already holds it."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    write_atomic(path, text.encode("utf-8"))
    return True


def _ai_act_first(entries: tuple[ManifestEntry, ...]) -> list[ManifestEntry]:
    """The AI Act comes first, so its ids are known when the Omnibus is parsed."""
    return sorted(entries, key=lambda e: e.id != AI_ACT_DOC)


def parse_all(manifest_path: Path, raw_dir: Path, out_dir: Path) -> ParseReport:
    """Parse every HTML document of the manifest; rewrite an output file only if it changed."""
    entries = html_entries(manifest_path)
    amended_ids: dict[Language, frozenset[str]] = {}
    counts: dict[str, int] = {}
    written: list[str] = []
    for entry in _ai_act_first(entries):
        rows = parse_document(
            read_raw(entry, raw_dir),
            entry.id,
            entry.language,
            amended_ids.get(entry.language, frozenset()),
        )
        if entry.id == AI_ACT_DOC:
            amended_ids[entry.language] = frozenset(row.provision_id for row in rows)
        label = f"{entry.id}.{entry.language}"
        counts[label] = len(rows)
        path = out_dir / f"{label}.jsonl"
        if _write_if_changed(path, dump_jsonl(rows)):
            written.append(str(path))
        logger.info("parsed %s: %d provisions", label, len(rows))
    ordered = tuple((f"{e.id}.{e.language}", counts[f"{e.id}.{e.language}"]) for e in entries)
    return ParseReport(ordered, tuple(written))
