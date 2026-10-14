"""The appliedAI disagreement review as markdown (V9; built by `appliedai_review`).

Every number is computed from the stored run named at the top. The experts' comments are quoted
from the stored labels with the CC BY 4.0 credit (`eval/appliedai/SOURCE.md`, decision 002); the
descriptions are never printed. Every text the report doesn't write itself (the engine's
answer, Annex point and step decisions, the experts' comment, a function tag) is shown on one
line, and with `|` escaped in a table cell, so it can't start a heading or a verdict.
"""

from collections import defaultdict
from collections.abc import Sequence

from aiact.eval.appliedai_review import (
    ANNEX_I_DISAGREEMENTS,
    TITLE,
    VERDICT_MARK,
    Review,
    ReviewCase,
    Verdict,
    accuracy,
)
from aiact.eval.failures import failure
from aiact.eval.metrics import risk_class_match
from aiact.eval.report import run_lines
from aiact.schemas import StepName

CREDIT = (
    "The appliedAI cases, their labels and the experts' comments come from the Risk "
    'Classification Database of the appliedAI Institute for Europe gGmbH. Credit: "appliedAI '
    'Institute for Europe gGmbH", licensed under CC BY 4.0 '
    "(<https://creativecommons.org/licenses/by/4.0/>). The comments are quoted as extracted in "
    "`eval/appliedai/appliedai.jsonl` (spaces tidied; see `eval/appliedai/SOURCE.md` and "
    "decision 002). The experts classified the systems in 2023 against the Commission's 2021 "
    'proposal: no Art. 6(3) filter, "Annex II" is today\'s Annex I.'
)
QUOTE_CREDIT = "appliedAI Institute for Europe gGmbH, CC BY 4.0"
HOW_TO = (
    f"**How to write a verdict.** Under each disagreement, after `{VERDICT_MARK}`, write "
    f"`{Verdict.ENGINE_ERROR.value}`, `{Verdict.OUTDATED_LABEL.value}` (the 2023 label no longer "
    f"fits the law) or `{Verdict.AMBIGUOUS.value}`, then any note of your own (for example "
    f"`{Verdict.OUTDATED_LABEL.value}: Art. 6(3) exempts it`). Keep the mark exactly as written "
    "and write only after it; a note line must not start with `#`. Then run "
    "`uv run aiact evaluate appliedai-review <run id>` again (from `backend/`): it keeps every "
    "verdict and recomputes the accuracy after excluding the outdated labels. `--check` fails "
    "while a disagreement has no verdict."
)
MATCH_RULES = (
    "Matching follows INIT's appliedAI mapping (`score_appliedai`): `low` accepts limited_risk, "
    "minimal_risk and out_of_scope (out_of_scope is reviewed all the same); `unclear` matches "
    "legally_ambiguous; needs_more_information on an `unclear` case is counted separately, out of "
    "accuracy, and reviewed. A not-assessed case (the model provider refused a check, decision "
    "030) is left out of accuracy and of the review, as in the run report."
)
ANNEX_I_NOTE = (
    "Cases the experts linked to Annex II of the 2021 proposal (today's Annex I, the product "
    "legislation route), tagged `annex_i`. They are reported apart from the other cases."
)
CLASSIFICATION_STEPS = (
    StepName.SCOPE,
    StepName.PROHIBITED,
    StepName.HIGH_RISK,
    StepName.TRANSPARENCY,
)
"""The steps that decide the class; the role step's duties don't bear on a verdict."""
NO_VERDICT = "missing"
NOT_REVIEWED = ""


def render_review(review: Review) -> str:
    """The whole review file."""
    others = tuple(case for case in review.cases if not case.is_annex_i)
    annex_i = tuple(case for case in review.cases if case.is_annex_i)
    parts = [
        _header(review),
        _accuracy(review, others, annex_i),
        _by_function(review),
        _table("## Cases (without Annex I)", "", others, review),
        _table("## Annex I cases (reported separately)", ANNEX_I_NOTE, annex_i, review),
        _disagreements("## Disagreements", others, review),
        _disagreements(ANNEX_I_DISAGREEMENTS, annex_i, review),
    ]
    return "\n".join(parts)


def _header(review: Review) -> str:
    info = review.info
    failed = sum(case.outcome.result is None for case in review.cases)
    not_assessed = sum(case.is_not_assessed for case in review.cases)
    lines = [
        TITLE,
        "",
        CREDIT,
        "",
        f"- Run id: `{info.id}`",
        *run_lines(info),
        f"- Cases: {len(review.cases)} ({failed} failed, {not_assessed} not assessed)",
    ]
    if review.scoring_errors:
        errors = ", ".join(review.scoring_errors)
        lines.append(f"- Scoring failed, left out of the review: {errors}")
    lines += [
        f"- Full metrics: `uv run aiact evaluate report {info.id}`",
        "",
        "Classifications are guidance, not legal advice.",
        "",
        HOW_TO,
        "",
        MATCH_RULES,
        "",
    ]
    return "\n".join(lines)


def _accuracy(review: Review, others: Sequence[ReviewCase], annex_i: Sequence[ReviewCase]) -> str:
    outdated = review.outdated
    rows = (
        ("Every case", review.cases),
        ("Without the Annex I cases", others),
        ("Annex I cases only", annex_i),
    )
    lines = [
        "## Risk-class accuracy",
        "",
        "| Cases | Before excluding outdated labels | After excluding outdated labels |",
        "| --- | ---: | ---: |",
        *(
            f"| {name} | {accuracy(cases).with_counts} | {accuracy(cases, outdated).with_counts} |"
            for name, cases in rows
        ),
        "",
        _verdict_counts(review),
    ]
    if review.missing:
        lines.append(
            f"The after column is provisional: {len(review.missing)} disagreements have no "
            "verdict yet."
        )
    separate = sum(case.is_counted_separately for case in review.cases)
    lines += [
        "",
        f"Counted separately (needs_more_information on an `unclear` case): {separate}.",
        "",
    ]
    return "\n".join(lines)


def _verdict_counts(review: Review) -> str:
    written = list(review.verdicts.values())
    counts = ", ".join(
        f"{verdict.value} {sum(w.verdict is verdict for w in written)}" for verdict in Verdict
    )
    total = len(review.disagreements)
    return f"Verdicts: {len(written)} of {total} disagreements ({counts})."


def _by_function(review: Review) -> str:
    groups: defaultdict[str, list[ReviewCase]] = defaultdict(list)
    for case in review.cases:
        groups[case.function].append(case)
    lines = [
        "## By appliedAI function",
        "",
        "appliedAI's own enterprise function (the `function:*` tag), Annex I cases included.",
        "",
        "| Function | Cases | Disagreements | Before excluding outdated labels "
        "| After excluding outdated labels |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for function in sorted(groups):
        cases = groups[function]
        disagreements = sum(case.needs_review for case in cases)
        lines.append(
            f"| {_cell(function)} | {len(cases)} | {disagreements} "
            f"| {accuracy(cases).with_counts} | {accuracy(cases, review.outdated).with_counts} |"
        )
    return "\n".join([*lines, ""])


def _table(heading: str, note: str, cases: Sequence[ReviewCase], review: Review) -> str:
    lines = [heading, ""]
    if note:
        lines += [note, ""]
    if not cases:
        return "\n".join([*lines, "None.", ""])
    lines += [
        "| Case | Function | Experts | Engine | Match | Review | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        review_mark = "yes" if case.needs_review else ""
        lines.append(
            f"| {case.case_id} | {_cell(case.function)} | {case.outcome.case.label} "
            f"| {_cell(engine_text(case))} "
            f"| {match_text(case)} | {review_mark} | {_verdict_cell(case, review)} |"
        )
    return "\n".join([*lines, ""])


def _verdict_cell(case: ReviewCase, review: Review) -> str:
    if not case.needs_review:
        return NOT_REVIEWED
    written = review.verdicts.get(case.case_id)
    return written.verdict.value if written else NO_VERDICT


def engine_text(case: ReviewCase) -> str:
    """The engine's answer in a few words, on one line: class, status and Annex point."""
    return _one_line(_engine_text(case))


def _engine_text(case: ReviewCase) -> str:
    result = case.outcome.result
    if result is None:
        return "failed (no result)"
    if case.is_not_assessed:
        refused = ", ".join(step.value for step in result.not_assessed)
        return f"not assessed ({refused} refused)"
    if result.risk_class is None:
        return f"no class, {result.status.value}"
    shown = f"{result.risk_class.value}, {result.status.value}"
    return f"{shown}, {result.annex_point}" if result.annex_point else shown


def match_text(case: ReviewCase) -> str:
    """Whether the answer matches the experts' label, as risk-class accuracy counts it."""
    if case.is_not_assessed:
        return "not assessed"
    if case.outcome.result is None:
        return "no (failed)"
    if case.is_counted_separately:
        return "counted separately"
    return "yes" if risk_class_match(case.outcome) else "no"


def _disagreements(heading: str, cases: Sequence[ReviewCase], review: Review) -> str:
    found = [case for case in cases if case.needs_review]
    lines = [f"{heading} ({len(found)})", ""]
    for case in found:
        written = review.verdicts.get(case.case_id)
        lines += [
            *_disagreement(case),
            "",
            f"{VERDICT_MARK} {written.text if written else ''}".rstrip(),
            "",
        ]
    return "\n".join(lines)


def _disagreement(case: ReviewCase) -> list[str]:
    notes = case.outcome.case.notes
    comment = f'"{_one_line(notes)}" ({QUOTE_CREDIT})' if notes else "none"
    lines = [
        f"### Case {case.case_id}",
        "",
        f"- Function: {_one_line(case.function)}",
        f"- Experts: {case.outcome.case.label}",
        f"- Engine: {engine_text(case)}",
        f"- Match: {match_text(case)}",
    ]
    found = failure(case.outcome)
    if found is not None:
        group, shown = found
        lines.append(f"- Look first at: {_one_line(f'{group} ({shown})')}")
    lines.append(f"- Experts' comment: {comment}")
    result = case.outcome.result
    steps = result.steps if result is not None else ()
    lines += [
        f"- Engine, {step.step.value} ({step.status.value}): {_one_line(step.decision)}"
        for step in steps
        if step.step in CLASSIFICATION_STEPS
    ]
    return lines


def _one_line(text: str) -> str:
    """A text on one line, so it can't start a heading or a verdict."""
    return " ".join(text.split())


def _cell(text: str) -> str:
    """A text on one line with `|` escaped, so it stays in its table cell."""
    return _one_line(text).replace("|", "\\|")
