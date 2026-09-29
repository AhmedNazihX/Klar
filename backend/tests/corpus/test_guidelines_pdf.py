"""Flattening a Docling document into blocks: markers, page breaks, furniture and tables."""

import pytest
from docling_core.types.doc.base import BoundingBox
from docling_core.types.doc.common.content_layer import ContentLayer
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.table.table_data import TableCell, TableData
from docling_core.types.doc.labels import DocItemLabel

from aiact.corpus.guidelines_pdf import Block, blocks_of, numbering, paragraph_number


def on_page(page: int) -> ProvenanceItem:
    return ProvenanceItem(page_no=page, bbox=BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, 1))


def table(rows: list[list[str]]) -> TableData:
    cells = [
        TableCell(
            text=text,
            start_row_offset_idx=r,
            end_row_offset_idx=r + 1,
            start_col_offset_idx=c,
            end_col_offset_idx=c + 1,
        )
        for r, row in enumerate(rows)
        for c, text in enumerate(row)
    ]
    return TableData(num_rows=len(rows), num_cols=len(rows[0]), table_cells=cells)


def sample_document() -> DoclingDocument:
    document = DoclingDocument(name="sample")
    document.add_text(DocItemLabel.PAGE_HEADER, "EN 1", prov=on_page(1))
    document.add_heading("3.2.1. Critical infrastructure", prov=on_page(1))
    group = document.add_list_group()
    document.add_list_item(
        "Point 2 of Annex III covers",
        enumerated=True,
        marker="(186)",
        parent=group,
        prov=on_page(1),
    )
    document.add_heading("a) Practical examples of AI systems falling within", prov=on_page(1))
    document.add_text(DocItemLabel.TEXT, "- A pressure sensor used in water", prov=on_page(1))
    document.add_text(DocItemLabel.FOOTNOTE, "27 Directive (EU) 2022/2557.", prov=on_page(1))
    group = document.add_list_group()
    document.add_list_item("networks for drinking water.", marker="", parent=group, prov=on_page(2))
    document.add_list_item("o AI based solutions to unlock a phone.", parent=group, prov=on_page(2))
    document.add_heading("- AI system for pilot recruitment", prov=on_page(2))
    document.add_text(DocItemLabel.TEXT, "(187) An AI system used in road traffic", prov=on_page(2))
    document.add_text(
        DocItemLabel.PAGE_FOOTER, "2", prov=on_page(2), content_layer=ContentLayer.FURNITURE
    )
    document.add_table(table([["Contents", "Page"]] + [["I. Introduction ........", "1"]] * 3))
    document.add_table(table([["Function", "Example"], ["Preventive", "Lift doors"]]))
    return document


def test_blocks_normalise_markers_and_join_page_breaks() -> None:
    blocks = blocks_of(sample_document())

    assert blocks[:8] == (
        Block("heading", "3.2.1. Critical infrastructure", 1),
        Block("list_item", "Point 2 of Annex III covers", 1, "(186)"),
        Block("heading", "a) Practical examples of AI systems falling within", 1),
        # The bullet runs over the page break; the footnote between stays separate.
        Block("list_item", "A pressure sensor used in water networks for drinking water.", 1, "-"),
        Block("footnote", "27 Directive (EU) 2022/2557.", 1),
        Block("list_item", "AI based solutions to unlock a phone.", 2, "o"),
        # A bold bullet title that Docling read as a heading is a bullet.
        Block("list_item", "AI system for pilot recruitment", 2, "-"),
        Block("list_item", "An AI system used in road traffic", 2, "(187)"),
    )
    assert blocks[5].is_sub_bullet
    assert blocks[7].is_numbered_paragraph


def test_page_headers_footers_and_tables_of_contents_are_left_out() -> None:
    blocks = blocks_of(sample_document())

    assert not any(b.text in ("EN 1", "2") for b in blocks)
    tables = [b for b in blocks if b.kind == "table"]
    assert len(tables) == 1
    assert "Preventive" in tables[0].text
    assert "  " not in tables[0].text


def test_a_word_hyphenated_over_a_page_break_is_closed_up() -> None:
    document = DoclingDocument(name="hyphen")
    document.add_text(DocItemLabel.TEXT, "quality-of-ser-", prov=on_page(3))
    document.add_text(DocItemLabel.TEXT, "vice monitoring.", prov=on_page(4))

    assert blocks_of(document) == (Block("paragraph", "quality-of-service monitoring.", 3),)


def test_a_capitalised_block_on_a_new_page_starts_a_new_paragraph() -> None:
    document = DoclingDocument(name="break")
    document.add_text(DocItemLabel.TEXT, "First paragraph.", prov=on_page(3))
    document.add_text(DocItemLabel.TEXT, "Second paragraph.", prov=on_page(4))

    assert [b.text for b in blocks_of(document)] == ["First paragraph.", "Second paragraph."]


def test_a_paragraph_number_out_of_sequence_becomes_text() -> None:
    document = DoclingDocument(name="sequence")
    group = document.add_list_group()
    for marker, text in (
        ("(59)", "Article 5 AI Act reads:"),
        ("(1)", "The following AI practices shall be prohibited:"),
        ("(60)", "The prohibition applies to providers."),
        ("(62)", "A number was not recovered before this one."),
        ("(63)", "The numbering goes on."),
    ):
        document.add_list_item(text, enumerated=True, marker=marker, parent=group, prov=on_page(5))
    document.add_heading("(64) Overview on the Prohibitions", prov=on_page(6))

    blocks = blocks_of(document)

    assert [paragraph_number(b) for b in blocks] == [59, None, 60, 62, 63, 64]
    assert blocks[1] == Block("paragraph", "(1) The following AI practices shall be prohibited:", 5)
    assert blocks[5] == Block("list_item", "Overview on the Prohibitions", 6, "(64)")


@pytest.mark.parametrize(
    ("numbers", "kept"),
    [
        # A quoted higher number never displaces the real paragraphs after it.
        ([1, 2, 3, 60, 4, 5, 61], [1, 2, 3, None, 4, 5, None]),
        ([1, 2, 3, 5, 4, 5, 6, 7], [1, 2, 3, None, 4, 5, 6, 7]),
        # Paragraph (5) quoting "(12) The notion of 'AI system'".
        ([4, 5, 12, 6, 7, 8, 9, 10, 11, 12, 13], [4, 5, None, 6, 7, 8, 9, 10, 11, 12, 13]),
        # A stray high number at the end is text.
        ([10, 11, 12, 13, 20], [10, 11, 12, 13, None]),
        # A quoted "(1)", an unrecovered number, and a part starting further on are fine.
        ([59, 1, 60, 62, 63], [59, None, 60, 62, 63]),
        ([1, 2, 14, 448, 449], [1, 2, None, 448, 449]),
        ([15, 16, 17], [15, 16, 17]),
    ],
)
def test_the_numbering_keeps_only_the_real_paragraph_numbers(
    numbers: list[int], kept: list[int | None]
) -> None:
    indexes = set(numbering(numbers))
    assert [n if i in indexes else None for i, n in enumerate(numbers)] == kept
