"""Provider refusals in a stored run (aiact/eval/refusals.py): engine-refused, answered by the
second model, refused by both, and the accuracy with and without them."""

from aiact.eval.metrics import Rate
from aiact.eval.refusals import (
    RefusalCase,
    calls_by_model,
    engine_refused_nodes,
    render_refusals,
    summarize_refusals,
)
from aiact.schemas import RiskClass
from tests.eval.outcomes import case, outcome, refused_result, result

LUNA = "openai/gpt-6-luna-20260922"
GEMINI = "google/gemini-3.1-flash-lite"
EMBEDDING = "qwen/qwen3-embedding-8b"


def served(*second_nodes: str) -> dict[str, dict[str, int]]:
    """Every node served by Luna (and the embedding model); `second_nodes` also by Gemini."""
    models = {node: {LUNA: 1, EMBEDDING: 2} for node in ("facts", "scope", "prohibited")}
    return {
        node: calls | ({GEMINI: 1} if node in second_nodes else {})
        for node, calls in models.items()
    }


def test_a_node_the_second_model_served_was_refused_by_the_engine_model() -> None:
    assert engine_refused_nodes(served("prohibited"), GEMINI) == ("prohibited",)
    assert engine_refused_nodes(served(), GEMINI) == ()
    assert engine_refused_nodes(served("prohibited"), None) == ()


def _cases() -> list[RefusalCase]:
    return [
        # answered by Luna, a hit
        RefusalCase(outcome=outcome(case("a")), models=served()),
        # refused by Luna, answered by Gemini, a miss
        RefusalCase(
            outcome=outcome(case("b"), result(RiskClass.MINIMAL_RISK)), models=served("facts")
        ),
        # refused by both: not assessed
        RefusalCase(outcome=outcome(case("c"), refused_result()), models=served("prohibited")),
        # failed: counted in none of them
        RefusalCase(outcome=outcome(case("d"), failed=True), models=served("scope")),
    ]


def test_refusals_are_counted_by_case() -> None:
    summary = summarize_refusals(_cases(), GEMINI)
    assert summary.answered == 3
    assert summary.engine_refused == ("b", "c")
    assert summary.second_answered == ("b",)
    assert summary.both_refused == ("c",)


def test_accuracy_is_given_with_and_without_the_refused_cases() -> None:
    summary = summarize_refusals(_cases(), GEMINI)
    assert summary.accuracy == Rate(hits=1, total=3)  # a hit, b miss, d failed; c left out
    assert summary.accuracy_not_assessed_as_miss == Rate(hits=1, total=4)
    assert summary.accuracy_without_second_answered == Rate(hits=1, total=2)


def test_a_not_assessed_case_counts_as_refused_without_a_second_model_call() -> None:
    """The second call failed transiently (decision 033): no Gemini reply, still refused."""
    cases = [RefusalCase(outcome=outcome(case("c"), refused_result()), models=served())]
    summary = summarize_refusals(cases, GEMINI)
    assert (summary.engine_refused, summary.both_refused) == (("c",), ("c",))


def test_calls_are_totalled_by_model() -> None:
    assert calls_by_model([served("facts"), served()]) == {EMBEDDING: 12, LUNA: 6, GEMINI: 1}


def test_the_section_names_the_cases_and_the_second_model() -> None:
    lines = render_refusals(summarize_refusals(_cases(), GEMINI))
    assert f"- Second model for refused requests: `{GEMINI}`" in lines
    assert "- Refused by the engine model: 2 of 3 (66.7%): b, c" in lines
    assert "- Answered by the second model: 1 of 3 (33.3%): b" in lines
    assert "- Refused by both (not assessed): 1 of 3 (33.3%): c" in lines
    assert "- Second model's refusal rate: 1 of 2 (50.0%)" in lines
    assert "| Reported (not-assessed cases left out) | 33.3% | 1/3 |" in lines
    assert "| Not-assessed cases counted as misses | 25.0% | 1/4 |" in lines
    assert "| Without the cases the second model answered | 50.0% | 1/2 |" in lines


def test_a_run_without_a_recorded_second_model_says_so() -> None:
    lines = render_refusals(summarize_refusals(_cases(), None))
    assert "- Second model: not recorded for this run (refusals can't be told apart)." in lines
    assert "- Refused by the engine model: 1 of 3 (33.3%): c" in lines
