"""Guideline chunks: a run over hand-made documents, and the committed `data/parsed/guide-*`.

The committed-output tests are the story's isolation check: every Pile B example of
`eval/split.json` (its `pile_b` list is the only part read) is present and tagged held out, and
no held-out example text sits in an untagged chunk.
"""

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from docling_core.types.doc.base import BoundingBox
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel
from typer.testing import CliRunner

from aiact import cli
from aiact.corpus import guidelines
from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, RawFileError
from aiact.corpus.fetch import DEFAULT_MANIFEST
from aiact.corpus.guideline_examples import ANNEX_I_DOC, ANNEX_III_DOC, LIST_SIZES
from aiact.corpus.guidelines import (
    DEFAULT_SPLIT_FILE,
    GuidelineChunk,
    GuidelineError,
    IsolationGapError,
    check_language,
    load_jsonl,
    load_pile_b,
    parse_guidelines,
    pdf_entries,
)
from aiact.corpus.guidelines_pdf import Block
from aiact.corpus.sources import Language

EXAMPLE_COUNT = 307
MIN_QUOTED_LINE = 40
"""Shorter lines ("AI system for office space optimization") can recur in running text."""


def on_page(page: int) -> ProvenanceItem:
    return ProvenanceItem(page_no=page, bbox=BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, 1))


def annex_i() -> DoclingDocument:
    document = DoclingDocument(name=ANNEX_I_DOC)
    document.add_heading("2.2.2 Safety components", prov=on_page(8))
    items = [
        ("(42)", "An AI system does not fulfil a safety function where it only optimises the use."),
        ("(43)", "By way of illustration, an optimiser is one. Conversely, a scheduler is not."),
        ("(49)", "By way of example, a smart thermostat is not a safety component of the product."),
    ]
    for marker, text in items:
        group = document.add_list_group()
        document.add_list_item(text, enumerated=True, marker=marker, parent=group, prov=on_page(8))
    return document


def annex_iii() -> DoclingDocument:
    document = DoclingDocument(name=ANNEX_III_DOC)
    document.add_heading("3.2.1. The supply of water", prov=on_page(45))
    document.add_text(
        DocItemLabel.TEXT, "The use case covers the supply of water.", prov=on_page(45)
    )
    document.add_heading("a) Practical examples of AI systems falling within", prov=on_page(45))
    group = document.add_list_group()
    for text in ("A pressure sensor in water monitoring.", "A sewage overflow predictor."):
        document.add_list_item(text, marker="-", parent=group, prov=on_page(45))
    document.add_heading("3.2.2. The supply of gas", prov=on_page(46))
    document.add_text(
        DocItemLabel.TEXT, "The gas use case is narrower than that.", prov=on_page(46)
    )
    return document


def german() -> DoclingDocument:
    document = DoclingDocument(name="guide-prohibited")
    document.add_heading("1. Hintergrund und Ziele", prov=on_page(1))
    document.add_text(
        DocItemLabel.TEXT,
        "Die Leitlinien erläutern die Verbote und das ist der Kern.",
        prov=on_page(1),
    )
    return document


DOCUMENTS = {
    f"{ANNEX_I_DOC}.en.pdf": annex_i,
    f"{ANNEX_III_DOC}.en.pdf": annex_iii,
    "guide-prohibited.de.pdf": german,
}


def fake_convert(content: bytes, name: str) -> DoclingDocument:
    assert content == name.encode()
    return DOCUMENTS[name]()


def pdf_entry(doc: str, language: Language, raw_dir: Path) -> dict[str, object]:
    file = f"{doc}.{language}.pdf"
    content = file.encode()
    (raw_dir / file).write_bytes(content)
    return {
        "id": doc,
        "language": language,
        "title": doc,
        "kind": "pdf",
        "status": "draft",
        "version": "2026-05-19",
        "source_page": "https://example.org",
        "url": "https://example.org/doc",
        "available": True,
        "file": file,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """A manifest with three PDFs, their raw files, and a split with two Pile B examples."""
    monkeypatch.setitem(LIST_SIZES, ANNEX_I_DOC, (2, 1))
    monkeypatch.setitem(LIST_SIZES, ANNEX_III_DOC, (2,))
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    entries = [
        pdf_entry(ANNEX_I_DOC, "en", raw_dir),
        pdf_entry(ANNEX_III_DOC, "en", raw_dir),
        pdf_entry("guide-prohibited", "de", raw_dir),
    ]
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"documents": entries}), encoding="utf-8")
    split = tmp_path / "split.json"
    split.write_text(json.dumps({"pile_a": ["hr-ex-001"], "pile_b": ["hr-ex-002", "hr-ex-004"]}))
    return manifest, raw_dir, split


def test_parse_writes_sections_and_tagged_examples(
    tmp_path: Path, setup: tuple[Path, Path, Path]
) -> None:
    manifest, raw_dir, split = setup
    out = tmp_path / "parsed"
    report = parse_guidelines(manifest, raw_dir, out, split, fake_convert)

    assert report.counts == (
        (f"{ANNEX_I_DOC}.en", 4, 3),
        (f"{ANNEX_III_DOC}.en", 4, 2),
        ("guide-prohibited.de", 1, 0),
    )
    assert report.held_out_ids == ("hr-ex-002", "hr-ex-004")
    chunks = load_jsonl(out / f"{ANNEX_III_DOC}.en.jsonl")
    assert [(c.provision_id, c.source_example_id, c.is_held_out) for c in chunks] == [
        (f"guide:{ANNEX_III_DOC}:sec:1", None, False),
        (f"guide:{ANNEX_III_DOC}:ex:004", "hr-ex-004", True),
        (f"guide:{ANNEX_III_DOC}:ex:005", "hr-ex-005", False),
        (f"guide:{ANNEX_III_DOC}:sec:2", None, False),
    ]
    assert chunks[1].heading == guidelines.HEADING_SEPARATOR.join(
        ("3.2.1. The supply of water", "a) Practical examples of AI systems falling within")
    )
    assert chunks[1].text == "A pressure sensor in water monitoring."
    assert chunks[3].text == "The gas use case is narrower than that."
    annex_i_chunks = load_jsonl(out / f"{ANNEX_I_DOC}.en.jsonl")
    assert [c.source_example_id for c in annex_i_chunks] == [
        None,
        "hr-ex-001",
        "hr-ex-002",
        "hr-ex-003",
    ]
    assert annex_i_chunks[2].text == "Conversely, a scheduler is not."


def test_a_second_run_changes_nothing(tmp_path: Path, setup: tuple[Path, Path, Path]) -> None:
    manifest, raw_dir, split = setup
    out = tmp_path / "parsed"
    first = parse_guidelines(manifest, raw_dir, out, split, fake_convert)
    second = parse_guidelines(manifest, raw_dir, out, split, fake_convert)

    assert len(first.written) == 3
    assert second.written == ()


def test_a_pile_b_example_that_is_not_found_stops_the_parse(
    tmp_path: Path, setup: tuple[Path, Path, Path]
) -> None:
    manifest, raw_dir, split = setup
    split.write_text(json.dumps({"pile_b": ["hr-ex-002", "hr-ex-099"]}))
    out = tmp_path / "parsed"

    with pytest.raises(IsolationGapError, match="hr-ex-099"):
        parse_guidelines(manifest, raw_dir, out, split, fake_convert)
    assert not out.exists()


def test_a_raw_file_that_changed_is_rejected(
    tmp_path: Path, setup: tuple[Path, Path, Path]
) -> None:
    manifest, raw_dir, split = setup
    (raw_dir / f"{ANNEX_I_DOC}.en.pdf").write_bytes(b"changed")

    with pytest.raises(RawFileError, match="sha256"):
        parse_guidelines(manifest, raw_dir, tmp_path / "parsed", split, fake_convert)


def test_the_cli_prints_counts_and_the_tagged_ids(
    tmp_path: Path, setup: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, raw_dir, split = setup
    monkeypatch.setattr(guidelines, "convert_pdf", fake_convert)
    arguments = ["--manifest", str(manifest), "--raw-dir", str(raw_dir), "--split", str(split)]
    result = CliRunner().invoke(
        cli.app, ["corpus", "guidelines", *arguments, "--out-dir", str(tmp_path / "out")]
    )

    assert result.exit_code == 0, result.output
    assert f"{ANNEX_III_DOC}.en: 4 chunks (2 examples)" in result.stdout
    assert "tagged held out (Pile B): 2\nhr-ex-002 hr-ex-004" in result.stdout


def test_pdf_entries_reject_a_failed_fetch(tmp_path: Path) -> None:
    failed = {**pdf_entry("guide-art50", "en", tmp_path), "available": None, "file": None}
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"documents": [failed]}), encoding="utf-8")

    with pytest.raises(RawFileError, match=r"guide-art50\.en"):
        pdf_entries(manifest)


@pytest.mark.parametrize(
    "content", ["{}", '{"pile_b": "hr-ex-001"}', '{"pile_b": ["example 1"]}', "not json"]
)
def test_a_malformed_split_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "split.json"
    path.write_text(content)
    with pytest.raises(GuidelineError, match="pile_b"):
        load_pile_b(path)


def test_the_language_check_catches_a_mislabelled_pdf() -> None:
    blocks = (Block("paragraph", "Die Leitlinien und das Verbot der Praktiken.", 1),)
    check_language(blocks, "de", "x.de")
    with pytest.raises(GuidelineError, match="reads as 'de'"):
        check_language(blocks, "en", "x.en")


# --- The committed output ----------------------------------------------------------------------


def committed_chunks() -> list[GuidelineChunk]:
    labels = [f"{e.id}.{e.language}" for e in pdf_entries(DEFAULT_MANIFEST)]
    return [c for label in labels for c in load_jsonl(DEFAULT_PARSED_DIR / f"{label}.jsonl")]


def test_every_pdf_of_the_manifest_is_parsed() -> None:
    for entry in pdf_entries(DEFAULT_MANIFEST):
        chunks = load_jsonl(DEFAULT_PARSED_DIR / f"{entry.id}.{entry.language}.jsonl")
        assert chunks, entry.id
        assert {(c.doc, c.language) for c in chunks} == {(entry.id, entry.language)}
        assert len({c.provision_id for c in chunks}) == len(chunks)


def test_the_committed_output_numbers_all_307_examples() -> None:
    examples = [c for c in committed_chunks() if c.kind == "example"]

    assert [c.source_example_id for c in examples] == [
        f"hr-ex-{n:03d}" for n in range(1, EXAMPLE_COUNT + 1)
    ]
    assert {c.doc for c in examples[:12]} == {ANNEX_I_DOC}
    assert {c.doc for c in examples[12:]} == {ANNEX_III_DOC}
    assert all(c.source_example_id is None for c in committed_chunks() if c.kind == "section")


def test_every_pile_b_example_is_present_and_tagged_held_out() -> None:
    pile_b = load_pile_b(DEFAULT_SPLIT_FILE)
    examples = {c.source_example_id: c for c in committed_chunks() if c.kind == "example"}

    assert pile_b <= examples.keys()
    assert {i for i, c in examples.items() if c.is_held_out} == pile_b


def test_no_pile_b_example_text_is_untagged() -> None:
    chunks = committed_chunks()
    untagged = [c.text for c in chunks if c.source_example_id is None]
    held_out_lines = [
        (c.source_example_id, line)
        for c in chunks
        if c.is_held_out
        for line in c.text.split("\n")
        if len(line) >= MIN_QUOTED_LINE
    ]

    assert len(held_out_lines) >= len(load_pile_b(DEFAULT_SPLIT_FILE))
    leaks = [(i, line[:60]) for i, line in held_out_lines if any(line in t for t in untagged)]
    assert leaks == []
