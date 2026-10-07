"""The screens' texts in the committed obligations table (story C9; decision 026): labels and formal
duties in both languages, the provider groups and the drafting templates the duties link to."""

from collections.abc import Mapping
from types import MappingProxyType

import pytest

from aiact.drafting.templates import DEPLOYER_TEMPLATES, TEMPLATES
from aiact.obligations.list import ObligationEntry, load_table
from aiact.schemas import ObligationGroup, Role

PROVIDER_SKELETONS: Mapping[str, str] = MappingProxyType(
    {
        "art_9_risk_management": "art:9",
        "annex_iv_technical_documentation": "art:11:1",
        "art_17_quality_management": "art:16:c",
        "art_27_fria": "art:27:1",
    }
)
"""The provider skeletons P8b adds, by the ids it gives them, and the article of the duty each
answers. Once they exist in TEMPLATES the tests below keep passing."""
DUTY_DOCUMENTS: Mapping[str, str] = MappingProxyType(
    {template.id: template.article for template in DEPLOYER_TEMPLATES} | dict(PROVIDER_SKELETONS)
)
"""Every document that answers one duty, with that duty's article."""
PLANNED_TEMPLATES = frozenset(TEMPLATES) | frozenset(PROVIDER_SKELETONS)
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


@pytest.mark.parametrize("entry", ENTRIES, ids=_id)
def test_labels_are_short_actions_and_duties_are_sentences(entry: ObligationEntry) -> None:
    for label in (entry.label_en, entry.label_de):
        assert len(label) <= MAX_LABEL_LENGTH
        assert not label.endswith(".")
    assert entry.duty_de.endswith(".")


def test_the_provider_layout_has_all_three_groups() -> None:
    groups = {row.obligation.group for row in ROWS if row.role is Role.PROVIDER}
    assert set(ObligationGroup) <= groups


def test_every_document_key_is_a_planned_drafting_template() -> None:
    """Re-run when P8b's skeletons exist: the keys must then be real templates or still planned."""
    documents = {entry.document for entry in ENTRIES if entry.document is not None}
    assert documents
    assert sorted(documents - PLANNED_TEMPLATES) == []


def test_each_duty_document_is_linked_from_the_one_duty_it_answers() -> None:
    """Every result that lists the duty can offer its draft (the Art. 9 skeleton on the Art. 9
    row, not a bundle of requirements)."""
    linked = {
        key: sorted(entry.article for entry in ENTRIES if entry.document == key)
        for key in DUTY_DOCUMENTS
    }
    assert linked == {key: [article] for key, article in DUTY_DOCUMENTS.items()}
