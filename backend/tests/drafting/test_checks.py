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
    prefill,
    run_checks,
)
from aiact.schemas import ClassificationResult, EvidenceTag, Fact, Language, LawVersion
from tests.drafting.builders import (
    WORKERS,
    WORKERS_ANSWERS,
    changed,
    edit_section,
    fresh_results,
    legacy_result,
    needs_information_result,
    no_stated_facts_result,
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
    for result in fresh_results():
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
    _failed(
        check_nothing_invented(added, worked_example_result(), WORKERS_ANSWERS),
        "'guarantee' is not the template's",
    )


def test_a_repeated_section_fails_the_sections_and_invented_content_checks() -> None:
    document = _notice()
    copy = changed(document.sections[3], paragraphs=(INJECTED,))
    repeated = with_sections(document, (*document.sections, copy))
    _failed(check_sections_present(repeated), "'recipients' appears more than once")
    _failed(
        check_nothing_invented(repeated, worked_example_result(), WORKERS_ANSWERS),
        "'recipients' holds content",
    )


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
    _failed(
        check_nothing_invented(document, worked_example_result(), WORKERS_ANSWERS),
        "'recipients' holds content",
    )


def test_an_added_paragraph_fails_the_invented_content_check() -> None:
    document = edit_section(
        _notice(), "start", lambda s: changed(s, paragraphs=(*s.paragraphs, INJECTED))
    )
    _failed(
        check_nothing_invented(document, worked_example_result(), WORKERS_ANSWERS),
        "'start' holds content",
    )


def test_a_section_filled_without_an_answer_fails_the_invented_content_check() -> None:
    answers = {key: value for key, value in WORKERS_ANSWERS.items() if key != "start_date"}
    document = edit_section(_notice(answers), "start", lambda s: changed(s, paragraphs=(INJECTED,)))
    _failed(
        check_nothing_invented(document, worked_example_result(), answers), "'start' holds content"
    )


def test_changed_fixed_wording_fails_the_invented_content_check() -> None:
    document = edit_section(_notice(), "why", lambda s: changed(s, paragraphs=(INJECTED,)))
    _failed(
        check_nothing_invented(document, worked_example_result(), WORKERS_ANSWERS),
        "'why' holds content",
    )


def test_a_section_relabelled_as_prefilled_fails_the_invented_content_check() -> None:
    document = edit_section(
        _notice(),
        "reviewer",
        lambda s: changed(
            s, provenance=Provenance.CLASSIFICATION, question_keys=(), paragraphs=(INJECTED,)
        ),
    )
    _failed(
        check_nothing_invented(document, worked_example_result(), WORKERS_ANSWERS),
        "claims to come from",
    )


def test_an_answer_moved_to_another_question_fails_the_invented_content_check() -> None:
    document = edit_section(_notice(), "start", lambda s: changed(s, question_keys=("reviewer",)))
    _failed(
        check_nothing_invented(document, worked_example_result(), WORKERS_ANSWERS),
        "answers another question",
    )


def test_a_changed_title_or_heading_fails_the_invented_content_check() -> None:
    retitled = DraftDocument.model_validate(
        {**_notice().model_dump(), "title": "Agreement with the works council"}
    )
    _failed(check_nothing_invented(retitled, worked_example_result(), WORKERS_ANSWERS), "title")
    reheaded = edit_section(_notice(), "why", lambda s: changed(s, heading="Agreed terms"))
    _failed(check_nothing_invented(reheaded, worked_example_result(), WORKERS_ANSWERS), "heading")


# --- Facts match the classification --------------------------------------------------------------


def test_an_altered_prefilled_fact_fails_the_facts_check() -> None:
    document = edit_section(
        _notice(),
        "system",
        lambda s: changed(s, paragraphs=(*s.paragraphs[:-1], "The tool decides who is hired")),
    )
    _failed(check_facts_match(document, worked_example_result()), "paragraph 3 is not a fact")
    _failed(check_facts_match(document, worked_example_result()), "leaves out stated fact 3")


def test_an_assumed_fact_passed_off_as_stated_fails_the_facts_check() -> None:
    document = edit_section(
        _notice(),
        "system",
        lambda s: changed(s, paragraphs=(*s.paragraphs, "The tool is used in the EU")),
    )
    _failed(check_facts_match(document, worked_example_result()), "paragraph 4 is not a fact")


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
    _failed(outcome, "the Annex point is not the result's")
    assert check_facts_match(_notice(), result).passed


def test_a_newly_stated_fact_missing_from_the_draft_fails_the_facts_check() -> None:
    result = worked_example_result()
    stated = result.facts[0].model_copy(update={"text": "The tool runs in the cloud"})
    rerun = rebuild(result, facts=(*result.facts, stated))
    _failed(check_facts_match(_notice(), rerun), "leaves out stated fact 4")


def test_a_draft_on_another_law_version_or_date_fails_the_facts_check() -> None:
    result = worked_example_result()
    for rerun in (
        rebuild(result, law_version=LawVersion.ORIGINAL),
        rebuild(result, as_of=date(2026, 10, 6)),
    ):
        _failed(check_facts_match(_notice(), rerun), "law version or date")


def test_reversed_stated_facts_fail_the_facts_check() -> None:
    document = edit_section(
        _notice(), "system", lambda s: changed(s, paragraphs=tuple(reversed(s.paragraphs)))
    )
    _failed(check_facts_match(document, worked_example_result()), "order of facts")


def test_a_draft_answering_another_duty_fails_the_facts_check() -> None:
    document = DraftDocument.model_validate({**_notice().model_dump(), "article": "art:26:11"})
    _failed(check_facts_match(document, worked_example_result()), "is not the template's")


@pytest.mark.parametrize(
    ("result", "problem"),
    [
        (needs_information_result(), "the class must be marked assumed"),
        (legacy_result(), "the date is not the result's"),
        (rebuild(worked_example_result(), annex_point="annex:III:4"), "the Annex point"),
        (
            rebuild(worked_example_result(), obligations=worked_example_result().obligations[:1]),
            "the date is not the result's",
        ),
    ],
    ids=["decided-vs-assumed", "legacy", "annex-point-prefix", "duty-not-listed"],
)
def test_a_draft_of_the_worked_example_fails_against_another_result(
    result: ClassificationResult, problem: str
) -> None:
    _failed(check_facts_match(_notice(), result), problem)


def test_an_assumed_class_drafted_as_decided_fails_the_facts_check() -> None:
    document = draft_document(
        TEMPLATES[WORKERS], needs_information_result(), WORKERS_ANSWERS, Language.EN
    )
    _failed(check_facts_match(document, worked_example_result()), "must not be marked assumed")


def test_a_legacy_duty_drafted_with_a_date_fails_the_facts_check() -> None:
    _failed(check_facts_match(_notice(), legacy_result()), "Art. 111(2) wording")


def test_a_wrong_class_fails_the_facts_check() -> None:
    document = edit_section(
        _notice(),
        "duty",
        lambda s: changed(
            s, paragraphs=(s.paragraphs[0].replace("high-risk", "minimal risk"), s.paragraphs[1])
        ),
    )
    _failed(check_facts_match(document, worked_example_result()), "the class is not the result's")


def test_the_no_facts_line_fails_when_the_result_states_facts_and_back() -> None:
    no_facts = draft_document(
        TEMPLATES[WORKERS], no_stated_facts_result(), WORKERS_ANSWERS, Language.EN
    )
    _failed(check_facts_match(no_facts, worked_example_result()), "must hold the stated facts")
    _failed(check_facts_match(_notice(), no_stated_facts_result()), "no facts were stated")


def test_a_drafter_bug_does_not_pass_its_own_facts_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """The facts check reads the result itself: a drafter writing a wrong date is caught."""
    monkeypatch.setattr(prefill, "long_date", lambda day, language: "1 January 2030")
    _failed(check_facts_match(_notice(), worked_example_result()), "the date is not the result's")


def test_a_sentence_added_to_a_prefilled_section_fails_the_invented_content_check() -> None:
    document = edit_section(
        _notice(), "duty", lambda s: changed(s, paragraphs=(*s.paragraphs, INJECTED))
    )
    outcome = check_nothing_invented(document, worked_example_result(), WORKERS_ANSWERS)
    _failed(outcome, "'duty' holds content the result doesn't give")


def test_a_duty_sentence_naming_another_duty_fails_the_facts_check() -> None:
    document = edit_section(
        _notice(),
        "duty",
        lambda s: changed(
            s, paragraphs=(s.paragraphs[0], s.paragraphs[1].replace("Art. 26(7)", "Art. 26(8)"))
        ),
    )
    outcome = check_facts_match(document, worked_example_result())
    _failed(outcome, "doesn't name the duty art:26:7")


@pytest.mark.parametrize(
    ("template", "language", "named", "longer"),
    [
        ("art_26_7_workers", Language.EN, "Art. 26(7)", "Art. 26(7)(b)"),
        ("art_26_2_oversight", Language.DE, "Art. 26 Abs. 2", "Art. 26 Abs. 21"),
    ],
)
def test_a_longer_provision_does_not_name_the_duty(
    template: str, language: Language, named: str, longer: str
) -> None:
    result = worked_example_result()
    document = draft_document(TEMPLATES[template], result, {}, language)
    document = edit_section(
        document,
        "duty",
        lambda s: changed(s, paragraphs=(s.paragraphs[0], s.paragraphs[1].replace(named, longer))),
    )
    article = TEMPLATES[template].article
    _failed(check_facts_match(document, result), f"doesn't name the duty {article}")
