"""The rows `aiact corpus load` writes: time slices, guideline checks, and the committed parse."""

from datetime import date
from pathlib import Path

import pytest

from aiact.corpus.amendments import Amendment
from aiact.corpus.build import (
    AI_ACT_IN_FORCE,
    LoadError,
    ProvisionRow,
    amended_slices,
    build_all,
    check_paragraphs,
    omnibus_in_force,
)
from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, ParsedProvision, ProvisionKind
from aiact.corpus.fetch import DEFAULT_MANIFEST
from aiact.corpus.guidelines import GuidelineChunk

OMNIBUS_IN_FORCE = date(2026, 7, 27)
OLD_TITLE = "Article 9 \u2014 Title\u0060"
NEW_TITLE = "Article 9 \u2014 Title'"


def _law(
    pid: str,
    text: str,
    parent: str | None = None,
    kind: ProvisionKind = "point",
    heading: str = "Article 5",
) -> ParsedProvision:
    return ParsedProvision(
        provision_id=pid,
        doc="ai-act",
        language="en",
        kind=kind,
        parent_id=parent,
        heading=heading,
        text=text,
    )


def _para(number: str, text: str, doc: str = "guide-definition") -> GuidelineChunk:
    return GuidelineChunk(
        provision_id=f"guide:{doc}:para:{number}",
        doc=doc,
        language="en",
        kind="section",
        heading=None,
        text=text,
        page=1,
    )


def _slices(rows: tuple[ProvisionRow, ...], pid: str) -> list[tuple[date, date | None, str]]:
    return [(r.valid_from, r.valid_to, r.text) for r in rows if r.provision_id == pid]


# art:5:1:b is a corrigendum ("bb typo" -> "b") under art:5:1, which the Omnibus amends.
# art:9's title is a corrigendum too, while its paragraph 1 is amended.
ORIGINAL = (
    _law("recital:1", "A recital.", kind="recital"),
    _law("art:5", "1. (a) a (b) bb typo 2. old", kind="article"),
    _law("art:5:1", "(a) a (b) bb typo", "art:5", "paragraph"),
    _law("art:5:1:a", "a", "art:5:1"),
    _law("art:5:1:b", "bb typo", "art:5:1"),
    _law("art:5:2", "old", "art:5", "paragraph"),
    _law("art:5:3", "gone", "art:5", "paragraph"),
    _law("art:6", "typo", kind="article"),
    _law("art:7", "same", kind="article"),
    _law("art:9", "1. old", kind="article", heading=OLD_TITLE),
    _law("art:9:1", "old", "art:9", "paragraph", heading=OLD_TITLE),
)
CONSOLIDATED = (
    _law("art:5", "1. (a) a (b) b (ba) ba 2. new", kind="article"),
    _law("art:5:1", "(a) a (b) b (ba) ba", "art:5", "paragraph"),
    _law("art:5:1:a", "a", "art:5:1"),
    _law("art:5:1:b", "b", "art:5:1"),
    _law("art:5:1:ba", "ba", "art:5:1"),
    _law("art:5:2", "new", "art:5", "paragraph"),
    _law("art:6", "fixed", kind="article"),
    _law("art:7", "same", kind="article"),
    _law("art:9", "1. new", kind="article", heading=NEW_TITLE),
    _law("art:9:1", "new", "art:9", "paragraph", heading=NEW_TITLE),
)
TARGETS = frozenset({"art:5:1:ba", "art:5:2", "art:5:3", "art:9:1"})


@pytest.fixture(scope="module")
def slices() -> tuple[ProvisionRow, ...]:
    return amended_slices(ORIGINAL, CONSOLIDATED, OMNIBUS_IN_FORCE, TARGETS)


def test_an_amended_provision_is_split_at_the_omnibus_date(slices: tuple[ProvisionRow, ...]):
    assert _slices(slices, "art:5:2") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "old"),
        (OMNIBUS_IN_FORCE, None, "new"),
    ]


def test_inserted_and_deleted_provisions_get_one_side(slices: tuple[ProvisionRow, ...]):
    assert _slices(slices, "art:5:1:ba") == [(OMNIBUS_IN_FORCE, None, "ba")]
    assert _slices(slices, "art:5:3") == [(AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "gone")]


def test_children_of_a_split_parent_are_split_with_it(slices: tuple[ProvisionRow, ...]):
    """art:5:1:a is unchanged, but its parent art:5:1 changed: each slice has a parent slice
    covering the same dates."""
    rows = [r for r in slices if r.provision_id == "art:5:1:a"]
    assert [(r.valid_from, r.valid_to, r.parent_valid_from) for r in rows] == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, AI_ACT_IN_FORCE),
        (OMNIBUS_IN_FORCE, None, OMNIBUS_IN_FORCE),
    ]


def test_an_untouched_difference_is_a_corrigendum_from_the_start(slices: tuple[ProvisionRow, ...]):
    assert _slices(slices, "art:6") == [(AI_ACT_IN_FORCE, None, "fixed")]
    assert _slices(slices, "art:7") == [(AI_ACT_IN_FORCE, None, "same")]


def test_a_corrigendum_under_an_amended_parent_applies_from_the_start(
    slices: tuple[ProvisionRow, ...],
):
    """Both slices of art:5:1:b have the corrected text, and so do the old slices of the
    ancestors that quote it; they still split for the amendment."""
    assert _slices(slices, "art:5:1:b") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "b"),
        (OMNIBUS_IN_FORCE, None, "b"),
    ]
    assert _slices(slices, "art:5:1")[0] == (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "(a) a (b) b")
    old_article = (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "1. (a) a (b) b 2. old")
    assert _slices(slices, "art:5")[0] == old_article


def test_a_title_corrigendum_applies_to_every_unit_of_the_article(
    slices: tuple[ProvisionRow, ...],
):
    rows = [r for r in slices if r.provision_id in ("art:9", "art:9:1")]
    assert len(rows) == 4
    assert {r.heading for r in rows} == {NEW_TITLE}


def test_a_corrigendum_the_parent_quotes_twice_fails():
    original = (
        _law("art:5", "b b", kind="article"),
        _law("art:5:1", "b", "art:5", "paragraph"),
    )
    consolidated = (
        _law("art:5", "c c", kind="article"),
        _law("art:5:1", "c", "art:5", "paragraph"),
    )
    with pytest.raises(LoadError, match="found 2 times"):
        amended_slices(original, consolidated, OMNIBUS_IN_FORCE, frozenset({"art:5:2"}))


def test_an_unknown_parent_fails():
    rows = (_law("art:5:1", "a", "art:5", "paragraph"),)
    with pytest.raises(LoadError, match="parent art:5 is not a provision"):
        amended_slices(rows, rows, OMNIBUS_IN_FORCE, frozenset())


def test_recitals_stay_in_the_original(slices: tuple[ProvisionRow, ...]):
    assert _slices(slices, "recital:1") == []


def test_parents_come_before_children(slices: tuple[ProvisionRow, ...]):
    seen: set[tuple[str, date]] = set()
    for row in slices:
        if row.parent_id is not None:
            assert row.parent_valid_from is not None
            assert (row.parent_id, row.parent_valid_from) in seen, row
        seen.add((row.provision_id, row.valid_from))


def test_omnibus_needs_one_entry_into_force_date():
    def entry(pid: str, in_force: date) -> ParsedProvision:
        amendment = Amendment(action="replace", targets=("art:5:2",), in_force_from=in_force)
        return _law(pid, "x").model_copy(update={"amendment": amendment})

    rows = (entry("art:1:1", OMNIBUS_IN_FORCE),)
    assert omnibus_in_force(rows) == (OMNIBUS_IN_FORCE, frozenset({"art:5:2"}))
    with pytest.raises(LoadError, match="one entry-into-force date"):
        omnibus_in_force((*rows, entry("art:1:2", date(2026, 8, 1))))


def test_check_paragraphs_accepts_the_printed_numbering():
    check_paragraphs(tuple(_para(str(n), f"({n}) text") for n in range(1, 65)), "definition")


def test_check_paragraphs_fails_on_a_wrong_last_paragraph():
    chunks = tuple(_para(str(n), f"({n}) text") for n in (1, 2, 70))
    with pytest.raises(LoadError, match="last paragraph is 70, the PDF prints 64"):
        check_paragraphs(chunks, "definition")


def test_check_paragraphs_fails_when_a_chunk_starts_elsewhere():
    with pytest.raises(LoadError, match="doesn't start with paragraph 2"):
        check_paragraphs((_para("1", "(1) a"), _para("2", "(3) b")), "definition")


# The committed parse output (data/parsed) and manifest.


@pytest.fixture(scope="module")
def committed() -> dict[str, tuple[ProvisionRow, ...]]:
    return {load.label: load.provisions for load in build_all(DEFAULT_MANIFEST, DEFAULT_PARSED_DIR)}


def test_every_available_document_is_built(committed: dict[str, tuple[ProvisionRow, ...]]):
    assert len(committed) == 15
    assert {"ai-act-consolidated.de", "guide-high-risk-annex-iii.en"} <= set(committed)


def test_new_prohibitions_start_with_the_omnibus(committed: dict[str, tuple[ProvisionRow, ...]]):
    for language in ("en", "de"):
        rows = committed[f"ai-act-consolidated.{language}"]
        assert [(r.valid_from, r.valid_to) for r in rows if r.provision_id == "art:5:1:ba"] == [
            (OMNIBUS_IN_FORCE, None)
        ]


def test_en_and_de_have_the_same_slices(committed: dict[str, tuple[ProvisionRow, ...]]):
    for doc in ("ai-act", "ai-act-consolidated", "omnibus", "guide-prohibited"):
        en, de = (
            {(r.provision_id, r.valid_from, r.valid_to) for r in committed[f"{doc}.{lang}"]}
            for lang in ("en", "de")
        )
        assert en == de, doc


def test_held_out_rows_are_examples(committed: dict[str, tuple[ProvisionRow, ...]]):
    held_out = [r for rows in committed.values() for r in rows if r.is_held_out]
    assert held_out
    assert all(r.source_example_id is not None for r in held_out)


def test_a_missing_parsed_file_fails(tmp_path: Path):
    with pytest.raises(LoadError, match="is missing"):
        build_all(DEFAULT_MANIFEST, tmp_path)
