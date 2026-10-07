"""The screens' texts in the committed obligations table (story C9; decision 026): labels and formal
duties in both languages, the provider groups and the drafting templates the duties link to."""

import pytest

from aiact.drafting.registry import TEMPLATES
from aiact.drafting.vendor_letters.templates import VENDOR_LETTER_TEMPLATES
from aiact.obligations.list import ObligationEntry, load_table
from aiact.schemas import ObligationGroup, Role

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


def test_every_document_key_is_a_drafting_template() -> None:
    documents = {entry.document for entry in ENTRIES if entry.document is not None}
    assert documents
    assert sorted(documents - set(TEMPLATES)) == []


def test_each_template_is_linked_from_the_one_duty_it_answers() -> None:
    """Every result that lists the duty can offer its draft: the duty is the one the template
    answers (`DocumentTemplate.article`), e.g. the Art. 9 skeleton on the Art. 9 row. The vendor
    letters answer no duty: a prohibited or ambiguous result offers them (P28), and no row links
    them."""
    letters = {template.id for template in VENDOR_LETTER_TEMPLATES}
    duty_templates = {key: t for key, t in TEMPLATES.items() if key not in letters}
    linked = {
        key: sorted(entry.article for entry in ENTRIES if entry.document == key)
        for key in TEMPLATES
    }
    assert linked == {
        **{key: [template.article] for key, template in duty_templates.items()},
        **{key: [] for key in letters},
    }
