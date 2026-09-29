"""The isolation measurements (aiact/eval/isolation.py) on hand-made inputs; the checks against
the real corpus and benchmark are in tests/test_isolation.py."""

from pathlib import Path

import pytest

from aiact.eval import isolation
from aiact.eval.cases import CaseSet
from aiact.eval.isolation import BenchmarkText, CorpusRow, EmbeddingCache
from aiact.llm.embeddings import EmbeddingBatch

EXAMPLE = (
    "An AI system intended to analyse past, completed eligibility files for quality assurance."
)


def test_words_are_compared_without_case_digits_apostrophes_or_inner_hyphens() -> None:
    words = isolation.normalised_words("The provider’s real‑time chatbot114 (Art. 6)")  # noqa: RUF001
    assert words == ("the", "providers", "realtime", "chatbot", "art")


def test_the_longest_shared_run_counts_words() -> None:
    first = isolation.normalised_words("a b c d e f")
    assert isolation.longest_shared_run(first, isolation.normalised_words("x c d e y")) == 3
    assert isolation.longest_shared_run(first, ()) == 0


def test_the_academic_domain_line_is_left_out() -> None:
    description = "Role: Provider\nDomain: Employment, workers management\nInput data: CVs"
    assert isolation.checked_description(CaseSet.ACADEMIC, description) == (
        "Role: Provider\nInput data: CVs"
    )
    assert isolation.checked_description(CaseSet.OWN, description) == description


def _rows(*texts: tuple[str, str | None]) -> tuple[CorpusRow, ...]:
    return tuple(
        CorpusRow(f"guide:test:para:{n}", "en", example_id, text)
        for n, (text, example_id) in enumerate(texts, start=1)
    )


def test_a_repeat_inside_prose_is_a_near_duplicate() -> None:
    rows = _rows(
        (f"(102) Some context first. {EXAMPLE} And an assessment.", None),
        ("Unrelated text about lifts and doors that close too early.", None),
    )
    (match,) = isolation.closest_by_ngram((BenchmarkText("hr-ex-269", EXAMPLE),), rows)
    assert (match.provision_id, match.coverage, match.is_example_row) == (
        "guide:test:para:1",
        1.0,
        False,
    )
    assert match.longest_run == len(isolation.normalised_words(EXAMPLE))
    assert match.is_near_duplicate


def test_example_rows_have_the_higher_limit() -> None:
    half = " ".join(isolation.normalised_words(EXAMPLE)[:9])
    rows = _rows((f"{half} but for another purpose entirely here", "hr-ex-268"))
    (match,) = isolation.closest_by_ngram((BenchmarkText("hr-ex-269", EXAMPLE),), rows)
    assert match.is_example_row
    assert isolation.PROSE_COVERAGE_LIMIT <= match.coverage < isolation.EXAMPLE_COVERAGE_LIMIT
    assert not match.is_near_duplicate


def test_a_text_that_shares_no_run_has_no_match() -> None:
    rows = _rows(("Nothing in common with the example at all, really.", None))
    assert isolation.closest_by_ngram((BenchmarkText("k", EXAMPLE),), rows) == ()


def test_vectors_round_trip_at_half_precision() -> None:
    vector = [0.5, -0.25, 0.1234]
    decoded = isolation.decode_vector(isolation.encode_vector(vector))
    assert decoded == pytest.approx(vector, abs=1e-3)


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        self.calls.append(texts)
        return EmbeddingBatch([[1.0, 0.0]] * len(texts), tokens=3 * len(texts), cost_usd=0.001)


def test_refresh_embeds_only_missing_texts_and_drops_stale_ones(tmp_path: Path) -> None:
    kept, new = BenchmarkText("a", "kept text"), BenchmarkText("b", "new text")
    stale_key = isolation.text_key("a case that was removed")
    vectors = {
        isolation.text_key(kept.text): isolation.encode_vector([0.0, 1.0]),
        stale_key: isolation.encode_vector([1.0, 0.0]),
    }
    cache = EmbeddingCache(model="m", dims=2, vectors=vectors)
    embedder = FakeEmbedder()
    outcome = isolation.refresh_cache(cache, (kept, new), embedder)
    assert embedder.calls == [["new text"]]
    assert (outcome.embedded, outcome.removed, outcome.tokens) == (1, 1, 3)
    assert set(outcome.cache.vectors) == {
        isolation.text_key(kept.text),
        isolation.text_key(new.text),
    }
    assert stale_key in cache.vectors  # the input cache is unchanged

    path = tmp_path / "embeddings.json"
    isolation.write_cache(outcome.cache, path)
    assert isolation.load_cache(path, "m", 2) == outcome.cache
    assert isolation.load_cache(path, "other-model", 2).vectors == {}
