"""The obligations checklist (P24): each classified tool's duties with their ticked state, the
progress per tool and overall, in English and German."""

from datetime import date
from io import BytesIO

from docx import Document

from aiact.export import render_docx, render_pdf
from aiact.report import ChecklistDuty, ChecklistTool, checklist_report
from aiact.report.texts import NOTHING
from aiact.schemas import (
    DISCLAIMER_DE,
    DISCLAIMER_EN,
    Language,
    LawVersion,
    LegacyStatus,
    RiskClass,
    Role,
    Status,
)
from tests.export.reading import pdf_pages

PREPARED_ON = date(2026, 10, 1)
COMPANY = "Nordwerk Logistik GmbH"

LOGS = ChecklistDuty(
    label="Keep the logs",
    article="art:26:6",
    applies_from=date(2027, 12, 2),
    is_done=True,
)
INFORM_STAFF = ChecklistDuty(
    label="Tell workers' representatives and staff before you start",
    article="art:26:7",
    applies_from=date(2027, 12, 2),
    legacy=LegacyStatus.UNCHANGED,
)
SCREENING = ChecklistTool(
    name="Applicant screening",
    risk_class=RiskClass.HIGH_RISK,
    status=Status.DECIDED,
    role=Role.DEPLOYER,
    law_version=LawVersion.AMENDED,
    as_of=date(2026, 9, 27),
    duties=(LOGS, INFORM_STAFF),
)
CV_EXTRACTION = SCREENING.model_copy(
    update={"name": "CV data extraction", "status": Status.LEGALLY_AMBIGUOUS, "duties": (LOGS,)}
)
UNCHECKED = ChecklistTool(name="Shift planner")


def _pages(
    tools: tuple[ChecklistTool, ...] = (SCREENING,),
    language: Language = Language.EN,
    company: str | None = COMPANY,
) -> str:
    paper = checklist_report(tools, language=language, prepared_on=PREPARED_ON, company=company)
    return " ".join(pdf_pages(render_pdf(paper)))


def _table_rows(tools: tuple[ChecklistTool, ...]) -> list[list[str]]:
    """The first duty table of the checklist's Word file, cell by cell."""
    paper = checklist_report(tools, language=Language.EN, prepared_on=PREPARED_ON)
    table = Document(BytesIO(render_docx(paper))).tables[0]
    return [[cell.text for cell in row.cells] for row in table.rows]


def test_each_duty_shows_whether_it_was_ticked_off() -> None:
    text = _pages()
    assert (
        "Obligations checklist Nordwerk Logistik GmbH Prepared on 1 October 2026. 1 of 2 done."
        in text
    )
    assert "Applicant screening High-risk, Deployer. 1 of 2 done." in text
    assert "Status Duty Provision Applies from" in text
    # The table's label, not the posted one.
    assert (
        "Done Keep the logs it creates for at least six months Art. 26(6) 2 December 2027" in text
    )
    assert (
        "Open Tell workers' representatives and staff before you start Art. 26(7) Only after a "
        "significant change (Art. 111(2))"
    ) in text
    assert "Klar keeps the list; it doesn't check the work for you." in text
    assert f"{DISCLAIMER_EN} Prepared with Klar, an AI system." in text


def test_the_overall_count_adds_up_every_tool() -> None:
    text = _pages((SCREENING, CV_EXTRACTION, UNCHECKED))
    assert "Prepared on 1 October 2026. 2 of 3 done." in text
    assert "CV data extraction High-risk (assumed), Deployer. 1 of 1 done." in text
    assert "Shift planner" not in text


def test_an_assumed_class_says_its_duties_apply_if_the_stricter_reading_holds() -> None:
    text = _pages((SCREENING, CV_EXTRACTION))
    flag = "These duties apply if the stricter reading holds."
    assert text.count(flag) == 1
    assert f"1 of 1 done. {flag}" in text


def test_an_informational_duty_has_no_state_and_is_not_counted() -> None:
    information = ChecklistDuty(
        label="Don't supply it",
        article="art:5:1",
        applies_from=date(2025, 2, 2),
        is_done=True,
    )
    distributor = ChecklistTool(
        name="Bild-App",
        risk_class=RiskClass.PROHIBITED,
        status=Status.DECIDED,
        role=Role.DISTRIBUTOR,
        law_version=LawVersion.AMENDED,
        as_of=date(2026, 9, 27),
        duties=(information,),
    )
    text = _pages((distributor,))
    assert "Bild-App Prohibited, Distributor. 0 of 0 done." in text
    assert "Stop using or supplying it now." in text
    [row] = _table_rows((distributor,))[1:]
    assert (row[0], row[2]) == (NOTHING, "Art. 5(1)")


def test_a_posted_duty_the_table_lacks_is_left_out_and_counted() -> None:
    unknown = ChecklistDuty(
        label="A duty Klar no longer lists", article="art:99:1", applies_from=date(2027, 12, 2)
    )
    text = _pages((SCREENING.model_copy(update={"duties": (LOGS, unknown)}),))
    assert "A duty Klar no longer lists" not in text
    assert "1 of 1 done." in text
    assert "1 more duty the result lists is not in Klar's table of duties" in text


def test_a_german_checklist() -> None:
    text = _pages(language=Language.DE)
    for line in (
        "Pflichten-Checkliste Nordwerk Logistik GmbH Erstellt am 1. Oktober 2026. "
        "1 von 2 erledigt.",
        "Applicant screening Hochrisiko, Betreiber. 1 von 2 erledigt.",
        "Stand Pflicht Vorschrift Gilt ab",
        "Erledigt Die automatisch erzeugten Protokolle mindestens sechs Monate aufbewahren "
        "Art. 26 Abs. 6 2. Dezember 2027",
        "Offen",
        "Klar führt die Liste; ob die Arbeit getan ist, prüft Klar nicht.",
        "Als erledigt markiert ist eine Pflicht, die Sie in Klar abgehakt haben.",
    ):
        assert line in text, line
    assert f"{DISCLAIMER_DE} Erstellt mit Klar, einem KI-System." in text
    flagged = _pages((CV_EXTRACTION,), Language.DE)
    assert "Diese Pflichten gelten, wenn die strengere Auslegung zutrifft." in flagged


def test_an_empty_checklist_without_a_company() -> None:
    text = _pages((UNCHECKED,), company=None)
    assert "Your obligations Prepared on 1 October 2026. 0 of 0 done." in text
    assert "The inventory has no tools yet." in text


def test_the_word_file_has_the_ticked_state_in_its_table() -> None:
    rows = _table_rows((SCREENING,))
    assert rows[0] == ["Status", "Duty", "Provision", "Applies from"]
    assert [row[0] for row in rows[1:]] == ["Done", "Open"]
