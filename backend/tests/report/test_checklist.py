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
    law_version: LawVersion = LawVersion.AMENDED,
) -> str:
    paper = checklist_report(
        tools,
        language=language,
        law_version=law_version,
        prepared_on=PREPARED_ON,
        company=company,
    )
    return " ".join(pdf_pages(render_pdf(paper)))


def _table_rows(tools: tuple[ChecklistTool, ...]) -> list[list[str]]:
    """The first duty table of the checklist's Word file, cell by cell."""
    paper = checklist_report(
        tools, language=Language.EN, law_version=LawVersion.AMENDED, prepared_on=PREPARED_ON
    )
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


def test_a_prohibited_tool_without_duties_says_only_to_stop() -> None:
    banned = ChecklistTool(
        name="Bild-App",
        risk_class=RiskClass.PROHIBITED,
        status=Status.DECIDED,
        role=Role.DEPLOYER,
        law_version=LawVersion.AMENDED,
        as_of=date(2026, 9, 27),
    )
    text = _pages((banned,))
    assert "Bild-App Prohibited, Deployer. 0 of 0 done. Stop using or supplying it now." in text
    assert "no specific duties" not in text.lower()
    assert "Nutzen oder liefern Sie es ab sofort nicht mehr." in _pages((banned,), Language.DE)


def test_a_duty_with_nothing_to_tick_is_listed_without_a_state_and_not_counted() -> None:
    """A duty stored before duties carried their key: the screen can't tick it, so it sends no
    state (`is_done` null) and the checklist counts it as the screen does."""
    keyless = LOGS.model_copy(update={"is_done": None})
    stored = SCREENING.model_copy(update={"duties": (keyless, INFORM_STAFF)})
    assert "Applicant screening High-risk, Deployer. 0 of 1 done." in _pages((stored,))
    assert [row[0] for row in _table_rows((stored,))[1:]] == [NOTHING, "Open"]


ANNEX_I_DUTY = ChecklistDuty(
    label="Use it as instructed", article="art:26:1", applies_from=date(2028, 8, 2)
)
AUTHORITY_DUTY = LOGS.model_copy(
    update={"applies_from": date(2030, 8, 2), "legacy": LegacyStatus.PUBLIC_AUTHORITY}
)


def test_under_the_original_text_each_route_duty_takes_its_routes_original_date() -> None:
    """Annex III 2 December 2027 becomes 2 August 2026, Annex I 2 August 2028 becomes 2 August
    2027 (the original Art. 113); a 2030 Art. 111(2) date and "only after a significant change"
    stay, as on the screen."""
    tool = SCREENING.model_copy(update={"duties": (LOGS, ANNEX_I_DUTY, INFORM_STAFF)})
    authority = SCREENING.model_copy(update={"name": "Benefits", "duties": (AUTHORITY_DUTY,)})
    original = _pages((tool, authority), law_version=LawVersion.ORIGINAL)
    assert "Art. 26(6) 2 August 2026" in original
    assert "Art. 26(1) 2 August 2027" in original
    assert "Only after a significant change (Art. 111(2))" in original
    assert "2 August 2030 (Art. 111(2))" in original
    assert "2 December 2027" not in original and "2028" not in original
    amended = _pages((tool,))
    assert "Art. 26(6) 2 December 2027" in amended and "Art. 26(1) 2 August 2028" in amended


def test_a_public_authority_duty_on_a_route_date_keeps_it_under_the_original_text() -> None:
    """The route swap skips an Art. 111(2) duty even when its date is the route's own."""
    on_route_date = LOGS.model_copy(
        update={"applies_from": date(2027, 12, 2), "legacy": LegacyStatus.PUBLIC_AUTHORITY}
    )
    tool = SCREENING.model_copy(update={"duties": (on_route_date,)})
    original = _pages((tool,), law_version=LawVersion.ORIGINAL)
    assert "2 December 2027 (Art. 111(2))" in original
    assert "2 August 2026" not in original


def test_the_checklist_names_the_law_text_its_dates_follow() -> None:
    notice = "Dates follow the original Art. 113. The duties shown are the amended text's."
    original = _pages(law_version=LawVersion.ORIGINAL)
    assert (
        "Dates under Regulation (EU) 2024/1689 as published on 12 July 2024 (CELEX 32024R1689)."
    ) in original
    assert notice in original
    assert "Checked under the amended text, as it applies on 27 September 2026." in original
    amended = _pages()
    assert notice not in amended
    assert (
        "Dates under Regulation (EU) 2024/1689 as amended, consolidated text of 27 July 2026 "
        "(CELEX 02024R1689-20260727)."
    ) in amended


def test_a_german_checklist_names_its_law_text_and_original_dates() -> None:
    original = _pages(language=Language.DE, law_version=LawVersion.ORIGINAL)
    for line in (
        "Daten nach der Verordnung (EU) 2024/1689 in der am 12. Juli 2024 veröffentlichten "
        "Fassung (CELEX 32024R1689).",
        "Die Daten folgen dem ursprünglichen Art. 113. Die angezeigten Pflichten sind die der "
        "geänderten Fassung.",
        "Geprüft nach der geänderten Fassung, wie sie am 27. September 2026 gilt.",
        "Art. 26 Abs. 6 2. August 2026",
    ):
        assert line in original, line
    assert (
        "Daten nach der Verordnung (EU) 2024/1689 in geänderter Fassung, konsolidierter Text "
        "vom 27. Juli 2026 (CELEX 02024R1689-20260727)."
    ) in _pages(language=Language.DE)
