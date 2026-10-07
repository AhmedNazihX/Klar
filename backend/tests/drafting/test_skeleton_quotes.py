"""Every skeleton has a section for each requirement its provision lists, and quotes it word for
word from the corpus, as `get_provision` and the citation validator read it (P8b).

The corpus is built from the committed `data/parsed/` (`tests/engine/built_corpus.py`), so this
runs without a database.
"""

import pytest

from aiact.corpus.eurlex import load_jsonl
from aiact.drafting import SKELETON_TEMPLATES, DocumentTemplate, draft_skeletons
from aiact.drafting.skeletons import (
    ANNEX_IV_SKELETON,
    ART_9_SKELETON,
    ART_17_SKELETON,
    ART_27_SKELETON,
)
from aiact.drafting.skeletons.quotes import QUOTES
from aiact.drafting.templates import RequirementSection
from aiact.engine.nodes.common import provision_citation
from aiact.schemas import LAW_TEXTS, Citation, Language, LawVersion
from aiact.settings import get_settings
from tests.drafting.builders import fria_deployer_result, provider_result
from tests.engine.built_corpus import built_corpus, omnibus_changes
from tests.schemas.worked_example import HIGH_RISK_DUTIES_FROM, worked_example_result

AMENDED = LAW_TEXTS[LawVersion.AMENDED]
AS_OF = worked_example_result().as_of
DATES = (AS_OF, HIGH_RISK_DUTIES_FROM)
"""The result's date, and the day the duties the skeletons answer apply from."""

ART_9_PARAGRAPHS_WITHOUT_SECTION = {"art:9:3", "art:9:4", "art:9:7", "art:9:10"}
"""Art. 9 paragraphs that limit or permit rather than require something to describe."""


def _children(parent: str) -> list[str]:
    """The units directly under `parent` in the consolidated text, in the Act's order."""
    path = get_settings().aiact_data_dir / "parsed" / f"{AMENDED.document_id}.en.jsonl"
    return [row.provision_id for row in load_jsonl(path) if row.parent_id == parent]


def _quoted(template: DocumentTemplate) -> list[str]:
    return [
        spec.requirement.provision_id
        for spec in template.sections
        if isinstance(spec, RequirementSection)
    ]


def _requirements() -> list[tuple[str, RequirementSection]]:
    return [
        (template.id, spec)
        for template in SKELETON_TEMPLATES
        for spec in template.sections
        if isinstance(spec, RequirementSection)
    ]


# --- Every required section is present -----------------------------------------------------------


def test_annex_iv_has_a_section_for_each_of_its_points() -> None:
    points = _children("annex:IV")
    assert points == [f"annex:IV:{number}" for number in range(1, 10)]
    assert _quoted(ANNEX_IV_SKELETON) == points


def test_art_17_has_a_section_for_each_aspect_of_paragraph_1() -> None:
    points = _children("art:17:1")
    assert len(points) == 13  # (a) to (m)
    assert _quoted(ART_17_SKELETON) == points


def test_art_27_has_a_section_for_each_element_of_the_assessment() -> None:
    points = _children("art:27:1")
    assert len(points) == 6  # (a) to (f)
    assert _quoted(ART_27_SKELETON) == points


def test_art_9_has_a_section_for_each_step_and_each_paragraph_that_requires_one() -> None:
    paragraphs = [p for p in _children("art:9") if p not in ART_9_PARAGRAPHS_WITHOUT_SECTION]
    steps = _children("art:9:2")
    assert len(steps) == 4  # (a) to (d)
    expected = [
        p for paragraph in paragraphs for p in (steps if paragraph == "art:9:2" else [paragraph])
    ]
    assert _quoted(ART_9_SKELETON) == expected


@pytest.mark.parametrize("language", list(Language))
def test_every_drafted_skeleton_shows_every_requirement_quoted(language: Language) -> None:
    results = (provider_result(), fria_deployer_result())
    documents = [doc for result in results for doc in draft_skeletons(result, {}, language, None)]
    assert [doc.template for doc in documents] == [t.id for t in SKELETON_TEMPLATES]
    for document, template in zip(documents, SKELETON_TEMPLATES, strict=True):
        quoted = [s.requirement.provision_id for s in document.sections if s.requirement]
        assert quoted == _quoted(template)
        assert all(s.requirement.language is language for s in document.sections if s.requirement)


# --- Quoted word for word ------------------------------------------------------------------------


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize(
    ("template_id", "spec"), _requirements(), ids=lambda item: getattr(item, "key", item)
)
def test_each_requirement_is_quoted_word_for_word_from_the_amended_text(
    template_id: str, spec: RequirementSection, language: Language
) -> None:
    for as_of in DATES:
        provision = built_corpus().provision(
            spec.requirement.provision_id, language, LawVersion.AMENDED, as_of
        )
        expected: Citation = provision_citation(provision).model_copy(
            update={"changed_by_omnibus": omnibus_changes().marks(provision)}
        )
        assert not provision.english_only, "the official German text exists"
        assert spec.requirement.citation(language) == expected, (
            f"{template_id}: regenerate QUOTES[{spec.requirement.provision_id!r}][{language}] "
            "from data/parsed (see aiact/drafting/skeletons/quotes.py)"
        )


def test_every_quote_is_used_by_exactly_one_section() -> None:
    used = [spec.requirement.provision_id for _, spec in _requirements()]
    assert sorted(used) == sorted(QUOTES)
