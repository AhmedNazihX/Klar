"""The rewrite-vs-source check (aiact/eval/similarity.py) on hand-made inputs: an invented
source example, a planted near-copy of it and a clean rewrite, with fake vectors."""

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import similarity
from aiact.eval.cases import BenchmarkCase
from aiact.eval.isolation import (
    EmbeddingCache,
    encode_vector,
    longest_shared_run,
    normalised_words,
    text_key,
)

SOURCE_ID = "hr-ex-999"
SOURCE_TEXT = (
    "A municipal agency deploys a tool that reads scanned tenancy applications, extracts the "
    "declared household income and ranks each applicant for access to subsidised flats."
)
LEAD_IN = "Examples of systems used by public bodies to allocate essential benefits include:"
NEAR_COPY = (
    "We are a 40-person software firm. Our client, a city office, uses our product: it reads "
    "scanned tenancy applications, extracts the declared household income and ranks each "
    "applicant for access to subsidised flats. It also has a dark mode."
)
CLEAN_REWRITE = (
    "Our housing department bought a screening product from a Dutch vendor last spring. Staff "
    "upload the forms people send in when they want a cheaper council flat; the software pulls "
    "out what each family earns and puts the families in order, which decides who is offered a "
    "home first. The same vendor also sells us a parking permit portal."
)
LEAD_IN_COPY = (
    "Our city lists, among systems used by public bodies to allocate essential benefits, a "
    "scoring tool for flat applicants."
)
CLEAN_RUN_CEILING = 3
"""The clean rewrite shares only short phrases ("each applicant"-length) with the source."""


def make_case(case_id: str, description: str, source_id: str | None = SOURCE_ID) -> BenchmarkCase:
    return BenchmarkCase.model_validate(
        {
            "id": case_id,
            "set_name": "commission_b",
            "language": "en",
            "description": description,
            "label": {"risk_class": "high_risk"},
            "label_citation": ["annex:III:5:a"],
            "source_example_id": source_id,
        }
    )


SOURCE = similarity.SourceExample(example_id=SOURCE_ID, text=SOURCE_TEXT, lead_in=LEAD_IN)
SOURCES = {SOURCE_ID: SOURCE}


def fake_cache(vectors: dict[str, list[float]]) -> EmbeddingCache:
    encoded = {text_key(text): encode_vector(vector) for text, vector in vectors.items()}
    return EmbeddingCache(model="fake", dims=3, vectors=encoded)


CACHE = fake_cache(
    {SOURCE_TEXT: [1.0, 0.0, 0.0], NEAR_COPY: [0.99, 0.14, 0.0], CLEAN_REWRITE: [0.6, 0.8, 0.0]}
)


# --- Measurements ---------------------------------------------------------------------------


def test_a_planted_near_copy_fails_on_its_shared_run() -> None:
    (result,) = similarity.measure([make_case("b-near", NEAR_COPY)], SOURCES, None)
    expected = "reads scanned tenancy applications extracts the declared household income and "
    expected += "ranks each applicant for access to subsidised flats"
    assert result.run == similarity.SharedRun("text", tuple(expected.split()))
    assert result.run.length >= similarity.RUN_LIMIT
    assert result.failures(similarity.Limits()) == (
        f"shares a {result.run.length}-word run with the text",
    )


def test_a_clean_rewrite_passes() -> None:
    (result,) = similarity.measure([make_case("b-clean", CLEAN_REWRITE)], SOURCES, CACHE)
    assert result.run.length <= CLEAN_RUN_CEILING
    assert result.failures(similarity.Limits()) == ()
    assert result.failures(similarity.Limits(cosine=0.95)) == ()


def test_the_run_limit_is_inclusive() -> None:
    (result,) = similarity.measure([make_case("b-near", NEAR_COPY)], SOURCES, None)
    assert result.failures(similarity.Limits(run=result.run.length))
    assert not result.failures(similarity.Limits(run=result.run.length + 1))


def test_the_lead_in_is_compared_too() -> None:
    (result,) = similarity.measure([make_case("b-lead", LEAD_IN_COPY)], SOURCES, None)
    assert result.run.part == "lead_in"
    assert (
        " ".join(result.run.words) == "systems used by public bodies to allocate essential benefits"
    )
    assert result.failures(similarity.Limits())


def test_the_cosine_comes_from_the_cache_and_gates_only_with_a_limit() -> None:
    near, clean = similarity.measure(
        [make_case("b-clean", CLEAN_REWRITE), make_case("b-near", NEAR_COPY)], SOURCES, CACHE
    )
    assert (near.case_id, clean.case_id) == ("b-near", "b-clean")
    assert near.cosine == pytest.approx(0.99, abs=1e-2)
    assert clean.cosine == pytest.approx(0.6, abs=1e-2)
    assert "cosine 0.990 >= 0.95" in near.failures(similarity.Limits(cosine=0.95))
    assert clean.failures(similarity.Limits(run=99, cosine=0.95)) == ()


def test_a_text_missing_from_the_cache_has_no_cosine() -> None:
    (result,) = similarity.measure([make_case("b-lead", LEAD_IN_COPY)], SOURCES, CACHE)
    assert result.cosine is None
    assert similarity.cached_cosine(None, SOURCE_TEXT, NEAR_COPY) is None


def test_cases_without_a_source_are_skipped_and_an_unknown_source_is_an_error() -> None:
    assert similarity.measure([make_case("b-own", CLEAN_REWRITE, None)], SOURCES, None) == ()
    with pytest.raises(similarity.SimilarityFileError, match="hr-ex-998"):
        similarity.measure([make_case("b-x", CLEAN_REWRITE, "hr-ex-998")], SOURCES, None)


def test_the_longest_run_matches_the_isolation_measure() -> None:
    first, second = normalised_words(NEAR_COPY), normalised_words(SOURCE_TEXT)
    shared = similarity.longest_shared_words(first, second)
    assert len(shared) == longest_shared_run(first, second)


def test_a_zero_vector_has_no_cosine() -> None:
    with pytest.raises(ValueError, match="zero vector"):
        similarity.cosine([0.0, 0.0], [1.0, 0.0])


# --- The command ----------------------------------------------------------------------------


def write_inputs(tmp_path: Path, descriptions: dict[str, str]) -> list[str]:
    """Cases, examples and a vector cache under `tmp_path`; returns the command's options."""
    folder = tmp_path / "cases" / "commission_b"
    folder.mkdir(parents=True)
    records = [make_case(i, d).model_dump(mode="json") for i, d in descriptions.items()]
    (folder / "cases.yaml").write_text(yaml.safe_dump(records), encoding="utf-8")
    examples = tmp_path / "examples.jsonl"
    examples.write_text(json.dumps(SOURCE.model_dump()) + "\n", encoding="utf-8")
    cache = tmp_path / "embeddings.json"
    cache.write_text(CACHE.model_dump_json(), encoding="utf-8")
    return [
        "--cases-dir",
        str(tmp_path / "cases"),
        "--examples",
        str(examples),
        "--embeddings",
        str(cache),
    ]


def test_the_command_fails_on_a_near_copy(tmp_path: Path) -> None:
    options = write_inputs(tmp_path, {"b-near": NEAR_COPY, "b-clean": CLEAN_REWRITE})
    result = CliRunner().invoke(app, ["evaluate", "similarity", *options])
    assert result.exit_code == 1, result.output
    assert "FAIL b-near <- hr-ex-999" in result.stdout
    assert "ok   b-clean <- hr-ex-999" in result.stdout
    assert "2 cases with a source example, 1 too close" in result.stderr


def test_the_command_passes_clean_rewrites(tmp_path: Path) -> None:
    options = write_inputs(tmp_path, {"b-clean": CLEAN_REWRITE})
    result = CliRunner().invoke(app, ["evaluate", "similarity", *options, "--max-cosine", "0.95"])
    assert result.exit_code == 0, result.output
    assert "cosine 0.600" in result.stdout
    assert "1 cases with a source example, 0 too close" in result.stdout


def test_the_command_reports_a_bad_example_file(tmp_path: Path) -> None:
    options = write_inputs(tmp_path, {"b-clean": CLEAN_REWRITE})
    (tmp_path / "examples.jsonl").write_text("not json\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["evaluate", "similarity", *options])
    assert result.exit_code == 2
    assert "not a valid example row" in result.stderr
