import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval.split import (
    DEFAULT_SEED,
    EXAMPLES_FILE,
    SPLIT_FILE,
    ExampleRow,
    Split,
    SplitError,
    SplitMode,
    check_every_area_in_both_piles,
    load_examples,
    make_split,
    write_split,
)


def rows_for(sizes: dict[tuple[str, str], int]) -> tuple[ExampleRow, ...]:
    """Synthetic rows with sequential IDs, `size` rows per (area, verdict) stratum."""
    rows: list[ExampleRow] = []
    for (area, verdict), size in sizes.items():
        for _ in range(size):
            example_id = f"hr-ex-{len(rows) + 1:03d}"
            rows.append(ExampleRow(example_id=example_id, area=area, verdict=verdict))
    return tuple(rows)


SIZES = {("a", "high"): 5, ("a", "not_high"): 4, ("b", "high"): 7, ("b", "not_high"): 9}
ROWS = rows_for(SIZES)


def pile_b_per_stratum(rows: tuple[ExampleRow, ...], split: Split) -> Counter[tuple[str, str]]:
    pile_b = set(split.pile_b)
    return Counter(row.stratum for row in rows if row.example_id in pile_b)


# --- make_split --------------------------------------------------------------------------------


def test_every_example_lands_in_exactly_one_pile() -> None:
    split = make_split(ROWS, seed=1)
    assert split.mode is SplitMode.SPLIT
    assert sorted(split.pile_a + split.pile_b) == sorted(row.example_id for row in ROWS)
    assert not set(split.pile_a) & set(split.pile_b)


def test_each_stratum_is_halved_and_odd_strata_bring_the_total_to_the_floor_of_half() -> None:
    split = make_split(ROWS, seed=1)
    assert len(split.pile_b) == len(ROWS) // 2
    for stratum, count in pile_b_per_stratum(ROWS, split).items():
        assert count in (SIZES[stratum] // 2, (SIZES[stratum] + 1) // 2)


def test_same_seed_gives_the_same_split_and_another_seed_a_different_one() -> None:
    assert make_split(ROWS, seed=7) == make_split(ROWS, seed=7)
    assert make_split(ROWS, seed=7).pile_b != make_split(ROWS, seed=8).pile_b


def test_row_order_does_not_change_the_split() -> None:
    assert make_split(tuple(reversed(ROWS)), seed=3) == make_split(ROWS, seed=3)


def test_the_fraction_and_seed_are_recorded() -> None:
    split = make_split(ROWS, seed=5, pile_b_fraction=0.25)
    assert (split.seed, split.pile_b_fraction) == (5, 0.25)
    assert split.stratify_by == ("area", "verdict")
    assert len(split.pile_b) == len(ROWS) // 4


def test_an_area_missing_from_a_pile_is_refused() -> None:
    rows = rows_for({("a", "high"): 2, ("b", "high"): 2})
    lopsided = Split(
        mode=SplitMode.SPLIT,
        seed=0,
        pile_b_fraction=0.5,
        stratify_by=("area", "verdict"),
        pile_a=("hr-ex-001", "hr-ex-002", "hr-ex-003"),
        pile_b=("hr-ex-004",),
    )
    with pytest.raises(SplitError, match="area a"):
        check_every_area_in_both_piles(rows, lopsided)


def test_a_single_example_area_may_sit_in_one_pile() -> None:
    rows = rows_for({("a", "high"): 1, ("b", "high"): 4})
    split = make_split(rows, seed=0)
    assert len(split.pile_b) == 2


@pytest.mark.parametrize("mode", list(SplitMode))
def test_piles_that_overlap_are_rejected(mode: SplitMode) -> None:
    with pytest.raises(ValueError, match="never both"):
        Split(
            mode=mode,
            seed=0,
            pile_b_fraction=0.5,
            stratify_by=("area",),
            pile_a=("hr-ex-001",),
            pile_b=("hr-ex-001",),
        )


# --- files -------------------------------------------------------------------------------------


def write_jsonl(path: Path, records: Sequence[Mapping[str, object]]) -> Path:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


def test_load_examples_keeps_only_the_split_fields(tmp_path: Path) -> None:
    record = {"example_id": "hr-ex-001", "area": "annex_i", "verdict": "high", "text": "…"}
    rows = load_examples(write_jsonl(tmp_path / "x.jsonl", [record]))
    assert rows == (ExampleRow(example_id="hr-ex-001", area="annex_i", verdict="high"),)


def test_load_examples_rejects_duplicates_and_bad_rows(tmp_path: Path) -> None:
    row = {"example_id": "hr-ex-001", "area": "a", "verdict": "high"}
    with pytest.raises(SplitError, match="duplicate"):
        load_examples(write_jsonl(tmp_path / "dup.jsonl", [row, row]))
    with pytest.raises(SplitError, match=":1:"):
        load_examples(write_jsonl(tmp_path / "bad.jsonl", [{"example_id": "x"}]))


def test_write_split_is_idempotent_and_refuses_a_different_split(tmp_path: Path) -> None:
    path = tmp_path / "split.json"
    assert write_split(make_split(ROWS, seed=1), path) is True
    assert write_split(make_split(ROWS, seed=1), path) is False
    with pytest.raises(SplitError, match="never changes"):
        write_split(make_split(ROWS, seed=2), path)
    assert Split.model_validate_json(path.read_text(encoding="utf-8")) == make_split(ROWS, seed=1)


def test_cli_writes_the_split(tmp_path: Path) -> None:
    records = [row.model_dump() for row in ROWS]
    examples = write_jsonl(tmp_path / "examples.jsonl", records)
    output = tmp_path / "split.json"
    args = ["eval", "split", "--examples", str(examples), "--output", str(output), "--seed", "1"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert f"Pile B: {len(ROWS) // 2}" in result.output
    assert CliRunner().invoke(app, [*args[:-1], "2"]).exit_code == 1


# --- the committed split -----------------------------------------------------------------------


def test_the_committed_split_covers_exactly_the_examples() -> None:
    """`eval/split.json` freezes the IDs: all 307 examples, every area in both piles.

    It is not compared with a fresh run, because a later verdict correction in `examples.jsonl`
    changes the strata but must not move an example between piles (decision 011).
    """
    rows = load_examples(EXAMPLES_FILE)
    committed = Split.model_validate_json(SPLIT_FILE.read_text(encoding="utf-8"))
    assert committed.mode is SplitMode.SPLIT
    assert committed.seed == DEFAULT_SEED
    assert set(committed.pile_a) | set(committed.pile_b) == {row.example_id for row in rows}
    assert len(committed.pile_a) + len(committed.pile_b) == len(rows) == 307
    check_every_area_in_both_piles(rows, committed)
