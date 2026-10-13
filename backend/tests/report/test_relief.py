"""P31 (user decision 2026-10-13, D6): the reports show the obligations table's relief note under
a duty when the company profile is an SME or a small mid-cap, under the amended text only (the
notes name small mid-caps, which only the Omnibus added), and never a posted note."""

from datetime import date

import pytest

from aiact.export import Paper, Table
from aiact.obligations.list import list_obligations
from aiact.report import checklist_report, inventory_report, result_report
from aiact.report.checklist import ChecklistDuty, ChecklistTool
from aiact.report.inventory import InventoryDuty, InventoryTool
from aiact.schemas import (
    ClassificationResult,
    HighRiskRoute,
    Language,
    LawVersion,
    Obligation,
    RiskClass,
    Role,
    Status,
)
from tests.schemas.builders import rebuild
from tests.schemas.worked_example import worked_example_result

EN, DE = Language.EN, Language.DE
ON = date(2026, 10, 1)
QMS_EN = (
    "Have a documented quality management system (Art. 17). Relief for your company: The quality "
    "management system may be proportionate to the size of the organisation for SMEs, including "
    "start-ups, and SMCs (Art. 17(2)). SMEs without partner or linked enterprises may comply with "
    "certain elements in a simplified manner (Art. 63(1))."
)
QMS_DE = (
    "Über ein dokumentiertes Qualitätsmanagementsystem verfügen, das Art. 17 entspricht. "
    "Erleichterung für Ihr Unternehmen: Für KMU, einschließlich Start-up-Unternehmen, und kleine "
    "Midcap-Unternehmen kann das Qualitätsmanagementsystem in einem angemessenen Verhältnis zur "
    "Größe der Organisation stehen (Art. 17 Abs. 2). KMU ohne Partnerunternehmen oder verbundene "
    "Unternehmen können bestimmte Elemente in vereinfachter Weise einhalten (Art. 63 Abs. 1)."
)
QMS_LABEL_EN = "Set up a quality management system Relief for your company: The quality"


def _provider_duties() -> tuple[Obligation, ...]:
    return list_obligations(Role.PROVIDER, RiskClass.HIGH_RISK, HighRiskRoute.ANNEX_III).obligations


def _provider_result(law_version: LawVersion = LawVersion.AMENDED) -> ClassificationResult:
    return rebuild(
        worked_example_result(),
        role=Role.PROVIDER,
        status=Status.DECIDED,
        law_version=law_version,
        obligations=_provider_duties(),
    )


def _duty_rows(paper: Paper) -> list[str]:
    tables = [block for block in paper.blocks if isinstance(block, Table)]
    return [str(row[0]) for row in tables[-1].rows]


def _qms_row(paper: Paper) -> str:
    (row,) = [row for row in _duty_rows(paper) if row.startswith("Have a documented quality")]
    return row


@pytest.mark.parametrize(
    ("size_class", "language", "row"),
    [
        ("sme", EN, QMS_EN),
        ("smc", EN, QMS_EN),
        ("sme", DE, QMS_DE),
        ("smc", DE, QMS_DE),
    ],
)
def test_an_sme_or_a_small_mid_cap_sees_the_relief_under_the_duty(
    size_class: str, language: Language, row: str
) -> None:
    paper = result_report(
        _provider_result(), language=language, prepared_on=ON, size_class=size_class
    )
    rows = _duty_rows(paper)
    assert row in rows
    # Only the duties the table gives a relief note carry one.
    assert sum("Relief for your company" in r or "Erleichterung" in r for r in rows) == 2


@pytest.mark.parametrize("size_class", ["none", None])
def test_a_larger_company_or_no_profile_sees_no_relief(size_class: str | None) -> None:
    for language in (EN, DE):
        paper = result_report(
            _provider_result(), language=language, prepared_on=ON, size_class=size_class
        )
        assert not any("Relief" in r or "Erleichterung" in r for r in _duty_rows(paper))


def test_no_relief_under_the_original_text() -> None:
    """The notes name small mid-caps, which only the Omnibus added."""
    result = _provider_result(LawVersion.ORIGINAL)
    for language in (EN, DE):
        paper = result_report(result, language=language, prepared_on=ON, size_class="sme")
        assert not any("Relief" in r or "Erleichterung" in r for r in _duty_rows(paper))


def test_the_relief_is_the_tables_never_the_posted_one() -> None:
    result = _provider_result()
    forged = tuple(
        duty.model_copy(update={"relief_note": "No duties for you.", "relief_note_de": "Keine."})
        for duty in result.obligations
    )
    paper = result_report(
        rebuild(result, obligations=forged), language=EN, prepared_on=ON, size_class="sme"
    )
    assert _qms_row(paper) == QMS_EN
    assert not any("No duties for you" in r for r in _duty_rows(paper))


def _tool(duty_type: type[InventoryDuty], law_version: LawVersion) -> dict[str, object]:
    duties = tuple(
        duty_type(label=duty.label_en, article=duty.article, applies_from=duty.applies_from)
        for duty in _provider_duties()
        if duty.label_en is not None
    )
    return {
        "name": "Driver scoring",
        "risk_class": RiskClass.HIGH_RISK,
        "status": Status.DECIDED,
        "role": Role.PROVIDER,
        "law_version": law_version,
        "as_of": ON,
        "duties": duties,
    }


@pytest.mark.parametrize(
    ("size_class", "is_shown"), [("sme", True), ("smc", True), ("none", False)]
)
def test_the_inventory_report_labels_carry_the_relief(size_class: str, is_shown: bool) -> None:
    tool = InventoryTool.model_validate(_tool(InventoryDuty, LawVersion.AMENDED))
    paper = inventory_report((tool,), language=EN, prepared_on=ON, size_class=size_class)
    text = " ".join(
        " ".join(map(str, row)) for t in paper.blocks if isinstance(t, Table) for row in t.rows
    )
    assert (QMS_LABEL_EN in text) is is_shown


@pytest.mark.parametrize(
    ("shown", "language", "expected"),
    [
        (LawVersion.AMENDED, EN, "Relief for your company:"),
        (LawVersion.AMENDED, DE, "Erleichterung für Ihr Unternehmen:"),
        (LawVersion.ORIGINAL, EN, None),
    ],
)
def test_the_checklist_shows_the_relief_under_the_amended_text_only(
    shown: LawVersion, language: Language, expected: str | None
) -> None:
    tool = ChecklistTool.model_validate(_tool(ChecklistDuty, LawVersion.AMENDED))
    paper = checklist_report(
        (tool,), language=language, law_version=shown, prepared_on=ON, size_class="smc"
    )
    cells = [str(row[1]) for t in paper.blocks if isinstance(t, Table) for row in t.rows]
    relieved = [cell for cell in cells if "Relief" in cell or "Erleichterung" in cell]
    if expected is None:
        assert relieved == []
    else:
        assert len(relieved) == 2
        assert all(expected in cell for cell in relieved)
