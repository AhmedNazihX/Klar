"""The screens' texts in the committed obligations table (story C9; decision 026): labels and formal
duties in both languages, the provider groups and the drafting templates the duties link to."""

from collections import Counter

import pytest

from aiact.drafting.templates import DEPLOYER_TEMPLATES, TEMPLATES, DocumentTemplate
from aiact.obligations.list import ObligationEntry, load_table
from aiact.schemas import ObligationGroup, RiskClass, Role

PROVIDER_SKELETONS = frozenset(
    {
        "annex_iv_technical_documentation",
        "art_9_risk_management",
        "art_17_quality_management",
        "art_27_fria",
    }
)
"""The provider skeletons P8b adds, by the ids it gives them. Once they exist in TEMPLATES this set
is redundant, and the tests below keep passing."""
PLANNED_TEMPLATES = frozenset(TEMPLATES) | PROVIDER_SKELETONS
"""Every drafting template key a duty may link to: P8a's deployer documents and P8b's skeletons."""

MAX_LABEL_LENGTH = 90
"""The longest label the checklists show on one or two lines (German runs about 30% longer)."""

ENTRIES = load_table().obligations
ROWS = load_table().rows()


def _id(entry: ObligationEntry) -> str:
    return entry.key


@pytest.mark.parametrize("entry", ENTRIES, ids=_id)
def test_every_entry_has_both_labels_and_both_duties(entry: ObligationEntry) -> None:
    texts = (entry.label_en, entry.label_de, entry.duty, entry.duty_de)
    assert all(text.strip() == text and text for text in texts)
    assert entry.label_en != entry.label_de
    assert entry.duty != entry.duty_de


def test_every_row_carries_both_labels_and_both_duties() -> None:
    assert ROWS
    for row in ROWS:
        obligation = row.obligation
        assert obligation.label_en and obligation.label_de, row.key
        assert obligation.duty and obligation.duty_de, row.key


@pytest.mark.parametrize("entry", ENTRIES, ids=_id)
def test_labels_are_short_actions_and_duties_are_sentences(entry: ObligationEntry) -> None:
    for label in (entry.label_en, entry.label_de):
        assert len(label) <= MAX_LABEL_LENGTH
        assert not label.endswith(".")
    assert entry.duty_de.endswith(".")


def test_every_provider_high_risk_row_has_a_group() -> None:
    provider_high_risk = [
        row for row in ROWS if row.role is Role.PROVIDER and row.risk_class is RiskClass.HIGH_RISK
    ]
    assert provider_high_risk
    assert [row.key for row in provider_high_risk if row.obligation.group is None] == []


def test_only_duties_a_provider_has_carry_a_group() -> None:
    provider_keys = {row.key for row in ROWS if row.role is Role.PROVIDER}
    assert [row.key for row in ROWS if row.obligation.group and row.key not in provider_keys] == []


def test_the_provider_layout_has_all_three_groups() -> None:
    groups = {row.obligation.group for row in ROWS if row.role is Role.PROVIDER}
    assert set(ObligationGroup) <= groups


def test_every_document_key_is_a_planned_drafting_template() -> None:
    """Re-run when P8b's skeletons exist: the keys must then be real templates or still planned."""
    documents = {entry.document for entry in ENTRIES if entry.document is not None}
    assert documents
    assert sorted(documents - PLANNED_TEMPLATES) == []


def test_every_duty_document_is_linked_from_exactly_one_duty() -> None:
    """Each deployer document and provider skeleton answers one duty, so every result that lists
    the duty can offer its draft."""
    duty_documents = {template.id for template in DEPLOYER_TEMPLATES} | PROVIDER_SKELETONS
    links = Counter(entry.document for entry in ENTRIES if entry.document is not None)
    assert {key: links[key] for key in duty_documents} == dict.fromkeys(duty_documents, 1)


@pytest.mark.parametrize("template", DEPLOYER_TEMPLATES, ids=lambda template: template.id)
def test_a_deployer_document_is_linked_from_the_duty_it_answers(
    template: DocumentTemplate,
) -> None:
    linked = [entry for entry in ENTRIES if entry.document == template.id]
    assert [entry.article for entry in linked] == [template.article]
