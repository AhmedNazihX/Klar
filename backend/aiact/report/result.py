"""The report for a lawyer (P25; artboard `ExportPDF`): one result laid out as a `Paper` of two A4
pages, in English or German.

Page one: the report ID, the tool, the company, the date, the law text and its CELEX number; the
Class, Status, Role and Duties-from grid; the basis; the facts the result rests on with their
source written out; the steps with the provisions each cites. Page two: the duties in their
formal wording, the points for legal review (the assumed facts the result rests on, and any open
question), and the box for the reviewer to sign. The disclaimer and "Page n of 2" close every
page.

The result is validated against the contract and nothing more (decision 031): its facts and the
steps' outcomes are the user's own run. Every sentence the report writes about them is its own,
in the report's language, as the Result screen says it (the basis, each step's outcome, the
duties' date), never the engine's English detail. The duties' formal wording and conditions are
the obligations table's, looked up by the result's class, role, article and law version
(`aiact.report.duties`), never the posted result's; a posted duty the table lacks is left out,
and the report says how many. Provisions are named by their ids in the report's citation style
("Art. 26(1)", "Art. 26 Abs. 1"), each kept on one line, and the notice is the report language's
own, never the posted result's.
"""

import hashlib
from collections import Counter
from collections.abc import Iterable
from datetime import date

from aiact.export import (
    Block,
    Fields,
    Heading,
    PageBreak,
    Paper,
    Paragraph,
    SignOff,
    SmallText,
    Table,
)
from aiact.provision_names import article_provision_name, provision_name
from aiact.report import texts
from aiact.report.common import (
    applies_when,
    class_name,
    day,
    duties_from,
    footer,
    left_out_note,
)
from aiact.report.duties import formal_duties, timing
from aiact.schemas import (
    LAW_TEXTS,
    ClassificationResult,
    EvidenceTag,
    Fact,
    Language,
    LawVersion,
    Obligation,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)

REPORT_ID_PREFIX = "KR-"
REPORT_ID_DIGITS = 8
"""The report ID is this many hex digits of the result's hash: the same result, the same ID."""

STEP_ROWS = (
    StepName.ROLE_OBLIGATIONS,
    StepName.SCOPE,
    StepName.PROHIBITED,
    StepName.HIGH_RISK,
    StepName.TRANSPARENCY,
)
"""The steps table's order: the role first, then the four checks (as the reviewer view)."""

ANNEX_I_POINT, ANNEX_III_POINT = "annex:I:", "annex:III:"
"""How the Annex point of a high-risk result begins, by route; the contract leaves
`annex_point` free, so any other value is no point the report names."""
LAW_PROVISIONS = ("art:", "annex:")
"""The ids of the Act's own provisions; a guideline's (`guide:…`) is no provision of the Act."""
NO_BREAK_SPACE = "\u00a0"
"""Between a citation's words, so a cell never breaks "Art. 6(3)" across two lines."""
FACT_WIDTHS = (3.0, 1.4)
STEP_WIDTHS = (1.25, 2.45, 1.9)
DUTY_WIDTHS = (3.8, 1.0)


class NoClassError(ValueError):
    """The result has no class (a needs-a-description result, E13, or a refused check, decision
    030): there is nothing to report."""


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
    with no class, or with a check not assessed (`assessed_class`)."""
    risk_class = result.assessed_class
    if risk_class is None:
        raise NoClassError(
            "a result with no class (too thin to start, or a refused check) has nothing to report"
        )
    duties = formal_duties(
        result.obligations,
        risk_class=risk_class,
        roles=_roles(result),
        law_version=result.law_version,
    )
    left_out = len(result.obligations) - len(duties)
    return Paper(
        language=language,
        kicker=texts.KICKER[language].format(id=report_id(result)),
        title=tool_name or texts.UNNAMED_TOOL[language],
        lines=_header_lines(result, language, prepared_on, company),
        blocks=(
            _fields(result, risk_class, duties, language),
            Heading(texts.BASIS[language]),
            Paragraph(_basis(result, risk_class, language)),
            *_facts(result, language),
            *_steps(result, language),
            PageBreak(),
            *_duties(result, duties, left_out, language),
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


def _roles(result: ClassificationResult) -> tuple[Role, ...]:
    """The result's role and the one it also has, if any."""
    return tuple(role for role in (result.role, result.also_role) if role is not None)


def _fields(
    result: ClassificationResult,
    risk_class: RiskClass,
    duties: tuple[Obligation, ...],
    language: Language,
) -> Fields:
    labels = texts.FIELD_LABELS
    role = texts.ROLE_NAMES[result.role][language] if result.role else texts.NO_ROLE[language]
    return Fields(
        (
            (labels["class"][language], class_name(risk_class, result.status, language)),
            (labels["status"][language], texts.STATUS_NAMES[result.status][language]),
            (labels["role"][language], role),
            (labels["from"][language], duties_from(tuple(map(timing, duties)), language)),
        )
    )


def _basis(result: ClassificationResult, risk_class: RiskClass, language: Language) -> str:
    """Why the class applies, as the Result screen says it (`basisSentence`): the Annex point a
    high-risk result is listed under, with an Annex III point's plain label, else the class's
    own reason."""
    point = result.annex_point or ""
    if risk_class is not RiskClass.HIGH_RISK or not point.startswith(
        (ANNEX_I_POINT, ANNEX_III_POINT)
    ):
        return texts.CLASS_BASIS[risk_class][language]
    name = _citation(provision_name(point, language))
    if point.startswith(ANNEX_I_POINT):
        return texts.BASIS_ANNEX_I[language].format(point=name)
    label = _annex_label(point)
    if label is None:
        return texts.BASIS_ANNEX_III_PLAIN[language].format(point=name)
    return texts.BASIS_ANNEX_III[language].format(point=name, label=label[language])


def _annex_label(point: str | None) -> texts.ByLanguage | None:
    """An Annex III point's plain label (`annex:III:4:a` is "III_4_a"), if the screens have
    one."""
    if point is None or not point.startswith(ANNEX_III_POINT):
        return None
    key = "_".join(("III", *point.removeprefix(ANNEX_III_POINT).split(":")))
    return texts.ANNEX_III_LABELS.get(key)


def _facts(result: ClassificationResult, language: Language) -> tuple[Block, ...]:
    """The facts the result rests on, as the Result screen lists them: the deciding facts, the
    assumed ones too, each once; without deciding facts, every fact found."""
    heading = Heading(texts.FACTS[language])
    facts = _unique(result.deciding_facts or result.facts)
    if not facts:
        return (heading, Paragraph(texts.NO_FACTS[language]))
    rows = tuple((fact.text, texts.EVIDENCE[fact.evidence][language]) for fact in facts)
    header = tuple(column[language] for column in texts.FACT_HEADER)
    return (heading, Table(header, rows, FACT_WIDTHS))


def _unique(facts: Iterable[Fact]) -> tuple[Fact, ...]:
    """Each fact once: its text is its identity (the engine lists a fact once per step)."""
    return tuple({fact.text: fact for fact in facts}.values())


def _steps(result: ClassificationResult, language: Language) -> tuple[Block, ...]:
    by_name = {step.step: step for step in result.steps}
    rows = tuple(
        (
            texts.STEP_NAMES[name][language],
            _outcome(by_name[name], result, language),
            _provisions(by_name[name], language),
        )
        for name in STEP_ROWS
        if name in by_name
    )
    header = tuple(column[language] for column in texts.STEP_HEADER)
    return (Heading(texts.STEPS[language]), Table(header, rows, STEP_WIDTHS))


def _outcome(step: StepResult, result: ClassificationResult, language: Language) -> str:
    """The step's outcome in one plain line, as the Result screen's step row says it
    (`stepOutcome`). No step was refused: a result with a check not assessed has no report."""
    if step.status is Status.NEEDS_MORE_INFORMATION:
        return texts.STEP_OUTCOMES["paused"][language]
    if step.status is Status.LEGALLY_AMBIGUOUS:
        return texts.STEP_OUTCOMES["ambiguous"][language]
    if step.step is StepName.ROLE_OBLIGATIONS:
        # The contract sets the role exactly when this step is present.
        role = result.role
        return (
            texts.ROLE_NAMES[role][language]
            if role
            else texts.STEP_OUTCOMES["notChecked"][language]
        )
    label = _annex_label(result.annex_point)
    outcome = texts.STEP_OUTCOMES[_outcome_key(step.step, result, has_label=label is not None)]
    count = len(result.transparency_duties)
    return outcome[language].format(label=label[language] if label else "", count=count)


def _outcome_key(name: StepName, result: ClassificationResult, *, has_label: bool) -> str:
    """Which of the screen's outcome lines a decided check's row says."""
    risk_class = result.risk_class
    if name is StepName.SCOPE:
        return "outOfScope" if risk_class is RiskClass.OUT_OF_SCOPE else "inScope"
    if name is StepName.PROHIBITED:
        return "ban" if risk_class is RiskClass.PROHIBITED else "noBan"
    if name is StepName.TRANSPARENCY:
        count = len(result.transparency_duties)
        if count == 0:
            return "noTransparency"
        return "transparencyDuty" if count == 1 else "transparencyDuties"
    if risk_class is not RiskClass.HIGH_RISK:
        return "notHighRisk"
    if (result.annex_point or "").startswith(ANNEX_I_POINT):
        return "highRiskAnnexI"
    return "highRiskAnnexIII" if has_label else "highRisk"


def _provisions(step: StepResult, language: Language) -> str:
    """The provisions of the Act the step cites, in the report's citation style, each once and
    on one line; for a step citing only guidance, what the step checks."""
    ids = dict.fromkeys(
        citation.provision_id
        for citation in step.citations
        if citation.provision_id.startswith(LAW_PROVISIONS)
    )
    if not ids:
        return texts.STEP_REFERENCES[step.step][language]
    return ", ".join(_citation(provision_name(provision_id, language)) for provision_id in ids)


def _citation(name: str) -> str:
    """A provision's name kept on one line."""
    return name.replace(" ", NO_BREAK_SPACE)


def _duties(
    result: ClassificationResult,
    duties: tuple[Obligation, ...],
    left_out: int,
    language: Language,
) -> tuple[Block, ...]:
    """The duties in their formal wording (the table's), with their provision. When most of
    them apply, from one date, or only after a significant change, goes in the heading, as the
    artboard shows it; a duty that applies otherwise says so after its provision. Then how many
    posted duties the table lacks, when any; "no specific duties" only when the result lists
    none at all."""
    heading = _duties_heading(result, language)
    if not duties:
        none = left_out_note(left_out, language) or (Paragraph(texts.NO_DUTIES[language]),)
        return (Heading(heading), *none)
    timings = Counter((duty.applies_from, duty.legacy) for duty in duties)
    usual = timings.most_common(1)[0][0]
    when = texts.WHEN[language]
    rows = tuple(
        (
            _duty_text(duty, language),
            _article(duty, language)
            if (duty.applies_from, duty.legacy) == usual
            else when.format(
                what=_article(duty, language),
                when=applies_when(duty.applies_from, duty.legacy, language),
            ),
        )
        for duty in duties
    )
    dated = when.format(what=heading, when=applies_when(*usual, language))
    header = tuple(column[language] for column in texts.DUTY_HEADER)
    return (Heading(dated), Table(header, rows, DUTY_WIDTHS), *left_out_note(left_out, language))


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
    """The duty's formal wording in the report's language, and its condition when it has one:
    in German when the duty carries the German condition, else the English one, so a condition
    is never dropped (the screen does the same: result-text.ts `dutyCondition`)."""
    text = duty.duty_de if language is Language.DE else duty.duty
    german = duty.applies_if_de if language is Language.DE else None
    condition = german or duty.applies_if
    if condition is None:
        return text
    return texts.APPLIES_IF[language].format(duty=text, condition=condition)


def _article(duty: Obligation, language: Language) -> str:
    return _citation(article_provision_name(duty.article, language))


def _legal_review(result: ClassificationResult, language: Language) -> tuple[Block, ...]:
    """The assumed facts the result rests on, then each step's open question of law, missing
    fact or refusal; a line saying there is none when nothing is open."""
    deciding = _unique(result.deciding_facts)
    assumed = [fact.text for fact in deciding if fact.evidence is EvidenceTag.ASSUMED]
    points: list[Block] = []
    if assumed:
        points.append(SmallText(texts.ASSUMED_FACTS[language]))
        points.extend(SmallText(texts.LISTED[language].format(text=text)) for text in assumed)
    points.extend(SmallText(text) for text in _open_points(result.steps, language))
    if not points:
        points.append(SmallText(texts.NOTHING_TO_REVIEW[language]))
    return (Heading(texts.LEGAL_REVIEW[language]), *points)


def _open_points(steps: Iterable[StepResult], language: Language) -> Iterable[str]:
    for step in steps:
        name = texts.STEP_NAMES[step.step][language]
        if step.open_question is not None:
            yield texts.OPEN_QUESTION[language].format(
                step=name, question=step.open_question.question
            )
        if step.missing_fact is not None:
            yield texts.MISSING_FACT[language].format(step=name, question=step.missing_fact.text)
