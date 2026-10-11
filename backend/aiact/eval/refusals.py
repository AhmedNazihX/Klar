"""Provider refusals in a stored run (decisions 029, 030, 033; BACKLOG > X2b's DoD addition).

A request the engine model's provider refused goes once more to the second model (decision 033);
when that one refuses too, the check is not assessed and the result has no class (decision 030).
From each stored case this module reads:
- **refused by the engine model:** a node whose calls include the run's second model (each
  stored row's `scores.models`, `{node: {model: calls}}`, X2c), or a result that lists a check
  as `not_assessed` (also when the second call failed transiently and left no model behind);
- **answered by the second model:** refused by the engine model, and nothing left not assessed;
- **refused by both:** the result lists a not-assessed check.
A failed case (no result) is counted in none of them: it has no answer to tell them apart.

The run report's main table already gives risk-class accuracy as reported (not-assessed cases
left out) and with the not-assessed cases counted as misses; this section adds it without the
cases the second model answered, so a reader can see whether the second model moves the number.
"""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from pydantic import Field

from aiact.eval.metrics import Outcome, Rate, is_not_assessed, summarize
from aiact.schemas.base import ContractModel

ServedModels = Mapping[str, Mapping[str, int]]
"""`{node: {model: calls}}`, as `runner.MODELS_KEY` stores it."""


class RefusalCase(ContractModel):
    """What one stored case says about refusals: its outcome and the models that served it."""

    outcome: Outcome
    models: dict[str, dict[str, int]] = Field(default_factory=dict)


class RefusalSummary(ContractModel):
    """A run's refusals, by case id, and the accuracy without the second model's answers."""

    second_model: str | None
    answered: int
    """Cases with a result: the denominator of every share here."""
    engine_refused: tuple[str, ...]
    second_answered: tuple[str, ...]
    both_refused: tuple[str, ...]
    accuracy_without_second_answered: Rate
    calls_by_model: dict[str, int]


def engine_refused_nodes(models: ServedModels, second_model: str | None) -> tuple[str, ...]:
    """The nodes the second model served: the engine model's provider refused them first."""
    if second_model is None:
        return ()
    return tuple(node for node, calls in models.items() if calls.get(second_model, 0) > 0)


def summarize_refusals(cases: Sequence[RefusalCase], second_model: str | None) -> RefusalSummary:
    """Count the refusals of a run's cases and the risk-class accuracy without the cases the
    second model answered."""
    with_result = [case for case in cases if case.outcome.result is not None]
    both = [case for case in with_result if is_not_assessed(case.outcome)]
    refused = [
        case
        for case in with_result
        if is_not_assessed(case.outcome) or engine_refused_nodes(case.models, second_model)
    ]
    second = [case for case in refused if not is_not_assessed(case.outcome)]
    second_ids = {case.outcome.case.id for case in second}
    outcomes = [case.outcome for case in cases]
    without_second = [o for o in outcomes if o.case.id not in second_ids]
    return RefusalSummary(
        second_model=second_model,
        answered=len(with_result),
        engine_refused=_ids(refused),
        second_answered=_ids(second),
        both_refused=_ids(both),
        accuracy_without_second_answered=summarize(without_second, None).risk_class_accuracy,
        calls_by_model=calls_by_model(case.models for case in cases),
    )


def calls_by_model(models: Iterable[ServedModels]) -> dict[str, int]:
    """Every call of the run by the model that served it, most calls first."""
    total: Counter[str] = Counter()
    for served in models:
        for calls in served.values():
            total.update(calls)
    return dict(total.most_common())


def _ids(cases: Iterable[RefusalCase]) -> tuple[str, ...]:
    return tuple(sorted(case.outcome.case.id for case in cases))


def _share(count: int, total: int) -> str:
    return f"{count} of {total} ({Rate(hits=count, total=total).percent})"


def render_refusals(summary: RefusalSummary) -> list[str]:
    """The run report's refusal section, as markdown lines."""
    lines = ["### Provider refusals (decisions 029, 030, 033)", ""]
    if summary.second_model is None:
        lines.append("- Second model: not recorded for this run (refusals can't be told apart).")
    else:
        lines.append(f"- Second model for refused requests: `{summary.second_model}`")
    total = summary.answered
    lines += [
        f"- Refused by the engine model: {_share(len(summary.engine_refused), total)}"
        f"{_listed(summary.engine_refused)}",
        f"- Answered by the second model: {_share(len(summary.second_answered), total)}"
        f"{_listed(summary.second_answered)}",
        f"- Refused by both (not assessed): {_share(len(summary.both_refused), total)}"
        f"{_listed(summary.both_refused)}",
        f"- Second model's refusal rate: "
        f"{_share(len(summary.both_refused), len(summary.engine_refused))}",
        f"- Risk-class accuracy without the cases the second model answered: "
        f"{_rate(summary.accuracy_without_second_answered)}",
        "",
        "Calls by the model that served them: "
        + (", ".join(f"`{m}` {n}" for m, n in summary.calls_by_model.items()) or "none recorded"),
    ]
    return lines


def _listed(case_ids: Sequence[str]) -> str:
    return f": {', '.join(case_ids)}" if case_ids else ""


def _rate(rate: Rate) -> str:
    return f"{rate.percent} ({rate.hits}/{rate.total})"
