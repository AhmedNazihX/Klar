"""Smoke probe rows for the recheck's tests, made by the real `run_probe` with a fake node, then
turned into the shape X2's first paid run stored (2026-10-01): the reply kept in `predicted`, but
failed because its generation record wasn't found within the ~18 s lookup. No model is called.
"""

from pydantic import JsonValue, SecretStr

from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.eval.experiments import smoke
from aiact.eval.experiments.smoke import CallRecord, ModelArm, NodeName, Probe, UsageTracker
from aiact.eval.experiments.smoke_served import FAILED_SCORES, ServedBy
from aiact.eval.runner import CaseRecord
from aiact.settings import Settings

SETTINGS = Settings(_env_file=None, openrouter_api_key=SecretStr("not-a-key"))  # pyright: ignore[reportCallIssue]


def reply(result: object, generation_id: str, finish_reason: str = "stop") -> smoke.NodeFactory:
    """Every node makes one call with `generation_id`, then returns `result` or raises it."""

    def build(node: NodeName, settings: Settings, tracker: UsageTracker) -> smoke.NodeRunner:
        def run(state: EngineState) -> FactsOutcome | CheckOutcome:
            tracker.record(CallRecord(0.002, 40, generation_id, finish_reason))
            if isinstance(result, Exception):
                raise result
            assert isinstance(result, FactsOutcome | CheckOutcome)
            return result

        return run

    return build


def probe_row(
    probe: Probe,
    result: object,
    arm: ModelArm = smoke.LUNA,
    *,
    finish_reason: str = "stop",
    served_by: ServedBy | None = None,
) -> CaseRecord:
    """The row today's `run_probe` stores (served by the arm's provider unless `served_by`)."""
    generation_id = f"gen-{probe.probe_id}"
    factory = reply(result, generation_id, finish_reason)
    lookup = served_by or (lambda _: arm.served_by)
    return smoke.run_probe(probe, arm, SETTINGS, lookup, factory)


def first_run_failed(record: CaseRecord) -> CaseRecord:
    """`record` as the first paid run stored it: failed by a record not found after 12 attempts,
    without the fields the deferred check added since."""
    info = record.predicted["smoke"]
    assert isinstance(info, dict)
    [generation_id] = info["generation_ids"]  # pyright: ignore[reportGeneralTypeIssues]
    old_info: dict[str, JsonValue] = {
        key: value for key, value in info.items() if key != "pending_generation_ids"
    }
    predicted: dict[str, JsonValue] = {
        **record.predicted,
        "smoke": {**old_info, "served_by": []},
        "not_pinned": f"generation {generation_id} not found after 12 attempts",
    }
    scores = {key: value for key, value in record.scores.items() if key != "pending_verification"}
    return CaseRecord(
        record.case_id,
        predicted,
        record.label,
        {**scores, **FAILED_SCORES, "served_as_pinned": None},
        None,
        record.cost_usd,
        record.tokens,
    )
