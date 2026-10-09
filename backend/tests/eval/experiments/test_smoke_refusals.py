"""Decision 033's rule over the engine model's and a second model's smoke runs, the stored flag it
reads, and the printed table (X2b). Probe ids here are made up, not benchmark cases."""

from collections.abc import Mapping
from uuid import uuid4

import pytest
from pydantic import JsonValue

from aiact.eval.experiments import smoke_refusals, smoke_verdict
from aiact.eval.experiments.smoke import NodeName, ProbeKind
from aiact.eval.experiments.smoke_refusals import RunInfo, Verdict, tabulate
from aiact.eval.experiments.smoke_verdict import ProbeScore

A, R, B, F = ProbeKind.ANSWERED, ProbeKind.REFUSED, ProbeKind.BROKEN, ProbeKind.FAILED


def probe(pid: str, kind: ProbeKind, correct: bool | None = None) -> ProbeScore:
    if correct is None and kind is A and not pid.startswith("facts:"):
        correct = True
    return ProbeScore(pid, kind, correct)


def refused(*pids: str) -> list[ProbeScore]:
    return [probe(pid, R) for pid in pids]


def row(table: smoke_refusals.RefusalTable, node: NodeName) -> smoke_refusals.NodeRow:
    return next(r for r in table.rows if r.node is node)


def test_the_rule_is_fixed_before_the_run() -> None:
    assert (smoke_refusals.ANSWERED_SHARE, smoke_refusals.MATCHED_SHARE) == ((4, 5), (4, 5))
    assert smoke_verdict.FAILED_SHARE_LIMIT == (1, 10)


def test_a_probe_refused_in_any_engine_run_is_counted_once() -> None:
    first = [*refused("prohibited:c-1"), probe("prohibited:c-2", A), probe("scope:b-1", A)]
    second_run = [probe("prohibited:c-1", A), *refused("prohibited:c-2")]
    table = tabulate([first, second_run], [probe("prohibited:c-1", A), probe("prohibited:c-2", A)])
    prohibited = row(table, NodeName.PROHIBITED)
    assert (prohibited.cases_run, prohibited.refused, prohibited.answered) == (2, 2, 2)
    assert (row(table, NodeName.SCOPE).cases_run, row(table, NodeName.SCOPE).refused) == (1, 0)
    assert table.verdict is Verdict.ADOPT


def test_each_outcome_of_the_second_model_has_its_column() -> None:
    engine = [refused("prohibited:c-1", "prohibited:c-2", "prohibited:c-3", "prohibited:c-4",
                      "prohibited:c-5", "facts:c-1")]  # fmt: skip
    second = [
        probe("prohibited:c-1", A, True),
        probe("prohibited:c-2", A, False),
        probe("prohibited:c-3", R),
        probe("prohibited:c-4", B, False),
        probe("facts:c-1", A),
    ]  # prohibited:c-5 not run: no answer
    table = tabulate(engine, second)
    prohibited = row(table, NodeName.PROHIBITED)
    assert (prohibited.refused, prohibited.answered, prohibited.matched) == (5, 2, 1)
    assert (prohibited.labelled, prohibited.refused_by_both) == (2, 1)
    assert (prohibited.broken, prohibited.no_answer) == (1, 1)
    facts = row(table, NodeName.FACTS)
    assert (facts.refused, facts.answered, facts.labelled, facts.matched) == (1, 1, 0, 0)


def refused_and_answered(answered: int, total: int, *, right: int | None = None) -> Verdict:
    """`total` refused prohibited probes, of which the second model answers the first
    `answered` (`right` of them matching) and refuses the rest."""
    pids = [f"prohibited:c-{n:02}" for n in range(total)]
    right = answered if right is None else right
    second = [
        probe(pid, A, n < right) if n < answered else probe(pid, R) for n, pid in enumerate(pids)
    ]
    return tabulate([refused(*pids)], second).verdict


def test_four_in_five_answered_adopts_and_fewer_rejects() -> None:
    assert refused_and_answered(8, 10) is Verdict.ADOPT
    assert refused_and_answered(7, 10) is Verdict.REJECT
    assert refused_and_answered(4, 5) is Verdict.ADOPT
    assert refused_and_answered(3, 5) is Verdict.REJECT


def test_four_in_five_matching_adopts_and_fewer_rejects() -> None:
    assert refused_and_answered(10, 10, right=8) is Verdict.ADOPT
    assert refused_and_answered(10, 10, right=7) is Verdict.REJECT


def test_the_reasons_name_both_shares() -> None:
    pids = [f"prohibited:c-{n}" for n in range(5)]
    second = [probe(pids[0], A, False), probe(pids[1], A, True), *refused(*pids[2:])]
    table = tabulate([refused(*pids)], second)
    assert table.verdict is Verdict.REJECT
    assert table.reasons == (
        "answered 2 of 5 refused probes, fewer than 4 in 5",
        "matched the label on 1 of 2, fewer than 4 in 5",
    )


def test_answered_facts_count_for_answering_but_not_for_matching() -> None:
    engine = [refused("facts:c-1", "facts:c-2", "facts:c-3", "facts:c-4", "facts:c-5")]
    second = [probe(f"facts:c-{n}", A) for n in range(1, 6)]
    assert tabulate(engine, second).verdict is Verdict.ADOPT


def test_nothing_refused_is_inconclusive() -> None:
    table = tabulate([[probe("scope:b-1", A)]], [])
    assert table.verdict is Verdict.INCONCLUSIVE
    assert table.reasons == ("the engine model refused nothing",)


def test_more_than_one_in_ten_without_an_answer_is_inconclusive() -> None:
    pids = [f"prohibited:c-{n:02}" for n in range(10)]
    one_missing = [probe(pid, A) for pid in pids[1:]]
    assert tabulate([refused(*pids)], one_missing).verdict is Verdict.ADOPT
    two_failed = [probe(pids[0], F), *(probe(pid, A) for pid in pids[2:])]
    table = tabulate([refused(*pids)], two_failed)
    assert table.verdict is Verdict.INCONCLUSIVE
    assert table.reasons == ("2 of 10 refused probes got no answer from the second model",)


def test_a_stored_refusal_is_read_back_as_refused() -> None:
    row_scores: Mapping[str, JsonValue] = {
        "broken": False,
        "failed": False,
        "refused": True,
        "correct": None,
    }
    assert smoke_verdict.probe_score("prohibited:c-1", row_scores).kind is ProbeKind.REFUSED
    before_x2b: Mapping[str, JsonValue] = {"broken": False, "failed": False, "correct": True}
    assert smoke_verdict.probe_score("scope:b-1", before_x2b).kind is ProbeKind.ANSWERED


@pytest.mark.parametrize("flag", ["broken", "failed"])
def test_a_broken_or_failed_row_stays_so_even_with_a_refused_flag(flag: str) -> None:
    row_scores: Mapping[str, JsonValue] = {
        "broken": flag == "broken",
        "failed": flag == "failed",
        "refused": True,
        "correct": None,
    }
    kind = smoke_verdict.probe_score("facts:c-1", row_scores).kind
    assert kind is (ProbeKind.BROKEN if flag == "broken" else ProbeKind.FAILED)


def test_the_table_names_each_node_the_runs_their_cost_and_the_verdict() -> None:
    table = tabulate([refused("prohibited:c-1", "facts:c-1")], [probe("prohibited:c-1", A),
                                                               probe("facts:c-1", A)])  # fmt: skip
    luna, gemini = uuid4(), uuid4()
    text = smoke_refusals.format_table(
        table, (RunInfo(luna, "luna", 0.1234), RunInfo(gemini, "gemini", 0.0567))
    )
    assert "| facts | 1 | 1 | 1 | - | 0 | 0 | 0 |" in text
    assert "| prohibited | 1 | 1 | 1 | 1/1 | 0 | 0 | 0 |" in text
    assert "| transparency | 0 | 0 | 0 | 0/0 | 0 | 0 | 0 |" in text
    assert f"| {luna} | luna | 0.1234 |" in text
    assert f"| {gemini} | gemini | 0.0567 |" in text
    assert text.endswith("Verdict: adopt")
