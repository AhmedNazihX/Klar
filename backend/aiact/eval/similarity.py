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
  missing (a Pile A source, or a case not embedded since its last edit); under a limit, a case
  without a cosine fails, since it wasn't measured.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from aiact.eval.cases import CASES_DIR, BenchmarkCase
from aiact.eval.isolation import (
    EMBEDDINGS_FILE,
    EmbeddingCache,
    ExampleText,
    decode_vector,
    load_example_texts,
    longest_shared_words,
    normalised_words,
    parse_cache,
    text_key,
    yaml_cases,
)
from aiact.eval.split import EXAMPLES_FILE

RUN_LIMIT = 8
"""A word run this long or longer, shared with the source example, fails the case."""
NO_COSINE = "no cosine: run `aiact evaluate isolation-embed`"


class SimilarityError(ValueError):
    """Nothing to check, or a case whose source example doesn't exist; the message says which."""


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
        """Why the case is too close to its source (or unmeasured); empty when it passes."""
        reasons: list[str] = []
        if self.run.length >= limits.run:
            reasons.append(f"shares a {self.run.length}-word run with the {self.run.part}")
        if limits.cosine is not None:
            if self.cosine is None:
                reasons.append(NO_COSINE)
            elif self.cosine >= limits.cosine:
                reasons.append(f"cosine {self.cosine:.3f} >= {limits.cosine}")
        return tuple(reasons)


# --- Inputs ---------------------------------------------------------------------------------


def read_cache(path: Path = EMBEDDINGS_FILE) -> EmbeddingCache | None:
    """The isolation vector cache, whatever its model (both vectors of a pair come from it), or
    None when there is none."""
    return parse_cache(path) if path.is_file() else None


def sourced_cases(cases_dir: Path = CASES_DIR) -> tuple[BenchmarkCase, ...]:
    """Every YAML case under `cases_dir` with a `source_example_id`. A missing folder raises
    FileNotFoundError and a folder without such a case SimilarityError: a mistyped path must not
    pass as "nothing too close"."""
    if not cases_dir.is_dir():
        raise FileNotFoundError(f"no case folder: {cases_dir}")
    cases = tuple(case for case in yaml_cases(cases_dir) if case.source_example_id is not None)
    if not cases:
        raise SimilarityError(f"no case with a source_example_id under {cases_dir}")
    return cases


# --- Measurements ---------------------------------------------------------------------------


def source_parts(source: ExampleText) -> tuple[tuple[str, str], ...]:
    """The Commission-written texts of an example, named: `text`, then `lead_in`."""
    return (("text", source.text),) + ((("lead_in", source.lead_in),) if source.lead_in else ())


def closest_run(description: str, source: ExampleText) -> SharedRun:
    """The longest run the description shares with any part of the source (`text` on a tie)."""
    words = normalised_words(description)
    runs = (
        SharedRun(name, longest_shared_words(words, normalised_words(part)))
        for name, part in source_parts(source)
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
    sources: Mapping[str, ExampleText],
    cache: EmbeddingCache | None,
) -> tuple[CaseSimilarity, ...]:
    """Every sourced case's closeness to its source example, longest run first. A case whose
    source example isn't among `sources` raises SimilarityError."""
    results: list[CaseSimilarity] = []
    for case in cases:
        source_id = case.source_example_id
        if source_id is None:
            continue
        source = sources.get(source_id)
        if source is None:
            raise SimilarityError(f"case {case.id}: unknown source example {source_id}")
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
    sources = {example.example_id: example for example in load_example_texts(examples_file)}
    return measure(sourced_cases(cases_dir), sources, read_cache(embeddings_file))
