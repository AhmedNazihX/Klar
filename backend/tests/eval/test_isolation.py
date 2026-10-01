"""The isolation measurements (aiact/eval/isolation.py) on hand-made inputs; the checks against
the real corpus and benchmark are in tests/test_isolation.py."""

from pathlib import Path

import pytest
import yaml

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


def _write_cases(folder: Path, name: str, records: list[dict[str, object]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(yaml.safe_dump(records), encoding="utf-8")


def _case(case_id: str, set_name: str, description: str) -> dict[str, object]:
    return {
        "id": case_id,
        "set_name": set_name,
        "language": "en",
        "description": description,
        "label": {"risk_class": "high_risk"},
        "label_citation": ["annex:III:4:a"],
    }


def test_case_texts_hold_every_yaml_case_in_set_and_file_order(tmp_path: Path) -> None:
    commission = tmp_path / "commission_b"
    _write_cases(commission / "sub", "b.yaml", [_case("cb-3", "commission_b", "Third.")])
    _write_cases(
        commission,
        "a.yaml",
        [_case("cb-1", "commission_b", "First."), _case("cb-2", "commission_b", "Second.")],
    )
    academic = "Role: Provider\nDomain: Employment, workers management\nInput data: CVs"
    _write_cases(tmp_path / "academic", "high_risk.yaml", [_case("ac-1", "academic", academic)])
    texts = isolation.case_texts(tmp_path, None)
    assert texts == (
        BenchmarkText("cb-1", "First."),
        BenchmarkText("cb-2", "Second."),
        BenchmarkText("cb-3", "Third."),
        BenchmarkText("ac-1", "Role: Provider\nInput data: CVs"),
    )


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
    with pytest.raises(isolation.IsolationFileError, match="delete the file"):
        isolation.load_cache(path, "other-model", 2)
    assert isolation.load_cache(tmp_path / "absent.json", "m", 2).vectors == {}


def test_a_corrupt_cache_is_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "embeddings.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(isolation.IsolationFileError, match="not a valid vector cache"):
        isolation.load_cache(path, "m", 2)


def words(prefix: str, count: int) -> str:
    """`count` distinct letter-only words (digits would be dropped by the normalisation)."""
    return " ".join(f"{prefix}{chr(97 + i % 26)}{chr(97 + i // 26)}" for i in range(count))


def test_a_long_run_is_found_in_a_row_that_is_not_the_highest_coverage_one() -> None:
    """Row A shares more 6-word runs, but only in 10-word pieces; row B shares fewer, as one
    30-word run. The text is a repeat through row B."""
    quote, rest = words("q", isolation.PROSE_RUN_LIMIT), words("z", 60).split()
    pieces = [" ".join(rest[i : i + 10]) for i in range(0, len(rest), 10)]
    row_a = " filler break ".join(pieces)
    text = BenchmarkText("hr-ex-900", f"{quote} {' '.join(rest)}")
    (match,) = isolation.closest_by_ngram((text,), _rows((row_a, None), (quote, None)))
    grams = len(isolation.ngrams(isolation.normalised_words(text.text)))
    assert (match.provision_id, match.longest_run) == ("guide:test:para:2", 30)
    assert match.coverage == 25 / grams < 30 / grams  # row A has the higher coverage
    assert match.is_near_duplicate


def test_a_long_verbatim_run_in_prose_is_a_repeat_at_low_coverage() -> None:
    quote = words("q", isolation.PROSE_RUN_LIMIT)  # statutory-length quote, then 60 new words
    text = BenchmarkText("hr-ex-900", f"{quote} {words('z', 60)}")
    (match,) = isolation.closest_by_ngram((text,), _rows((quote, None)))
    assert match.coverage < isolation.PROSE_COVERAGE_LIMIT
    assert match.longest_run == isolation.PROSE_RUN_LIMIT
    assert match.is_near_duplicate
    example_row = isolation.NgramMatch("k", "guide:x:ex:001", True, match.coverage, 60)
    assert not example_row.is_near_duplicate  # sibling examples: coverage only
