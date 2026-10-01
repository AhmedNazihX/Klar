"""The recheck of stored smoke runs (X2): which failed probes qualify, the score their stored reply
earns, and the row the recheck writes. No model or lookup is called and no database is used; the
stored-run flow is in `tests/db/test_smoke_recheck.py`.

The cases here are made up, not benchmark cases.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aiact.engine.nodes import facts, role_obligations
from aiact.engine.state import FactsOutcome
from aiact.eval.experiments import smoke_recheck
from aiact.eval.experiments.smoke import GEMINI, LUNA, NodeName, Probe, ProbeKind
from aiact.eval.experiments.smoke_recheck import (
    ProbeRecheck,
    RecheckError,
    RecheckResult,
    RunRecheck,
    StoredRow,
)
from aiact.eval.experiments.smoke_served import Served
from aiact.eval.runner import CaseRecord
from aiact.llm.generations import GenerationNotFoundError
from aiact.schemas import RiskClass, Role
from tests.eval.experiments.builders import case, role_outcome
from tests.eval.experiments.stored_rows import first_run_failed, probe_row

ROLE = Probe(NodeName.ROLE, case("d-1", RiskClass.LIMITED_RISK, role=Role.DEPLOYER))
FACTS = Probe(NodeName.FACTS, case("e-1"))
AT = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)


def stored(record: CaseRecord) -> StoredRow:
    return StoredRow(record.case_id, record.predicted, record.label, record.scores)


def first_run(probe: Probe, result: object, finish_reason: str = "stop") -> StoredRow:
    return stored(first_run_failed(probe_row(probe, result, finish_reason=finish_reason)))


@pytest.mark.parametrize(
    ("probe", "result", "finish_reason", "expected"),
    [
        (ROLE, role_outcome(Role.DEPLOYER), "stop", (ProbeKind.ANSWERED, True)),
        (ROLE, role_outcome(Role.PROVIDER), "stop", (ProbeKind.ANSWERED, False)),
        (ROLE, role_obligations.RoleOutputError("x"), "stop", (ProbeKind.BROKEN, False)),
        (FACTS, FactsOutcome(), "stop", (ProbeKind.ANSWERED, None)),
        (FACTS, facts.FactsOutputError("x"), "stop", (ProbeKind.BROKEN, None)),
        (FACTS, facts.FactsOutputError("cut off"), "length", (ProbeKind.BROKEN, None)),
    ],
    ids=["correct", "wrong", "broken", "facts", "facts-broken", "length"],
)
def test_a_reply_failed_only_by_its_lookup_is_rescored_as_the_live_path_scores_it(
    probe: Probe, result: object, finish_reason: str, expected: tuple[ProbeKind, bool | None]
) -> None:
    row = first_run(probe, result, finish_reason)
    assert smoke_recheck.qualifies(row)
    assert smoke_recheck.rescore(probe, row.predicted) == expected
    live = probe_row(probe, result, finish_reason=finish_reason)  # the same reply, found in time
    assert (live.scores["broken"], live.scores["correct"]) == (
        expected[0] is ProbeKind.BROKEN,
        expected[1],
    )


def not_found(generation_id: str) -> str:
    raise GenerationNotFoundError(f"generation {generation_id} not found after 12 attempts")


def test_a_transport_error_is_never_rescored() -> None:
    """A provider error in the body after a billed call, with its lookup not found either."""
    error = ValueError("OpenRouter API returned an error: upstream timeout (code: 504)")
    row = stored(probe_row(ROLE, error, served_by=not_found))
    assert str(row.predicted["not_pinned"]).endswith("not found after 12 attempts")
    assert not smoke_recheck.qualifies(row)
    with pytest.raises(RecheckError, match="got no answer"):
        smoke_recheck.rescore(ROLE, row.predicted)


def test_a_reply_the_provider_broke_off_is_never_rescored() -> None:
    record = probe_row(ROLE, role_outcome(Role.DEPLOYER), GEMINI, finish_reason="error")
    assert "provider_error" in record.predicted
    with_lookup = {**record.predicted, "not_pinned": "generation g not found after 12 attempts"}
    assert not smoke_recheck.qualifies(StoredRow(record.case_id, with_lookup, {}, record.scores))
    without_flag = {key: value for key, value in with_lookup.items() if key != "provider_error"}
    assert not smoke_recheck.qualifies(StoredRow(record.case_id, without_flag, {}, record.scores))


@pytest.mark.parametrize(
    "reason",
    [
        "served by Google AI Studio, not Google",
        "the reply carries no generation id",
        "generation lookup failed: OpenRouterError (HTTP 401)",
    ],
)
def test_a_probe_failed_for_another_reason_does_not_qualify(reason: str) -> None:
    row = first_run(ROLE, role_outcome(Role.DEPLOYER))
    other = StoredRow(row.case_id, {**row.predicted, "not_pinned": reason}, row.label, row.scores)
    assert not smoke_recheck.qualifies(other)


@pytest.mark.parametrize(
    "reason",
    [
        "generation lookup failed: ReadTimeout",
        "generation lookup failed: NoResponseError",
        "generation lookup failed: OpenRouterError (HTTP 503)",
        "generation lookup failed: OpenRouterError (HTTP 429)",
        "generation gen-1 not found within 300 s",
    ],
)
def test_a_probe_failed_by_a_transient_lookup_qualifies(reason: str) -> None:
    row = first_run(ROLE, role_outcome(Role.DEPLOYER))
    flaky = StoredRow(row.case_id, {**row.predicted, "not_pinned": reason}, row.label, row.scores)
    assert smoke_recheck.qualifies(flaky)


def test_a_probe_that_did_not_fail_does_not_qualify() -> None:
    assert not smoke_recheck.qualifies(stored(probe_row(ROLE, role_outcome(Role.DEPLOYER))))


def test_only_a_failed_probe_qualifies_even_with_a_late_lookup_reason() -> None:
    """Pins the `failed is True` guard: everything else about the row qualifies."""
    row = first_run(ROLE, role_outcome(Role.DEPLOYER))
    assert smoke_recheck.qualifies(row)
    scored = StoredRow(row.case_id, row.predicted, row.label, {**row.scores, "failed": False})
    assert not smoke_recheck.qualifies(scored)


def test_a_provider_error_alone_keeps_a_probe_from_qualifying() -> None:
    """Pins the `provider_error` guard: its calls ended normally, so only the flag stops it."""
    row = first_run(ROLE, role_outcome(Role.DEPLOYER))
    flagged = {**row.predicted, "provider_error": "a call ended with finish_reason error"}
    assert smoke_recheck.reply_kind(flagged) is None
    assert not smoke_recheck.qualifies(StoredRow(row.case_id, flagged, row.label, row.scores))


def test_a_stored_answer_that_does_not_read_back_is_an_error() -> None:
    row = first_run(ROLE, role_outcome(Role.DEPLOYER))
    with pytest.raises(RecheckError, match="doesn't read back"):
        smoke_recheck.rescore(ROLE, {**row.predicted, "unexpected": 1})


def test_a_confirmed_row_gets_its_score_and_the_audit_trail() -> None:
    row = first_run(ROLE, role_outcome(Role.DEPLOYER))
    original = row.predicted["not_pinned"]
    served = Served(("Azure",), as_pinned=True)
    record = smoke_recheck.rechecked_record(row, (ProbeKind.ANSWERED, True), served, AT)
    assert {**row.scores, **record.scores} == record.scores
    assert {key: record.scores[key] for key in ("broken", "failed", "correct", "is_error")} == {
        "broken": False,
        "failed": False,
        "correct": True,
        "is_error": False,
    }
    assert record.scores["served_as_pinned"] is True
    assert record.scores["cost_usd"] == row.scores["cost_usd"]
    assert "not_pinned" not in record.predicted
    info = record.predicted["smoke"]
    assert isinstance(info, dict)
    assert info["served_by"] == ["Azure"]
    assert info["recheck"] == {
        "at": "2026-10-02T09:00:00+00:00",
        "original_not_pinned": original,
        "served_by": ["Azure"],
        "by": "smoke-recheck",
    }
    old_info = row.predicted["smoke"]
    assert isinstance(old_info, dict) and info["calls"] == old_info["calls"]


def test_a_confirmed_broken_row_is_broken_and_wrong() -> None:
    row = first_run(ROLE, role_obligations.RoleOutputError("x"))
    served = Served(("Azure",), as_pinned=True)
    record = smoke_recheck.rechecked_record(row, (ProbeKind.BROKEN, False), served, AT)
    assert (record.scores["broken"], record.scores["failed"], record.scores["correct"]) == (
        True,
        False,
        False,
    )
    assert record.scores["is_error"] is True


def test_a_row_served_by_another_provider_stays_failed_with_the_reason() -> None:
    row = first_run(ROLE, role_outcome(Role.DEPLOYER))
    served = Served(("Google AI Studio",), as_pinned=False, not_counted="served by X, not Google")
    record = smoke_recheck.rechecked_record(row, (ProbeKind.ANSWERED, True), served, AT)
    assert (record.scores["failed"], record.scores["correct"]) == (True, None)
    assert record.scores["served_as_pinned"] is False
    assert record.predicted["not_pinned"] == "served by X, not Google"
    info = record.predicted["smoke"]
    assert isinstance(info, dict) and isinstance(info["recheck"], dict)
    assert info["recheck"]["original_not_pinned"] == row.predicted["not_pinned"]


def recheck(arm: str, *results: RecheckResult) -> RunRecheck:
    probes = tuple(
        ProbeRecheck(f"role_obligations:d-{n}", result, ProbeKind.ANSWERED, True, ("Azure",), None)
        for n, result in enumerate(results)
    )
    return RunRecheck(uuid4(), arm, probes)


def test_the_comparison_needs_one_luna_and_one_gemini_run() -> None:
    luna, gemini = recheck(LUNA.name), recheck(GEMINI.name)
    assert smoke_recheck.comparison_pair([gemini, luna]) == {
        "luna": luna.run_id,
        "gemini": gemini.run_id,
    }
    assert smoke_recheck.comparison_pair([luna]) is None
    assert smoke_recheck.comparison_pair([luna, recheck(LUNA.name), gemini]) is None


def test_the_summary_counts_and_names_each_probe() -> None:
    summary = recheck(LUNA.name, RecheckResult.CONFIRMED, RecheckResult.STILL_FAILING)
    text = smoke_recheck.format_recheck(summary)
    assert text.splitlines()[0].endswith(
        "2 probes rechecked, 1 confirmed on Azure, 1 still failing"
    )
    assert "  role_obligations:d-0: confirmed on Azure: answered, correct" in text
    assert "  role_obligations:d-1: still failing" in text
