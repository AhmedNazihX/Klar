"""Build the rows `aiact corpus load` writes: one `DocumentLoad` per manifest entry and language.

Reads only `data/manifest.yaml` and the parsed JSONL (`data/parsed/<doc>.<lang>.jsonl`); nothing
here touches the database (that is `aiact.corpus.load`). The rules are decision 009's:
- The original AI Act (`law_version = 'original'`) has one open-ended slice per provision from
  the AI Act's entry into force, 2024-08-01.
- The consolidated text (`'amended'`) carries the full history (decision 014). A difference
  between the original and the consolidation that the Digital Omnibus doesn't explain (no
  amendment targets the provision, an ancestor, a descendant or a neighbour, see
  `corrected_original`) is a corrigendum, which applies from the start. Corrigenda are pinned:
  one that isn't in `CORRIGENDA` fails the load: the "corrected original" is the original with every
  corrigendum's consolidated text put in, in the provision and in the text of each of its
  ancestors. A provision whose
  corrected original still differs from the consolidation gets two slices, split at the
  Omnibus's entry into force (`amendment.in_force_from`, 2026-07-27): the corrected original
  before, the consolidated text after. Its descendants are split too (both slices from their
  own corrected original and consolidated text), so a slice's parent always covers the same
  dates. A provision the Omnibus deleted keeps only the old slice, an inserted one only the new.
  Every other provision has one slice from 2024-08-01 with the consolidated text. The
  consolidation has no recitals; they stay in the original.
- Deferred application dates inside an amendment (`amendment.dates`, such as 2 December 2026 for
  the new Art. 5(1) points) are not slice boundaries: the text is law from 2026-07-27, and when a
  rule starts to apply is what the text itself says (decision 014).
- The Omnibus is an amending act (`is_amending`, no `law_version`), one slice per entry from its
  entry into force. Guidance has one slice per chunk from its `published_on`.
- EN and DE are linked by `provision_id`, which the parsers make language-independent.

Guideline chunks keep `source_example_id` and `is_held_out` (decision 012). Every guideline whose
last printed paragraph is known is checked against it, and every `para:<n>` chunk must start with
its number, so a numbering slip in the parse fails the load instead of mislinking EN and DE.
"""

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from typing import Literal

from aiact.corpus import guidelines
from aiact.corpus.eurlex import AI_ACT_DOC, ParsedProvision
from aiact.corpus.eurlex import load_jsonl as load_law_jsonl
from aiact.corpus.fetch import ManifestEntry, load_manifest
from aiact.corpus.guidelines import GuidelineChunk
from aiact.corpus.sources import Language

DocType = Literal["law", "guideline", "code"]
DocumentStatus = Literal["final", "draft", "consolidated"]
LawVersion = Literal["original", "amended"]

CONSOLIDATED_DOC = "ai-act-consolidated"
OMNIBUS_DOC = "omnibus"
CODE_PREFIX = "code-"
LAW_VERSIONS: dict[str, LawVersion] = {AI_ACT_DOC: "original", CONSOLIDATED_DOC: "amended"}
AI_ACT_IN_FORCE = date(2024, 8, 1)
"""Art. 113: the twentieth day after publication in the Official Journal (12 July 2024)."""
LAST_PARAGRAPH: dict[str, int] = {
    "guide-prohibited": 433,
    "guide-definition": 64,
    "guide-high-risk-annex-iii": 447,
    "guide-high-risk-general": 451,
    "guide-high-risk-annex-i": 62,
}
"""The last numbered paragraph as printed in each guideline (read off the PDFs in C2's review)."""
CORRIGENDA: dict[Language, dict[str, str]] = {
    "en": {
        "art:1": "title: the Official Journal HTML prints a stray backtick (Subject matter`)",
        "art:108": 'amends Reg. 2018/1139: the consolidation adds a stray ";" line after a quote',
        "art:108:2": 'the same stray ";" line as art:108',
        "art:108:3": 'the same stray ";" line as art:108',
        "art:108:4": 'the same stray ";" line as art:108',
    },
    "de": {
        "art:3:40": "the Official Journal text lacks 'nicht' (sofern es sich nicht um ...)",
    },
}
"""The reviewed corrigenda (decision 014): units, or article titles, that differ between the
original and the consolidation without an Omnibus amendment. Any other such difference fails the
load. Heading-only differences of Art. 1's units follow from the Art. 1 title entry."""
DIFF_CONTEXT = 30
"""Characters shown on each side of the first difference in an unexpected-corrigendum error."""
PARAGRAPH_ID_RE = re.compile(r":para:(\d+)$")
STATUS: dict[str, DocumentStatus] = {
    "law": "final",
    "consolidated": "consolidated",
    "final": "final",
    "draft": "draft",
}
"""Manifest status → `documents.status` (an Official Journal act is final)."""


class LoadError(Exception):
    """The parsed files can't be loaded as they are (missing, inconsistent or misnumbered)."""


@dataclass(frozen=True)
class DocumentRow:
    """One `documents` row."""

    doc_key: str
    title: str
    celex: str | None
    doc_type: DocType
    is_amending: bool
    status: DocumentStatus
    law_version: LawVersion | None
    language: Language
    published_on: date | None
    in_force_from: date | None
    source_url: str
    sha256: str


@dataclass(frozen=True)
class ProvisionRow:
    """One `provisions` row (one time slice). The parent is named by its `provision_id` and the
    `valid_from` of the parent slice that covers this one."""

    provision_id: str
    parent_id: str | None
    parent_valid_from: date | None
    heading: str | None
    text: str
    valid_from: date
    valid_to: date | None = None
    source_example_id: str | None = None
    is_held_out: bool = False


@dataclass(frozen=True)
class DocumentLoad:
    """A document and its provisions, parents before their children."""

    document: DocumentRow
    provisions: tuple[ProvisionRow, ...]

    @property
    def label(self) -> str:
        return f"{self.document.doc_key}.{self.document.language}"

    @property
    def load_sha256(self) -> str:
        """sha256 of the provision rows, for skipping an unchanged document on reload."""
        rows = [asdict(row) for row in self.provisions]
        payload = json.dumps(rows, default=str, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Unit:
    """A parsed unit reduced to what a slice needs."""

    provision_id: str
    parent_id: str | None
    heading: str | None
    text: str


def _unit(row: ParsedProvision) -> _Unit:
    return _Unit(row.provision_id, row.parent_id, row.heading, row.text)


def _open_slices(units: Iterable[_Unit], valid_from: date) -> tuple[ProvisionRow, ...]:
    return tuple(
        ProvisionRow(
            u.provision_id,
            u.parent_id,
            None if u.parent_id is None else valid_from,
            u.heading,
            u.text,
            valid_from,
        )
        for u in units
    )


def omnibus_in_force(rows: tuple[ParsedProvision, ...]) -> tuple[date, frozenset[str]]:
    """The Omnibus's entry into force and every AI Act provision id its amendments target."""
    amendments = [row.amendment for row in rows if row.amendment is not None]
    dates = {a.in_force_from for a in amendments}
    if len(dates) != 1 or None in dates:
        raise LoadError(
            f"omnibus: expected one entry-into-force date, found {sorted(map(str, dates))}"
        )
    (in_force,) = dates
    assert in_force is not None
    return in_force, frozenset(t for a in amendments for t in a.targets)


def _is_touched(provision_id: str, targets: frozenset[str]) -> bool:
    """True if a target is this provision, one of its ancestors or one of its descendants."""
    return any(
        t == provision_id or provision_id.startswith(t + ":") or t.startswith(provision_id + ":")
        for t in targets
    )


def _content(unit: _Unit) -> tuple[str | None, str]:
    return unit.heading, unit.text


def _children(units: dict[str, _Unit]) -> dict[str, list[str]]:
    """Each parent's children, in document order."""
    children: dict[str, list[str]] = {}
    for pid, unit in units.items():
        if unit.parent_id is not None:
            children.setdefault(unit.parent_id, []).append(pid)
    return children


def _neighbours(children: dict[str, list[str]], targets: frozenset[str]) -> set[str]:
    """The siblings right before and after each target, and the second-to-last point of a list
    whose last point is a target. Inserting or deleting a point changes its neighbours' closing
    punctuation or moves a trailing "and"/"or" (to the second-to-last point when a point is
    appended or the last one deleted), so they are touched."""
    found: set[str] = set()
    for siblings in children.values():
        for i, pid in enumerate(siblings):
            if pid not in targets:
                continue
            is_last = i == len(siblings) - 1
            start = max(i - (2 if is_last else 1), 0)
            found.update(siblings[start:i] + siblings[i + 1 : i + 2])
    return found


def _diff(before: str | None, after: str | None) -> str:
    """The first difference between two texts, with a little context on each side."""
    before, after = before or "", after or ""
    first = next(
        (i for i, (b, a) in enumerate(zip(before, after, strict=False)) if b != a),
        min(len(before), len(after)),
    )
    start = max(first - DIFF_CONTEXT, 0)
    end = first + DIFF_CONTEXT
    return f"{before[start:end]!r} -> {after[start:end]!r}"


def _check_corrigendum(pid: str, what: str, diff: str, corrigenda: frozenset[str]) -> None:
    if pid not in corrigenda:
        raise LoadError(
            f"{CONSOLIDATED_DOC}: unexpected corrigendum {pid} ({what}: {diff}); the Omnibus "
            "doesn't explain it. Check it and add it to aiact.corpus.build.CORRIGENDA, or fix "
            "the parse"
        )


def corrected_original(
    old: dict[str, _Unit],
    new: dict[str, _Unit],
    targets: frozenset[str],
    corrigenda: frozenset[str],
) -> dict[str, _Unit]:
    """The original units with every corrigendum applied: a unit that differs from the
    consolidation although the Omnibus doesn't touch it (no target is the unit, an ancestor, a
    descendant, an adjacent sibling or an ancestor's adjacent sibling) takes the consolidated
    unit, and each ancestor's text takes its corrected child's text in place of the old one. An
    article's or annex's heading is shared by all its units, so a heading corrigendum (the title
    changed, but the Omnibus doesn't target the article itself) is applied to all of them.

    Every corrigendum must be one of `corrigenda` (the reviewed ones, `CORRIGENDA`); any other
    raises `LoadError` naming the unit and the difference, so a person decides."""
    children = _children(old)
    headings = {
        pid: new[pid].heading
        for pid, unit in old.items()
        if unit.parent_id is None and pid in new and pid not in targets
        if unit.heading != new[pid].heading
    }
    for pid, heading in headings.items():
        _check_corrigendum(pid, "title", _diff(old[pid].heading, heading), corrigenda)
    neighbours = _neighbours(children, targets) | _neighbours(_children(new), targets)
    corrected: dict[str, _Unit] = {}

    def is_touched(pid: str) -> bool:
        """A target is the unit, an ancestor or a descendant, or the unit or an ancestor is a
        target's neighbour (the "; or" lands on a neighbour's last sub-point)."""
        if _is_touched(pid, targets):
            return True
        ancestor: str | None = pid
        while ancestor is not None:
            if ancestor in neighbours:
                return True
            ancestor = old[ancestor].parent_id if ancestor in old else None
        return False

    def correct(pid: str, heading: str | None = None) -> _Unit:
        if pid in corrected:
            return corrected[pid]
        heading = headings.get(pid, heading)
        unit, after = old[pid], new.get(pid)
        if heading is not None:
            unit = replace(unit, heading=heading)
        is_corrigendum = (
            after is not None and _content(unit) != _content(after) and not is_touched(pid)
        )
        if is_corrigendum:
            assert after is not None
            is_text = unit.text != after.text
            diff = _diff(unit.text, after.text) if is_text else _diff(unit.heading, after.heading)
            _check_corrigendum(pid, "text" if is_text else "heading", diff, corrigenda)
            result = after
        else:
            text = unit.text
            for child in children.get(pid, []):
                fixed = correct(child, heading).text
                if fixed != old[child].text:
                    text = _replace_once(text, old[child].text, fixed, f"{pid} > {child}")
            result = replace(unit, text=text)
        corrected[pid] = result
        return result

    return {pid: correct(pid) for pid in old}


def _replace_once(text: str, old: str, new: str, where: str) -> str:
    """`text` with its one copy of `old` replaced; fails when `old` isn't there exactly once."""
    count = text.count(old)
    if count != 1:
        raise LoadError(
            f"{CONSOLIDATED_DOC}: corrigendum {where} found {count} times in the parent"
        )
    return text.replace(old, new)


def amended_slices(
    original: tuple[ParsedProvision, ...],
    consolidated: tuple[ParsedProvision, ...],
    in_force: date,
    targets: frozenset[str],
    corrigenda: frozenset[str],
) -> tuple[ProvisionRow, ...]:
    """The consolidated document's full history (see the module docstring); `corrigenda` are
    the reviewed units that may differ without an amendment."""
    new = {r.provision_id: _unit(r) for r in consolidated}
    originals = {r.provision_id: _unit(r) for r in original if r.kind != "recital"}
    old = corrected_original(originals, new, targets, corrigenda)
    parents = {pid: u.parent_id for pid, u in (old | new).items()}

    def is_changed(pid: str) -> bool:
        before, after = old.get(pid), new.get(pid)
        return before is None or after is None or _content(before) != _content(after)

    def is_split(pid: str | None) -> bool:
        if pid is None:
            return False
        if pid not in parents:
            raise LoadError(f"{CONSOLIDATED_DOC}: parent {pid} is not a provision of either text")
        return is_changed(pid) or is_split(parents[pid])

    # Parents come before their children: the consolidated order, then the deleted provisions.
    order = [*new, *(pid for pid in old if pid not in new)]
    rows: list[ProvisionRow] = []
    for pid in order:
        if not is_split(pid):
            rows.extend(_open_slices([new[pid]], AI_ACT_IN_FORCE))
            continue
        if pid in old:
            u = old[pid]
            parent_from = None if u.parent_id is None else AI_ACT_IN_FORCE
            rows.append(
                ProvisionRow(
                    pid, u.parent_id, parent_from, u.heading, u.text, AI_ACT_IN_FORCE, in_force
                )
            )
        if pid in new:
            u = new[pid]
            # A split parent's new slice starts with this one; an unsplit parent spans both.
            parent_from = None
            if u.parent_id is not None:
                parent_from = in_force if is_split(u.parent_id) else AI_ACT_IN_FORCE
            rows.append(ProvisionRow(pid, u.parent_id, parent_from, u.heading, u.text, in_force))
    _check_parents(rows, CONSOLIDATED_DOC)
    return tuple(rows)


def _check_parents(rows: list[ProvisionRow], label: str) -> None:
    """Every parent slice exists and covers its child's dates."""
    slices = {(r.provision_id, r.valid_from): r for r in rows}
    for row in rows:
        if row.parent_id is None:
            continue
        assert row.parent_valid_from is not None
        parent = slices.get((row.parent_id, row.parent_valid_from))
        if parent is None:
            raise LoadError(f"{label}: {row.provision_id} has no parent slice {row.parent_id}")
        ends_inside = parent.valid_to is None or (
            row.valid_to is not None and row.valid_to <= parent.valid_to
        )
        if row.valid_from < parent.valid_from or not ends_inside:
            raise LoadError(f"{label}: {row.provision_id} outlives its parent {row.parent_id}")


def check_paragraphs(chunks: tuple[GuidelineChunk, ...], label: str) -> None:
    """Each `para:<n>` chunk starts with its number, and the last `n` is the printed last one."""
    numbers: list[int] = []
    for chunk in chunks:
        match = PARAGRAPH_ID_RE.search(chunk.provision_id)
        if match is None:
            continue
        number = match.group(1)
        if not re.match(rf"^\(?{number}[.)]", chunk.text):
            raise LoadError(f"{label}: {chunk.provision_id} doesn't start with paragraph {number}")
        numbers.append(int(number))
    expected = LAST_PARAGRAPH.get(chunks[0].doc) if chunks else None
    if expected is not None and max(numbers, default=None) != expected:
        raise LoadError(
            f"{label}: last paragraph is {max(numbers, default=None)}, the PDF prints {expected}; "
            "the parse took a quoted number run as the numbering (re-run `aiact corpus guidelines`)"
        )


def guideline_rows(
    chunks: tuple[GuidelineChunk, ...], valid_from: date
) -> tuple[ProvisionRow, ...]:
    return tuple(
        ProvisionRow(
            provision_id=c.provision_id,
            parent_id=None,
            parent_valid_from=None,
            heading=c.heading,
            text=c.text,
            valid_from=valid_from,
            source_example_id=c.source_example_id,
            is_held_out=c.is_held_out,
        )
        for c in chunks
    )


def document_row(entry: ManifestEntry, in_force: date | None) -> DocumentRow:
    """The `documents` row of a manifest entry; `in_force` is the Omnibus's entry into force."""
    if entry.sha256 is None:
        raise LoadError(f"{entry.id}.{entry.language}: the manifest records no sha256")
    is_law = entry.kind == "html"
    law_version = LAW_VERSIONS.get(entry.id)
    if is_law and law_version is None and entry.id != OMNIBUS_DOC:
        raise LoadError(f"{entry.id}: an unknown law; add it to aiact.corpus.build")
    doc_type: DocType = (
        "law" if is_law else "code" if entry.id.startswith(CODE_PREFIX) else "guideline"
    )
    return DocumentRow(
        doc_key=entry.id,
        title=entry.title,
        celex=entry.celex,
        doc_type=doc_type,
        is_amending=entry.id == OMNIBUS_DOC,
        status=STATUS[entry.status],
        law_version=law_version,
        language=entry.language,
        published_on=date.fromisoformat(entry.version),
        in_force_from=in_force if entry.id == OMNIBUS_DOC else AI_ACT_IN_FORCE if is_law else None,
        source_url=entry.source_page,
        sha256=entry.sha256,
    )


def _parsed_path(parsed_dir: Path, doc: str, language: Language) -> Path:
    path = parsed_dir / f"{doc}.{language}.jsonl"
    if not path.exists():
        raise LoadError(f"{path} is missing; run `aiact corpus parse` or `aiact corpus guidelines`")
    return path


def _laws(parsed_dir: Path, language: Language) -> dict[str, tuple[ParsedProvision, ...]]:
    """The three parsed laws of one language: the amended text is built from all of them."""
    names = (AI_ACT_DOC, CONSOLIDATED_DOC, OMNIBUS_DOC)
    return {name: load_law_jsonl(_parsed_path(parsed_dir, name, language)) for name in names}


def build_all(manifest_path: Path, parsed_dir: Path) -> tuple[DocumentLoad, ...]:
    """Every available manifest entry as a `DocumentLoad`, in manifest order."""
    manifest = load_manifest(manifest_path)
    failed = [f"{e.id}.{e.language}" for e in manifest.documents if e.available is None]
    if failed:
        raise LoadError(f"fetch failed for {', '.join(failed)}; re-run `aiact corpus fetch`")
    return tuple(_build(e, parsed_dir) for e in manifest.documents if e.available)


def _build(entry: ManifestEntry, parsed_dir: Path) -> DocumentLoad:
    label = f"{entry.id}.{entry.language}"
    if entry.kind == "pdf":
        chunks = guidelines.load_jsonl(_parsed_path(parsed_dir, entry.id, entry.language))
        check_paragraphs(chunks, label)
        document = document_row(entry, None)
        return DocumentLoad(document, guideline_rows(chunks, date.fromisoformat(entry.version)))
    laws = _laws(parsed_dir, entry.language)
    in_force, targets = omnibus_in_force(laws[OMNIBUS_DOC])
    document = document_row(entry, in_force)
    if entry.id == CONSOLIDATED_DOC:
        corrigenda = frozenset(CORRIGENDA[entry.language])
        slices = amended_slices(laws[AI_ACT_DOC], laws[entry.id], in_force, targets, corrigenda)
    else:
        start = in_force if entry.id == OMNIBUS_DOC else AI_ACT_IN_FORCE
        slices = _open_slices(map(_unit, laws[entry.id]), start)
    return DocumentLoad(document, slices)
