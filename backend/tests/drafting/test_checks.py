"""The three automatic checks on a draft (P8a), each passing on a fresh draft and failing on a
draft that breaks it."""

from datetime import date

import pytest

from aiact.drafting import (
    CHECK_LABELS,
    TEMPLATES,
    CheckName,
    CheckResult,
    DraftDocument,
    Provenance,
    check_facts_match,
    check_nothing_invented,
    check_sections_present,
    draft_deployer_documents,
    draft_document,
    run_checks,
)
from aiact.schemas import EvidenceTag, Fact, Language, LawVersion
from tests.drafting.builders import (
    WORKERS,
    WORKERS_ANSWERS,
    changed,
    edit_section,
    limited_risk_result,
    with_sections,
)
from tests.schemas.builders import rebuild
from tests.schemas.worked_example import worked_example_result

INJECTED = "The works council has already agreed to the tool."


def _notice(answers: dict[str, str] = WORKERS_ANSWERS) -> DraftDocument:
    return draft_document(TEMPLATES[WORKERS], worked_example_result(), answers, Language.EN)


def _failed(outcome: CheckResult, problem: str) -> None:
    assert not outcome.passed
    assert any(problem in item for item in outcome.problems), outcome.problems


def test_the_checks_carry_the_artboard_s_names() -> None:
    assert list(CHECK_LABELS.values()) == [
        "Every required section is present",
        "No content you didn't supply",
        "Facts match the classification",
    ]


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize("answered", [True, False])
def test_every_fresh_draft_passes_all_three_checks(language: Language, answered: bool) -> None:
    answers = WORKERS_ANSWERS if answered else {}
    for result in (
        worked_example_result(),
        limited_risk_result("art:50:1", "art:50:3", "art:50:4"),
    ):
        for document in draft_deployer_documents(result, {WORKERS: answers}, language):
            given = answers if document.template == WORKERS else {}
            outcomes = run_checks(document, result, given)
            assert [outcome.check for outcome in outcomes] == list(CheckName)
            assert all(outcome.passed for outcome in outcomes), outcomes


# --- Every required section is present -----------------------------------------------------------


def test_a_missing_section_fails_the_sections_check() -> None:
    document = _notice()
    dropped = with_sections(document, tuple(s for s in document.sections if s.key != "start"))
    _failed(check_sections_present(dropped), "missing section 'start'")


def test_an_added_section_fails_the_sections_and_invented_content_checks() -> None:
    document = _notice()
    extra = changed(document.sections[2], key="guarantee", heading="Our guarantee")
    added = with_sections(document, (*document.sections, extra))
    _failed(check_sections_present(added), "'guarantee' is not in the template")
    _failed(check_nothing_invented(added, WORKERS_ANSWERS), "'guarantee' is not the template's")


def test_a_repeated_section_fails_the_sections_and_invented_content_checks() -> None:
    document = _notice()
    copy = changed(document.sections[3], paragraphs=(INJECTED,))
    repeated = with_sections(document, (*document.sections, copy))
    _failed(check_sections_present(repeated), "'recipients' appears more than once")
    _failed(check_nothing_invented(repeated, WORKERS_ANSWERS), "'recipients' holds content")


def test_sections_out_of_order_fail_the_sections_check() -> None:
    document = _notice()
    swapped = with_sections(document, tuple(reversed(document.sections)))
    _failed(check_sections_present(swapped), "out of order")


def test_a_draft_of_an_unknown_template_fails_every_check() -> None:
    document = DraftDocument.model_validate({**_notice().model_dump(), "template": "art_99_notice"})
    for outcome in run_checks(document, worked_example_result(), WORKERS_ANSWERS):
        _failed(outcome, "unknown template")


# --- No content you didn't supply ----------------------------------------------------------------


def test_a_sentence_added_to_an_answer_fails_the_invented_content_check() -> None:
    document = edit_section(
        _notice(),
        "recipients",
        lambda s: changed(s, paragraphs=(f"{s.paragraphs[0]} {INJECTED}",)),
    )
    _failed(check_nothing_invented(document, WORKERS_ANSWERS), "'recipients' holds content")


def test_an_added_paragraph_fails_the_invented_content_check() -> None:
    document = edit_section(
        _notice(), "start", lambda s: changed(s, paragraphs=(*s.paragraphs, INJECTED))
    )
    _failed(check_nothing_invented(document, WORKERS_ANSWERS), "'start' holds content")


def test_a_section_filled_without_an_answer_fails_the_invented_content_check() -> None:
    answers = {key: value for key, value in WORKERS_ANSWERS.items() if key != "start_date"}
    document = edit_section(_notice(answers), "start", lambda s: changed(s, paragraphs=(INJECTED,)))
    _failed(check_nothing_invented(document, answers), "'start' holds content")


def test_changed_fixed_wording_fails_the_invented_content_check() -> None:
    document = edit_section(_notice(), "why", lambda s: changed(s, paragraphs=(INJECTED,)))
    _failed(check_nothing_invented(document, WORKERS_ANSWERS), "'why' holds content")


def test_a_section_relabelled_as_prefilled_fails_the_invented_content_check() -> None:
    document = edit_section(
        _notice(),
        "reviewer",
        lambda s: changed(
            s, provenance=Provenance.CLASSIFICATION, question_key=None, paragraphs=(INJECTED,)
        ),
    )
    _failed(check_nothing_invented(document, WORKERS_ANSWERS), "claims to come from")


def test_an_answer_moved_to_another_question_fails_the_invented_content_check() -> None:
    document = edit_section(_notice(), "start", lambda s: changed(s, question_key="reviewer"))
    _failed(check_nothing_invented(document, WORKERS_ANSWERS), "answers another question")


def test_a_changed_title_or_heading_fails_the_invented_content_check() -> None:
    retitled = DraftDocument.model_validate(
        {**_notice().model_dump(), "title": "Agreement with the works council"}
    )
    _failed(check_nothing_invented(retitled, WORKERS_ANSWERS), "title")
    reheaded = edit_section(_notice(), "why", lambda s: changed(s, heading="Agreed terms"))
    _failed(check_nothing_invented(reheaded, WORKERS_ANSWERS), "heading")


# --- Facts match the classification --------------------------------------------------------------


def test_an_altered_prefilled_fact_fails_the_facts_check() -> None:
    document = edit_section(
        _notice(),
        "system",
        lambda s: changed(s, paragraphs=(*s.paragraphs[:-1], "The tool decides who is hired")),
    )
    _failed(check_facts_match(document, worked_example_result()), "'system' doesn't match")


def test_an_assumed_fact_passed_off_as_stated_fails_the_facts_check() -> None:
    document = edit_section(
        _notice(),
        "system",
        lambda s: changed(s, paragraphs=(*s.paragraphs, "The tool is used in the EU")),
    )
    _failed(check_facts_match(document, worked_example_result()), "'system' doesn't match")


def test_a_draft_checked_against_a_changed_result_fails_the_facts_check() -> None:
    result = worked_example_result()
    rerun = rebuild(
        result,
        facts=(
            *result.facts,
            Fact(text="The tool also screens video interviews", evidence=EvidenceTag.INFERRED),
        ),
        annex_point="annex:III:4:b",
    )
    outcome = check_facts_match(_notice(), rerun)
    _failed(outcome, "'duty' doesn't match")
    assert check_facts_match(_notice(), result).passed


def test_a_newly_stated_fact_missing_from_the_draft_fails_the_facts_check() -> None:
    result = worked_example_result()
    stated = result.facts[0].model_copy(update={"text": "The tool runs in the cloud"})
    rerun = rebuild(result, facts=(*result.facts, stated))
    _failed(check_facts_match(_notice(), rerun), "'system' doesn't match")


def test_a_draft_on_another_law_version_or_date_fails_the_facts_check() -> None:
    result = worked_example_result()
    for rerun in (
        rebuild(result, law_version=LawVersion.ORIGINAL),
        rebuild(result, as_of=date(2026, 10, 6)),
    ):
        _failed(check_facts_match(_notice(), rerun), "law version or date")
