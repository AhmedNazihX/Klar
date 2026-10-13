"""Judged metrics: the four checks that need judgement, scored by V4's judge (INIT > Metrics,
Judge; story V5).

- Citation support: each step that cites provisions is one item; its decision is the claim and
  the quotes it cites, each under its provision's name, are the cited text.
- Evidence-tag accuracy: each distinct fact tagged "stated" (the result's facts, its deciding
  facts and every step's facts) is one item, judged against the case's description.
- No invented content: the documents the result calls for (P8a's deployer documents, P8b's
  skeletons, P28's vendor letter) are drafted as `aiact.drafting` drafts them, and each section
  that isn't the template's own wording (pre-filled from the result, or the user's answers
  written up) is one item, judged against the facts supplied: the user's answers and what the
  result found (`supplied_facts`). It complements the deterministic "No content you didn't
  supply" check (`aiact.drafting.checks`).
- Q&A support: a Q&A answer is one item, its question and answer the claim and the provisions
  it was answered from the sources (`qa_support_item`).

An item the judge couldn't answer (`JudgeError`, with what it spent) or one too long to send
(`JudgeItem`'s caps) is "not measured": counted apart, never as a fail. Each check's tally
(`CheckScore`) is stored in a case's `eval_case_results.scores` as flat numbers
(`stored_scores`; the table's check allows numbers there) and summed into the run report's
"Judged metrics" table (`render_judged`). The judge's settings (models and unsure margin) are
the run's `config.judged`.

The judge sends what it reads to Jev, which has no EU endpoint (decision 006): only benchmark
cases, the corpus's text and the engine's answers to them reach it, never a user's description.
"""

import logging
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Protocol, Self

from pydantic import Field, ValidationError

from aiact.dates import long_date
from aiact.drafting.documents import templates_for
from aiact.drafting.draft import Answers, UnwritableTextError, draft_document
from aiact.drafting.models import Provenance
from aiact.drafting.prefill import CLASS_NAMES, DutyDateError, NoClassError
from aiact.eval.judge import JudgeCheck, JudgeError, JudgeItem, Verdict
from aiact.eval.metrics import Rate
from aiact.provision_names import annex_point_name, provision_name
from aiact.schemas import (
    Citation,
    ClassificationResult,
    EvidenceTag,
    Language,
    LegacyStatus,
    Obligation,
)
from aiact.schemas.base import ContractModel
from aiact.schemas.evidence import Fact

logger = logging.getLogger(__name__)

Planned = JudgeItem | None
"""An item to judge, or None for one that can't be sent (too long, or nothing to judge it
against): counted as not measured."""

CLASSIFICATION_CHECKS = (
    JudgeCheck.CITATION_SUPPORT,
    JudgeCheck.EVIDENCE_TAG,
    JudgeCheck.INVENTED_CONTENT,
)
"""The checks judged on a classification run's results."""
QA_CHECKS = (JudgeCheck.QA_SUPPORT,)
"""The check judged on a Q&A run's answers."""

KEY_PREFIX = "judged"
SCORE_FIELDS = ("held", "judged", "not_measured", "backup", "cost_usd", "tokens")
"""A check's tally as `scores` stores it: `judged_<check>_<field>`."""
NAMED_PROVISION_PREFIXES = ("art:", "annex:")
"""Provisions `provision_name` names; any other id (a recital, a guideline unit) stays an id."""

CHECK_NAMES: Mapping[JudgeCheck, str] = {
    JudgeCheck.CITATION_SUPPORT: "Citation support",
    JudgeCheck.EVIDENCE_TAG: "Evidence-tag accuracy",
    JudgeCheck.INVENTED_CONTENT: "No invented content (drafted documents)",
    JudgeCheck.QA_SUPPORT: "Q&A support",
}


class JudgedRecordError(ValueError):
    """A stored judged score isn't a whole, non-negative number; the message names the key."""


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
    if provision_id.startswith(NAMED_PROVISION_PREFIXES):
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
    """One item per stated fact: is it in the description?"""
    return tuple(
        planned_item(JudgeCheck.EVIDENCE_TAG, language, fact, description)
        for fact in stated_facts(result)
    )


def qa_support_item(
    question: str, answer: str, sources: Sequence[str], language: Language
) -> Planned:
    """One Q&A answer: do the sources support it? None without a source to judge it against."""
    if not sources:
        return None
    claim = f"Question: {question}\nAnswer: {answer}"
    return planned_item(JudgeCheck.QA_SUPPORT, language, claim, "\n\n".join(sources))


DRAFTING_ERRORS = (DutyDateError, NoClassError, UnwritableTextError)
"""A document that can't be drafted from the result: counted as one item not measured."""


def invented_content_items(
    result: ClassificationResult,
    language: Language,
    answers: Mapping[str, Answers] | None = None,
) -> tuple[Planned, ...]:
    """One item per drafted section that isn't the template's own wording: does it keep to the
    supplied facts? `answers` are the interview answers by template id; without them only the
    pre-filled sections have content. Corpus quotes (decision 031) aren't read: a quoting
    section is drafted without them, its own paragraphs unchanged."""
    answers = answers or {}
    items: list[Planned] = []
    for template in templates_for(result):
        template_answers = answers.get(template.id, {})
        try:
            document = draft_document(template, result, template_answers, language)
        except DRAFTING_ERRORS as exc:
            logger.warning("%s couldn't be drafted: %s", template.id, type(exc).__name__)
            items.append(None)
            continue
        source = supplied_facts(result, template_answers, language)
        items += [
            planned_item(
                JudgeCheck.INVENTED_CONTENT, language, "\n".join(section.paragraphs), source
            )
            for section in document.sections
            if section.paragraphs and section.provenance is not Provenance.TEMPLATE
        ]
    return tuple(items)


def supplied_facts(result: ClassificationResult, answers: Answers, language: Language) -> str:
    """What a document may state, as labelled lines: the user's answers and what the result
    found (its facts, class, role, duties, the text of the Act and the date it was read at, and
    any open question), named as the documents name them."""
    as_of = long_date(result.as_of, language)
    lines = [f"Stated fact: {fact}" for fact in stated_facts(result)]
    lines += [f"Fact the result rests on: {fact.text}" for fact in result.deciding_facts]
    lines += _classification_lines(result, language)
    lines += [_duty_line(duty, language) for duty in result.obligations]
    lines.append(f"Text of the AI Act: {result.law_version.value}, as of {as_of}")
    lines += _open_question_lines(result)
    lines += [f"Answer ({key}): {answer}" for key, answer in answers.items()]
    return "\n".join(lines)


def _classification_lines(result: ClassificationResult, language: Language) -> list[str]:
    lines: list[str] = []
    if result.assessed_class is not None:
        name = CLASS_NAMES[language][result.assessed_class]
        lines.append(f"Classification: {name} (status: {result.status.value})")
    if result.annex_point is not None:
        lines.append(f"Annex point: {annex_point_name(result.annex_point, language)}")
    roles = [role.value for role in (result.role, result.also_role) if role is not None]
    if roles:
        lines.append(f"Role: {', '.join(roles)}")
    cited = dict.fromkeys(
        _provision_heading(c.provision_id, language)
        for step in result.steps
        for c in step.citations
    )
    if cited:
        lines.append(f"Provisions the classification cites: {', '.join(cited)}")
    return lines


def _duty_line(duty: Obligation, language: Language) -> str:
    text = duty.duty_de if language is Language.DE else duty.duty
    if duty.legacy is LegacyStatus.UNCHANGED:
        when = "only after a significant change to the system"
    else:
        when = f"from {long_date(duty.applies_from, language)}"
    return f"Duty under {_provision_heading(duty.article, language)}: {text} (applies {when})"


def _open_question_lines(result: ClassificationResult) -> list[str]:
    lines: list[str] = []
    for question in (step.open_question for step in result.steps if step.open_question):
        lines.append(f"Open question: {question.question}")
        lines += [f"Reading: {reading.explanation}" for reading in question.readings]
        lines += [f"Settled by: {settled.text}" for settled in question.settled_by]
    return lines


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
    """One item's tally. A `JudgeError` is not measured, with what the item spent."""
    if item is None:
        return CheckScore(not_measured=1)
    try:
        verdict = judge.judge(item)
    except JudgeError as exc:
        logger.warning("%s not measured: %s", item.check.value, exc)
        return CheckScore(not_measured=1, cost_usd=exc.cost_usd, tokens=exc.tokens)
    return CheckScore(
        held=int(verdict.holds),
        judged=1,
        backup=int(verdict.decided_by == "backup"),
        cost_usd=verdict.cost_usd,
        tokens=verdict.tokens,
    )


def judge_plan(
    judge: Judges, plan: Mapping[JudgeCheck, Sequence[Planned]], concurrency: int = 1
) -> dict[JudgeCheck, CheckScore]:
    """Each check's tally over its items, `concurrency` items in flight at once. Every check of
    the plan gets a tally, an empty one when it has no item."""
    flat = [(check, item) for check, items in plan.items() for item in items]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        scores = list(pool.map(partial(judge_one, judge), [item for _, item in flat]))
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
    for check in JudgeCheck:
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
    "Not measured: the judge couldn't answer, or the item was too long to send; never counted "
    "as a fail."
)


def render_judged(
    totals: Mapping[JudgeCheck, CheckScore],
    cases_judged: int,
    cases: int,
    settings: JudgedSettings | None,
) -> list[str]:
    """The report's "Judged metrics" section: each check's rate, what wasn't measured, what the
    backup judge decided and what the judge spent, per item and in all."""
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
    lines += [_judged_row(check, totals[check]) for check in JudgeCheck if check in totals]
    return [*lines, "", NOT_MEASURED_NOTE]


def _judged_row(check: JudgeCheck, score: CheckScore) -> str:
    rate = score.rate
    per_item = f"${score.cost_usd / score.items:.6f}" if score.items else "n/a"
    return (
        f"| {CHECK_NAMES[check]} | {rate.percent} | {rate.hits}/{rate.total} | "
        f"{score.not_measured} | {score.backup} | ${score.cost_usd:.4f} | {per_item} |"
    )
