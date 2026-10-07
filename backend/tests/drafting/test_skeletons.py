"""The provider document skeletons (P8b): which a result calls for, the simplified-form note,
the sections' statuses and answers, and the three automatic checks on a skeleton."""

import re

import pytest
from pydantic import ValidationError

from aiact.drafting import (
    SKELETON_TEMPLATES,
    TEMPLATES,
    DocumentTemplate,
    DraftDocument,
    DraftStatus,
    Provenance,
    SectionStatus,
    SizeClass,
    check_nothing_invented,
    check_sections_present,
    draft_document,
    draft_skeletons,
    run_checks,
    skeleton_templates_for,
)
from aiact.drafting.models import TEMPLATE_PATTERN, DraftSection
from aiact.drafting.skeletons import ANNEX_IV_SKELETON, ART_9_SKELETON, ART_17_SKELETON
from aiact.drafting.templates import Question, RequirementSection
from aiact.schemas import Language, Role
from tests.drafting.builders import (
    changed,
    edit_section,
    fria_deployer_result,
    provider_result,
    with_sections,
)
from tests.schemas.builders import rebuild
from tests.schemas.worked_example import worked_example_result

EN, DE = Language.EN, Language.DE
NOTE = {
    EN: "A simplified form for SMEs and small mid-caps is expected (Art. 11(1)). Until the "
    "Commission publishes it, this is the full Annex IV.",
    DE: "Ein vereinfachtes Formular für KMU und kleine Midcap-Unternehmen wird erwartet "
    "(Art. 11 Abs. 1). Bis die Kommission es veröffentlicht, ist dies der vollständige "
    "Anhang IV.",
}
"""The note as decision 026 (item 21) words it, and its German."""

C9_DOCUMENT_KEYS = [
    "annex_iv_technical_documentation",
    "art_17_quality_management",
    "art_9_risk_management",
    "art_27_fria",
]
"""The template ids the obligations seed's `document` keys name (C9)."""

DEVELOPMENT_ANSWERS = {
    "development_methods": "Fine-tuned an open model on our own CVs.",
    "cybersecurity": "  Access control and yearly penetration tests.  ",
}


def _annex_iv(
    size_class: SizeClass | None = None, answers: dict[str, str] | None = None
) -> DraftDocument:
    return draft_document(
        ANNEX_IV_SKELETON, provider_result(), answers or {}, Language.EN, size_class
    )


def _section(document: DraftDocument, key: str) -> DraftSection:
    return next(section for section in document.sections if section.key == key)


# --- Which skeletons a result calls for ----------------------------------------------------------


def test_the_skeleton_ids_are_the_obligations_seed_s_document_keys() -> None:
    assert [template.id for template in SKELETON_TEMPLATES] == C9_DOCUMENT_KEYS
    assert all(TEMPLATES[key].id == key for key in C9_DOCUMENT_KEYS)


def test_a_high_risk_provider_gets_annex_iv_art_17_and_art_9() -> None:
    templates = skeleton_templates_for(provider_result())
    assert [template.id for template in templates] == C9_DOCUMENT_KEYS[:3]


def test_a_deployer_with_the_impact_assessment_duty_gets_the_art_27_skeleton() -> None:
    assert [t.id for t in skeleton_templates_for(fria_deployer_result())] == ["art_27_fria"]


def test_a_result_without_those_duties_gets_no_skeleton() -> None:
    assert skeleton_templates_for(worked_example_result()) == ()
    assert draft_skeletons(rebuild(provider_result(), obligations=()), {}, EN, None) == ()


# --- The simplified-form note --------------------------------------------------------------------


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize("size_class", [SizeClass.SME, SizeClass.SMC])
def test_an_sme_or_small_mid_cap_gets_the_simplified_form_note(
    size_class: SizeClass, language: Language
) -> None:
    documents = draft_skeletons(provider_result(), {}, language, size_class)
    notes = {document.template: document.note for document in documents}
    assert notes == {
        "annex_iv_technical_documentation": NOTE[language],
        "art_17_quality_management": None,
        "art_9_risk_management": None,
    }


@pytest.mark.parametrize("size_class", [SizeClass.NONE, None], ids=["neither", "no profile"])
def test_neither_size_class_nor_no_profile_gets_the_note(size_class: SizeClass | None) -> None:
    for language in Language:
        documents = draft_skeletons(provider_result(), {}, language, size_class)
        assert [document.note for document in documents] == [None, None, None]


def test_an_sme_still_gets_every_annex_iv_section() -> None:
    sme, neither = _annex_iv(SizeClass.SME), _annex_iv(SizeClass.NONE)
    assert [s.key for s in sme.sections] == [s.key for s in neither.sections]


# --- Sections, statuses and answers --------------------------------------------------------------


def test_an_unanswered_section_quotes_its_requirement_and_waits_for_its_questions() -> None:
    document = _annex_iv()
    development = _section(document, "development")
    assert development.paragraphs == ()
    assert development.requirement is not None
    assert development.requirement.provision_id == "annex:IV:2"
    assert development.status is SectionStatus.QUESTIONS
    assert development.unanswered == development.question_keys
    assert len(development.question_keys) == 8  # one per point (a) to (h)


def test_each_section_shows_what_it_waits_for() -> None:
    statuses = {section.key: section.status for section in _annex_iv().sections}
    assert statuses == {
        "system": SectionStatus.DRAFTED,
        "duty": SectionStatus.DRAFTED,
        "general_description": SectionStatus.QUESTIONS,
        "development": SectionStatus.QUESTIONS,
        "monitoring": SectionStatus.QUESTIONS,
        "performance_metrics": SectionStatus.QUESTIONS,
        "risk_management": SectionStatus.TO_FILL_IN,
        "lifecycle_changes": SectionStatus.TO_FILL_IN,
        "standards": SectionStatus.NEEDS_EVIDENCE,
        "declaration_of_conformity": SectionStatus.GENERATED_LAST,
        "post_market_monitoring": SectionStatus.TO_FILL_IN,
    }


def test_answers_fill_a_section_word_for_word_in_the_order_asked() -> None:
    development = _section(_annex_iv(answers=DEVELOPMENT_ANSWERS), "development")
    assert development.paragraphs == (
        "Fine-tuned an open model on our own CVs.",
        "Access control and yearly penetration tests.",
    )
    assert development.provenance is Provenance.INTERVIEW
    assert len(development.unanswered) == 6
    assert "cybersecurity" not in development.unanswered
    assert development.status is SectionStatus.QUESTIONS


def test_a_fully_answered_section_is_drafted() -> None:
    answers = {"metrics_appropriateness": "Recall per group, as the users rank candidates."}
    section = _section(_annex_iv(answers=answers), "performance_metrics")
    assert (section.status, section.unanswered) == (SectionStatus.DRAFTED, ())
    assert section.requirement is not None, "the quote stays with a filled section"


def test_the_document_counts_its_unanswered_questions() -> None:
    fresh = _annex_iv()
    assert (fresh.status, fresh.unanswered) == (DraftStatus.NEEDS_ANSWERS, 26)
    answered = _annex_iv(answers=DEVELOPMENT_ANSWERS)
    assert answered.unanswered == 24
    every = {question.key: "Answered." for question in ANNEX_IV_SKELETON.questions}
    assert _annex_iv(answers=every).status is DraftStatus.READY_TO_REVIEW


def test_the_prefilled_sections_name_the_skeleton_s_duty() -> None:
    document = draft_document(ART_9_SKELETON, provider_result(), {}, DE)
    duty = _section(document, "duty")
    assert duty.provenance is Provenance.CLASSIFICATION
    assert (
        duty.paragraphs[1]
        == "Sie nennt die Pflicht nach Art. 16 Buchst. a, die ab dem 2. Dezember 2027 gilt."
    )


def test_a_skeleton_in_german_quotes_the_official_german_text() -> None:
    document = draft_document(ART_17_SKELETON, provider_result(), {}, DE)
    requirement = _section(document, "accountability").requirement
    assert requirement is not None
    assert requirement.language is DE
    assert requirement.quote.startswith("einen Rechenschaftsrahmen")


# --- The automatic checks on a skeleton ----------------------------------------------------------


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize("size_class", [*SizeClass, None])
def test_every_fresh_skeleton_passes_all_three_checks(
    language: Language, size_class: SizeClass | None
) -> None:
    for result in (provider_result(), fria_deployer_result()):
        answers = {template.id: _some_answers(template) for template in SKELETON_TEMPLATES}
        for document in draft_skeletons(result, answers, language, size_class):
            outcomes = run_checks(document, result, answers[document.template])
            assert all(outcome.passed for outcome in outcomes), outcomes


def _some_answers(template: DocumentTemplate) -> dict[str, str]:
    """Every other question of `template` answered."""
    return {question.key: f"Answer {n}." for n, question in enumerate(template.questions[::2])}


def test_a_dropped_requirement_section_fails_the_sections_check() -> None:
    document = _annex_iv()
    dropped = with_sections(document, tuple(s for s in document.sections if s.key != "standards"))
    outcome = check_sections_present(dropped)
    assert not outcome.passed
    assert "missing section 'standards'" in outcome.problems


def test_a_reworded_quote_fails_the_invented_content_check() -> None:
    def reword(section: DraftSection) -> DraftSection:
        assert section.requirement is not None
        quote = section.requirement.quote.replace("cybersecurity", "basic security")
        requirement = section.requirement.model_copy(update={"quote": quote})
        return changed(section, requirement=requirement.model_dump())

    document = edit_section(_annex_iv(), "development", reword)
    outcome = check_nothing_invented(document, provider_result(), {})
    assert outcome.problems == ("section 'development' quotes a requirement the template doesn't",)


def test_a_quote_added_to_a_prefilled_section_fails_the_invented_content_check() -> None:
    document = _annex_iv()
    quote = _section(document, "development").requirement
    assert quote is not None
    forged = edit_section(document, "system", lambda s: changed(s, requirement=quote.model_dump()))
    outcome = check_nothing_invented(forged, provider_result(), {})
    assert outcome.problems == ("section 'system' quotes a requirement the template doesn't",)


def test_a_misstated_status_fails_the_invented_content_check() -> None:
    document = edit_section(
        _annex_iv(), "standards", lambda s: changed(s, status=SectionStatus.QUESTIONS)
    )
    outcome = check_nothing_invented(document, provider_result(), {})
    assert outcome.problems == ("section 'standards' misstates what is left to answer",)


def test_an_answer_written_into_another_section_fails_the_invented_content_check() -> None:
    answers = {"cybersecurity": "Access control."}
    document = edit_section(
        _annex_iv(answers=answers),
        "monitoring",
        lambda s: changed(s, paragraphs=("Access control.",)),
    )
    outcome = check_nothing_invented(document, provider_result(), answers)
    assert outcome.problems == ("section 'monitoring' holds content the user didn't supply",)


def test_a_note_the_template_does_not_give_fails_the_invented_content_check() -> None:
    forged = DraftDocument.model_validate(
        {**_annex_iv().model_dump(), "note": "No simplified form applies to you."}
    )
    assert not check_nothing_invented(forged, provider_result(), {}).passed
    art_17 = draft_document(ART_17_SKELETON, provider_result(), {}, EN, SizeClass.SME)
    noted = DraftDocument.model_validate({**art_17.model_dump(), "note": NOTE[EN]})
    assert check_nothing_invented(noted, provider_result(), {}).problems == (
        "the note is not the template's",
    )


# --- The templates and the section rules ---------------------------------------------------------


@pytest.mark.parametrize("template", SKELETON_TEMPLATES, ids=lambda template: template.id)
def test_every_skeleton_is_complete_in_both_languages(template: DocumentTemplate) -> None:
    assert re.fullmatch(TEMPLATE_PATTERN, template.id)
    keys = [spec.key for spec in template.sections]
    question_keys = [question.key for question in template.questions]
    assert len(set(keys)) == len(keys)
    assert len(set(question_keys)) == len(question_keys)
    for language in Language:
        assert template.title[language]
        for spec in template.sections:
            assert spec.heading[language]
        for question in template.questions:
            assert question.text[language].endswith(("?", "."))


def test_only_annex_iv_carries_the_simplified_form_note() -> None:
    notes = {template.id: template.small_company_note for template in SKELETON_TEMPLATES}
    assert notes.pop("annex_iv_technical_documentation") == NOTE
    assert set(notes.values()) == {None}


def test_a_requirement_section_needs_a_question_and_something_to_wait_for() -> None:
    spec = next(s for s in ANNEX_IV_SKELETON.sections if isinstance(s, RequirementSection))
    with pytest.raises(ValueError, match="needs a question"):
        RequirementSection("empty", spec.heading, spec.requirement, ())
    question = Question("q", {EN: "?", DE: "?"})
    with pytest.raises(ValueError, match="wait for nothing"):
        RequirementSection("x", spec.heading, spec.requirement, (question,), SectionStatus.DRAFTED)


def test_a_section_s_status_must_follow_its_unanswered_questions() -> None:
    section = _section(_annex_iv(), "performance_metrics")
    with pytest.raises(ValidationError, match="drafted exactly when"):
        changed(section, status=SectionStatus.DRAFTED)
    with pytest.raises(ValidationError, match="some of the section's questions"):
        changed(section, unanswered=("hardware",))
    with pytest.raises(ValidationError, match="exactly on interview sections"):
        changed(section, question_keys=(), unanswered=(), status=SectionStatus.DRAFTED)


def test_a_provider_role_is_not_what_selects_a_skeleton() -> None:
    """The duties listed decide, so a provider whose result lists none gets none."""
    result = rebuild(worked_example_result(), role=Role.PROVIDER)
    assert skeleton_templates_for(result) == ()
