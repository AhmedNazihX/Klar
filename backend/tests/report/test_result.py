"""The report for a lawyer (P25): INIT's worked example on two A4 pages with every section and
the disclaimer on both, German citation style in a German render, and the class of the result
it was made from; a real engine result (the worked example's replay) on two pages in both
languages, in the report's own words."""

from datetime import date
from pathlib import Path

import pytest

from aiact.export import Fields, Heading, Paper, Table, render_docx, render_pdf
from aiact.report import NoClassError, report_id, result_report
from aiact.schemas import (
    DISCLAIMER_DE,
    DISCLAIMER_EN,
    ClassificationResult,
    EvidenceTag,
    Fact,
    HighRiskRoute,
    Language,
    LawVersion,
    LegacyStatus,
    RiskClass,
    Role,
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
REPLAYED = Path(__file__).parents[1] / "fixtures" / "report" / "replayed_worked_example.json"
"""The result the worked example's recorded replay gives (tests/engine/
test_classify_worked_example.py): real engine step details, eleven duties of the deployer, six
of them with a condition, Art. 4's among them with its own date, three assumed deciding facts."""
EU_JOBS = Fact(text="It is used for jobs in the EU.", evidence=EvidenceTag.ASSUMED)
NBSP = "\u00a0"


def replayed_result() -> ClassificationResult:
    """The replayed result with a fourth assumed fact it rests on, as the artboard has."""
    result = ClassificationResult.model_validate_json(REPLAYED.read_text(encoding="utf-8"))
    return rebuild(result, deciding_facts=(*result.deciding_facts, EU_JOBS))


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


def _tables(paper: Paper) -> list[Table]:
    return [block for block in paper.blocks if isinstance(block, Table)]


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
        "Basis The tool is listed in Annex III 4(a): recruitment and selection of people.",
        "Facts the result rests on Fact Source",
        "The tool scores and ranks applicants Stated by the user",
        "The tool is used under the vendor's name Assumed, not yet confirmed",
        "How the result was reached Step Decision Provision",
        "Role Deployer Art. 26(1)",
        "1 Scope In scope Art. 3(1)",
        "2 Prohibited practices No match with a banned practice Art. 5(1)",
        "3 High-risk Yes: recruitment and selection of people Annex III 4(a), Art. 6(3)",
        "4 Transparency No separate duty found Art. 50(1)",
        "Page 1 of 2",
    ):
        assert text in first, text
    for text in (
        "Duties of the deployer, from 2 December 2027 Duty Provision",
        "Use the system according to the provider's instructions for use, with appropriate "
        "technical and organisational measures. Art. 26(1)",
        "Inform the people concerned that they are subject to the use of the high-risk system. "
        "Applies if: The system makes, or helps make, decisions about natural persons. "
        "Art. 26(11)",
        "Points for legal review These facts the result rests on are assumed and should be "
        "confirmed: \u2013 The tool is used under the vendor's name",
        "For the reviewer Reviewed by Date This report sets out how Klar applied the AI Act",
        "Page 2 of 2",
    ):
        assert text in second, text
    footer = f"{DISCLAIMER_EN} Prepared with Klar, an AI system."
    assert footer in first
    assert footer in second


def test_the_facts_are_the_ones_the_result_rests_on_assumed_ones_included() -> None:
    result = replayed_result()
    facts = _tables(_report(result))[0]
    assert len(facts.rows) == len(result.deciding_facts)
    assumed = [text for text, source in facts.rows if source == "Assumed, not yet confirmed"]
    assert len(assumed) == 4
    assert EU_JOBS.text in assumed
    german = _tables(_report(result, DE))[0]
    assert (EU_JOBS.text, "Angenommen, noch nicht bestätigt") in german.rows


def test_only_the_assumed_deciding_facts_are_points_for_legal_review() -> None:
    second = _pages()[1]
    # Assumed, but not one the result rests on (it is no deciding fact).
    assert "The tool is used in the EU" not in second
    assert "The tool was not modified" not in second.split("Points for legal review")[1]


@pytest.mark.parametrize("language", [EN, DE])
def test_a_real_engine_result_fits_two_pages(language: Language) -> None:
    pages = _pages(replayed_result(), language)
    assert len(pages) == 2
    second = pages[1]
    page_of = "Page 2 of 2" if language is EN else "Seite 2 von 2"
    assert page_of in second
    assert ("For the reviewer" if language is EN else "Für die prüfende Person") in second
    assert one_line(EU_JOBS.text) in second.split("Points" if language is EN else "Punkte")[1]


@pytest.mark.parametrize("language", [EN, DE])
def test_no_engine_sentence_and_no_raw_value_reaches_the_report(language: Language) -> None:
    result = replayed_result()
    text = " ".join(_pages(result, language))
    for step in result.steps:
        assert one_line(step.decision) not in text, step.step
    # The values in snake case ("high_risk"); "provider" or "stated" are words a fact may use.
    enums = (*RiskClass, *Status, *Role, *StepName, *EvidenceTag, *LawVersion, *LegacyStatus)
    raw_values = [member.value for member in enums if "_" in member.value]
    assert "high_risk" in raw_values
    for value in raw_values:
        assert value not in text, value


def test_the_steps_say_what_the_result_screen_says_in_german() -> None:
    steps = _tables(_report(replayed_result(), DE))[1]
    assert [row[:2] for row in steps.rows] == [
        ("Rolle", "Betreiber"),
        ("1 Anwendungsbereich", "Vorerst angenommen: eine Angabe fehlt"),
        ("2 Verbotene Praktiken", "Kein Treffer bei den verbotenen Praktiken"),
        ("3 Hochrisiko", "Ja: Einstellung und Auswahl von Personen"),
        ("4 Transparenz", "Keine eigene Pflicht gefunden"),
    ]


def test_the_basis_is_one_sentence_in_the_reports_language() -> None:
    assert _report().blocks[2].text == (  # pyright: ignore[reportAttributeAccessIssue]
        f"The tool is listed in Annex{NBSP}III{NBSP}4(a): recruitment and selection of people."
    )
    assert _report(language=DE).blocks[2].text == (  # pyright: ignore[reportAttributeAccessIssue]
        f"Das Tool ist in Anhang{NBSP}III{NBSP}Nr.{NBSP}4{NBSP}Buchst.{NBSP}a aufgeführt: "
        "Einstellung und Auswahl von Personen."
    )


def test_duties_apply_from_the_routes_date_as_on_the_result_screen() -> None:
    """Art. 4's AI-literacy duty applies from 2 February 2025, but a high-risk result's duties
    apply from its route's date, as the Result screen says it; Art. 4 keeps its own date."""
    paper = _report(replayed_result())
    assert _grid(paper)["Duties apply from"] == "2 December 2027"
    assert _grid(_report(replayed_result(), DE))["Pflichten gelten ab"] == "2. Dezember 2027"
    duties = _tables(paper)[-1]
    assert duties.rows[0][1] == f"Art.{NBSP}4(1), from 2 February 2025"
    assert duties.rows[1][1] == f"Art.{NBSP}26(1)"
    headings = [block.text for block in paper.blocks if isinstance(block, Heading)]
    assert "Duties of the deployer, from 2 December 2027" in headings


def test_a_citation_is_kept_on_one_line() -> None:
    steps = _tables(_report())[1]
    assert steps.rows[3][2] == f"Annex{NBSP}III{NBSP}4(a), Art.{NBSP}6(3)"
    german = _tables(_report(language=DE))[1]
    assert german.rows[3][2] == (
        f"Anhang{NBSP}III{NBSP}Nr.{NBSP}4{NBSP}Buchst.{NBSP}a, Art.{NBSP}6{NBSP}Abs.{NBSP}3"
    )


@pytest.mark.parametrize("language", [EN, DE])
def test_the_page_break_puts_the_duties_on_page_two(language: Language) -> None:
    """A short result leaves room on page one: only the page break moves the duties."""
    first, second = _pages(limited_risk_result("art:50:1"), language)
    basis, duties = (
        ("Basis", "Duties of the deployer")
        if language is EN
        else ("Grundlage", "Pflichten des Betreibers")
    )
    assert basis in first
    assert duties not in first
    assert second.startswith(duties)


def test_a_german_render_uses_german_citation_style_and_terms() -> None:
    first, second = _pages(language=DE)
    for text in (
        "Bericht zur Einstufung · Bericht",
        f"{COMPANY}. Erstellt am 1. Oktober 2026.",
        "Geprüft nach der Verordnung (EU) 2024/1689 in geänderter Fassung, konsolidierter Text "
        "vom 27. Juli 2026 (CELEX 02024R1689-20260727), wie sie am 27. September 2026 gilt.",
        "Einstufung Status Rolle Pflichten gelten ab Hochrisiko Entschieden Betreiber "
        "2. Dezember 2027",
        "Grundlage Das Tool ist in Anhang III Nr. 4 Buchst. a aufgeführt: Einstellung und "
        "Auswahl von Personen.",
        "Fakten, auf denen das Ergebnis beruht Fakt Quelle",
        "The tool scores and ranks applicants In der Beschreibung angegeben",
        "The tool is used under the vendor's name Angenommen, noch nicht bestätigt",
        "Wie das Ergebnis zustande kam Schritt Entscheidung Vorschrift",
        "Rolle Betreiber Art. 26 Abs. 1",
        "1 Anwendungsbereich Anwendbar Art. 3 Abs. 1",
        "Anhang III Nr. 4 Buchst. a, Art. 6 Abs. 3",
        "Seite 1 von 2",
    ):
        assert text in first, text
    for text in (
        "Pflichten des Betreibers, ab dem 2. Dezember 2027 Pflicht Vorschrift",
        "Das System gemäß der beigefügten Betriebsanleitung verwenden und dafür geeignete "
        "technische und organisatorische Maßnahmen treffen. Art. 26 Abs. 1",
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
    assert "3 High-risk Legally ambiguous: the stricter reading applies" in ambiguous_page[0]
    assert "Open question of law (3 High-risk):" in one_line(" ".join(ambiguous_page))
    paused = " ".join(_pages(needs_information_result()))
    assert "3 High-risk Assumed for now: one fact is missing" in paused
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
    assert "3 High-risk Not assessed: a person must review this check." in pages
    assert "Not assessed (3 High-risk): the model provider declined to assess this check" in pages


def test_nothing_open_says_so() -> None:
    result = rebuild(worked_example_result(), deciding_facts=worked_example_result().facts[:3])
    assert "No fact the result rests on is assumed, and no question is open." in _pages(result)[1]


def test_a_duty_of_another_date_says_so_after_its_provision() -> None:
    result = worked_example_result()
    earlier = result.obligations[0].model_copy(update={"applies_from": date(2026, 8, 2)})
    paper = _report(rebuild(result, obligations=(earlier, *result.obligations[1:])))
    duties = _tables(paper)[-1]
    assert duties.header == ("Duty", "Provision")
    assert duties.rows[0][1] == f"Art.{NBSP}26(1), from 2 August 2026"
    assert duties.rows[1][1] == f"Art.{NBSP}26(2)"
    # Not a route duty: the earliest date, as the Result screen dates it.
    assert _grid(paper)["Duties apply from"] == "2 August 2026"


def test_a_legacy_duty_applies_only_after_a_significant_change() -> None:
    result = legacy_result()
    routed = tuple(
        duty.model_copy(update={"high_risk_route": HighRiskRoute.ANNEX_III})
        for duty in result.obligations
    )
    paper = _report(rebuild(result, obligations=routed), DE)
    headings = [block.text for block in paper.blocks if isinstance(block, Heading)]
    assert "Pflichten des Betreibers, nur nach einer wesentlichen Änderung (Art. 111 Abs. 2)" in (
        headings
    )
    assert _grid(paper)["Pflichten gelten ab"] == (
        "Nur nach einer wesentlichen Änderung (Art. 111 Abs. 2)"
    )


def test_a_public_authoritys_legacy_duty_keeps_its_2030_date() -> None:
    result = worked_example_result()
    duties = tuple(
        duty.model_copy(
            update={
                "legacy": LegacyStatus.PUBLIC_AUTHORITY,
                "applies_from": date(2030, 8, 2),
                "high_risk_route": HighRiskRoute.ANNEX_III,
            }
        )
        for duty in result.obligations
    )
    paper = _report(rebuild(result, obligations=duties))
    headings = [block.text for block in paper.blocks if isinstance(block, Heading)]
    assert "Duties of the deployer, from 2 August 2030 (Art. 111(2))" in headings
    assert _grid(paper)["Duties apply from"] == "2 August 2030 (Art. 111(2))"


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
