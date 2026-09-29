"""The rows `aiact corpus load` writes: time slices, guideline checks, and the committed parse."""

from datetime import date
from pathlib import Path

import pytest

from aiact.corpus.amendments import Amendment
from aiact.corpus.build import (
    AI_ACT_IN_FORCE,
    Corrigendum,
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


# art:8:1:a is a corrigendum ("aa typo" -> "a") under art:8:1, whose point (c) the Omnibus
# replaces; (a) is two points from (c), so no neighbour rule reaches it.
# art:9's title is a corrigendum too, while its paragraph 1 is amended.
ORIGINAL = (
    _law("recital:1", "A recital.", kind="recital"),
    _law("art:5", "1. (a) a (b) b 2. old", kind="article"),
    _law("art:5:1", "(a) a (b) b", "art:5", "paragraph"),
    _law("art:5:1:a", "a", "art:5:1"),
    _law("art:5:1:b", "b", "art:5:1"),
    _law("art:5:2", "old", "art:5", "paragraph"),
    _law("art:5:3", "gone", "art:5", "paragraph"),
    _law("art:6", "typo", kind="article"),
    _law("art:7", "same", kind="article"),
    _law("art:8", "1. (a) aa typo (b) b (c) old c (d) d", kind="article"),
    _law("art:8:1", "(a) aa typo (b) b (c) old c (d) d", "art:8", "paragraph"),
    _law("art:8:1:a", "aa typo", "art:8:1"),
    _law("art:8:1:b", "b", "art:8:1"),
    _law("art:8:1:c", "old c", "art:8:1"),
    _law("art:8:1:d", "d", "art:8:1"),
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
    _law("art:8", "1. (a) a (b) b (c) new c (d) d", kind="article"),
    _law("art:8:1", "(a) a (b) b (c) new c (d) d", "art:8", "paragraph"),
    _law("art:8:1:a", "a", "art:8:1"),
    _law("art:8:1:b", "b", "art:8:1"),
    _law("art:8:1:c", "new c", "art:8:1"),
    _law("art:8:1:d", "d", "art:8:1"),
    _law("art:9", "1. new", kind="article", heading=NEW_TITLE),
    _law("art:9:1", "new", "art:9", "paragraph", heading=NEW_TITLE),
)
TARGETS = frozenset({"art:5:1:ba", "art:5:2", "art:5:3", "art:8:1:c", "art:9:1"})
FIXTURE_CORRIGENDA = {
    "art:6": Corrigendum.of("text", "fixed", "typo"),
    "art:8:1:a": Corrigendum.of("text", "a", "typo"),
    "art:9": Corrigendum.of("title", NEW_TITLE, "stray backtick"),
}


@pytest.fixture(scope="module")
def slices() -> tuple[ProvisionRow, ...]:
    return amended_slices(ORIGINAL, CONSOLIDATED, OMNIBUS_IN_FORCE, TARGETS, FIXTURE_CORRIGENDA)


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
    """Both slices of art:8:1:a have the corrected text, and so do the old slices of the
    ancestors that quote it; they still split for the amendment."""
    assert _slices(slices, "art:8:1:a") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "a"),
        (OMNIBUS_IN_FORCE, None, "a"),
    ]
    old_paragraph = (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "(a) a (b) b (c) old c (d) d")
    assert _slices(slices, "art:8:1")[0] == old_paragraph
    old_article = (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "1. (a) a (b) b (c) old c (d) d")
    assert _slices(slices, "art:8")[0] == old_article


def test_a_title_corrigendum_applies_to_every_unit_of_the_article(
    slices: tuple[ProvisionRow, ...],
):
    rows = [r for r in slices if r.provision_id in ("art:9", "art:9:1")]
    assert len(rows) == 4
    assert {r.heading for r in rows} == {NEW_TITLE}


RIGHT = Corrigendum.of("text", "right.", "typo")


def _article(points: dict[str, str]) -> tuple[ParsedProvision, ...]:
    """Art. 6 with the points `{label: text}`, in order; a label `b:i` is a sub-point of (b)."""
    units = []
    for label, text in points.items():
        parent = "art:6:" + label.rsplit(":", 1)[0] if ":" in label else "art:6"
        units.append(_law(f"art:6:{label}", text, parent))
    return (_law("art:6", " ".join(points.values()), kind="article"), *units)


def _list_slices(
    original_points: dict[str, str],
    consolidated_points: dict[str, str],
    targets: set[str],
    corrigenda: dict[str, Corrigendum] | None = None,
) -> tuple[ProvisionRow, ...]:
    return amended_slices(
        _article(original_points),
        _article(consolidated_points),
        OMNIBUS_IN_FORCE,
        frozenset(targets),
        corrigenda or {},
    )


def test_the_point_before_an_inserted_point_changes_with_the_omnibus():
    """Inserting (c) moves the "or" and the full stop: (b) is split, not backdated."""
    rows = _list_slices(
        {"a": "x;", "b": "y."},
        {"a": "x;", "b": "y; or", "c": "z."},
        {"art:6:c"},
    )
    assert _slices(rows, "art:6:b") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "y."),
        (OMNIBUS_IN_FORCE, None, "y; or"),
    ]
    assert _slices(rows, "art:6:a") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "x;"),
        (OMNIBUS_IN_FORCE, None, "x;"),
    ]


def test_the_points_around_a_deleted_point_change_with_the_omnibus():
    """Deleting (b) moves the "and" to (a) and the full stop to (c)."""
    rows = _list_slices(
        {"a": "x;", "b": "y; and", "c": "z;", "d": "w."},
        {"a": "x; and", "c": "z.", "d": "w."},
        {"art:6:b"},
    )
    assert _slices(rows, "art:6:a")[0] == (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "x;")
    assert _slices(rows, "art:6:c")[0] == (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "z;")
    assert _slices(rows, "art:6:b") == [(AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "y; and")]


def test_a_difference_away_from_the_targets_stays_a_corrigendum():
    """(d) isn't next to the inserted (b1), so its fix applies from the start."""
    rows = _list_slices(
        {"a": "x;", "b": "y;", "c": "z;", "d": "wrong."},
        {"a": "x;", "b": "y;", "b1": "new;", "c": "z;", "d": "right."},
        {"art:6:b1"},
        {"art:6:d": RIGHT},
    )
    assert _slices(rows, "art:6:d") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "right."),
        (OMNIBUS_IN_FORCE, None, "right."),
    ]


def test_the_and_moves_two_points_back_when_a_point_is_appended():
    """Appending (d) moves the "and" from (b) to (c): (b) is two points from the target."""
    rows = _list_slices(
        {"a": "x;", "b": "y; and", "c": "z."},
        {"a": "x;", "b": "y;", "c": "z; and", "d": "w."},
        {"art:6:d"},
    )
    assert _slices(rows, "art:6:b") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "y; and"),
        (OMNIBUS_IN_FORCE, None, "y;"),
    ]


def test_deleting_the_last_point_moves_the_and_two_points_back():
    """Deleting (c) moves the "and" from (b) to (a) and the full stop to (b)."""
    rows = _list_slices(
        {"a": "x;", "b": "y; and", "c": "z."},
        {"a": "x; and", "b": "y."},
        {"art:6:c"},
    )
    assert _slices(rows, "art:6:a")[0] == (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "x;")
    assert _slices(rows, "art:6:b")[0] == (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "y; and")


def test_an_insertion_after_a_point_with_sub_points_reaches_its_last_sub_point():
    """Inserting (c) after (b) puts the "; or" on (b)(ii)."""
    rows = _list_slices(
        {"a": "x;", "b": "y:", "b:i": "p;", "b:ii": "q."},
        {"a": "x;", "b": "y:", "b:i": "p;", "b:ii": "q; or", "c": "z."},
        {"art:6:c"},
    )
    assert _slices(rows, "art:6:b:ii") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "q."),
        (OMNIBUS_IN_FORCE, None, "q; or"),
    ]


def test_an_unexpected_corrigendum_fails_the_load():
    with pytest.raises(LoadError, match=r"unexpected corrigendum art:6:d \(text: 'wrong\.'"):
        _list_slices(
            {"a": "x;", "b": "y;", "c": "z;", "d": "wrong."},
            {"a": "x;", "b": "y;", "b1": "new;", "c": "z;", "d": "right."},
            {"art:6:b1"},
        )


def test_an_unexpected_title_corrigendum_fails_the_load():
    corrigenda = {k: v for k, v in FIXTURE_CORRIGENDA.items() if k != "art:9"}
    with pytest.raises(LoadError, match="unexpected corrigendum art:9 \\(title"):
        amended_slices(ORIGINAL, CONSOLIDATED, OMNIBUS_IN_FORCE, TARGETS, corrigenda)


def test_a_reviewed_corrigendum_that_no_longer_occurs_fails_the_load():
    """If a rule change made art:7 look amended, its reviewed fix must not vanish silently."""
    corrigenda = {**FIXTURE_CORRIGENDA, "art:7": Corrigendum.of("text", "same", "typo")}
    with pytest.raises(LoadError, match="reviewed corrigenda art:7 no longer occur"):
        amended_slices(ORIGINAL, CONSOLIDATED, OMNIBUS_IN_FORCE, TARGETS, corrigenda)


def test_a_reviewed_corrigendum_with_a_new_consolidated_text_fails_the_load():
    corrigenda = {**FIXTURE_CORRIGENDA, "art:6": Corrigendum.of("text", "fixed again", "typo")}
    with pytest.raises(LoadError, match="corrigendum art:6 changed"):
        amended_slices(ORIGINAL, CONSOLIDATED, OMNIBUS_IN_FORCE, TARGETS, corrigenda)


def test_a_reviewed_corrigendum_of_another_kind_fails_the_load():
    corrigenda = {**FIXTURE_CORRIGENDA, "art:6": Corrigendum.of("heading", "fixed", "typo")}
    with pytest.raises(LoadError, match="corrigendum art:6 changed"):
        amended_slices(ORIGINAL, CONSOLIDATED, OMNIBUS_IN_FORCE, TARGETS, corrigenda)


def test_replacing_the_last_point_leaves_the_point_two_back_alone():
    """Only an appended or dropped last point moves the "and"; (b)'s fix stays a corrigendum."""
    rows = _list_slices(
        {"a": "x;", "b": "wrong;", "c": "z;", "d": "old."},
        {"a": "x;", "b": "right;", "c": "z;", "d": "new."},
        {"art:6:d"},
        {"art:6:b": Corrigendum.of("text", "right;", "typo")},
    )
    assert _slices(rows, "art:6:b") == [
        (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE, "right;"),
        (OMNIBUS_IN_FORCE, None, "right;"),
    ]


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
        targets = frozenset({"art:5:2"})
        corrigenda = {"art:5:1": Corrigendum.of("text", "c", "typo")}
        amended_slices(original, consolidated, OMNIBUS_IN_FORCE, targets, corrigenda)


def test_an_unknown_parent_fails():
    rows = (_law("art:5:1", "a", "art:5", "paragraph"),)
    with pytest.raises(LoadError, match="parent art:5 is not a provision"):
        amended_slices(rows, rows, OMNIBUS_IN_FORCE, frozenset(), {})


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


def test_the_de_art_3_40_corrigendum_applies_before_the_omnibus(
    committed: dict[str, tuple[ProvisionRow, ...]],
):
    rows = committed["ai-act-consolidated.de"]
    for pid in ("art:3", "art:3:40"):
        before = next(r for r in rows if r.provision_id == pid and r.valid_to == OMNIBUS_IN_FORCE)
        assert "sofern es sich nicht um" in before.text, pid


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
