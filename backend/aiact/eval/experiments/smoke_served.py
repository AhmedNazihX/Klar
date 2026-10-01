"""Who served a smoke probe's calls, judged from OpenRouter's generation records (X2; decision 023
addendum). Shared by the run's own check (`smoke`) and the check of stored runs (`smoke_recheck`),
so both judge a provider the same way: a call counts only when its record names the arm's pinned
provider, compared by exact name (`ModelArm.served_by`: `Azure` for Luna, `Google` for Gemini).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from pydantic import JsonValue

from aiact.eval.runner import CaseRecord, Score
from aiact.llm.generations import GenerationLookupError

ServedBy = Callable[[str], str]
"""Generation id to the name of the provider that served it."""
VerifyAll = Callable[[Sequence[str]], Mapping[str, str | GenerationLookupError]]
"""Generation ids to each one's provider name, or the error that settles it, after a long wait
(`GenerationLookup.served_by_all`)."""


@dataclass(frozen=True)
class Served:
    """Who served the probe's calls. `as_pinned` is True when every call is shown to come from
    the pinned provider, False when one is shown to come from another, and None when unknown;
    `not_counted` says why a reply can't count. `pending` holds the generation ids whose record
    didn't show up in time during the run: they are checked again at the end of the run."""

    providers: tuple[str, ...] = ()
    as_pinned: bool | None = None
    not_counted: str | None = None
    lookup_skipped: str | None = None
    pending: tuple[str, ...] = ()


def judge(names: Sequence[str], pinned: str, lookup_skipped: str | None = None) -> Served:
    """Every call's provider is known: pinned when all are `pinned`."""
    providers = tuple(names)
    others = sorted({name for name in providers if name != pinned})
    if others:
        reason = f"served by {', '.join(others)}, not {pinned}"
        return Served(providers, as_pinned=False, not_counted=reason, lookup_skipped=lookup_skipped)
    return Served(providers, as_pinned=True, lookup_skipped=lookup_skipped)


def settle(
    generation_ids: Sequence[str],
    found: Mapping[str, str | GenerationLookupError],
    pinned: str,
) -> Served:
    """The verdict on calls looked up after a long wait: another provider settles it first, then
    any record that couldn't be read (or still isn't there), else they are all pinned."""
    results = [found[generation_id] for generation_id in generation_ids]
    names = [result for result in results if isinstance(result, str)]
    errors = [result for result in results if isinstance(result, GenerationLookupError)]
    served = judge(names, pinned)
    if served.as_pinned is False or not errors:
        return served
    return Served(tuple(names), as_pinned=None, not_counted=str(errors[0]))


# --- Stored rows --------------------------------------------------------------------------------

FAILED_SCORES: Mapping[str, Score] = {
    "broken": False,
    "failed": True,
    "correct": None,
    "is_error": True,
}
"""The scores a probe without a usable answer gets (cost and tokens stay as billed)."""


def stored_smoke_info(predicted: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """A probe row's `predicted.smoke`: its calls, generation ids and providers."""
    info = predicted.get("smoke")
    if not isinstance(info, dict):
        raise ValueError("the row has no predicted.smoke object; not a smoke probe")
    return dict(info)


def stored_ids(info: Mapping[str, JsonValue], key: str) -> tuple[str, ...]:
    """A list of generation ids in `predicted.smoke`."""
    value = info.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"predicted.smoke.{key} is not a list of generation ids")
    return tuple(item for item in value if isinstance(item, str))


def pending_ids(record: CaseRecord) -> tuple[str, ...]:
    return stored_ids(stored_smoke_info(record.predicted), "pending_generation_ids")


def settle_pending(record: CaseRecord, served: Served, checked_at: datetime) -> CaseRecord:
    """A pending probe's final row: its own score when `served` confirms the pinned provider,
    else failed with the reason in `not_pinned`. `predicted.smoke.deferred_check` says when and
    what was found."""
    info = {
        **stored_smoke_info(record.predicted),
        "served_by": list(served.providers),
        "pending_generation_ids": [],
        "deferred_check": {
            "at": checked_at.isoformat(),
            "served_by": list(served.providers),
            "result": "confirmed" if served.not_counted is None else served.not_counted,
        },
    }
    predicted: dict[str, JsonValue] = {**record.predicted, "smoke": info}
    scores: dict[str, Score] = {
        **record.scores,
        "served_as_pinned": served.as_pinned,
        "pending_verification": False,
    }
    if served.not_counted is None:
        return replace(record, predicted=predicted, scores=scores)
    return replace(
        record,
        predicted={**predicted, "not_pinned": served.not_counted},
        scores={**scores, **FAILED_SCORES},
    )
