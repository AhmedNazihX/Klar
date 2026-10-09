"""The inventory report (P25): every tool with its class, status, role and first duty date, then
each classified tool's duties, in English and German."""

from datetime import date

from aiact.export import render_pdf
from aiact.report import InventoryDuty, InventoryTool, inventory_report
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

SCREENING = InventoryTool(
    name="Applicant screening",
    risk_class=RiskClass.HIGH_RISK,
    status=Status.DECIDED,
    role=Role.DEPLOYER,
    law_version=LawVersion.AMENDED,
    as_of=date(2026, 9, 27),
    duties=(
        InventoryDuty(
            label="Keep the logs it creates for at least six months",
            article="art:26:6",
            applies_from=date(2027, 12, 2),
        ),
        InventoryDuty(
            label="Tell workers' representatives and staff before you start",
            article="art:26:7",
            applies_from=date(2027, 12, 2),
            legacy=LegacyStatus.UNCHANGED,
        ),
    ),
)
CHATBOT = InventoryTool(
    risk_class=RiskClass.LIMITED_RISK,
    status=Status.LEGALLY_AMBIGUOUS,
    role=Role.PROVIDER,
    law_version=LawVersion.AMENDED,
    as_of=date(2026, 9, 30),
    duties=(
        InventoryDuty(
            label="Tell people they're talking to an AI",
            article="art:50:1",
            applies_from=date(2026, 8, 2),
        ),
    ),
)
UNCHECKED = InventoryTool(name="Shift planner")
NOTHING_TO_DO = InventoryTool(
    name="Spam filter", risk_class=RiskClass.MINIMAL_RISK, status=Status.DECIDED, role=Role.DEPLOYER
)
TOOLS = (SCREENING, CHATBOT, UNCHECKED, NOTHING_TO_DO)


COMPANY = "Nordwerk Logistik GmbH"


def _pages(
    language: Language = Language.EN,
    *,
    tools: tuple[InventoryTool, ...] = TOOLS,
    company: str | None = COMPANY,
) -> str:
    """The report's pages as one line, each page checked for its page line."""
    paper = inventory_report(tools, language=language, prepared_on=PREPARED_ON, company=company)
    pages = pdf_pages(render_pdf(paper))
    page_line = "Page {} of {}" if language is Language.EN else "Seite {} von {}"
    for number, page in enumerate(pages, start=1):
        assert page_line.format(number, len(pages)) in page
    return " ".join(pages)


def test_every_tool_is_listed_with_its_class_status_role_and_first_date() -> None:
    text = _pages()
    for line in (
        "Inventory report Nordwerk Logistik GmbH Prepared on 1 October 2026. 4 tools.",
        "Tool Class Status Role Duties apply from",
        "Applicant screening High-risk Decided Deployer 2 December 2027",
        "Your tool Limited risk (assumed) Legally ambiguous Provider 2 August 2026",
        "Shift planner Not classified yet \u2013 \u2013 \u2013",
        "Spam filter Minimal risk Decided Deployer No specific duties",
    ):
        assert line in text, line
    assert f"{DISCLAIMER_EN} Prepared with Klar, an AI system." in text


def test_each_classified_tool_lists_its_duties() -> None:
    text = _pages()
    for line in (
        "Applicant screening Checked under the amended text, as it applies on 27 September 2026.",
        "Duty Provision Applies from Keep the logs it creates for at least six months "
        "Art. 26(6) 2 December 2027",
        "Tell workers' representatives and staff before you start Art. 26(7) Only after a "
        "significant change (Art. 111(2))",
        "Your tool Checked under the amended text, as it applies on 30 September 2026.",
        "Spam filter The result lists no specific duties for this tool.",
    ):
        assert line in text, line
    assert "Shift planner Checked" not in text


def test_a_german_inventory_report() -> None:
    text = _pages(Language.DE)
    for line in (
        "Inventarbericht Nordwerk Logistik GmbH Erstellt am 1. Oktober 2026. 4 Tools.",
        "Tool Einstufung Status Rolle Pflichten gelten ab",
        "Applicant screening Hochrisiko Entschieden Betreiber 2. Dezember 2027",
        "Ihr Tool Begrenztes Risiko (angenommen) Rechtlich unklar Anbieter 2. August 2026",
        "Shift planner Noch nicht eingestuft",
        "Art. 26 Abs. 6 2. Dezember 2027",
        "Nur nach einer wesentlichen Änderung (Art. 111 Abs. 2)",
        "Geprüft nach der geänderten Fassung, wie sie am 27. September 2026 gilt.",
    ):
        assert line in text, line
    assert f"{DISCLAIMER_DE} Erstellt mit Klar, einem KI-System." in text


def test_an_empty_inventory_without_a_company() -> None:
    text = _pages(tools=(), company=None)
    assert "Your AI inventory Prepared on 1 October 2026. 0 tools." in text
    assert "The inventory has no tools yet." in text


def test_one_tool_is_counted_in_the_singular() -> None:
    assert "1 tool." in _pages(tools=(SCREENING,))
    assert "1 Tool." in _pages(Language.DE, tools=(SCREENING,))


AI_LITERACY = InventoryDuty(
    label="Help the people who run or use it build their AI literacy",
    article="art:4:1",
    applies_from=date(2025, 2, 2),
)


def test_a_high_risk_tools_duties_apply_from_its_routes_date_not_art_4s() -> None:
    """As the inventory screen dates it: Art. 4's AI-literacy duty (2 February 2025) doesn't
    date a high-risk tool; its route's duties do."""
    tool = SCREENING.model_copy(update={"duties": (AI_LITERACY, *SCREENING.duties[:1])})
    text = _pages(tools=(tool,))
    assert "Applicant screening High-risk Decided Deployer 2 December 2027" in text
    assert "Art. 4(1) 2 February 2025" in text


def test_a_limited_risk_tools_duties_apply_from_its_art_50_date() -> None:
    chatbot = CHATBOT.model_copy(update={"duties": (AI_LITERACY, *CHATBOT.duties)})
    assert "Your tool Limited risk (assumed) Legally ambiguous Provider 2 August 2026" in _pages(
        tools=(chatbot,)
    )


def test_a_prohibited_tool_says_to_stop_using_or_supplying_it() -> None:
    banned = InventoryTool(
        name="Bild-App", risk_class=RiskClass.PROHIBITED, status=Status.DECIDED, role=Role.DEPLOYER
    )
    english = _pages(tools=(banned,))
    assert "Bild-App Prohibited Decided Deployer Stop using or supplying it now" in english
    assert "Bild-App Stop using or supplying it now." in english
    assert "no specific duties" not in english.lower()
    german = _pages(Language.DE, tools=(banned,))
    assert (
        "Bild-App Verboten Entschieden Betreiber Nutzen oder liefern Sie es ab sofort nicht mehr"
        in german
    )
    assert "Bild-App Nutzen oder liefern Sie es ab sofort nicht mehr." in german
    assert "keine besonderen Pflichten" not in german


def test_a_duty_is_labelled_as_the_table_labels_it_when_the_table_has_it() -> None:
    posted = InventoryDuty(
        label="Keep the logs", article="art:26:6", applies_from=date(2027, 12, 2)
    )
    unknown = InventoryDuty(
        label="A duty Klar no longer lists", article="art:99:1", applies_from=date(2027, 12, 2)
    )
    tool = SCREENING.model_copy(update={"duties": (posted, unknown)})
    english = _pages(tools=(tool,))
    assert "Keep the logs it creates for at least six months Art. 26(6)" in english
    assert "A duty Klar no longer lists" not in english
    assert (
        "1 more duty the result lists is not in Klar's table of duties, so it is left out here."
        in english
    )
    german = _pages(Language.DE, tools=(tool,))
    assert "Die automatisch erzeugten Protokolle mindestens sechs Monate aufbewahren" in german


SECRET = "Confidential: the Hamburg pilot of Project Falcon"


def test_a_posted_label_never_prints() -> None:
    """Decision 031: a duty the table lacks for the tool (another article, another role, a law
    version it doesn't hold) is left out and counted, never shown with its posted label."""
    forged = (
        InventoryDuty(label=SECRET, article="art:99:1", applies_from=date(2027, 12, 2)),
        InventoryDuty(label=SECRET, article="art:16:a", applies_from=date(2027, 12, 2)),
    )
    original = SCREENING.model_copy(update={"law_version": LawVersion.ORIGINAL})
    tools = (SCREENING.model_copy(update={"duties": forged}), original)
    for language in (Language.EN, Language.DE):
        assert "Confidential" not in _pages(language, tools=tools)
    english = _pages(tools=tools)
    assert "2 more duties the result lists are not in Klar's table of duties" in english
    assert "Applicant screening Checked under the original 2024 text" in english
    assert "Keep the logs it creates" not in english


def test_a_provider_that_also_deploys_keeps_its_deployer_duties() -> None:
    provider = SCREENING.model_copy(update={"role": Role.PROVIDER})
    assert "Keep the logs it creates" not in _pages(tools=(provider,))
    both = provider.model_copy(update={"also_role": Role.DEPLOYER})
    text = _pages(tools=(both,))
    assert "Keep the logs it creates for at least six months Art. 26(6)" in text
    assert "not in Klar's table" not in text
