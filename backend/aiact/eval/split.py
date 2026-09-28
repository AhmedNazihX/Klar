"""The Pile A / Pile B split of the Commission high-risk examples (INIT > Benchmark isolation 1).

Every example in `eval/commission_examples/examples.jsonl` goes to Pile A (stays in the corpus as
retrievable guidance) or Pile B (held out of the corpus and rewritten into the headline benchmark).
The assignment is seeded and stratified by `area` x `verdict`, so every stratum lands in both piles.
`eval/split.json` is committed once, before any engine code exists, and never changes afterwards
(decisions 001 and 011); `write_split` refuses to overwrite it with a different assignment.
"""

import json
import math
import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from aiact.eval.cases import EVAL_DIR
from aiact.schemas.base import ContractModel

EXAMPLES_FILE = EVAL_DIR / "commission_examples" / "examples.jsonl"
SPLIT_FILE = EVAL_DIR / "split.json"

DEFAULT_SEED = 20260928
"""The seed of the committed split (decision 011): the date the split was settled."""
DEFAULT_PILE_B_FRACTION = 0.5
"""A half split (decision 011): about 150 of the 307 examples go to Pile B."""
STRATIFY_BY = ("area", "verdict")


class SplitMode(StrEnum):
    """`split` holds Pile B out of the corpus; `loo` (leave-one-out) is for fewer than ~40."""

    SPLIT = "split"
    LOO = "loo"


class ExampleRow(BaseModel):
    """The fields of an example row the split needs; the other label fields are ignored here."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    example_id: str = Field(pattern=r"^hr-ex-[0-9]{3}$")
    area: str = Field(min_length=1)
    verdict: str = Field(min_length=1)

    @property
    def stratum(self) -> tuple[str, str]:
        return (self.area, self.verdict)


class Split(ContractModel):
    """The content of `eval/split.json`."""

    mode: SplitMode
    seed: int
    pile_b_fraction: float = Field(gt=0, lt=1)
    stratify_by: tuple[str, ...]
    pile_a: tuple[str, ...]
    pile_b: tuple[str, ...]

    @model_validator(mode="after")
    def _piles_are_disjoint(self) -> Self:
        if set(self.pile_a) & set(self.pile_b):
            raise ValueError("an example is in Pile A or Pile B, never both")
        return self


class SplitError(ValueError):
    """Examples that can't be split, or a committed split that a new run would change."""


def load_examples(path: Path = EXAMPLES_FILE) -> tuple[ExampleRow, ...]:
    """Read the example rows, one JSON object per non-blank line, with unique IDs."""
    rows: list[ExampleRow] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(ExampleRow.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise SplitError(f"{path}:{number}: not a valid example row: {exc}") from exc
    ids = [row.example_id for row in rows]
    if len(set(ids)) != len(ids):
        raise SplitError(f"{path}: duplicate example_id")
    if not rows:
        raise SplitError(f"{path}: no examples")
    return tuple(rows)


def make_split(
    rows: Sequence[ExampleRow],
    seed: int = DEFAULT_SEED,
    pile_b_fraction: float = DEFAULT_PILE_B_FRACTION,
) -> Split:
    """Assign each row to a pile: shuffle each stratum with the seed and take its Pile B share.

    Each stratum gets `floor(n * fraction)` Pile B examples. The strata whose share isn't whole
    get one more, in seeded order, until Pile B holds `floor(total * fraction)` (largest
    remainder), so the total stays as close to the fraction as whole examples allow.
    """
    rng = random.Random(seed)
    strata = _strata(rows)
    shuffled = {key: _shuffled(ids, rng) for key, ids in sorted(strata.items())}
    quotas = _quotas({key: len(ids) for key, ids in shuffled.items()}, pile_b_fraction, rng)
    pile_b = {id_ for key, ids in shuffled.items() for id_ in ids[: quotas[key]]}
    split = Split(
        mode=SplitMode.SPLIT,
        seed=seed,
        pile_b_fraction=pile_b_fraction,
        stratify_by=STRATIFY_BY,
        pile_a=tuple(sorted(row.example_id for row in rows if row.example_id not in pile_b)),
        pile_b=tuple(sorted(pile_b)),
    )
    check_every_area_in_both_piles(rows, split)
    return split


def _strata(rows: Iterable[ExampleRow]) -> dict[tuple[str, str], tuple[str, ...]]:
    grouped: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        grouped[row.stratum].append(row.example_id)
    return {key: tuple(sorted(ids)) for key, ids in grouped.items()}


def _shuffled(ids: Sequence[str], rng: random.Random) -> tuple[str, ...]:
    return tuple(rng.sample(ids, k=len(ids)))


def _quotas[K](sizes: dict[K, int], fraction: float, rng: random.Random) -> dict[K, int]:
    """Largest-remainder allocation of `floor(total * fraction)` over the strata; ties seeded."""
    base = {key: math.floor(size * fraction) for key, size in sizes.items()}
    missing = math.floor(sum(sizes.values()) * fraction) - sum(base.values())
    remainders = {key: size * fraction - base[key] for key, size in sizes.items()}
    order = rng.sample(list(sizes), k=len(sizes))
    ranked = sorted(order, key=lambda key: remainders[key], reverse=True)
    topped_up = set(ranked[:missing])
    return {key: base[key] + (key in topped_up) for key in sizes}


def check_every_area_in_both_piles(rows: Iterable[ExampleRow], split: Split) -> None:
    """The DoD: every area with more than one example appears in both piles."""
    pile_b = set(split.pile_b)
    by_area: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_area[row.area].append(row.example_id)
    for area, ids in sorted(by_area.items()):
        in_b = sum(id_ in pile_b for id_ in ids)
        if len(ids) > 1 and in_b in (0, len(ids)):
            raise SplitError(f"area {area} has {len(ids)} examples but is missing from a pile")


def render(split: Split) -> str:
    """The exact text of `eval/split.json`: stable key order, one ID per line."""
    return json.dumps(split.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"


def write_split(split: Split, path: Path = SPLIT_FILE) -> bool:
    """Write the split; `False` when the file already holds it. A different split is refused,
    because the committed assignment is frozen (INIT > Benchmark isolation 1)."""
    text = render(split)
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return False
        raise SplitError(f"{path} already holds a different split; the split never changes")
    path.write_text(text, encoding="utf-8")
    return True
