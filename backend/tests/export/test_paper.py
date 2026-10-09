"""The blocks a paper holds (P9, P25): every text each one draws, and a table's shape."""

import pytest

from aiact.export import (
    Fields,
    FillMarker,
    Heading,
    Note,
    PageBreak,
    Paragraph,
    Quote,
    SignOff,
    SmallText,
    Table,
    block_texts,
)


def test_every_text_a_block_draws_is_counted() -> None:
    assert block_texts(Heading("h")) == ("h",)
    assert block_texts(Paragraph("p")) == ("p",)
    assert block_texts(SmallText("s")) == ("s",)
    assert block_texts(FillMarker("f")) == ("f",)
    assert block_texts(Note("n")) == ("n",)
    assert block_texts(Quote("q", "s")) == ("q", "s")
    assert block_texts(Fields((("a", "1"), ("b", "2")))) == ("a", "1", "b", "2")
    table = Table(("x", "y"), (("1", "2"), ("3", "4")), (1.0, 1.0))
    assert block_texts(table) == ("x", "y", "1", "2", "3", "4")
    assert block_texts(SignOff("h", ("by", "date"), "t")) == ("h", "by", "date", "t")
    assert block_texts(PageBreak()) == ()


@pytest.mark.parametrize(
    ("rows", "widths"),
    [((("1", "2"),), (1.0,)), ((("1", "2"), ("3",)), (1.0, 1.0))],
)
def test_a_table_has_one_entry_per_column_in_every_row(
    rows: tuple[tuple[str, ...], ...], widths: tuple[float, ...]
) -> None:
    with pytest.raises(ValueError, match="one entry per column"):
        Table(("x", "y"), rows, widths)
