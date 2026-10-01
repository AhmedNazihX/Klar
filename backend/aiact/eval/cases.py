"""Benchmark cases: the schema, the loader and the appliedAI label mapping (INIT > Evaluation).

A case is one system description with its labelled answer. Cases live under
`eval/cases/<set>/**/*.yaml`; a YAML file holds one case (a mapping) or several (a list), so a
soft-wording pair or a consistency triple can share a file. The appliedAI extraction is JSONL in
`eval/private/` (gitignored, licence unclear) and keeps the experts' own coarse label, which
`score_appliedai` maps onto the engine's `RiskClass` and `Status` at scoring time.

A rewritten Commission example (B4) carries its row's `accepted_bases`, `label_status` and
`flip_variants` (decision 001); `metrics.basis_matches` holds the any-of basis rule. Q&A items
(B7) are not system descriptions, so they have their own model (`QAItem`) and loader
(`load_qa_items`) over `eval/cases/qa/`.
"""

import json
from collections import Counter
from collections.abc import Collection, Hashable, Iterable
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import (
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)
from yaml.constructor import ConstructorError

from aiact.retrieval.provisions import PROVISION_ID_RE
from aiact.schemas.base import ContractModel
from aiact.schemas.enums import Language, RiskClass, Role, Status
from aiact.schemas.questions import SLUG_PATTERN
from aiact.settings import BACKEND_DIR

EVAL_DIR = BACKEND_DIR.parent / "eval"
CASES_DIR = EVAL_DIR / "cases"
APPLIEDAI_FILE = EVAL_DIR / "private" / "appliedai.jsonl"
QA_DIR_NAME = "qa"
"""The Q&A items' folder under `eval/cases/` (B7); not a `CaseSet`, as items aren't cases."""
CASE_FILE_SUFFIX = ".yaml"
NOTE_SUFFIXES = (".md",)
"""Notes kept next to cases (the academic set's SOURCE.md); allowed and never loaded."""
IGNORED_FILE_NAMES = frozenset({".gitkeep", ".DS_Store"})
"""Folder placeholders and OS litter; allowed and never loaded."""
YAML_MERGE_TAG = "tag:yaml.org,2002:merge"

CASE_ID_PATTERN = r"^[a-z0-9][a-z0-9_.:-]{0,127}$"
ANNEX_POINT_PATTERN = r"^annex:(I:[AB]:[0-9]+|III:[0-9]+(:[a-z])?)$"
"""A point of Annex I, by section as the corpus numbers it (`annex:I:A:11`, `annex:I:B:21`), or of
Annex III (`annex:III:4:a`)."""
EXAMPLE_ID_PATTERN = r"^hr-ex-[0-9]{3}$"
"""A Commission worked-example id (decision 001)."""
KEY_FACT_KEY_PATTERN = r"^([a-z][a-z0-9_]{0,63}|[a-z]+(:[A-Za-z0-9_.-]+)+)$"
"""A follow-up question's id (`SLUG_PATTERN`) or the topic it is `about` (a provision_id)."""

WITHIN_USE_CASE = "within_use_case"
SAFETY_COMPONENT = "safety_component"
OUTSIDE_USE_CASE = "outside_use_case"
NOT_SAFETY_COMPONENT = "not_safety_component"
ART_6_3_FILTER = "art_6_3_filter"
"""The Art. 6(3) basis; a lettered form such as `art_6_3_filter:d` names the exemption point."""
HIGH_BASES = frozenset({WITHIN_USE_CASE, SAFETY_COMPONENT})
"""The bases of a high-risk verdict; every other basis gives `not_high` (decision 001)."""
BASIS_PATTERN = (
    rf"^({WITHIN_USE_CASE}|{SAFETY_COMPONENT}|{OUTSIDE_USE_CASE}|{NOT_SAFETY_COMPONENT}"
    rf"|{ART_6_3_FILTER}(:[a-d])?)$"
)

AnnexPoint = Annotated[str, StringConstraints(pattern=ANNEX_POINT_PATTERN)]
ProvisionId = Annotated[str, StringConstraints(pattern=PROVISION_ID_RE.pattern)]
Basis = Annotated[str, StringConstraints(pattern=BASIS_PATTERN)]
KeyFactKey = Annotated[str, StringConstraints(pattern=KEY_FACT_KEY_PATTERN)]
NonEmptyText = Annotated[str, StringConstraints(min_length=1)]


class CaseSet(StrEnum):
    """The benchmark sets; each YAML set is the folder of the same name under `eval/cases/`."""

    COMMISSION_B = "commission_b"
    OWN = "own"
    SOFT_PAIRS = "soft_pairs"
    CONSISTENCY = "consistency"
    ACADEMIC = "academic"
    APPLIEDAI = "appliedai"
    ANNEX_MATCH = "annex_match"


OWN_LABELLED_SETS = frozenset(
    {
        CaseSet.COMMISSION_B,
        CaseSet.OWN,
        CaseSet.SOFT_PAIRS,
        CaseSet.CONSISTENCY,
        CaseSet.ANNEX_MATCH,
    }
)
"""Sets whose labels are the student's own, so the cite-or-ambiguous rule applies."""


class AppliedAILabel(StrEnum):
    """The appliedAI experts' label: coarser than `RiskClass`, given against the 2021 draft."""

    HIGH = "high"
    PROHIBITED = "prohibited"
    LOW = "low"
    UNCLEAR = "unclear"


class SourceLabelStatus(StrEnum):
    """A Commission example row's own `label_status` (decision 001), kept on its rewritten case."""

    SETTLED = "settled"
    LEGALLY_AMBIGUOUS = "legally_ambiguous"


class CommissionVerdict(StrEnum):
    """A Commission example verdict (decision 001); `prohibited` occurs only in flip variants."""

    HIGH = "high"
    NOT_HIGH = "not_high"
    PROHIBITED = "prohibited"


class FlipVariant(ContractModel):
    """A "however / if" feature that would flip the verdict (decision 001's product rule): the
    engine should ask about it or flag it, as `metrics.flags_flip_variant` scores."""

    feature: str = Field(min_length=1)
    resulting_verdict: CommissionVerdict
    provision_ids: tuple[ProvisionId, ...] = Field(
        min_length=1, description="The provisions the feature brings in, e.g. `annex:III:7:a`."
    )


class CaseLabel(ContractModel):
    """The expected answer in the engine's vocabulary. An uncertain status keeps the stricter
    reading in `risk_class`, as the engine does (INIT > Risk classes)."""

    risk_class: RiskClass
    status: Status = Status.DECIDED
    role: Role | None = None
    annex_point: tuple[AnnexPoint, ...] = Field(
        default=(),
        description="Every Annex point the system falls under; a result naming any one matches. "
        "A file may give one point as a plain string.",
    )

    @field_validator("annex_point", mode="before")
    @classmethod
    def _one_point_or_several(cls, value: object) -> object:
        if value is None:
            return ()
        return (value,) if isinstance(value, str) else value


class BenchmarkCase(ContractModel):
    """One labelled system description."""

    id: str = Field(pattern=CASE_ID_PATTERN)
    set_name: CaseSet
    language: Language
    description: str = Field(min_length=1)
    label: CaseLabel | AppliedAILabel = Field(
        description="`AppliedAILabel` for the appliedAI set only; `CaseLabel` everywhere else."
    )
    label_citation: tuple[str, ...] = Field(
        default=(),
        description="The provision_ids or Commission example ids that settle the label.",
    )
    source_example_id: str | None = Field(
        default=None,
        pattern=EXAMPLE_ID_PATTERN,
        description="The Commission example a rewritten case comes from (B4, B6).",
    )
    accepted_bases: tuple[Basis, ...] = Field(
        default=(),
        description="The source row's accepted bases; any one counts (`metrics.basis_matches`).",
    )
    label_status: SourceLabelStatus | None = Field(
        default=None, description="The source row's own status; the case's is `label.status`."
    )
    flip_variants: tuple[FlipVariant, ...] = ()
    pair_id: str | None = Field(
        default=None,
        pattern=CASE_ID_PATTERN,
        description="Links the plain and the softened case of a soft-wording pair (B6).",
    )
    key_fact_answers: dict[KeyFactKey, NonEmptyText] = Field(
        default_factory=dict,
        description="Fixed answers to likely key-fact questions, by question id or topic "
        '(decision 019); a question with no entry is answered "don\'t know".',
    )
    business_function: str | None = Field(
        default=None, pattern=SLUG_PATTERN, description="For example `hr`; W1 reports by it."
    )
    as_of: date | None = Field(
        default=None,
        description="The date the case is judged on, for a label that depends on it (the "
        "December 2026 prohibitions); None means the run's date.",
    )
    notes: str | None = None
    tags: tuple[str, ...] = ()

    @property
    def flip_variant_provisions(self) -> tuple[str, ...]:
        """Every provision any flip variant brings in, in order and without repeats."""
        found = (pid for variant in self.flip_variants for pid in variant.provision_ids)
        return tuple(dict.fromkeys(found))

    @model_validator(mode="after")
    def _label_matches_set(self) -> Self:
        is_appliedai = self.set_name is CaseSet.APPLIEDAI
        if is_appliedai != isinstance(self.label, AppliedAILabel):
            raise ValueError("the appliedAI set, and only it, uses an appliedAI label")
        return self

    @model_validator(mode="after")
    def _cite_or_ambiguous(self) -> Self:
        """INIT > Label rules: a label cites what settles it, or is ambiguous with the open
        question and both readings in `notes`."""
        if self.set_name not in OWN_LABELLED_SETS or not isinstance(self.label, CaseLabel):
            return self
        if self.label.status is Status.LEGALLY_AMBIGUOUS:
            if not self.notes:
                raise ValueError("an ambiguous label needs the open question and readings in notes")
        elif not self.label_citation:
            raise ValueError("a label that isn't legally_ambiguous needs a label_citation")
        return self

    @model_validator(mode="after")
    def _source_row_fields(self) -> Self:
        """`accepted_bases` and `label_status` come from a Commission row, so they need its id;
        an ambiguous row stays an ambiguous case (hr-ex-307, decision 001)."""
        if (self.accepted_bases or self.label_status) and self.source_example_id is None:
            raise ValueError("accepted_bases and label_status need a source_example_id")
        is_ambiguous_label = (
            isinstance(self.label, CaseLabel) and self.label.status is Status.LEGALLY_AMBIGUOUS
        )
        if self.label_status is SourceLabelStatus.LEGALLY_AMBIGUOUS and not is_ambiguous_label:
            raise ValueError("a case from a legally_ambiguous row needs a legally_ambiguous label")
        return self

    @model_validator(mode="after")
    def _bases_match_the_class(self) -> Self:
        """A decided high-risk label takes high-risk bases only, any other class none of them."""
        label = self.label
        if not isinstance(label, CaseLabel) or label.status is not Status.DECIDED:
            return self
        is_high = label.risk_class is RiskClass.HIGH_RISK
        if any((basis in HIGH_BASES) is not is_high for basis in self.accepted_bases):
            raise ValueError(f"accepted_bases {list(self.accepted_bases)} contradict the label")
        return self


class QAItem(ContractModel):
    """One Q&A question (B7). An answerable one names the provisions a correct answer must cite
    and a reference answer; an unanswerable one (off-topic, or about a law the corpus doesn't
    hold) names no provisions, and C8/X1 calibrate the relevance cut-off on it."""

    id: str = Field(pattern=CASE_ID_PATTERN)
    language: Language
    question: str = Field(min_length=1)
    answerable: bool = True
    required_provision_ids: tuple[ProvisionId, ...] = ()
    reference_answer: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _answerable_needs_provisions(self) -> Self:
        if not self.answerable:
            if self.required_provision_ids:
                raise ValueError("an unanswerable question has no required_provision_ids")
            return self
        if not self.required_provision_ids or self.reference_answer is None:
            raise ValueError("an answerable question needs required_provision_ids and an answer")
        return self


class CaseFileError(ValueError):
    """A case file that can't be read or doesn't validate; the message names the file."""


def load_cases(case_set: CaseSet, cases_dir: Path = CASES_DIR) -> tuple[BenchmarkCase, ...]:
    """Load and validate every `*.yaml` file under `cases_dir/<set>/`, subfolders included."""
    set_dir = cases_dir / case_set.value
    if not set_dir.is_dir():
        raise FileNotFoundError(f"no case folder for set {case_set.value}: {set_dir}")
    cases = tuple(case for path in _case_files(set_dir) for case in load_yaml_file(path))
    return _pairs_complete(_unique(_in_set(cases, case_set, set_dir), set_dir), set_dir)


def load_yaml_file(path: Path) -> tuple[BenchmarkCase, ...]:
    """Validate one YAML file holding a single case (a mapping) or several (a list)."""
    return _load_yaml(path, BenchmarkCase)


def load_qa_items(cases_dir: Path = CASES_DIR) -> tuple[QAItem, ...]:
    """Load and validate every `*.yaml` file under `cases_dir/qa/` (one item or a list each)."""
    qa_dir = cases_dir / QA_DIR_NAME
    if not qa_dir.is_dir():
        raise FileNotFoundError(f"no Q&A folder: {qa_dir}")
    items = tuple(item for path in _case_files(qa_dir) for item in _load_yaml(path, QAItem))
    return _unique(items, qa_dir)


def load_jsonl(path: Path, case_set: CaseSet = CaseSet.APPLIEDAI) -> tuple[BenchmarkCase, ...]:
    """Validate a JSONL file with one `case_set` case per non-blank line, such as `APPLIEDAI_FILE`.

    `eval/private/` is gitignored and may be absent; a missing file raises `FileNotFoundError`.
    """
    cases: list[BenchmarkCase] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CaseFileError(f"{path}:{number}: not valid JSON: {exc.msg}") from exc
        cases.append(_validate(record, f"{path}:{number}", BenchmarkCase))
    return _unique(_in_set(cases, case_set, path), path)


def derived_from_pile_a(cases: Iterable[BenchmarkCase], pile_a: Collection[str]) -> tuple[str, ...]:
    """The ids of cases whose `source_example_id` is a Pile A example. Pile A stays retrievable,
    so no benchmark case may come from one (B6; INIT > Benchmark isolation); a test asserts this
    is empty against `eval/split.json`."""
    return tuple(case.id for case in cases if case.source_example_id in pile_a)


def _case_files(folder: Path) -> list[Path]:
    """The `*.yaml` files under `folder`, sorted, hidden ones included. Any other file is an
    error, so a `.yml` or a JSON case can't be skipped silently; only `IGNORED_FILE_NAMES` and
    `*.md` notes are allowed, and neither is loaded."""
    files = sorted(path for path in folder.rglob("*") if path.is_file())
    stray = [
        path
        for path in files
        if path.suffix not in (CASE_FILE_SUFFIX, *NOTE_SUFFIXES)
        and path.name not in IGNORED_FILE_NAMES
    ]
    if stray:
        raise CaseFileError(f"not a {CASE_FILE_SUFFIX} case file: {', '.join(map(str, stray))}")
    return [path for path in files if path.suffix == CASE_FILE_SUFFIX]


class _UniqueKeyLoader(yaml.SafeLoader):
    """A safe loader that rejects a key repeated in one mapping (PyYAML keeps the last). Merge
    keys (`<<: *anchor`) are left to the base class, so they load as with `yaml.safe_load`."""

    def construct_mapping(
        self, node: yaml.MappingNode, deep: bool = False
    ) -> dict[Hashable, object]:
        seen: set[Hashable] = set()
        for key_node, _ in node.value:
            if key_node.tag == YAML_MERGE_TAG:
                continue
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                continue  # the base class reports an unhashable key
            if key in seen:
                raise ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _load_yaml[Item: (BenchmarkCase, QAItem)](path: Path, model: type[Item]) -> tuple[Item, ...]:
    try:
        document: object = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise CaseFileError(f"{path}: not valid YAML: {exc}") from exc
    records = [document] if isinstance(document, dict) else document
    if not isinstance(records, list) or not records:
        raise CaseFileError(f"{path}: expected a case mapping or a non-empty list of cases")
    return tuple(
        _validate(record, f"{path}[{index}]", model) for index, record in enumerate(records)
    )


def _in_set(
    cases: Iterable[BenchmarkCase], case_set: CaseSet, where: Path
) -> tuple[BenchmarkCase, ...]:
    checked = tuple(cases)
    for case in checked:
        if case.set_name is not case_set:
            raise CaseFileError(f"case {case.id} has set_name {case.set_name} in {where}")
    return checked


def _validate[Item: (BenchmarkCase, QAItem)](record: object, where: str, model: type[Item]) -> Item:
    try:
        return model.model_validate(record)
    except ValidationError as exc:
        raise CaseFileError(f"{where}: {exc}") from exc


def _unique[Item: (BenchmarkCase, QAItem)](items: Iterable[Item], where: Path) -> tuple[Item, ...]:
    checked = tuple(items)
    seen: set[str] = set()
    for item in checked:
        if item.id in seen:
            raise CaseFileError(f"duplicate case id {item.id} in {where}")
        seen.add(item.id)
    return checked


def _pairs_complete(cases: tuple[BenchmarkCase, ...], where: Path) -> tuple[BenchmarkCase, ...]:
    """A `pair_id` links exactly two cases of a set: the plain and the softened wording (B6)."""
    counts = Counter(case.pair_id for case in cases if case.pair_id is not None)
    broken = sorted(pair_id for pair_id, count in counts.items() if count != 2)
    if broken:
        raise CaseFileError(f"pair_id {', '.join(broken)} must link exactly two cases in {where}")
    return cases


class AppliedAIScore(ContractModel):
    """How one engine answer scores against an appliedAI label (INIT > Label mapping)."""

    is_match: bool
    needs_disagreement_review: bool = Field(
        description="Every mismatch, plus `out_of_scope` for `low`, which matches but is reviewed."
    )
    is_counted_separately: bool = Field(
        description="`needs_more_information` on an `unclear` case, reported on its own."
    )


APPLIEDAI_MATCHES: dict[AppliedAILabel, frozenset[RiskClass]] = {
    AppliedAILabel.HIGH: frozenset({RiskClass.HIGH_RISK}),
    AppliedAILabel.PROHIBITED: frozenset({RiskClass.PROHIBITED}),
    AppliedAILabel.LOW: frozenset(
        {RiskClass.LIMITED_RISK, RiskClass.MINIMAL_RISK, RiskClass.OUT_OF_SCOPE}
    ),
}
"""The engine classes each class-like label accepts. `unclear` is scored on status instead.
Annex II references in the labels are read as Annex I."""


def score_appliedai(label: AppliedAILabel, risk_class: RiskClass, status: Status) -> AppliedAIScore:
    """Score an engine answer against an appliedAI label.

    For high, prohibited and low an uncertain answer is scored on its working-assumption class,
    so "assumed high-risk pending legal review" matches `high`.
    """
    if label is AppliedAILabel.UNCLEAR:
        is_match = status is Status.LEGALLY_AMBIGUOUS
        return AppliedAIScore(
            is_match=is_match,
            needs_disagreement_review=not is_match,
            is_counted_separately=status is Status.NEEDS_MORE_INFORMATION,
        )
    is_match = risk_class in APPLIEDAI_MATCHES[label]
    is_out_of_scope_low = label is AppliedAILabel.LOW and risk_class is RiskClass.OUT_OF_SCOPE
    return AppliedAIScore(
        is_match=is_match,
        needs_disagreement_review=not is_match or is_out_of_scope_low,
        is_counted_separately=False,
    )
