"""Every document a result calls for, drafted, checked and with its interview (P9)."""

import pytest

from aiact.drafting import SizeClass
from aiact.drafting.documents import (
    DocumentNotCalledForError,
    InterviewQuestion,
    checked_draft,
    checked_drafts,
    interview,
    templates_for,
)
from aiact.drafting.registry import TEMPLATES
from aiact.schemas import Language
from tests.drafting.builders import (
    WORKERS,
    WORKERS_ANSWERS,
    fria_deployer_result,
    limited_risk_result,
    provider_result,
)
from tests.schemas.worked_example import worked_example_result

EN, DE = Language.EN, Language.DE
ANNEX_IV = "annex_iv_technical_documentation"


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


def test_every_draft_passes_its_checks_and_lists_its_interview() -> None:
    drafts = checked_drafts(provider_result(), {}, EN, SizeClass.SMC)
    assert [draft.document.template for draft in drafts] == [
        t.id for t in templates_for(provider_result())
    ]
    for draft in drafts:
        assert all(check.passed for check in draft.checks)
        template = TEMPLATES[draft.document.template]
        assert [q.key for q in draft.questions] == [q.key for q in template.questions]
    assert drafts[0].document.note is not None, "the size class reaches the Annex IV note"


def test_answers_reach_their_own_document_only() -> None:
    answers = {WORKERS: WORKERS_ANSWERS, "art_26_2_oversight": {"tool_and_supplier": "TalentRank."}}
    drafts = {
        d.document.template: d for d in checked_drafts(worked_example_result(), answers, EN, None)
    }
    assert drafts[WORKERS].document.unanswered == 0
    assert drafts["art_26_11_affected"].document.unanswered > 0
    assert all(check.passed for draft in drafts.values() for check in draft.checks)


def test_a_stale_answer_key_or_template_never_blocks_a_draft() -> None:
    answers = {
        WORKERS: {**WORKERS_ANSWERS, "works_council": "Yes"},
        "annex_iv_technical_documentation": {"anything": "kept for a later run"},
        "retired_template": {"x": "y"},
    }
    drafts = checked_drafts(worked_example_result(), answers, EN, None)
    workers = next(d for d in drafts if d.document.template == WORKERS)
    assert workers.document.unanswered == 0
    assert all(check.passed for check in workers.checks)


def test_one_document_is_drafted_as_the_list_drafts_it() -> None:
    listed = checked_drafts(
        provider_result(), {ANNEX_IV: {"cybersecurity": "tested"}}, DE, SizeClass.SME
    )
    one = checked_draft(ANNEX_IV, provider_result(), {"cybersecurity": "tested"}, DE, SizeClass.SME)
    assert one == listed[0]


def test_a_document_the_result_does_not_call_for_is_refused() -> None:
    with pytest.raises(DocumentNotCalledForError):
        checked_draft(WORKERS, provider_result(), {}, EN, None)
    with pytest.raises(DocumentNotCalledForError):
        checked_draft("no_such_template", provider_result(), {}, EN, None)


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
