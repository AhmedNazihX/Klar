"""The short deployer documents drafted from a result and the user's answers (P8a)."""

import logging
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
    DutyDateError,
    Provenance,
    deployer_templates_for,
    draft_deployer_documents,
    draft_document,
    run_checks,
)
from aiact.drafting.models import TEMPLATE_PATTERN
from aiact.drafting.prefill import Fill, NoClassError
from aiact.drafting.templates import (
    NO_STATED_FACTS,
    ClassificationSection,
    InterviewSection,
    TemplateSection,
)
from aiact.schemas import (
    DISCLAIMER,
    ClassificationResult,
    Language,
    LegacyStatus,
    Role,
    Status,
    StepName,
)
from tests.drafting.builders import WORKERS, WORKERS_ANSWERS, limited_risk_result
from tests.schemas.builders import (
    missing_fact,
    needs_description,
    rebuild,
    steps_with,
    stored_before_decision_030,
)
from tests.schemas.worked_example import EU_USE, worked_example_result


def _section(document: DraftDocument, key: str) -> tuple[str, ...]:
    return next(section.paragraphs for section in document.sections if section.key == key)


def _workers_notice(answers: dict[str, str], language: Language = Language.EN) -> DraftDocument:
    return draft_document(TEMPLATES[WORKERS], worked_example_result(), answers, language)


# --- Which documents a result calls for ----------------------------------------------------------


def test_high_risk_deployer_gets_the_three_art_26_documents() -> None:
    templates = deployer_templates_for(worked_example_result())
    assert [template.article for template in templates] == ["art:26:2", "art:26:7", "art:26:11"]


def test_a_deployer_gets_disclosure_texts_for_the_deployer_s_art_50_duties_only() -> None:
    result = limited_risk_result("art:50:1", "art:50:2", "art:50:3", "art:50:4")
    articles = [template.article for template in deployer_templates_for(result)]
    assert articles == ["art:50:3", "art:50:4"]


def test_a_provider_gets_no_deployer_documents() -> None:
    result = limited_risk_result("art:50:1", "art:50:2", "art:50:3", "art:50:4")
    provider = rebuild(result, role=Role.PROVIDER)
    assert deployer_templates_for(provider) == ()
    high_risk_provider = rebuild(worked_example_result(), role=Role.PROVIDER)
    assert deployer_templates_for(high_risk_provider) == ()


def test_a_provider_that_also_uses_the_system_gets_the_deployer_documents() -> None:
    result = rebuild(worked_example_result(), role=Role.PROVIDER, also_role=Role.DEPLOYER)
    assert [template.article for template in deployer_templates_for(result)] == [
        "art:26:2",
        "art:26:7",
        "art:26:11",
    ]


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
    assert len(documents) == 5
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


@pytest.mark.parametrize("blank", ["   ", "\ufeff", " \ufeff\x1c\x85\u3000 "])
def test_a_blank_answer_leaves_the_section_to_fill_in(blank: str) -> None:
    """Blank is `BLANK`'s space only, a byte order mark too, as the Documents screen counts it."""
    document = _workers_notice({"reviewer": blank})
    assert _section(document, "reviewer") == ()
    assert document.unanswered == 4


def test_an_answer_to_a_question_the_template_does_not_ask_is_left_out_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stale = {**WORKERS_ANSWERS, "works_council": "A stale answer, secret words"}
    with caplog.at_level(logging.WARNING, logger="aiact.drafting.draft"):
        document = _workers_notice(stale)
    assert document == _workers_notice(WORKERS_ANSWERS)
    assert caplog.messages == [f"{WORKERS}: left out 1 answers to questions it doesn't ask"]
    assert "secret" not in caplog.text
    assert "works_council" not in caplog.text


# --- Where each section's content comes from -----------------------------------------------------


def test_answers_are_written_in_word_for_word() -> None:
    document = _workers_notice({"reviewer": "  HR team lead, as named.\nAnd her deputy.  "})
    section = next(section for section in document.sections if section.key == "reviewer")
    assert section.paragraphs == ("HR team lead, as named.\nAnd her deputy.",)
    assert (section.provenance, section.question_keys) == (Provenance.INTERVIEW, ("reviewer",))


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


def test_a_duty_listed_with_several_dates_is_refused() -> None:
    result = worked_example_result()
    later = result.obligations[1].model_copy(update={"applies_from": date(2028, 8, 2)})
    assert later.article == "art:26:2"
    with pytest.raises(DutyDateError, match="art:26:2"):
        draft_document(
            TEMPLATES["art_26_2_oversight"],
            rebuild(result, obligations=(*result.obligations, later)),
            {},
            Language.EN,
        )


def test_without_stated_facts_the_system_section_says_so() -> None:
    result = rebuild(worked_example_result(), facts=(EU_USE,), deciding_facts=())
    for language in Language:
        document = draft_document(TEMPLATES[WORKERS], result, WORKERS_ANSWERS, language)
        section = next(section for section in document.sections if section.key == "system")
        assert section.provenance is Provenance.TEMPLATE
        assert section.paragraphs == (NO_STATED_FACTS[language],)
        assert document.status is DraftStatus.READY_TO_REVIEW


def test_a_disclosure_not_in_the_obligations_names_the_duty_without_a_date() -> None:
    document = draft_document(
        TEMPLATES["art_50_3_disclosure"], limited_risk_result("art:50:3"), {}, Language.EN
    )
    assert _section(document, "duty") == (
        "Your classification: limited risk.",
        "It lists the duty under Art. 50(3).",
    )
    assert _section(document, "notice") == ()


ART_50_3 = "art_50_3_disclosure"
NOTICES = {
    ("emotion_recognition", Language.EN): "An AI system for emotion recognition is in operation "
    "here.",
    ("emotion_recognition", Language.DE): "Hier ist ein KI-System zur Emotionserkennung in "
    "Betrieb.",
    ("biometric_categorisation", Language.EN): "An AI system for biometric categorisation is in "
    "operation here.",
    ("biometric_categorisation", Language.DE): "Hier ist ein KI-System zur biometrischen "
    "Kategorisierung in Betrieb.",
    ("both", Language.EN): "An AI system for emotion recognition and biometric categorisation is "
    "in operation here.",
    ("both", Language.DE): "Hier ist ein KI-System zur Emotionserkennung und biometrischen "
    "Kategorisierung in Betrieb.",
}
"""The Art. 50(3) notice for each choice: it names only what the system does."""


@pytest.mark.parametrize(("choice", "language"), list(NOTICES))
def test_the_art_50_3_notice_names_only_what_the_user_chose(
    choice: str, language: Language
) -> None:
    result = limited_risk_result("art:50:3")
    document = draft_document(TEMPLATES[ART_50_3], result, {"recognises": choice}, language)
    notice = next(section for section in document.sections if section.key == "notice")
    assert notice.paragraphs == (NOTICES[choice, language],)
    assert (notice.unanswered, notice.status.value) == ((), "drafted")
    assert all(check.passed for check in run_checks(document, result, {"recognises": choice}))


@pytest.mark.parametrize(
    "answer", ["", "\ufeff", "emotion recognition", "Both!", "BOTH", "both and more"]
)
def test_an_art_50_3_answer_that_names_no_choice_leaves_the_notice_to_fill_in(answer: str) -> None:
    result = limited_risk_result("art:50:3")
    document = draft_document(TEMPLATES[ART_50_3], result, {"recognises": answer}, Language.EN)
    notice = next(section for section in document.sections if section.key == "notice")
    assert (notice.paragraphs, notice.unanswered) == ((), ("recognises",))
    assert all(check.passed for check in run_checks(document, result, {"recognises": answer}))


def test_a_notice_that_names_another_choice_than_the_answer_fails_nothing_invented() -> None:
    result = limited_risk_result("art:50:3")
    document = draft_document(TEMPLATES[ART_50_3], result, {"recognises": "both"}, Language.EN)
    checks = run_checks(document, result, {"recognises": "emotion_recognition"})
    assert [check.check.value for check in checks if not check.passed] == ["nothing_invented"]


def test_the_art_50_3_choice_is_asked_in_both_languages() -> None:
    (question,) = [q for q in TEMPLATES[ART_50_3].questions if q.key == "recognises"]
    assert question.text == {
        Language.EN: "Does the system recognise emotions, sort people into categories from "
        "biometric data, or both?",
        Language.DE: "Erkennt das System Emotionen, ordnet es Personen anhand biometrischer Daten "
        "Kategorien zu oder beides?",
    }
    assert [(c.key, c.label[Language.EN], c.label[Language.DE]) for c in question.choices] == [
        ("emotion_recognition", "It recognises emotions", "Es erkennt Emotionen"),
        (
            "biometric_categorisation",
            "It sorts people into categories from biometric data",
            "Es ordnet Personen anhand biometrischer Daten Kategorien zu",
        ),
        ("both", "Both", "Beides"),
    ]


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
    question_keys = [question.key for question in template.questions]
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


def test_a_system_facts_section_needs_its_no_facts_line() -> None:
    with pytest.raises(ValueError, match="no facts were stated"):
        ClassificationSection("system", {Language.EN: "The system"}, Fill.SYSTEM_FACTS)


@pytest.mark.parametrize(
    "result",
    [needs_description(), stored_before_decision_030(worked_example_result())],
    ids=["needs_description", "check_not_assessed"],
)
def test_a_result_with_no_class_drafts_no_document(result: ClassificationResult) -> None:
    """A result with no class (E13), or with a check not assessed next to the class decision 029
    assumed, has no class sentence to state."""
    with pytest.raises(NoClassError):
        draft_document(TEMPLATES[WORKERS], result, {}, Language.EN)
