"""A drafted document laid out for Word and PDF (P9): the stamp, title, law text, note and
footer, and each section's content or its requirement and marker, in English and German."""

import pytest

from aiact.drafting import TEMPLATES, DraftDocument, SizeClass, draft_document
from aiact.drafting.paper import document_paper
from aiact.export import FillMarker, Heading, Note, Paragraph, Quote
from aiact.schemas import DISCLAIMER, Language
from tests.drafting.builders import WORKERS, WORKERS_ANSWERS, provider_result
from tests.schemas.worked_example import worked_example_result

EN, DE = Language.EN, Language.DE
ANNEX_IV = "annex_iv_technical_documentation"


def _annex_iv(language: Language, answers: dict[str, str] | None = None) -> DraftDocument:
    template = TEMPLATES[ANNEX_IV]
    return draft_document(template, provider_result(), answers or {}, language, SizeClass.SME)


@pytest.mark.parametrize(
    ("language", "stamp", "law_line", "footer"),
    [
        (
            EN,
            "DRAFT",
            "AI Act text: CELEX 02024R1689-20260727, as it applies on {date}.",
            "Draft prepared with Klar. ",
        ),
        (
            DE,
            "ENTWURF",
            "Text der KI-Verordnung: CELEX 02024R1689-20260727, in der am {date} geltenden "
            "Fassung.",
            "Entwurf erstellt mit Klar. ",
        ),
    ],
)
def test_the_paper_carries_the_stamp_title_law_text_and_notice(
    language: Language, stamp: str, law_line: str, footer: str
) -> None:
    document = _annex_iv(language)
    paper = document_paper(document)
    date = {EN: "27 September 2026", DE: "27. September 2026"}[language]
    assert document.as_of.isoformat() == "2026-09-27"
    assert (paper.stamp, paper.title, paper.language) == (stamp, document.title, language)
    assert paper.lines == (law_line.format(date=date),)
    assert paper.footer == footer + DISCLAIMER[language]
    assert paper.blocks[0] == Note(document.note or "")


def test_a_waiting_section_shows_its_requirement_and_its_marker() -> None:
    paper = document_paper(_annex_iv(EN))
    start = paper.blocks.index(Heading("Elements and development process"))
    quote, marker = paper.blocks[start + 1], paper.blocks[start + 2]
    assert isinstance(quote, Quote)
    assert quote.text.startswith("A detailed description of the elements of the AI system")
    assert quote.source == "Annex IV 2, Regulation (EU) 2024/1689, consolidated text"
    assert marker == FillMarker("To fill in.")


def test_a_german_waiting_section_quotes_the_german_text_and_marks_it_in_german() -> None:
    paper = document_paper(_annex_iv(DE))
    start = paper.blocks.index(Heading("Bestandteile und Entwicklungsprozess"))
    quote, marker = paper.blocks[start + 1], paper.blocks[start + 2]
    assert isinstance(quote, Quote)
    assert quote.source == "Anhang IV Nr. 2, Verordnung (EU) 2024/1689, konsolidierte Fassung"
    assert marker == FillMarker("Noch auszufüllen.")


def test_answers_stand_before_the_marker_until_every_question_is_answered() -> None:
    paper = document_paper(_annex_iv(EN, {"development_methods": "fine-tuned an open model"}))
    start = paper.blocks.index(Heading("Elements and development process"))
    assert paper.blocks[start + 1] == Paragraph("Fine-tuned an open model.")
    assert isinstance(paper.blocks[start + 2], Quote)


@pytest.mark.parametrize(
    ("key", "marker"),
    [
        ("standards", "To fill in: this section needs your evidence, such as test reports."),
        ("declaration_of_conformity", "To fill in last, once every other section is complete."),
    ],
)
def test_the_marker_says_what_the_section_waits_for(key: str, marker: str) -> None:
    document = _annex_iv(EN)
    section = next(section for section in document.sections if section.key == key)
    paper = document_paper(document)
    start = paper.blocks.index(Heading(section.heading))
    assert paper.blocks[start + 2] == FillMarker(marker)


def test_the_german_markers_for_evidence_and_the_declaration() -> None:
    blocks = document_paper(_annex_iv(DE)).blocks
    assert (
        FillMarker("Noch auszufüllen: Dieser Abschnitt braucht Ihre Nachweise, etwa Prüfberichte.")
        in blocks
    )
    assert FillMarker("Zuletzt auszufüllen, wenn alle anderen Abschnitte fertig sind.") in blocks


def test_a_drafted_section_has_no_marker_and_a_notice_quotes_nothing() -> None:
    template = TEMPLATES[WORKERS]
    document = draft_document(template, worked_example_result(), WORKERS_ANSWERS, EN)
    paper = document_paper(document)
    assert not any(isinstance(block, FillMarker | Quote | Note) for block in paper.blocks)
    assert Paragraph(WORKERS_ANSWERS["reviewer"]) in paper.blocks


def test_a_waiting_notice_section_is_marked_in_the_drafts_language() -> None:
    template = TEMPLATES[WORKERS]
    paper = document_paper(draft_document(template, worked_example_result(), {}, DE))
    assert FillMarker("Noch auszufüllen.") in paper.blocks
    assert not any(isinstance(block, Quote) for block in paper.blocks)
