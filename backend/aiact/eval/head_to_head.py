"""The head-to-head case draw (V10a, decision 036): which labels-v1 cases go through the
Commission's AI Act Service Desk checker by hand.

The rule (`DRAW_RULE`), fixed and committed before any checker run:
- **Pool.** The headline sets (`commission_b`, `own`) as tagged `labels-v1`, English cases with a
  decided label and a class only: `risk_class_match` skips `legally_ambiguous` and thin labels, and
  the checker can't answer "needs more information" either.
- **Strata.** The risk class of the label. `DRAW_SIZE` cases are split evenly over the classes in
  the pool; a class whose share isn't whole gets one more, in seeded order.
- **Steps.** Every engine step (`DrawStep`) gets at least `STEP_MINIMUM` cases. Steps are served
  first, in `DrawStep` order, each by seeded picks among the cases that exercise it and whose
  class still has room; then every class is filled to its share by a seeded sample. For the Annex
  steps (`POSITIVE_STEPS`) at least one of those cases is a positive, a high-risk label reached
  through that Annex, when the pool has one: the step's picks are among its positives until one
  is drawn.

A case exercises a step by what decides its label (`case_steps`): an own case by its category
(a transparency, b scope, c prohibited practices, d roles, e Annex I, f Annex III), a Commission
rewrite by its Annex area, either by a class only one step gives (`CLASS_STEPS`: out of scope,
prohibited, limited risk), and by the Art. 6(3) filter when its basis is that filter or it cites a
lettered Art. 6(3) condition.

The draw is written once to `DRAW_FILE`, under `eval/reports/pile_b/` because it names Pile B
cases and their labels, which the Engine lane must not read (`label_filter.PILE_B_FOLDER`).
"""

import io
import json
import random
import re
import tarfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self

from pydantic import Field, ValidationError, model_validator

from aiact.eval.cases import ART_6_3_FILTER, BenchmarkCase, CaseLabel, CaseSet, load_cases
from aiact.eval.label_filter import PILE_B_FOLDER, REPORTS_DIR
from aiact.eval.label_freeze import CASES_PATH, REPO_DIR, FreezeCheckError, git_bytes
from aiact.schemas.base import ContractModel
from aiact.schemas.enums import Language, RiskClass, Status

HEAD_TO_HEAD_DIR = REPORTS_DIR / PILE_B_FOLDER
DRAW_FILE = HEAD_TO_HEAD_DIR / "head_to_head_draw.json"
HEAD_TO_HEAD_BENCHMARK = "head_to_head"
"""The `eval_runs.benchmark` of a run of exactly the drawn cases (`aiact evaluate run
--cases-from-draw`, V10b); it holds Pile B cases, so its report names none (`report.is_pile_b`)."""

LABELS_REF = "labels-v1"
"""The tag of the frozen labels the cases are drawn from (B10b)."""
DRAW_SEED = 20261014
"""The seed of the committed draw: the date decision 036 was settled."""
DRAW_SIZE = 25
"""Within decision 036's 20-30: five per class over the five classes."""
MIN_DRAW_SIZE = 20
MAX_DRAW_SIZE = 30
STEP_MINIMUM = 2
DRAW_SETS = (CaseSet.COMMISSION_B, CaseSet.OWN)
"""The headline sets (INIT > Test sets) whose cases are drawn."""
DRAW_LANGUAGE = Language.EN

DRAW_RULE = (
    "Pool: commission_b and own cases at labels-v1, English, label status decided with a class. "
    "Strata: the label's risk class; the draw size is split evenly over the classes in the pool, "
    "a class whose share isn't whole getting one more in seeded order. Steps: each engine step, "
    "in order (scope, prohibited, annex_iii, annex_i, art_6_3, transparency, roles), first gets "
    "seeded picks among the cases that exercise it and whose class still has room, until it has "
    "the step minimum and, for annex_iii and annex_i, a positive (label class high_risk) when "
    "the pool has one: while it lacks that positive, the pick is among its positives. Then each "
    "class is filled to its share by a seeded sample. A case exercises: own category a "
    "transparency, b scope, c prohibited, d roles, e annex_i, "
    "f annex_iii; Commission area annex_i or annex_iii_*; label class out_of_scope scope, "
    "prohibited prohibited, limited_risk transparency; art_6_3 when its basis is the Art. 6(3) "
    "filter or it cites a lettered Art. 6(3) condition. Cases are sorted by set, then id."
)
"""The rule as the draw file states it; `draw_cases` implements it."""


class DrawStep(StrEnum):
    """The engine steps decision 036 asks at least `STEP_MINIMUM` cases for, in draw order."""

    SCOPE = "scope"
    PROHIBITED = "prohibited"
    ANNEX_III = "annex_iii"
    ANNEX_I = "annex_i"
    ART_6_3 = "art_6_3"
    TRANSPARENCY = "transparency"
    ROLES = "roles"


OWN_CATEGORY_STEPS: Mapping[str, DrawStep] = {
    "a": DrawStep.TRANSPARENCY,
    "b": DrawStep.SCOPE,
    "c": DrawStep.PROHIBITED,
    "d": DrawStep.ROLES,
    "e": DrawStep.ANNEX_I,
    "f": DrawStep.ANNEX_III,
}
"""An own case's `category:<letter>` tag (docs/LAYOUT.md > eval/cases/own)."""
CLASS_STEPS: Mapping[RiskClass, DrawStep] = {
    RiskClass.OUT_OF_SCOPE: DrawStep.SCOPE,
    RiskClass.PROHIBITED: DrawStep.PROHIBITED,
    RiskClass.LIMITED_RISK: DrawStep.TRANSPARENCY,
}
"""The classes only one step can give: whatever the case's category, that step decided it."""
POSITIVE_STEPS = frozenset({DrawStep.ANNEX_III, DrawStep.ANNEX_I})
"""The steps whose draw includes a positive (a high-risk label through that Annex) when the pool
has one: a draw of only exempt or out-of-area Annex cases wouldn't show that the step finds one."""
CATEGORY_TAG_PREFIX = "category:"
AREA_TAG_PREFIX = "area:"
ANNEX_I_AREA = "annex_i"
ANNEX_III_AREA_PREFIX = "annex_iii_"
ART_6_3_CONDITION = re.compile(r"^art:6:3:[a-d]$")
"""A lettered Art. 6(3) condition in a label citation; a bare `art:6:3` is also cited by the
high-risk labels it doesn't exempt, so it doesn't count."""


class DrawError(ValueError):
    """The pool can't give the draw the rule asks for, or a committed draw would change."""


class DrawnCase(ContractModel):
    """One drawn case, with what the draw read from its labels-v1 label."""

    case_id: str = Field(min_length=1)
    set_name: CaseSet
    risk_class: RiskClass
    steps: tuple[DrawStep, ...]


class Draw(ContractModel):
    """The content of `DRAW_FILE`."""

    labels_ref: str = Field(min_length=1)
    labels_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    seed: int
    size: int = Field(ge=MIN_DRAW_SIZE, le=MAX_DRAW_SIZE)
    step_minimum: int = Field(ge=1)
    rule: str = Field(min_length=1)
    cases: tuple[DrawnCase, ...]

    @model_validator(mode="after")
    def _cases_fit_the_size(self) -> Self:
        ids = [case.case_id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("a case is drawn once")
        if len(ids) != self.size:
            raise ValueError(f"{len(ids)} cases drawn for a size of {self.size}")
        return self

    def by_id(self) -> dict[str, DrawnCase]:
        return {case.case_id: case for case in self.cases}


# --- which cases, which steps ---------------------------------------------------------------------


def case_steps(case: BenchmarkCase) -> tuple[DrawStep, ...]:
    """The steps a case exercises, in `DrawStep` order (the module docstring has the rule)."""
    label_class = case.label.risk_class if isinstance(case.label, CaseLabel) else None
    found = {
        *(_tag_step(case.set_name, tag) for tag in case.tags),
        CLASS_STEPS.get(label_class) if label_class else None,
        DrawStep.ART_6_3 if _rests_on_art_6_3(case) else None,
    }
    return tuple(step for step in DrawStep if step in found)


def _tag_step(set_name: CaseSet, tag: str) -> DrawStep | None:
    """The step an own case's category tag or a Commission rewrite's area tag names."""
    if set_name is CaseSet.OWN and tag.startswith(CATEGORY_TAG_PREFIX):
        return OWN_CATEGORY_STEPS.get(tag.removeprefix(CATEGORY_TAG_PREFIX))
    if set_name is not CaseSet.COMMISSION_B or not tag.startswith(AREA_TAG_PREFIX):
        return None
    area = tag.removeprefix(AREA_TAG_PREFIX)
    if area == ANNEX_I_AREA:
        return DrawStep.ANNEX_I
    return DrawStep.ANNEX_III if area.startswith(ANNEX_III_AREA_PREFIX) else None


def _rests_on_art_6_3(case: BenchmarkCase) -> bool:
    return any(basis.startswith(ART_6_3_FILTER) for basis in case.accepted_bases) or any(
        ART_6_3_CONDITION.fullmatch(citation) for citation in case.label_citation
    )


def drawable_class(case: BenchmarkCase) -> RiskClass | None:
    """The label's class when the case is in the pool: English, decided, with a class."""
    label = case.label
    if case.set_name not in DRAW_SETS or case.language is not DRAW_LANGUAGE:
        return None
    if not isinstance(label, CaseLabel) or label.status is not Status.DECIDED:
        return None
    return label.risk_class


# --- the draw -------------------------------------------------------------------------------------


def make_draw(
    cases: Iterable[BenchmarkCase],
    labels_commit: str,
    seed: int = DRAW_SEED,
    size: int = DRAW_SIZE,
    step_minimum: int = STEP_MINIMUM,
) -> Draw:
    """Draw `size` cases from `cases` (the labels at `labels_commit`) by `DRAW_RULE`."""
    drawn = draw_cases(cases, seed, size, step_minimum)
    return Draw(
        labels_ref=LABELS_REF,
        labels_commit=labels_commit,
        seed=seed,
        size=size,
        step_minimum=step_minimum,
        rule=DRAW_RULE,
        cases=drawn,
    )


def draw_cases(
    cases: Iterable[BenchmarkCase],
    seed: int = DRAW_SEED,
    size: int = DRAW_SIZE,
    step_minimum: int = STEP_MINIMUM,
) -> tuple[DrawnCase, ...]:
    """The drawn cases, sorted by set and id; `DrawError` when the pool can't meet the rule."""
    pool = sorted((case for case in cases if drawable_class(case)), key=lambda case: case.id)
    rng = random.Random(seed)
    quotas = _even_quotas(sorted({_class(case) for case in pool}, key=_class_order), size, rng)
    for risk_class, quota in quotas.items():
        available = sum(_class(case) is risk_class for case in pool)
        if available < quota:
            raise DrawError(f"{risk_class}: {available} cases in the pool for a share of {quota}")
    chosen: tuple[BenchmarkCase, ...] = ()
    for step in DrawStep:
        chosen = _serve_step(pool, chosen, step, step_minimum, quotas, rng)
    for risk_class, quota in quotas.items():
        taken_ids = {case.id for case in chosen}
        rest = [case for case in pool if _class(case) is risk_class and case.id not in taken_ids]
        missing = quota - sum(_class(case) is risk_class for case in chosen)
        chosen = (*chosen, *rng.sample(rest, k=missing))
    ordered = sorted(chosen, key=lambda case: (DRAW_SETS.index(case.set_name), case.id))
    return tuple(_drawn(case) for case in ordered)


def _serve_step(
    pool: Sequence[BenchmarkCase],
    chosen: tuple[BenchmarkCase, ...],
    step: DrawStep,
    step_minimum: int,
    quotas: Mapping[RiskClass, int],
    rng: random.Random,
) -> tuple[BenchmarkCase, ...]:
    """Pick cases that exercise `step` until it has `step_minimum`, and a positive when
    `POSITIVE_STEPS` asks for one, within the class shares."""
    exercising = [case for case in pool if step in case_steps(case)]
    wants_positive = step in POSITIVE_STEPS and any(map(_is_positive, exercising))
    while True:
        covered = sum(step in case_steps(case) for case in chosen)
        needs_positive = wants_positive and not any(
            _is_positive(case) and step in case_steps(case) for case in chosen
        )
        if covered >= step_minimum and not needs_positive:
            return chosen
        taken = Counter(_class(case) for case in chosen)
        taken_ids = {case.id for case in chosen}
        open_cases = [
            case
            for case in exercising
            if case.id not in taken_ids
            and taken[_class(case)] < quotas[_class(case)]
            and (_is_positive(case) or not needs_positive)
        ]
        if not open_cases:
            wanted = "a positive" if needs_positive else f"{step_minimum} cases"
            raise DrawError(
                f"step {step}: {covered} of {step_minimum} cases; no other pool case gives it "
                f"{wanted} within the class shares"
            )
        chosen = (*chosen, rng.choice(open_cases))


def _is_positive(case: BenchmarkCase) -> bool:
    """A high-risk label; for a case exercising an Annex step, reached through that Annex."""
    return _class(case) is RiskClass.HIGH_RISK


def _even_quotas(
    classes: Sequence[RiskClass], size: int, rng: random.Random
) -> dict[RiskClass, int]:
    """`size` split evenly over `classes`; the remainder goes one each to a seeded choice."""
    if not classes:
        raise DrawError("no case in the pool")
    base, remainder = divmod(size, len(classes))
    topped_up = set(rng.sample(list(classes), k=remainder))
    return {risk_class: base + (risk_class in topped_up) for risk_class in classes}


def _class(case: BenchmarkCase) -> RiskClass:
    risk_class = drawable_class(case)
    if risk_class is None:
        raise DrawError(f"case {case.id} is not in the pool")
    return risk_class


def _class_order(risk_class: RiskClass) -> int:
    return list(RiskClass).index(risk_class)


def _drawn(case: BenchmarkCase) -> DrawnCase:
    return DrawnCase(
        case_id=case.id, set_name=case.set_name, risk_class=_class(case), steps=case_steps(case)
    )


def step_counts(draw: Draw) -> dict[DrawStep, int]:
    """How many drawn cases exercise each step, every step listed."""
    return {step: sum(step in case.steps for case in draw.cases) for step in DrawStep}


# --- the labels at the tag ------------------------------------------------------------------------


def cases_at(
    ref: str = LABELS_REF, repo_dir: Path = REPO_DIR
) -> tuple[str, tuple[BenchmarkCase, ...]]:
    """The commit `ref` names and the `DRAW_SETS` cases as they were there, read through
    `git archive` into a temporary folder and validated by `load_cases`."""
    if not ref or ref.startswith("-"):
        raise DrawError(f"not a git ref: {ref!r}")
    try:
        commit = (
            git_bytes(["rev-parse", "--verify", f"{ref}^{{commit}}"], repo_dir).decode().strip()
        )
        archive = git_bytes(["archive", "--format=tar", commit, "--", str(CASES_PATH)], repo_dir)
    except FreezeCheckError as exc:
        raise DrawError(str(exc)) from exc
    with TemporaryDirectory() as folder, tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(folder, filter="data")
        cases_dir = Path(folder) / CASES_PATH
        return commit, tuple(case for s in DRAW_SETS for case in load_cases(s, cases_dir))


# --- the draw file --------------------------------------------------------------------------------


def render_draw(draw: Draw) -> str:
    """The exact text of the draw file: stable key order, two-space indent."""
    return json.dumps(draw.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"


def write_draw(draw: Draw, path: Path = DRAW_FILE) -> bool:
    """Write the draw; `False` when the file already holds it. A different draw is refused: the
    cases are fixed before any checker run (decision 036)."""
    text = render_draw(draw)
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return False
        raise DrawError(f"{path} already holds a different draw; the draw never changes")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def load_draw(path: Path = DRAW_FILE) -> Draw:
    try:
        return Draw.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise DrawError(f"{path}: not a valid draw: {exc}") from exc
