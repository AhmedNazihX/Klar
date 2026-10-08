"""Every document a result calls for, with its interview, and one of them drafted and checked
(P9)."""

from collections.abc import Sequence
from datetime import date

import pytest

from aiact.drafting import SizeClass, UnknownPointError, draft_document
from aiact.drafting.documents import (
    DocumentNotCalledForError,
    InterviewChoice,
    InterviewQuestion,
    checked_draft,
    interview,
    listed_documents,
    templates_for,
)
from aiact.drafting.registry import TEMPLATES
from aiact.schemas import Citation, Language, LawVersion
from tests.drafting.builders import (
    WORKERS,
    WORKERS_ANSWERS,
    ambiguous_result,
    fria_deployer_result,
    limited_risk_result,
    provider_result,
)
from tests.drafting.vendor_builders import EMOTIONS_QUOTE, corpus_quotes, prohibited_result
from tests.schemas.worked_example import worked_example_result

EN, DE = Language.EN, Language.DE
ANNEX_IV = "annex_iv_technical_documentation"
MESSAGE = "vendor_message_prohibited"
LETTER_ANSWERS = {"vendor": "Rank GmbH", "tool_name": "MoodMeter", "sender": "Jana Berg"}


def no_corpus(
    provision_ids: Sequence[str], language: Language, law_version: LawVersion, as_of: date | None
) -> tuple[Citation, ...]:
    """A corpus no document but the vendor message may read."""
    raise AssertionError("only the vendor message reads the corpus")


def test_a_deployer_gets_the_short_documents_then_its_impact_assessment() -> None:
    assert [t.id for t in templates_for(fria_deployer_result())] == [
        "art_26_2_oversight",
        "art_26_7_workers",
        "art_26_11_affected",
        "art_27_fria",
    ]


def test_a_provider_gets_the_three_skeletons() -> None:
    assert [t.id for t in templates_for(provider_result())] == [
        ANNEX_IV,
        "art_17_quality_management",
        "art_9_risk_management",
    ]


def test_a_limited_risk_deployer_gets_its_disclosure_texts() -> None:
    result = limited_risk_result("art:50:1", "art:50:3", "art:50:4")
    assert [t.id for t in templates_for(result)] == ["art_50_3_disclosure", "art_50_4_disclosure"]


def test_a_prohibited_result_lists_the_vendor_message() -> None:
    assert [t.id for t in templates_for(prohibited_result())] == [MESSAGE]


def test_an_ambiguous_result_lists_the_vendor_request_after_its_other_documents() -> None:
    ids = [t.id for t in templates_for(ambiguous_result())]
    assert ids[-1] == "vendor_request_ambiguous"
    assert MESSAGE not in ids


def test_the_list_gives_each_document_s_title_duty_and_interview_in_its_language() -> None:
    listed = listed_documents(worked_example_result(), DE)
    assert [item.template for item in listed] == [
        t.id for t in templates_for(worked_example_result())
    ]
    workers = next(item for item in listed if item.template == WORKERS)
    assert (workers.title, workers.article) == (TEMPLATES[WORKERS].title[DE], "art:26:7")
    assert workers.questions == interview(TEMPLATES[WORKERS], DE)


def test_every_document_drafts_and_passes_its_checks_with_no_corpus_read() -> None:
    for result in (provider_result(), worked_example_result(), fria_deployer_result()):
        for template in templates_for(result):
            draft = checked_draft(template.id, result, {}, EN, SizeClass.SMC, no_corpus)
            assert all(check.passed for check in draft.checks), template.id
            assert [q.key for q in draft.questions] == [q.key for q in template.questions]


def test_the_size_class_reaches_the_note_and_its_check() -> None:
    draft = checked_draft(ANNEX_IV, provider_result(), {}, EN, SizeClass.SME, no_corpus)
    assert draft.document.note is not None
    assert all(check.passed for check in draft.checks)


def test_the_answers_fill_their_document() -> None:
    draft = checked_draft(WORKERS, worked_example_result(), WORKERS_ANSWERS, EN, None, no_corpus)
    assert draft.document.unanswered == 0
    assert all(check.passed for check in draft.checks)


def test_a_stale_answer_key_never_blocks_a_draft() -> None:
    answers = {**WORKERS_ANSWERS, "works_council": "Yes"}
    draft = checked_draft(WORKERS, worked_example_result(), answers, EN, None, no_corpus)
    assert draft.document.unanswered == 0
    assert all(check.passed for check in draft.checks)


@pytest.mark.parametrize("language", list(Language))
def test_the_vendor_message_quotes_the_corpus_and_passes_its_checks(language: Language) -> None:
    result = prohibited_result()
    draft = checked_draft(MESSAGE, result, LETTER_ANSWERS, language, None, corpus_quotes())
    quotes = [quote for section in draft.document.sections for quote in section.quotes]
    assert [quote.provision_id for quote in quotes] == ["art:5:1:f"]
    assert all(quote.language is language for quote in quotes)
    if language is EN:
        assert quotes[0].quote.startswith(EMOTIONS_QUOTE[:60])
    assert all(check.passed for check in draft.checks)


def test_a_vendor_message_on_a_point_the_corpus_lacks_is_refused() -> None:
    def missing(
        provision_ids: Sequence[str],
        language: Language,
        law_version: LawVersion,
        as_of: date | None,
    ) -> tuple[Citation, ...]:
        raise LookupError(provision_ids[0])

    with pytest.raises(UnknownPointError):
        checked_draft(MESSAGE, prohibited_result(), {}, EN, None, missing)


def test_the_draft_is_the_one_draft_document_makes() -> None:
    """One drafting path: the screen's draft and the exported file's are the same document."""
    answers = {"cybersecurity": "tested"}
    draft = checked_draft(ANNEX_IV, provider_result(), answers, DE, SizeClass.SME, no_corpus)
    expected = draft_document(TEMPLATES[ANNEX_IV], provider_result(), answers, DE, SizeClass.SME)
    assert draft.document == expected


def test_a_document_the_result_does_not_call_for_is_refused() -> None:
    with pytest.raises(DocumentNotCalledForError):
        checked_draft(WORKERS, provider_result(), {}, EN, None, no_corpus)
    with pytest.raises(DocumentNotCalledForError):
        checked_draft("no_such_template", provider_result(), {}, EN, None, no_corpus)


def test_the_interview_asks_each_question_with_its_section_in_the_drafts_language() -> None:
    assert [(q.key, q.section) for q in interview(TEMPLATES[WORKERS], EN)] == [
        ("recipients", "recipients"),
        ("tool_and_supplier", "tool"),
        ("start_date", "start"),
        ("reviewer", "reviewer"),
    ]
    tool = interview(TEMPLATES[WORKERS], DE)[1]
    assert tool == InterviewQuestion(
        key="tool_and_supplier", text="Wie heißt das Tool, und wer liefert es?", section="tool"
    )
    assert interview(TEMPLATES[WORKERS], EN)[1].text == (
        "What is the tool called, and who supplies it?"
    )


def test_a_choice_question_lists_its_choices_in_the_drafts_language() -> None:
    (asked, *_) = interview(TEMPLATES["art_50_3_disclosure"], DE)
    assert (asked.key, asked.section) == ("recognises", "notice")
    assert asked.choices == (
        InterviewChoice(key="emotion_recognition", label="Es erkennt Emotionen"),
        InterviewChoice(
            key="biometric_categorisation",
            label="Es ordnet Personen anhand biometrischer Daten Kategorien zu",
        ),
        InterviewChoice(key="both", label="Beides"),
    )
