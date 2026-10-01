"""Decision 023's rule over two runs' probe scores, the rows it reads, and the printed table (X2).
Reading stored runs from Postgres is tested in `tests/db/test_smoke_runs.py`."""

from collections.abc import Mapping
from uuid import uuid4

import pytest
from pydantic import JsonValue

from aiact.eval.experiments import smoke_verdict
from aiact.eval.experiments.smoke import GEMINI, LUNA, ProbeKind
from aiact.eval.experiments.smoke_verdict import ProbeScore, Verdict


def scores(
    answered_right: int,
    answered_wrong: int = 0,
    broken: int = 0,
    failed: int = 0,
    facts_ok: int = 0,
) -> list[ProbeScore]:
    """Scope probes numbered in this order: right, wrong, broken, failed; then facts probes."""
    kinds = (
        [(ProbeKind.ANSWERED, True)] * answered_right
        + [(ProbeKind.ANSWERED, False)] * answered_wrong
        + [(ProbeKind.BROKEN, False)] * broken
        + [(ProbeKind.FAILED, None)] * failed
    )
    checks = [ProbeScore(f"scope:c-{n:03}", kind, ok) for n, (kind, ok) in enumerate(kinds)]
    facts_rows = [ProbeScore(f"facts:c-{n:03}", ProbeKind.ANSWERED, None) for n in range(facts_ok)]
    return checks + facts_rows


compare = smoke_verdict.compare


def test_equal_models_keep_luna() -> None:
    result = compare(scores(18, 2), scores(18, 2))
    assert result.verdict is Verdict.KEEP_LUNA
    assert (result.scored, result.luna_accuracy, result.gemini_accuracy) == (20, 0.9, 0.9)
    assert result.reasons == ()


def test_exactly_10_percent_broken_keeps_luna_and_one_more_drops_it() -> None:
    kept = compare(scores(18, broken=2), scores(18, 2))  # 2 of 20 broken: not more than 10%
    assert kept.verdict is Verdict.KEEP_LUNA
    dropped = compare(scores(17, 1, broken=3), scores(17, 3, 1))  # 3 of 21 answers broken
    assert dropped.verdict is Verdict.DROP_LUNA
    assert dropped.reasons == ("luna: 3 of 21 answers broken, more than 10%",)


def test_the_broken_share_is_over_replies_not_planned_probes() -> None:
    """6 of 60 planned is exactly 10%, but 6 of the 55 replies is more."""
    result = compare(scores(49, broken=6, failed=5), scores(60))
    assert result.verdict is Verdict.DROP_LUNA
    assert "luna: 6 of 55 answers broken, more than 10%" in result.reasons


def test_broken_facts_count_towards_the_share() -> None:
    extra = ("facts:x-1", "facts:x-2", "facts:x-3")
    luna = [*scores(10, facts_ok=8), *(ProbeScore(pid, ProbeKind.BROKEN, None) for pid in extra)]
    gemini = [
        *scores(10, facts_ok=8),
        *(ProbeScore(pid, ProbeKind.ANSWERED, None) for pid in extra),
    ]
    result = compare(luna, gemini)
    assert result.luna.broken == 3
    assert result.luna.broken_by_node == {"facts": 3}
    assert result.verdict is Verdict.DROP_LUNA  # 3 of 21 replies


def test_ten_points_below_drops_luna_and_less_keeps_it() -> None:
    at_limit = compare(scores(8, 2), scores(9, 1))  # 80% against 90%
    assert at_limit.verdict is Verdict.DROP_LUNA
    assert at_limit.reasons == ("luna: 8/10 correct, 10 or more points below gemini's 9/10",)
    below_limit = compare(scores(9, 12), scores(11, 10))  # 42.9% against 52.4%: 9.5 points
    assert below_limit.verdict is Verdict.KEEP_LUNA


def test_a_broken_answer_counts_as_wrong_in_the_accuracy() -> None:
    result = compare(scores(9, broken=1), scores(10))
    assert (result.luna_correct, result.gemini_correct, result.scored) == (9, 10, 10)
    assert result.verdict is Verdict.DROP_LUNA


def test_accuracy_uses_only_probes_both_models_replied_to() -> None:
    luna = scores(8, 1, failed=1)  # c-009 failed for luna
    gemini = scores(9, 1)  # c-009 is wrong for gemini
    result = compare(luna, gemini)
    assert result.scored == 9
    assert (result.luna_correct, result.gemini_correct) == (8, 9)


def test_many_unanswered_luna_probes_make_it_inconclusive() -> None:
    result = compare(scores(15, failed=5), scores(20))
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.reasons == ("luna: 5 of 20 probes got no answer",)


def test_many_unanswered_gemini_probes_make_it_inconclusive() -> None:
    result = compare(scores(20), scores(15, failed=5))
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.reasons == ("gemini: 5 of 20 probes got no answer",)


def test_one_in_ten_unanswered_stays_conclusive_and_two_do_not() -> None:
    assert compare(scores(10), scores(9, failed=1)).verdict is Verdict.KEEP_LUNA
    two = compare(scores(10), scores(8, failed=2))
    assert two.verdict is Verdict.INCONCLUSIVE
    assert two.reasons == ("gemini: 2 of 10 probes got no answer",)


def test_a_probe_one_run_lacks_counts_as_unanswered() -> None:
    result = compare(scores(8), scores(10))
    assert (result.luna.failed, result.luna.planned) == (2, 10)
    assert result.verdict is Verdict.INCONCLUSIVE


def test_no_probe_scored_for_both_is_inconclusive() -> None:
    result = compare(scores(0, facts_ok=3), scores(0, facts_ok=3))
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.reasons == ("no probe scored for both",)


def test_a_stored_row_is_read_back_by_its_flags() -> None:
    row: Mapping[str, JsonValue] = {"broken": True, "failed": False, "correct": False}
    assert smoke_verdict.probe_score("high_risk:e-1", row) == ProbeScore(
        "high_risk:e-1", ProbeKind.BROKEN, False
    )
    failed: Mapping[str, JsonValue] = {"broken": False, "failed": True, "correct": None}
    assert smoke_verdict.probe_score("facts:e-1", failed).kind is ProbeKind.FAILED


def test_only_rechecks_that_confirmed_a_probe_are_noted_with_any_other_provider() -> None:
    entries: tuple[Mapping[str, JsonValue], ...] = (
        {"at": "2026-10-02T09:00:00+00:00", "by": "smoke-recheck", "confirmed": 0},
        {
            "at": "2026-10-02T10:00:00+00:00",
            "by": "smoke-recheck",
            "confirmed": 0,
            "other_provider": 1,
        },
        {
            "at": "2026-10-03T09:00:00+00:00",
            "by": "smoke-recheck",
            "confirmed": 3,
            "other_provider": 2,
        },
        {
            "at": "2026-10-04T09:00:00+00:00",
            "by": "smoke-recheck",
            "confirmed": 1,
            "other_provider": 0,
        },
    )
    run = smoke_verdict.StoredRun("gemini", 4, (), entries)
    assert smoke_verdict.recheck_notes(run) == (
        "gemini: rechecked on 2026-10-03: 3 probes confirmed late, 2 found served by another "
        "provider (smoke-recheck)",
        "gemini: rechecked on 2026-10-04: 1 probes confirmed late (smoke-recheck)",
    )


def test_a_row_still_pending_its_provider_check_counts_as_failed() -> None:
    """Only a run stopped before its end-of-run check leaves one; it never counts as answered."""
    row: Mapping[str, JsonValue] = {
        "broken": False,
        "failed": False,
        "correct": True,
        "pending_verification": True,
    }
    assert smoke_verdict.probe_score("role_obligations:d-1", row).kind is ProbeKind.FAILED


@pytest.mark.parametrize(
    ("probe_id", "row"),
    [
        ("scope:b-1", {"cost_usd": 0.1, "is_error": False}),
        ("scope:b-1", {"broken": False, "failed": False, "correct": 1}),
        ("baseline:b-1", {"broken": False, "failed": False, "correct": True}),
    ],
)
def test_a_row_that_is_not_a_smoke_probe_is_refused(
    probe_id: str, row: Mapping[str, JsonValue]
) -> None:
    with pytest.raises(ValueError):
        smoke_verdict.probe_score(probe_id, row)


def test_the_comparison_table_names_the_run_ids_and_the_verdict() -> None:
    luna_id, gemini_id = uuid4(), uuid4()
    comparison = compare(scores(8, 1, broken=1), scores(9, 1))
    text = smoke_verdict.format_comparison(comparison, {"luna": luna_id, "gemini": gemini_id})
    luna_row = f"| {LUNA.model} | {luna_id} | 1/10 (10.0%): scope 1 | 0/10 (0.0%) | 8/10 (80.0%) |"
    gemini_row = f"| {GEMINI.model} | {gemini_id} | 0/10 (0.0%) | 0/10 (0.0%) | 9/10 (90.0%) |"
    assert luna_row in text
    assert gemini_row in text
    assert "Verdict: drop_luna" in text
