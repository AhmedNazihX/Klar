"""Rewrite-vs-source similarity check (story B4a; INIT > Benchmark isolation 3).

A case rewritten from a Commission example (`source_example_id` set) must not reuse the
Commission's wording. For each such case this measures, against its own source example:
- **The longest shared word run** with the example's `text` and its `lead_in` (the list's
  introduction, Commission prose too), compared as `isolation.normalised_words` compares text:
  lower-case, letters only. A run of `RUN_LIMIT` words or more fails the case (the `/case`
  skill's rule: rewrite any case at 8 words or more).
- **The embedding cosine** between the description and the example's `text`, read from the
  isolation vector cache (`isolation.EMBEDDINGS_FILE`, filled by `aiact evaluate isolation-embed`),
  so the check makes no paid call. A rewrite keeps the facts that decide the verdict, so a high
  cosine is expected (B13: a Pile B text scores a median 0.918 against its own row); the cosine
  is reported and gates a case only when a limit is given. It is None when either vector is
  missing (a Pile A source, or a case not yet embedded).
"""

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseSet, load_cases
from aiact.eval.isolation import (
    EMBEDDINGS_FILE,
    EmbeddingCache,
    decode_vector,
    normalised_words,
    text_key,
)
from aiact.eval.split import EXAMPLES_FILE

RUN_LIMIT = 8
"""A word run this long or longer, shared with the source example, fails the case."""


class SimilarityFileError(ValueError):
    """An input that can't be read as expected, or a case whose source example doesn't exist;
    the message names the file or the case."""


class SourceExample(BaseModel):
    """The fields of a B2 example row the check compares with."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    example_id: str = Field(pattern=r"^hr-ex-[0-9]{3}$")
    text: str = Field(min_length=1)
    lead_in: str | None = None

    def parts(self) -> tuple[tuple[str, str], ...]:
        """The Commission-written texts to compare with, named: `text`, then `lead_in`."""
        return (("text", self.text),) + ((("lead_in", self.lead_in),) if self.lead_in else ())


@dataclass(frozen=True)
class SharedRun:
    """The longest word run a description shares with one part of its source example."""

    part: str
    words: tuple[str, ...]

    @property
    def length(self) -> int:
        return len(self.words)


@dataclass(frozen=True)
class Limits:
    run: int = RUN_LIMIT
    cosine: float | None = None
    """None: the cosine is reported, not checked."""


@dataclass(frozen=True)
class CaseSimilarity:
    """How close one case is to its source example."""

    case_id: str
    source_example_id: str
    run: SharedRun
    cosine: float | None

    def failures(self, limits: Limits) -> tuple[str, ...]:
        """Why the case is too close to its source; empty when it passes."""
        reasons: list[str] = []
        if self.run.length >= limits.run:
            reasons.append(f"shares a {self.run.length}-word run with the {self.run.part}")
        if limits.cosine is not None and self.cosine is not None and self.cosine >= limits.cosine:
            reasons.append(f"cosine {self.cosine:.3f} >= {limits.cosine}")
        return tuple(reasons)


# --- Inputs ---------------------------------------------------------------------------------


def load_sources(path: Path = EXAMPLES_FILE) -> dict[str, SourceExample]:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        rows = [SourceExample.model_validate(json.loads(line)) for line in lines if line.strip()]
    except (json.JSONDecodeError, ValidationError) as error:
        raise SimilarityFileError(f"{path}: not a valid example row: {error}") from error
    return {row.example_id: row for row in rows}


def read_cache(path: Path = EMBEDDINGS_FILE) -> EmbeddingCache | None:
    """The isolation vector cache, whatever its model (both vectors of a pair come from it), or
    None when there is none."""
    if not path.is_file():
        return None
    try:
        return EmbeddingCache.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise SimilarityFileError(f"{path}: not a valid vector cache: {error}") from error


def sourced_cases(cases_dir: Path = CASES_DIR) -> tuple[BenchmarkCase, ...]:
    """Every case of the YAML sets that exist with a `source_example_id`."""
    sets = (s for s in CaseSet if s is not CaseSet.APPLIEDAI and (cases_dir / s.value).is_dir())
    cases = (case for case_set in sets for case in load_cases(case_set, cases_dir))
    return tuple(case for case in cases if case.source_example_id is not None)


# --- Measurements ---------------------------------------------------------------------------


def longest_shared_words(first: Sequence[str], second: Sequence[str]) -> tuple[str, ...]:
    """The longest run of words both sequences contain (the first one found on a tie)."""
    matcher = SequenceMatcher(None, first, second, autojunk=False)
    match = matcher.find_longest_match(0, len(first), 0, len(second))
    return tuple(first[match.a : match.a + match.size])


def closest_run(description: str, source: SourceExample) -> SharedRun:
    """The longest run the description shares with any part of the source (`text` on a tie)."""
    words = normalised_words(description)
    runs = (
        SharedRun(name, longest_shared_words(words, normalised_words(part)))
        for name, part in source.parts()
    )
    return max(runs, key=lambda run: run.length)


def cosine(first: Sequence[float], second: Sequence[float]) -> float:
    norms = math.hypot(*first) * math.hypot(*second)
    if norms == 0:
        raise ValueError("a zero vector has no cosine")
    return math.fsum(a * b for a, b in zip(first, second, strict=True)) / norms


def cached_cosine(cache: EmbeddingCache | None, first: str, second: str) -> float | None:
    """The cosine of two texts' cached vectors, or None when either is missing."""
    if cache is None:
        return None
    vectors = [cache.vectors.get(text_key(text)) for text in (first, second)]
    if vectors[0] is None or vectors[1] is None:
        return None
    return cosine(decode_vector(vectors[0]), decode_vector(vectors[1]))


def measure(
    cases: Iterable[BenchmarkCase],
    sources: Mapping[str, SourceExample],
    cache: EmbeddingCache | None,
) -> tuple[CaseSimilarity, ...]:
    """Every case's closeness to its source example, longest run first. A case whose source
    example isn't among `sources` raises SimilarityFileError."""
    results: list[CaseSimilarity] = []
    for case in cases:
        source_id = case.source_example_id
        if source_id is None:
            continue
        source = sources.get(source_id)
        if source is None:
            raise SimilarityFileError(f"case {case.id}: unknown source example {source_id}")
        run = closest_run(case.description, source)
        closeness = cached_cosine(cache, case.description, source.text)
        results.append(CaseSimilarity(case.id, source_id, run, closeness))
    return tuple(sorted(results, key=lambda r: (-r.run.length, -(r.cosine or 0.0), r.case_id)))


def check_similarity(
    cases_dir: Path = CASES_DIR,
    examples_file: Path = EXAMPLES_FILE,
    embeddings_file: Path = EMBEDDINGS_FILE,
) -> tuple[CaseSimilarity, ...]:
    """Measure every sourced case of `cases_dir` against the examples in `examples_file`."""
    return measure(
        sourced_cases(cases_dir), load_sources(examples_file), read_cache(embeddings_file)
    )
