"""Judged metrics: the checks that need judgement, scored by V4's judge (INIT > Metrics, Judge;
story V5).

- Citation support: each step that cites provisions is one item; its decision is the claim and
  the quotes it cites, each under its provision's name, are the cited text.
- Evidence-tag accuracy: each distinct fact tagged "stated" (the result's facts, its deciding
  facts and every step's facts) is one item, judged against the text the engine read: the case's
  description, with the fixed answers appended on an `--answers-from` run.
- Q&A support: a Q&A answer is one item, its question and answer the claim and the provisions
  it was answered from the sources (`qa_support_item`).

No invented content is not judged (the user's decision, 2026-10-13; decision 006 > Consequences):
drafting is model-free (the template's wording, the result's facts and the user's answers word
for word), so a judge would only re-read text that is correct by construction. The report shows
P8a's deterministic check instead (`code_checked_documents`).

An item the judge couldn't answer (a refused or broken reply, `JudgeError`, with what it spent)
or one too long to send (`JudgeItem`'s caps) is "not measured": counted apart, never as a fail.
A call that reached no model (key, endpoint, guardrail or network) is no item's failure: when
the backup judge's call is the one that reached none (V4's judge falls back to the backup on a
Jev error, by design), it stops the pass (`JudgeUnreachedError`). Each check's tally
(`CheckScore`) is stored in a case's `eval_case_results.scores` as flat numbers
(`stored_scores`; the table's check allows numbers there) and summed into the run report's
"Judged metrics" table (`render_judged`). The judge's settings (models and unsure margin) are
the run's `config.judged`.

The judge sends what it reads to Jev, which has no EU endpoint (decision 006): only benchmark
cases, the corpus's text and the engine's answers to them reach it, never a user's description.
"""

import logging
import threading
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol, Self

from pydantic import Field, ValidationError

from aiact.drafting.checks import check_nothing_invented
from aiact.drafting.documents import templates_for
from aiact.drafting.draft import UnwritableTextError, draft_document
from aiact.drafting.prefill import DutyDateError, NoClassError
from aiact.eval.judge import JudgeCheck, JudgeError, JudgeItem, Verdict
from aiact.eval.metrics import Rate
from aiact.eval.ragas_metrics import ANSWER_KIND
from aiact.eval.runner import is_failed
from aiact.provision_names import provision_name
from aiact.qa.models import AnswerKind
from aiact.report.result import LAW_PROVISIONS
from aiact.schemas import Citation, ClassificationResult, EvidenceTag, Language
from aiact.schemas.base import ContractModel
from aiact.schemas.evidence import Fact

logger = logging.getLogger(__name__)

Planned = JudgeItem | None
"""An item to judge, or None for one that can't be sent (too long, or nothing to judge it
against): counted as not measured."""

KEY_PREFIX = "judged"
SCORE_FIELDS = ("held", "judged", "not_measured", "backup", "cost_usd", "tokens")
"""A check's tally as `scores` stores it: `judged_<check>_<field>`."""

CHECK_NAMES: Mapping[JudgeCheck, str] = {
    JudgeCheck.CITATION_SUPPORT: "Citation support",
    JudgeCheck.EVIDENCE_TAG: "Evidence-tag accuracy",
    JudgeCheck.QA_SUPPORT: "Q&A support",
}
"""The checks V5 judges, as the report names them; V4's invented-content check isn't one."""


class JudgedRecordError(ValueError):
    """A stored judged score isn't a whole, non-negative number; the message names the key."""


class JudgeUnreachedError(RuntimeError):
    """The backup judge's call reached no model (key, endpoint, guardrail or network): the pass
    stops and the case isn't stored, so a rerun judges it. Carries what the case's items spent."""

    def __init__(self, cost_usd: float, tokens: int) -> None:
        super().__init__(
            "the backup judge's call reached no model (key, endpoint, guardrail or network)"
        )
        self.cost_usd = cost_usd
        self.tokens = tokens


# --- the items -----------------------------------------------------------------------------------


def planned_item(check: JudgeCheck, language: Language, claim: str, source: str) -> Planned:
    """The item, or None when it can't be sent: a text over `JudgeItem`'s caps, or an empty one.
    Nothing is logged: the texts are the item's."""
    try:
        return JudgeItem(check=check, language=language, claim=claim, source=source)
    except ValidationError:
        return None


def cited_text(citations: Iterable[Citation]) -> str:
    """Each quote under its provision's name, as the validation cases give a cited text."""
    return "\n\n".join(
        f"{_provision_heading(c.provision_id, c.language)}\n{c.quote}" for c in citations
    )


def _provision_heading(provision_id: str, language: Language) -> str:
    """The Act's provisions by name; any other id (a recital, a guideline unit) stays an id."""
    if provision_id.startswith(LAW_PROVISIONS):
        return provision_name(provision_id, language)
    return provision_id


def citation_support_items(result: ClassificationResult, language: Language) -> tuple[Planned, ...]:
    """One item per step that cites: does the cited text support the step's decision?"""
    return tuple(
        planned_item(
            JudgeCheck.CITATION_SUPPORT, language, step.decision, cited_text(step.citations)
        )
        for step in result.steps
        if step.citations
    )


def stated_facts(result: ClassificationResult) -> tuple[str, ...]:
    """Every distinct fact tagged "stated", in the order the result first gives it."""
    facts: list[Fact] = [*result.facts, *result.deciding_facts]
    facts += [fact for step in result.steps for fact in step.facts_used]
    stated = (fact.text for fact in facts if fact.evidence is EvidenceTag.STATED)
    return tuple(dict.fromkeys(stated))


def evidence_tag_items(
    result: ClassificationResult, description: str, language: Language
) -> tuple[Planned, ...]:
    """One item per stated fact: is it in `description`, the text the engine read?"""
    return tuple(
        planned_item(JudgeCheck.EVIDENCE_TAG, language, fact, description)
        for fact in stated_facts(result)
    )


def qa_answer(predicted: object) -> tuple[str, list[object]] | None:
    """The answer and the hits it was drawn from, when a stored Q&A prediction holds one to
    judge; None for a failed answer, a row with no answer, or one of P7's fixed answers (outside
    the corpus, a compliance question, refused), which claims nothing from the hits. V6's
    stand-in answerer stores no kind; its answers are judged."""
    if is_failed(predicted) or not isinstance(predicted, Mapping):
        return None
    answer, retrieved = predicted.get("answer"), predicted.get("retrieved")
    kind = predicted.get(ANSWER_KIND)
    if not isinstance(answer, str) or not isinstance(retrieved, list):
        return None
    if kind is not None and kind != AnswerKind.ANSWERED.value:
        return None
    return answer, retrieved


def qa_support_item(
    question: str, answer: str, sources: Sequence[str], language: Language
) -> Planned:
    """One Q&A answer: do the sources support it? None without a source to judge it against."""
    if not sources:
        return None
    claim = f"Question: {question}\nAnswer: {answer}"
    return planned_item(JudgeCheck.QA_SUPPORT, language, claim, "\n\n".join(sources))


# --- judging -------------------------------------------------------------------------------------


class Judges(Protocol):
    """V4's `Judge`, or a fake in the tests."""

    def judge(self, item: JudgeItem) -> Verdict: ...


class CheckScore(ContractModel):
    """One check's tally on a case or a run: verdicts (`held` of `judged`), items not measured,
    how many the backup judge decided, and what the judge spent on them all."""

    held: int = Field(default=0, ge=0)
    judged: int = Field(default=0, ge=0)
    not_measured: int = Field(default=0, ge=0)
    backup: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    tokens: int = Field(default=0, ge=0)

    def __add__(self, other: Self) -> Self:
        return type(self)(
            held=self.held + other.held,
            judged=self.judged + other.judged,
            not_measured=self.not_measured + other.not_measured,
            backup=self.backup + other.backup,
            cost_usd=self.cost_usd + other.cost_usd,
            tokens=self.tokens + other.tokens,
        )

    @property
    def rate(self) -> Rate:
        return Rate(hits=self.held, total=self.judged)

    @property
    def items(self) -> int:
        """Every item of the check, measured or not."""
        return self.judged + self.not_measured


def judge_one(judge: Judges, item: Planned) -> CheckScore:
    """One item's tally. A `JudgeError` is not measured, with what the item spent; one whose
    call reached no model (`is_call_failed`) is raised again, for the pass to stop."""
    if item is None:
        return CheckScore(not_measured=1)
    try:
        verdict = judge.judge(item)
    except JudgeError as exc:
        if exc.is_call_failed:
            raise
        logger.warning("%s not measured: %s", item.check.value, exc)
        return CheckScore(not_measured=1, cost_usd=exc.cost_usd, tokens=exc.tokens)
    return CheckScore(
        held=int(verdict.holds),
        judged=1,
        backup=int(verdict.decided_by == "backup"),
        cost_usd=verdict.cost_usd,
        tokens=verdict.tokens,
    )


Outcome = CheckScore | JudgeError | None
"""An item's tally, the error of a call that reached no model, or None for an item skipped
after one."""


def judge_plan(
    judge: Judges, plan: Mapping[JudgeCheck, Sequence[Planned]], concurrency: int = 1
) -> dict[JudgeCheck, CheckScore]:
    """Each check's tally over its items, `concurrency` items in flight at once. Every check of
    the plan gets a tally, an empty one when it has no item. Raises `JudgeUnreachedError`, with
    what the items sent spent, when the backup judge's call reached no model; no item starts
    after it."""
    flat = [(check, item) for check, items in plan.items() for item in items]
    unreached = threading.Event()

    def outcome(item: Planned) -> Outcome:
        if unreached.is_set():
            return None
        try:
            return judge_one(judge, item)
        except JudgeError as exc:
            unreached.set()
            logger.warning("a judge's call reached no model; stopping the pass: %s", exc)
            return exc

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        outcomes = list(pool.map(outcome, [item for _, item in flat]))
    scores = [score for score in outcomes if isinstance(score, CheckScore)]
    if unreached.is_set():
        spent = [done for done in outcomes if done is not None]
        raise JudgeUnreachedError(
            sum(done.cost_usd for done in spent), sum(done.tokens for done in spent)
        )
    totals = dict.fromkeys(plan, CheckScore())
    for (check, _), score in zip(flat, scores, strict=True):
        totals = totals | {check: totals[check] + score}
    return totals


# --- stored scores -------------------------------------------------------------------------------


def score_key(check: JudgeCheck, field: str) -> str:
    return f"{KEY_PREFIX}_{check.value}_{field}"


def stored_scores(scores: Mapping[JudgeCheck, CheckScore]) -> dict[str, float | int]:
    """The case's tallies as `eval_case_results.scores` keys, one number each."""
    return {
        score_key(check, field): getattr(score, field)
        for check, score in scores.items()
        for field in SCORE_FIELDS
    }


def read_stored(scores: Mapping[str, object]) -> dict[JudgeCheck, CheckScore]:
    """The tallies a case's scores hold, by check; a check with no stored key is left out.
    Raises `JudgedRecordError` for a value that isn't a non-negative number."""
    found: dict[JudgeCheck, CheckScore] = {}
    for check in CHECK_NAMES:
        keys = {field: score_key(check, field) for field in SCORE_FIELDS}
        if not any(key in scores for key in keys.values()):
            continue
        values = {field: scores.get(key, 0) for field, key in keys.items()}
        try:
            found[check] = CheckScore.model_validate(values)
        except ValidationError as exc:
            raise JudgedRecordError(f"stored judged scores of {check.value} are malformed") from exc
    return found


def is_judged(scores: Mapping[str, object]) -> bool:
    """Whether a case's scores already hold a judged tally."""
    return any(key.startswith(f"{KEY_PREFIX}_") for key in scores)


def run_totals(cases: Iterable[Mapping[JudgeCheck, CheckScore]]) -> dict[JudgeCheck, CheckScore]:
    """Each check's tally summed over the run's judged cases."""
    totals: dict[JudgeCheck, CheckScore] = {}
    for scores in cases:
        for check, score in scores.items():
            totals = totals | {check: totals.get(check, CheckScore()) + score}
    return totals


# --- no invented content, checked by code --------------------------------------------------------

DRAFTING_ERRORS = (DutyDateError, NoClassError, UnwritableTextError)
"""A document that can't be drafted from its result: counted apart, not checked."""


@dataclass(frozen=True)
class CodeCheck:
    """P8a's "No content you didn't supply" check over a run's drafted documents."""

    passed: int = 0
    checked: int = 0
    not_drafted: int = 0

    @property
    def rate(self) -> Rate:
        return Rate(hits=self.passed, total=self.checked)


def code_checked_documents(results: Iterable[tuple[ClassificationResult, Language]]) -> CodeCheck:
    """Each document a result calls for, drafted as `aiact.drafting` drafts it (no interview
    answers, no corpus quotes) in the case's language, and checked by `check_nothing_invented`.
    No model call."""
    passed = checked = not_drafted = 0
    for result, language in results:
        for template in templates_for(result):
            try:
                document = draft_document(template, result, {}, language)
            except DRAFTING_ERRORS as exc:
                logger.warning("%s couldn't be drafted: %s", template.id, type(exc).__name__)
                not_drafted += 1
                continue
            checked += 1
            passed += check_nothing_invented(document, result, {}).passed
    return CodeCheck(passed, checked, not_drafted)


def render_code_check(check: CodeCheck) -> list[str]:
    """The report's line for no invented content: checked by code, not judged."""
    rate = check.rate
    line = (
        f"- No invented content: checked by code (P8a's `check_nothing_invented` on each "
        f"document the results call for), not judged: {rate.percent}, {rate.hits}/{rate.total} "
        "documents"
    )
    if check.not_drafted:
        line += f"; {check.not_drafted} couldn't be drafted"
    return [line]


# --- the judge's settings and the report ---------------------------------------------------------


class JudgedSettings(ContractModel):
    """The judge a run was judged with, kept in the run's `config.judged`."""

    jev_model: str
    backup_model: str
    backup_provider: str
    margin: float = Field(gt=0, lt=0.5)


def parse_settings(config: object) -> JudgedSettings | None:
    """`config.judged`, or None when the run wasn't judged or holds another shape."""
    if not isinstance(config, Mapping) or KEY_PREFIX not in config:
        return None
    try:
        return JudgedSettings.model_validate(config[KEY_PREFIX])
    except ValidationError:
        return None


NOT_JUDGED = "Judged metrics: not judged yet (`aiact evaluate judged <run_id>`)."
NOT_MEASURED_NOTE = (
    "Not measured: the judge's reply was refused or broken, or the item was too long to send; "
    "never counted as a fail."
)


def render_judged(
    totals: Mapping[JudgeCheck, CheckScore],
    cases_judged: int,
    cases: int,
    settings: JudgedSettings | None,
) -> list[str]:
    """The report's "Judged metrics" section: each check's rate, what wasn't measured, what the
    backup judge decided and what the judge spent, per item and in all. `cases` counts the rows
    a pass would judge."""
    if not totals:
        return [NOT_JUDGED]
    spent = sum(score.cost_usd for score in totals.values())
    tokens = sum(score.tokens for score in totals.values())
    lines = ["### Judged metrics", ""]
    if settings is not None:
        lines.append(
            f"- Judge: Jev `{settings.jev_model}`, backup `{settings.backup_model}` on "
            f"`{settings.backup_provider}`, unsure margin {settings.margin} (decision 006)"
        )
    lines += [
        f"- Cases judged: {cases_judged} of {cases}",
        f"- Judge cost: ${spent:.4f}, {tokens} tokens (not in the run's cost above)",
        "",
        "| Metric | Value | Count | Not measured | Backup decided | Cost | Cost per item |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines += [_judged_row(check, totals[check]) for check in CHECK_NAMES if check in totals]
    return [*lines, "", NOT_MEASURED_NOTE]


def _judged_row(check: JudgeCheck, score: CheckScore) -> str:
    rate = score.rate
    per_item = f"${score.cost_usd / score.items:.6f}" if score.items else "n/a"
    return (
        f"| {CHECK_NAMES[check]} | {rate.percent} | {rate.hits}/{rate.total} | "
        f"{score.not_measured} | {score.backup} | ${score.cost_usd:.4f} | {per_item} |"
    )
