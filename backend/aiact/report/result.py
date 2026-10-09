"""The report for a lawyer (P25; artboard `ExportPDF`): one result laid out as a `Paper` of two A4
pages, in English or German.

Page one: the report ID, the tool, the company, the date, the law text and its CELEX number; the
Class, Status, Role and Duties-from grid; the basis; the facts with their source written out;
the steps with the provisions each cites. Page two: the duties in their formal wording, the
points for legal review (the assumed facts the result rests on, and any open question), and the
box for the reviewer to sign. The disclaimer and "Page n of 2" close every page.

The result is validated against the contract and nothing more (decision 031): its facts and
decisions are the user's own run, shown as given. The report quotes no text of the Act; it names
provisions by their ids, in the report's citation style ("Art. 26(1)", "Art. 26 Abs. 1"), and its
notice is the report language's own, never the posted result's.
"""

import hashlib
from collections.abc import Iterable
from datetime import date

from aiact.export import Block, Fields, Heading, PageBreak, Paper, Paragraph, SignOff, Table
from aiact.provision_names import annex_point_name, article_provision_name, provision_name
from aiact.report import texts
from aiact.report.common import class_name, day, duties_from, duty_timing, footer
from aiact.schemas import (
    LAW_TEXTS,
    ClassificationResult,
    EvidenceTag,
    Language,
    LawVersion,
    Obligation,
    RiskClass,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.steps import PROVIDER_REFUSAL

REPORT_ID_PREFIX = "KR-"
REPORT_ID_DIGITS = 8
"""The report ID is this many hex digits of the result's hash: the same result, the same ID."""

DECIDING_STEP: dict[RiskClass, StepName] = {
    RiskClass.OUT_OF_SCOPE: StepName.SCOPE,
    RiskClass.PROHIBITED: StepName.PROHIBITED,
    RiskClass.HIGH_RISK: StepName.HIGH_RISK,
    RiskClass.LIMITED_RISK: StepName.TRANSPARENCY,
}
"""The step whose decision is the result's basis; a minimal-risk result has none."""
STEP_ROWS = (
    StepName.ROLE_OBLIGATIONS,
    StepName.SCOPE,
    StepName.PROHIBITED,
    StepName.HIGH_RISK,
    StepName.TRANSPARENCY,
)
"""The steps table's order: the role first, then the four checks (as the reviewer view)."""

ANNEX_I = "annex:I:"
LAW_PROVISIONS = ("art:", "annex:")
"""The ids of the Act's own provisions; a guideline's (`guide:…`) is no provision of the Act."""
FACT_WIDTHS = (3.0, 1.4)
STEP_WIDTHS = (1.3, 3.2, 1.5)
DUTY_WIDTHS = (3.4, 1.0)
DATED_DUTY_WIDTHS = (3.0, 1.0, 1.3)


class NoClassError(ValueError):
    """The result has no class (a needs-a-description result, E13): there is nothing to
    report."""


def report_id(result: ClassificationResult) -> str:
    """The report's ID, from the result's content: a report of the same result has the same
    ID, and one of another result a different one."""
    digest = hashlib.sha256(result.model_dump_json().encode()).hexdigest()
    return REPORT_ID_PREFIX + digest[:REPORT_ID_DIGITS].upper()


def result_report(
    result: ClassificationResult,
    *,
    language: Language,
    prepared_on: date,
    tool_name: str | None = None,
    company: str | None = None,
) -> Paper:
    """`result` as the report for a lawyer, in `language`; raises NoClassError for a result
    with no class."""
    if result.risk_class is None:
        raise NoClassError("a needs-a-description result has no class to report")
    return Paper(
        language=language,
        kicker=texts.KICKER[language].format(id=report_id(result)),
        title=tool_name or texts.UNNAMED_TOOL[language],
        lines=_header_lines(result, language, prepared_on, company),
        blocks=(
            _fields(result, result.risk_class, language),
            Heading(texts.BASIS[language]),
            Paragraph(_basis(result, result.risk_class, language)),
            *_facts(result, language),
            *_steps(result, language),
            PageBreak(),
            *_duties(result, language),
            *_legal_review(result, language),
            SignOff(
                heading=texts.REVIEWER[language],
                labels=tuple(label[language] for label in texts.REVIEWER_LABELS),
                text=texts.REVIEWER_TEXT[language],
            ),
        ),
        footer=footer(language),
    )


def _header_lines(
    result: ClassificationResult, language: Language, prepared_on: date, company: str | None
) -> tuple[str, ...]:
    """The company and the date it was prepared on; the law text, its CELEX number, and the
    date the result applies it as of."""
    prepared = texts.PREPARED[language].format(date=day(prepared_on, language))
    law_text = LAW_TEXTS[result.law_version]
    law_line = texts.LAW_LINES[result.law_version is LawVersion.AMENDED][language].format(
        version=day(law_text.version_date, language),
        celex=law_text.celex,
        as_of=day(result.as_of, language),
    )
    first = f"{company}. {prepared}" if company else prepared
    return (first, law_line)


def _fields(result: ClassificationResult, risk_class: RiskClass, language: Language) -> Fields:
    labels = texts.FIELD_LABELS
    role = texts.ROLE_NAMES[result.role][language] if result.role else texts.NO_ROLE[language]
    timings = ((duty.applies_from, duty.legacy) for duty in result.obligations)
    return Fields(
        (
            (labels["class"][language], class_name(risk_class, result.status, language)),
            (labels["status"][language], texts.STATUS_NAMES[result.status][language]),
            (labels["role"][language], role),
            (labels["from"][language], duties_from(timings, language)),
        )
    )


def _basis(result: ClassificationResult, risk_class: RiskClass, language: Language) -> str:
    """The deciding step's decision, after the Annex point a high-risk result is listed under;
    a minimal-risk result's basis is that no check found anything."""
    name = DECIDING_STEP.get(risk_class)
    step = next((step for step in result.steps if step.step is name), None)
    if step is None:
        return texts.MINIMAL_BASIS[language]
    if risk_class is not RiskClass.HIGH_RISK or not result.annex_point:
        return step.decision
    point = annex_point_name(result.annex_point, language)
    is_annex_i = result.annex_point.startswith(ANNEX_I)
    listed = (texts.ANNEX_I_BASIS if is_annex_i else texts.LISTED_IN)[language]
    return f"{listed.format(point=point)} {step.decision}"


def _facts(result: ClassificationResult, language: Language) -> tuple[Block, ...]:
    heading = Heading(texts.FACTS[language])
    if not result.facts:
        return (heading, Paragraph(texts.NO_FACTS[language]))
    rows = tuple((fact.text, texts.EVIDENCE[fact.evidence][language]) for fact in result.facts)
    header = tuple(column[language] for column in texts.FACT_HEADER)
    return (heading, Table(header, rows, FACT_WIDTHS))


def _steps(result: ClassificationResult, language: Language) -> tuple[Block, ...]:
    by_name = {step.step: step for step in result.steps}
    rows = tuple(
        (
            texts.STEP_NAMES[name][language],
            _decision(by_name[name], language),
            _provisions(by_name[name], language),
        )
        for name in STEP_ROWS
        if name in by_name
    )
    header = tuple(column[language] for column in texts.STEP_HEADER)
    return (Heading(texts.STEPS[language]), Table(header, rows, STEP_WIDTHS))


def _decision(step: StepResult, language: Language) -> str:
    """The step's decision, and why it is not settled when it isn't."""
    if step.error == PROVIDER_REFUSAL:
        return f"{step.decision} {texts.STEP_NOT_ASSESSED[language]}"
    if step.status is Status.LEGALLY_AMBIGUOUS:
        return f"{step.decision} {texts.STEP_AMBIGUOUS[language]}"
    if step.status is Status.NEEDS_MORE_INFORMATION:
        return f"{step.decision} {texts.STEP_ASSUMED[language]}"
    return step.decision


def _provisions(step: StepResult, language: Language) -> str:
    """The provisions of the Act the step cites, in the report's citation style, each once;
    for a step citing only guidance, what the step checks."""
    ids = dict.fromkeys(
        citation.provision_id
        for citation in step.citations
        if citation.provision_id.startswith(LAW_PROVISIONS)
    )
    if not ids:
        return texts.STEP_REFERENCES[step.step][language]
    return ", ".join(provision_name(provision_id, language) for provision_id in ids)


def _duties(result: ClassificationResult, language: Language) -> tuple[Block, ...]:
    """The duties in their formal wording, with their provision; when they share one date, it
    goes in the heading, as the artboard shows it, else each duty's date in its own column."""
    heading = _duties_heading(result, language)
    duties = result.obligations
    if not duties:
        return (Heading(heading), Paragraph(texts.NO_DUTIES[language]))
    header = tuple(column[language] for column in texts.DUTY_HEADER)
    timings = {(duty.applies_from, duty.legacy) for duty in duties}
    if len(timings) == 1 and duties[0].legacy is None:
        dated = texts.DUTIES_FROM[language].format(
            heading=heading, date=day(duties[0].applies_from, language)
        )
        rows = tuple((_duty_text(duty, language), _article(duty, language)) for duty in duties)
        return (Heading(dated), Table(header, rows, DUTY_WIDTHS))
    rows = tuple(
        (
            _duty_text(duty, language),
            _article(duty, language),
            duty_timing(duty.applies_from, duty.legacy, language),
        )
        for duty in duties
    )
    header = (*header, texts.FROM_HEADER[language])
    return (Heading(heading), Table(header, rows, DATED_DUTY_WIDTHS))


def _duties_heading(result: ClassificationResult, language: Language) -> str:
    if result.role is None:
        return texts.DUTIES[language]
    role = texts.ROLE_OF[result.role][language]
    if result.also_role is not None:
        role = texts.ROLES_JOINED[language].format(
            first=role, second=texts.ROLE_OF[result.also_role][language]
        )
    return texts.DUTIES_OF[language].format(role=role)


def _duty_text(duty: Obligation, language: Language) -> str:
    """The duty's formal wording in the report's language, and its condition when it has one."""
    text = duty.duty_de if language is Language.DE else duty.duty
    if duty.applies_if is None:
        return text
    return texts.APPLIES_IF[language].format(duty=text, condition=duty.applies_if)


def _article(duty: Obligation, language: Language) -> str:
    return article_provision_name(duty.article, language)


def _legal_review(result: ClassificationResult, language: Language) -> tuple[Block, ...]:
    """The assumed facts the result rests on, then each step's open question of law, missing
    fact or refusal; a line saying there is none when nothing is open."""
    assumed = [fact.text for fact in result.deciding_facts if fact.evidence is EvidenceTag.ASSUMED]
    points: list[Block] = []
    if assumed:
        points.append(Paragraph(texts.ASSUMED_FACTS[language]))
        points.extend(Paragraph(texts.LISTED[language].format(text=text)) for text in assumed)
    points.extend(Paragraph(text) for text in _open_points(result.steps, language))
    if not points:
        points.append(Paragraph(texts.NOTHING_TO_REVIEW[language]))
    return (Heading(texts.LEGAL_REVIEW[language]), *points)


def _open_points(steps: Iterable[StepResult], language: Language) -> Iterable[str]:
    for step in steps:
        name = texts.STEP_NAMES[step.step][language]
        if step.error == PROVIDER_REFUSAL:
            yield texts.NOT_ASSESSED[language].format(step=name)
        if step.open_question is not None:
            yield texts.OPEN_QUESTION[language].format(
                step=name, question=step.open_question.question
            )
        if step.missing_fact is not None:
            yield texts.MISSING_FACT[language].format(step=name, question=step.missing_fact.text)
