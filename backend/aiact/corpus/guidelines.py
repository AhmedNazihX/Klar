"""Parse the guideline PDFs into chunks: `raw/<doc>.<lang>.pdf` → `parsed/<doc>.<lang>.jsonl`.

`aiact corpus guidelines` reads every PDF entry of `data/manifest.yaml` (`kind: pdf`: the
Commission guidelines and the Code of Practice), checks its sha256, converts it with Docling
(`aiact.corpus.guidelines_pdf`) and writes one JSON line per chunk:
- a **section** chunk is the text under one heading, in reading order; a long section is split
  at block boundaries into several chunks with the same heading. Footnotes stay in the section
  where they are printed. `provision_id` is `guide:<doc>:sec:<n>`, numbered through the document.
- an **example** chunk is one Commission worked example of the high-risk guidelines
  (`aiact.corpus.guideline_examples`, decision 001), with `source_example_id` = `hr-ex-NNN` and
  `provision_id` = `guide:<doc>:ex:<NNN>`. Its text never appears in a section chunk, so the
  `source_example_id` filter removes all of it.

Held-out examples (Pile B) are kept and tagged (decision 012): their chunks carry
`is_held_out: true`, and search excludes them by default. The Pile B IDs come from the `pile_b`
list of `eval/split.json`, the one benchmark file corpus code may read; nothing else in it is
used. Every Pile B ID must be found in the PDFs, or the parse stops (an isolation gap).

Section numbers come from the layout Docling finds, so the EN and DE versions of a guideline can
number their sections differently; example IDs don't depend on the layout.
"""

import json
import logging
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from docling_core.types.doc.document import DoclingDocument
from pydantic import BaseModel, ConfigDict

from aiact.corpus.eurlex import RawFileError, read_raw
from aiact.corpus.fetch import ManifestEntry, load_manifest
from aiact.corpus.files import write_if_changed
from aiact.corpus.guideline_examples import (
    EXAMPLE_DOCS,
    ExampleList,
    Segment,
    extract_examples,
    number_examples,
)
from aiact.corpus.guidelines_pdf import Block, blocks_of, convert_pdf
from aiact.corpus.sources import Language
from aiact.settings import BACKEND_DIR

logger = logging.getLogger(__name__)

ChunkKind = Literal["section", "example"]
Converter = Callable[[bytes, str], DoclingDocument]

DEFAULT_SPLIT_FILE = BACKEND_DIR.parent / "eval" / "split.json"
"""The committed benchmark split; only its `pile_b` list is read."""
EXAMPLE_ID_RE = re.compile(r"^hr-ex-(\d{3})$")
MAX_SECTION_CHARS = 4000
"""A longer section is split into several chunks at block boundaries."""
HEADING_SEPARATOR = " \u203a "
"""Joins nested headings (a single right-pointing angle quote)."""
LANGUAGE_WORDS: dict[Language, frozenset[str]] = {
    "en": frozenset({"the", "and", "of", "to", "is"}),
    "de": frozenset({"der", "die", "und", "das", "ist"}),
}
"""Frequent function words, to check a PDF is in the language the registry says."""
WORD_RE = re.compile(r"[^\W\d_]+")


class GuidelineError(Exception):
    """A guideline can't be parsed as expected (wrong language, unreadable split)."""


class IsolationGapError(GuidelineError):
    """A Pile B example wasn't found in the PDFs, so it couldn't be tagged."""


class GuidelineChunk(BaseModel):
    """One chunk of a guideline in one language: a line of `data/parsed/<doc>.<lang>.jsonl`."""

    model_config = ConfigDict(frozen=True)

    provision_id: str
    """`guide:<doc>:sec:<n>` for a section chunk, `guide:<doc>:ex:<NNN>` for an example."""
    doc: str
    """The manifest id of the document (`guide-prohibited`, `code-of-practice-transparency`)."""
    language: Language
    kind: ChunkKind
    heading: str | None
    """The section heading; for an example, the list heading (and sub-heading) under it."""
    text: str
    """The chunk text as printed; an example's lead-in sentence comes first."""
    page: int
    """The physical PDF page the chunk starts on."""
    source_example_id: str | None = None
    """`hr-ex-NNN` for a worked example (decision 001), None for guideline prose."""
    is_held_out: bool = False
    """True for a Pile B example: stored, but excluded from search by default (decision 012)."""


def load_pile_b(path: Path) -> frozenset[str]:
    """The `pile_b` example IDs of the committed split. Nothing else in the file is used."""
    try:
        ids = json.loads(path.read_text(encoding="utf-8"))["pile_b"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise GuidelineError(f"{path}: no readable `pile_b` list") from error
    if not isinstance(ids, list) or not all(
        isinstance(i, str) and EXAMPLE_ID_RE.match(i) for i in ids
    ):
        raise GuidelineError(f"{path}: `pile_b` must be a list of hr-ex-NNN ids")
    return frozenset(ids)


def pdf_entries(manifest_path: Path) -> tuple[ManifestEntry, ...]:
    """The manifest's PDF entries that exist. A failed fetch (`available: null`) is an error."""
    entries = tuple(e for e in load_manifest(manifest_path).documents if e.kind == "pdf")
    failed = [f"{e.id}.{e.language}" for e in entries if e.available is None]
    if failed:
        raise RawFileError(f"fetch failed for {', '.join(failed)}; re-run `aiact corpus fetch`")
    return tuple(e for e in entries if e.available)


def check_language(blocks: tuple[Block, ...], language: Language, label: str) -> None:
    """Raise if the text reads more like another language than the one the registry names."""
    words = [w.lower() for b in blocks for w in WORD_RE.findall(b.text)]
    hits = {lang: sum(w in markers for w in words) for lang, markers in LANGUAGE_WORDS.items()}
    best = max(hits, key=lambda lang: hits[lang])
    if hits[language] == 0 or best != language:
        raise GuidelineError(f"{label}: the text reads as {best!r}, the manifest says {language!r}")


@dataclass
class _Sections:
    """Builds section chunks while walking a document's segments."""

    doc: str
    language: Language
    chunks: list[GuidelineChunk] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    """Headings seen since the last body block; they head the next section."""
    heading: str | None = None
    body: list[Block] = field(default_factory=list)
    count: int = 0

    def add_heading(self, text: str) -> None:
        if self.body:
            self.flush()
            self.headings = []
        self.headings.append(text)

    def add_body(self, block: Block) -> None:
        if not self.body and self.headings:
            self.heading, self.headings = HEADING_SEPARATOR.join(self.headings), []
        self.body.append(block)

    def flush(self) -> None:
        for part in _parts(self.body):
            self.count += 1
            self.chunks.append(
                GuidelineChunk(
                    provision_id=f"guide:{self.doc}:sec:{self.count}",
                    doc=self.doc,
                    language=self.language,
                    kind="section",
                    heading=self.heading,
                    text="\n\n".join(b.rendered for b in part),
                    page=part[0].page,
                )
            )
        self.body = []

    def context(self) -> str | None:
        """The heading an example list sits under."""
        return HEADING_SEPARATOR.join(self.headings) if self.headings else self.heading


def _parts(blocks: list[Block]) -> Iterator[list[Block]]:
    """`blocks` in runs of at most MAX_SECTION_CHARS (a longer block stays whole)."""
    part: list[Block] = []
    size = 0
    for block in blocks:
        if part and size + len(block.rendered) > MAX_SECTION_CHARS:
            yield part
            part, size = [], 0
        part.append(block)
        size += len(block.rendered)
    if part:
        yield part


def chunk_document(
    doc: str, language: Language, segments: tuple[Segment, ...], held_out: frozenset[str]
) -> tuple[GuidelineChunk, ...]:
    """The chunks of one document, in reading order. Examples must already be numbered."""
    sections = _Sections(doc, language)
    for segment in segments:
        if isinstance(segment, ExampleList):
            sections.flush()
            sections.chunks.extend(_example_chunks(sections, segment, held_out))
        elif segment.kind == "heading":
            sections.add_heading(segment.text)
        else:
            sections.add_body(segment)
    sections.flush()
    return tuple(sections.chunks)


def _example_chunks(
    sections: _Sections, example_list: ExampleList, held_out: frozenset[str]
) -> Iterator[GuidelineChunk]:
    context = sections.context()
    for example in example_list.examples:
        if example.example_id is None:
            raise GuidelineError(f"{sections.doc}: an example on p. {example.page} has no id")
        number = example.example_id.removeprefix("hr-ex-")
        headings = (context, example_list.heading, example.subheading)
        yield GuidelineChunk(
            provision_id=f"guide:{sections.doc}:ex:{number}",
            doc=sections.doc,
            language=sections.language,
            kind="example",
            heading=HEADING_SEPARATOR.join(h for h in headings if h),
            text="\n".join(t for t in (example.lead_in, example.text) if t),
            page=example.page,
            source_example_id=example.example_id,
            is_held_out=example.example_id in held_out,
        )


def check_held_out(chunks: tuple[GuidelineChunk, ...], pile_b: frozenset[str]) -> None:
    """Every Pile B ID must be tagged on an example chunk, or the benchmark could leak."""
    tagged = {c.source_example_id for c in chunks if c.is_held_out}
    missing = sorted(pile_b - tagged)
    if missing:
        raise IsolationGapError(
            f"{len(missing)} Pile B examples not found in the guidelines: {', '.join(missing)}"
        )


def dump_jsonl(chunks: tuple[GuidelineChunk, ...]) -> str:
    return "".join(chunk.model_dump_json() + "\n" for chunk in chunks)


def load_jsonl(path: Path) -> tuple[GuidelineChunk, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return tuple(GuidelineChunk.model_validate_json(line) for line in lines if line)


@dataclass(frozen=True)
class GuidelineReport:
    counts: tuple[tuple[str, int, int], ...] = ()
    """`doc.lang`, its number of chunks and of example chunks, in manifest order."""
    held_out_ids: tuple[str, ...] = ()
    """The Pile B example IDs tagged `is_held_out`, sorted."""
    written: tuple[str, ...] = ()
    """Output files whose content changed."""


def _segments(
    entries: tuple[ManifestEntry, ...], raw_dir: Path, convert: Converter
) -> dict[str, tuple[Segment, ...]]:
    """Each entry's segments, keyed `doc.lang`, with the examples numbered."""
    by_label: dict[str, tuple[Segment, ...]] = {}
    for entry in entries:
        label = f"{entry.id}.{entry.language}"
        blocks = blocks_of(convert(read_raw(entry, raw_dir), entry.file or label))
        check_language(blocks, entry.language, label)
        by_label[label] = extract_examples(entry.id, blocks)
        logger.info("converted %s: %d blocks", label, len(blocks))
    numbered = number_examples({doc: by_label[f"{doc}.en"] for doc in EXAMPLE_DOCS})
    return by_label | {f"{doc}.en": segments for doc, segments in numbered.items()}


def parse_guidelines(
    manifest_path: Path,
    raw_dir: Path,
    out_dir: Path,
    split_path: Path,
    convert: Converter | None = None,
) -> GuidelineReport:
    """Parse every PDF of the manifest; rewrite an output file only if it changed.

    `convert` turns PDF bytes into a Docling document (default: `convert_pdf`). Raises
    `IsolationGapError` before writing anything if a Pile B example isn't found.
    """
    pile_b = load_pile_b(split_path)
    entries = pdf_entries(manifest_path)
    labels = {f"{e.id}.{e.language}" for e in entries}
    missing = [doc for doc in EXAMPLE_DOCS if f"{doc}.en" not in labels]
    if missing:
        raise RawFileError(f"the manifest has no English PDF for {', '.join(missing)}")
    segments = _segments(entries, raw_dir, convert or convert_pdf)
    chunks = {
        f"{e.id}.{e.language}": chunk_document(
            e.id, e.language, segments[f"{e.id}.{e.language}"], pile_b
        )
        for e in entries
    }
    all_chunks = tuple(c for doc_chunks in chunks.values() for c in doc_chunks)
    check_held_out(all_chunks, pile_b)
    written: list[str] = []
    counts: list[tuple[str, int, int]] = []
    for label, doc_chunks in chunks.items():
        path = out_dir / f"{label}.jsonl"
        if write_if_changed(path, dump_jsonl(doc_chunks)):
            written.append(str(path))
        counts.append((label, len(doc_chunks), sum(c.kind == "example" for c in doc_chunks)))
        logger.info("parsed %s: %d chunks, %d examples", *counts[-1])
    held_out_ids = tuple(sorted(c.source_example_id or "" for c in all_chunks if c.is_held_out))
    logger.info("tagged %d Pile B examples: %s", len(held_out_ids), ", ".join(held_out_ids))
    return GuidelineReport(tuple(counts), held_out_ids, tuple(written))
