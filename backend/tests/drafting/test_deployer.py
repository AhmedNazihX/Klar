"""The short deployer documents drafted from a result and the user's answers (P8a)."""

import re
from datetime import date

import pytest
from pydantic import ValidationError

from aiact.drafting import (
    DEPLOYER_TEMPLATES,
    TEMPLATES,
    DocumentTemplate,
    DraftDocument,
    DraftStatus,
    Provenance,
    UnknownQuestionError,
    deployer_templates_for,
    draft_deployer_documents,
    draft_document,
)
from aiact.drafting.models import TEMPLATE_PATTERN
from aiact.drafting.templates import InterviewSection, TemplateSection
from aiact.schemas import (
    DISCLAIMER,
    HighRiskRoute,
    Language,
    LegacyStatus,
    Obligation,
    Status,
    StepName,
)
from tests.drafting.builders import WORKERS, WORKERS_ANSWERS, limited_risk_result
from tests.schemas.builders import missing_fact, rebuild, steps_with
from tests.schemas.worked_example import worked_example_result


def _section(document: DraftDocument, key: str) -> tuple[str, ...]:
    return next(section.paragraphs for section in document.sections if section.key == key)


def _workers_notice(answers: dict[str, str], language: Language = Language.EN) -> DraftDocument:
    return draft_document(TEMPLATES[WORKERS], worked_example_result(), answers, language)


# --- Which documents a result calls for ----------------------------------------------------------


def test_high_risk_deployer_gets_the_three_art_26_documents() -> None:
    templates = deployer_templates_for(worked_example_result())
    assert [template.article for template in templates] == ["art:26:2", "art:26:7", "art:26:11"]


def test_art_50_duties_get_a_disclosure_text_except_marking() -> None:
    result = limited_risk_result("art:50:1", "art:50:2", "art:50:3", "art:50:4")
    articles = [template.article for template in deployer_templates_for(result)]
    assert articles == ["art:50:1", "art:50:3", "art:50:4"]


def test_a_result_without_deployer_duties_gets_no_documents() -> None:
    result = rebuild(worked_example_result(), obligations=())
    assert draft_deployer_documents(result, {}, Language.EN) == ()


def test_answers_go_to_their_own_template_only() -> None:
    documents = draft_deployer_documents(
        worked_example_result(), {WORKERS: WORKERS_ANSWERS}, Language.EN
    )
    by_template = {document.template: document for document in documents}
    assert by_template[WORKERS].status is DraftStatus.READY_TO_REVIEW
    assert by_template["art_26_11_affected"].unanswered == 3


# --- DRAFT label, notice and status --------------------------------------------------------------


@pytest.mark.parametrize("language", list(Language))
def test_every_draft_is_labelled_draft_with_the_notice(language: Language) -> None:
    result = limited_risk_result("art:50:1", "art:50:3", "art:50:4")
    documents = draft_deployer_documents(worked_example_result(), {}, language)
    documents += draft_deployer_documents(result, {}, language)
    assert len(documents) == 6
    for document in documents:
        assert document.label == "DRAFT"
        assert document.disclaimer == DISCLAIMER[language]
        assert (document.law_version, document.as_of) == (result.law_version, result.as_of)


def test_unanswered_questions_make_the_status_needs_answers() -> None:
    document = _workers_notice({"reviewer": WORKERS_ANSWERS["reviewer"]})
    assert (document.status, document.unanswered) == (DraftStatus.NEEDS_ANSWERS, 3)


def test_all_questions_answered_make_it_ready_to_review() -> None:
    document = _workers_notice(WORKERS_ANSWERS)
    assert (document.status, document.unanswered) == (DraftStatus.READY_TO_REVIEW, 0)


def test_a_blank_answer_leaves_the_section_to_fill_in() -> None:
    document = _workers_notice({"reviewer": "   "})
    assert _section(document, "reviewer") == ()
    assert document.unanswered == 4


def test_an_answer_to_a_question_the_template_does_not_ask_is_rejected() -> None:
    with pytest.raises(UnknownQuestionError, match="works_council"):
        _workers_notice({"works_council": "Yes"})


# --- Where each section's content comes from -----------------------------------------------------


def test_answers_are_written_in_word_for_word() -> None:
    document = _workers_notice({"reviewer": "  HR team lead, as named.\nAnd her deputy.  "})
    section = next(section for section in document.sections if section.key == "reviewer")
    assert section.paragraphs == ("HR team lead, as named.\nAnd her deputy.",)
    assert (section.provenance, section.question_key) == (Provenance.INTERVIEW, "reviewer")


def test_prefilled_facts_are_only_the_ones_the_user_stated() -> None:
    document = _workers_notice({})
    assert _section(document, "system") == (
        "The company uses a tool bought from a vendor",
        "The tool scores and ranks applicants",
        "The tool was not modified",
    )
    section = next(section for section in document.sections if section.key == "system")
    assert section.provenance is Provenance.CLASSIFICATION


def test_the_duty_section_names_the_class_annex_point_and_date() -> None:
    assert _section(_workers_notice({}), "duty") == (
        "Your classification: high-risk, Annex III point 4(a).",
        "It lists the duty under Art. 26(7), which applies from 2 December 2027.",
    )
    assert _section(_workers_notice({}, Language.DE), "duty") == (
        "Ihre Einstufung: Hochrisiko, Anhang III Nummer 4 Buchstabe a.",
        "Sie nennt die Pflicht nach Art. 26 Abs. 7, die ab dem 2. Dezember 2027 gilt.",
    )


def test_an_uncertain_class_is_drafted_as_assumed() -> None:
    step = missing_fact(StepName.HIGH_RISK)
    result = rebuild(
        worked_example_result(), status=Status.NEEDS_MORE_INFORMATION, steps=steps_with(step)
    )
    document = draft_document(TEMPLATES[WORKERS], result, {}, Language.EN)
    assert _section(document, "duty")[0] == (
        "Your classification: high-risk, Annex III point 4(a), assumed until you answer its "
        "open question."
    )


def test_a_legacy_duty_applies_only_after_a_significant_change() -> None:
    result = worked_example_result()
    obligations = tuple(
        item.model_copy(update={"legacy": LegacyStatus.UNCHANGED}) for item in result.obligations
    )
    document = draft_document(
        TEMPLATES[WORKERS], rebuild(result, obligations=obligations), {}, Language.EN
    )
    assert _section(document, "duty")[1] == (
        "It lists the duty under Art. 26(7), which applies only after a significant change to "
        "the system (Art. 111(2))."
    )


def test_the_date_follows_the_result_s_route() -> None:
    def oversight(route: HighRiskRoute, day: date) -> Obligation:
        return Obligation(
            duty="Assign human oversight",
            article="art:26:2",
            applies_from=day,
            high_risk_route=route,
        )

    both_routes = (
        oversight(HighRiskRoute.ANNEX_I, date(2028, 8, 2)),
        oversight(HighRiskRoute.ANNEX_III, date(2027, 12, 2)),
    )
    result = rebuild(worked_example_result(), obligations=both_routes)
    document = draft_document(TEMPLATES["art_26_2_oversight"], result, {}, Language.EN)
    assert _section(document, "duty")[1].endswith("applies from 2 December 2027.")


def test_a_disclosure_not_in_the_obligations_names_the_duty_without_a_date() -> None:
    document = draft_document(
        TEMPLATES["art_50_1_disclosure"], limited_risk_result("art:50:1"), {}, Language.EN
    )
    assert _section(document, "duty") == (
        "Your classification: limited risk.",
        "It lists the duty under Art. 50(1).",
    )
    assert _section(document, "notice") == ("You are interacting with an AI system.",)


# --- The draft's own rules -----------------------------------------------------------------------


def test_a_draft_with_another_language_s_notice_is_rejected() -> None:
    dump = _workers_notice({}).model_dump()
    with pytest.raises(ValidationError, match="disclaimer"):
        DraftDocument.model_validate({**dump, "disclaimer": DISCLAIMER[Language.DE]})


def test_a_draft_whose_status_ignores_its_sections_is_rejected() -> None:
    dump = _workers_notice({}).model_dump()
    with pytest.raises(ValidationError, match="unanswered"):
        DraftDocument.model_validate({**dump, "unanswered": 0})
    with pytest.raises(ValidationError, match="needs_answers"):
        DraftDocument.model_validate({**dump, "status": DraftStatus.READY_TO_REVIEW})


def test_a_draft_cannot_drop_its_draft_label() -> None:
    dump = _workers_notice({}).model_dump()
    with pytest.raises(ValidationError, match="label"):
        DraftDocument.model_validate({**dump, "label": "FINAL"})


# --- The templates themselves --------------------------------------------------------------------


@pytest.mark.parametrize("template", DEPLOYER_TEMPLATES, ids=lambda template: template.id)
def test_every_template_is_complete_in_both_languages(template: DocumentTemplate) -> None:
    assert TEMPLATES[template.id] is template
    assert re.fullmatch(TEMPLATE_PATTERN, template.id)
    keys = [spec.key for spec in template.sections]
    question_keys = [question.question_key for question in template.questions]
    assert len(set(keys)) == len(keys)
    assert len(set(question_keys)) == len(question_keys)
    for language in Language:
        assert template.title[language]
        for spec in template.sections:
            assert spec.heading[language]
            if isinstance(spec, TemplateSection):
                assert spec.text[language]
            if isinstance(spec, InterviewSection):
                assert spec.question[language]
