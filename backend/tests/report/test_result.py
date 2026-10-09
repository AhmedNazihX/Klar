"""The report for a lawyer (P25): INIT's worked example on two A4 pages with every section and
the disclaimer on both, German citation style in a German render, and the class of the result
it was made from."""

from datetime import date

import pytest

from aiact.export import Fields, Paper, Table, render_docx, render_pdf
from aiact.report import NoClassError, report_id, result_report
from aiact.schemas import (
    DISCLAIMER_DE,
    DISCLAIMER_EN,
    ClassificationResult,
    Language,
    LawVersion,
    LegacyStatus,
    RiskClass,
    Status,
    StepName,
)
from tests.drafting.builders import (
    ambiguous_result,
    legacy_result,
    limited_risk_result,
    needs_information_result,
    provider_also_deployer_result,
)
from tests.drafting.vendor_builders import prohibited_result
from tests.export.reading import one_line, pdf_pages, read_docx
from tests.schemas.builders import ends_early, needs_description, rebuild, steps_with, unverified
from tests.schemas.worked_example import worked_example_result

PREPARED_ON = date(2026, 10, 1)
TOOL = "Applicant screening"
COMPANY = "Nordwerk Logistik GmbH"
EN, DE = Language.EN, Language.DE


def _report(
    result: ClassificationResult | None = None, language: Language = EN, **names: str | None
) -> Paper:
    fields: dict[str, str | None] = {"tool_name": TOOL, "company": COMPANY, **names}
    return result_report(
        result or worked_example_result(), language=language, prepared_on=PREPARED_ON, **fields
    )


def _pages(result: ClassificationResult | None = None, language: Language = EN) -> list[str]:
    return pdf_pages(render_pdf(_report(result, language)))


def _grid(paper: Paper) -> dict[str, str]:
    """The Class, Status, Role and Duties-from grid, label to value."""
    fields = next(block for block in paper.blocks if isinstance(block, Fields))
    return dict(fields.items)


def test_the_worked_example_fills_two_pages_with_every_section_and_the_disclaimer_on_both() -> None:
    first, second, *rest = _pages()
    assert rest == []
    for text in (
        f"Classification report · Report {report_id(worked_example_result())}",
        TOOL,
        f"{COMPANY}. Prepared on 1 October 2026.",
        "Checked under Regulation (EU) 2024/1689 as amended, consolidated text of 27 July 2026 "
        "(CELEX 02024R1689-20260727), as it applies on 27 September 2026.",
        "Class Status Role Duties apply from High-risk Decided Deployer 2 December 2027",
        "Basis Listed in Annex III point 4(a). High-risk: recruitment use",
        "Facts the result rests on Fact Source",
        "The tool scores and ranks applicants Stated by the user",
        "The tool is used under the vendor's name Assumed, not yet confirmed",
        "How the result was reached Step Decision Provision",
        "Role Stays a deployer: not modified, not rebranded, used for its intended purpose "
        "Art. 26(1)",
        "1 Scope In scope: an AI system used in the EU Art. 3(1)",
        "Annex III 4(a), Art. 6(3)",
        "4 Transparency No separate transparency duty identified from the description Art. 50(1)",
        "Page 1 of 2",
    ):
        assert text in first, text
    for text in (
        "Duties of the deployer, from 2 December 2027 Duty Provision",
        "Use the system according to the provider's instructions Art. 26(1)",
        "Inform applicants that the system is used to decide about them Art. 26(11)",
        "Points for legal review These facts the result rests on are assumed and should be "
        "confirmed: \u2013 The tool is used under the vendor's name",
        "For the reviewer Reviewed by Date This report sets out how Klar applied the AI Act",
        "Page 2 of 2",
    ):
        assert text in second, text
    footer = f"{DISCLAIMER_EN} Prepared with Klar, an AI system."
    assert footer in first
    assert footer in second


def test_only_the_assumed_deciding_facts_are_points_for_legal_review() -> None:
    second = _pages()[1]
    # Assumed, but not one the result rests on (it is no deciding fact).
    assert "The tool is used in the EU" not in second
    assert "The tool was not modified" not in second.split("Points for legal review")[1]


def test_a_german_render_uses_german_citation_style_and_terms() -> None:
    first, second = _pages(language=DE)
    for text in (
        "Klassifizierungsbericht · Bericht",
        f"{COMPANY}. Erstellt am 1. Oktober 2026.",
        "Geprüft nach der Verordnung (EU) 2024/1689 in geänderter Fassung, konsolidierter Text "
        "vom 27. Juli 2026 (CELEX 02024R1689-20260727), wie sie am 27. September 2026 gilt.",
        "Einstufung Status Rolle Pflichten gelten ab Hochrisiko Entschieden Betreiber "
        "2. Dezember 2027",
        "Grundlage Aufgeführt in Anhang III Nummer 4 Buchstabe a.",
        "Fakten, auf denen das Ergebnis beruht Fakt Quelle",
        "The tool scores and ranks applicants In der Beschreibung angegeben",
        "The tool is used under the vendor's name Angenommen, noch nicht bestätigt",
        "Wie das Ergebnis zustande kam Schritt Entscheidung Vorschrift",
        "Art. 26 Abs. 1",
        "1 Anwendungsbereich In scope: an AI system used in the EU Art. 3 Abs. 1",
        "Anhang III Nr. 4 Buchst. a, Art. 6 Abs. 3",
        "Seite 1 von 2",
    ):
        assert text in first, text
    for text in (
        "Pflichten des Betreibers, ab dem 2. Dezember 2027 Pflicht Vorschrift",
        "Das System gemäß der Betriebsanleitung verwenden. Art. 26 Abs. 1",
        "Art. 26 Abs. 11",
        "Punkte für die rechtliche Prüfung Diese Fakten, auf denen das Ergebnis beruht, sind "
        "angenommen und sollten bestätigt werden:",
        "Für die prüfende Person Geprüft von Datum Dieser Bericht legt dar",
        "Seite 2 von 2",
    ):
        assert text in second, text
    for page in (first, second):
        assert f"{DISCLAIMER_DE} Erstellt mit Klar, einem KI-System." in page
        assert "Art. 26(" not in page
        assert "Art. 6(3)," not in page


@pytest.mark.parametrize(
    ("result", "label"),
    [
        (worked_example_result(), "High-risk"),
        (limited_risk_result("art:50:1"), "Limited risk"),
        (
            ends_early(
                RiskClass.OUT_OF_SCOPE,
                steps_with(worked_example_result().steps[0], 1),
                Status.DECIDED,
            ),
            "Out of scope",
        ),
        (prohibited_result(), "Prohibited"),
        (
            rebuild(
                limited_risk_result("art:50:1"),
                risk_class=RiskClass.MINIMAL_RISK,
                transparency_duties=(),
            ),
            "Minimal risk",
        ),
        (ambiguous_result(), "High-risk (assumed)"),
    ],
)
def test_the_reports_class_is_the_results(result: ClassificationResult, label: str) -> None:
    assert _grid(_report(result))["Class"] == label
    assert f"Class Status Role Duties apply from {label} " in _pages(result)[0]


def test_a_result_with_no_class_has_no_report() -> None:
    with pytest.raises(NoClassError):
        _report(needs_description())


def test_the_report_id_follows_the_results_content() -> None:
    worked = worked_example_result()
    assert report_id(worked) == report_id(worked_example_result())
    assert report_id(worked) != report_id(ambiguous_result())
    assert report_id(worked).startswith("KR-")
    assert len(report_id(worked)) == len("KR-") + 8


def test_a_tool_without_a_name_and_no_company() -> None:
    first = pdf_pages(render_pdf(_report(tool_name=None, company=None)))[0]
    assert "Your tool Prepared on 1 October 2026." in first
    assert COMPANY not in first


def test_the_original_text_is_named_with_its_own_celex() -> None:
    original = rebuild(worked_example_result(), law_version=LawVersion.ORIGINAL)
    assert (
        "Checked under Regulation (EU) 2024/1689 as published on 12 July 2024 (CELEX 32024R1689), "
        "as it applies on 27 September 2026."
    ) in _pages(original)[0]


def test_an_open_question_and_a_missing_fact_are_points_for_legal_review() -> None:
    ambiguous_page = _pages(ambiguous_result())
    assert (
        "The law doesn't settle this The law leaves this open; the stricter reading is applied."
        in ambiguous_page[0]
    )
    assert "Open question of law (3 High-risk):" in one_line(" ".join(ambiguous_page))
    paused = " ".join(_pages(needs_information_result()))
    assert "A deciding fact is missing Assumed until a missing fact is confirmed." in paused
    assert "Missing fact (3 High-risk): Is the tool used in the EU?" in paused


def test_a_check_not_assessed_is_a_point_for_legal_review() -> None:
    refused = unverified(StepName.HIGH_RISK).model_copy(update={"error": "provider_refusal"})
    result = rebuild(
        worked_example_result(),
        status=Status.NEEDS_MORE_INFORMATION,
        steps=steps_with(refused),
        not_assessed=(StepName.HIGH_RISK,),
    )
    pages = " ".join(_pages(result))
    assert "Not assessed: a person must review this check." in pages
    assert "Not assessed (3 High-risk): the model provider declined to assess this check" in pages


def test_nothing_open_says_so() -> None:
    result = rebuild(worked_example_result(), deciding_facts=worked_example_result().facts[:3])
    assert "No fact the result rests on is assumed, and no question is open." in _pages(result)[1]


def test_duties_of_different_dates_each_show_their_own() -> None:
    result = worked_example_result()
    earlier = result.obligations[0].model_copy(update={"applies_from": date(2026, 8, 2)})
    paper = _report(rebuild(result, obligations=(earlier, *result.obligations[1:])))
    duties = [block for block in paper.blocks if isinstance(block, Table)][-1]
    assert duties.header == ("Duty", "Provision", "Applies from")
    assert duties.rows[0][2] == "2 August 2026"
    assert duties.rows[1][2] == "2 December 2027"
    assert _grid(paper)["Duties apply from"] == "2 August 2026"


def test_a_legacy_duty_applies_only_after_a_significant_change() -> None:
    paper = _report(legacy_result(), DE)
    duties = [block for block in paper.blocks if isinstance(block, Table)][-1]
    assert duties.rows[0][2] == "Nur nach einer wesentlichen Änderung (Art. 111 Abs. 2)"
    assert _grid(paper)["Pflichten gelten ab"] == (
        "Nur nach einer wesentlichen Änderung (Art. 111 Abs. 2)"
    )


def test_a_public_authoritys_legacy_duty_keeps_its_2030_date() -> None:
    result = worked_example_result()
    duties = tuple(
        duty.model_copy(
            update={"legacy": LegacyStatus.PUBLIC_AUTHORITY, "applies_from": date(2030, 8, 2)}
        )
        for duty in result.obligations
    )
    table = [b for b in _report(rebuild(result, obligations=duties)).blocks if isinstance(b, Table)]
    assert table[-1].rows[0][2] == "2 August 2030 (Art. 111(2))"


def test_a_provider_that_also_deploys_names_both_roles() -> None:
    first, second = _pages(provider_also_deployer_result())
    assert "Provider" in first
    assert "Duties of the provider and the deployer, from 2 December 2027" in second
    german = _pages(provider_also_deployer_result(), DE)[1]
    assert "Pflichten des Anbieters und des Betreibers, ab dem 2. Dezember 2027" in german


def test_a_result_that_ends_at_art_5_has_no_role_and_no_duties() -> None:
    paper = _report(prohibited_result())
    assert _grid(paper) == {
        "Class": "Prohibited",
        "Status": "Decided",
        "Role": "Not determined",
        "Duties apply from": "No specific duties",
    }
    second = pdf_pages(render_pdf(paper))[1]
    assert "Duties The result lists no specific duties for this tool." in second


def test_the_word_file_holds_the_same_sections() -> None:
    word = read_docx(render_docx(_report()))
    for text in (
        f"Classification report · Report {report_id(worked_example_result())}",
        TOOL,
        "Basis",
        "Facts the result rests on",
        "How the result was reached",
        "Duties of the deployer, from 2 December 2027",
        "Points for legal review",
        "For the reviewer",
        "Reviewed by",
    ):
        assert text in word.paragraphs, text
    assert word.footer[0] == f"{DISCLAIMER_EN} Prepared with Klar, an AI system."
