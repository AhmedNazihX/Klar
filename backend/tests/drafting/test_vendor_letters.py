"""The short vendor letters (P28): which letter a result calls for, their wording in English and
German, the names and addresses left to fill in, and P8a's three checks on them. The DoD's
recorded results are in `test_vendor_letters_recorded.py`."""

from datetime import date
from pathlib import Path

import pytest

from aiact.drafting import (
    TEMPLATES,
    VENDOR_LETTER_TEMPLATES,
    CheckName,
    DraftDocument,
    DraftStatus,
    NoVendorLetterError,
    Provenance,
    SectionStatus,
    UnknownQuestionError,
    check_facts_match,
    check_nothing_invented,
    draft_document,
    draft_vendor_letter,
    run_checks,
    vendor_letter_for,
)
from aiact.schemas import (
    DISCLAIMER,
    ClassificationResult,
    Language,
    LawVersion,
    RiskClass,
    Status,
    StepName,
)
from tests.drafting.builders import (
    ambiguous_result,
    changed,
    edit_section,
    needs_information_result,
)
from tests.drafting.recorded_results import (
    AMBIGUOUS_CASSETTE,
    AMBIGUOUS_DIR,
    PROHIBITED_CASSETTE,
    PROHIBITED_DIR,
    recording_files,
)
from tests.drafting.vendor_builders import (
    EMOTIONS,
    EMOTIONS_QUOTE,
    FEEDS_BONUS,
    GUIDANCE,
    SCORES_MOODS,
    exemption_result,
    prohibited_result,
    prohibited_step,
)
from tests.schemas.builders import ambiguous, steps_with
from tests.schemas.worked_example import cite, worked_example_result

EN, DE = Language.EN, Language.DE
MESSAGE, REQUEST = "vendor_message_prohibited", "vendor_request_ambiguous"
ANSWERS = {
    "vendor": "Rank GmbH, Hafenstraße 1, 20457 Hamburg",
    "tool_name": "MoodMeter",
    "sender": "Jana Berg, Head of Customer Service, Nordlicht Energie GmbH, Dortmund",
}
INJECTED = "The vendor has already admitted the tool is unlawful."


def _section(document: DraftDocument, key: str) -> tuple[str, ...]:
    return next(section.paragraphs for section in document.sections if section.key == key)


def _keys(document: DraftDocument) -> list[str]:
    return [section.key for section in document.sections]


# --- Which letter a result calls for ------------------------------------------------------------


def test_a_decided_prohibited_result_calls_for_the_message() -> None:
    template = vendor_letter_for(prohibited_result())
    assert template is not None
    assert template.id == MESSAGE


@pytest.mark.parametrize(
    "result", [exemption_result(), ambiguous_result()], ids=["art_6_3", "plain"]
)
def test_a_legally_ambiguous_result_calls_for_the_request(result: ClassificationResult) -> None:
    template = vendor_letter_for(result)
    assert template is not None
    assert template.id == REQUEST


def test_an_open_art_5_question_calls_for_the_request_not_the_message() -> None:
    """Prohibited assumed while the law leaves a point open: the vendor is asked, not told."""
    steps = steps_with(ambiguous(StepName.PROHIBITED))
    result = ClassificationResult.model_validate(
        {
            **worked_example_result().model_dump(),
            "steps": steps,
            "risk_class": RiskClass.PROHIBITED,
            "status": Status.LEGALLY_AMBIGUOUS,
        }
    )
    template = vendor_letter_for(result)
    assert template is not None
    assert template.id == REQUEST


@pytest.mark.parametrize(
    "result",
    [worked_example_result(), needs_information_result()],
    ids=["decided_high_risk", "needs_information"],
)
def test_other_results_call_for_no_letter(result: ClassificationResult) -> None:
    assert vendor_letter_for(result) is None
    with pytest.raises(NoVendorLetterError):
        draft_vendor_letter(result, {}, EN)


def test_a_prohibited_step_citing_no_art_5_1_point_calls_for_no_message() -> None:
    result = prohibited_result(prohibited_step(GUIDANCE))
    assert vendor_letter_for(result) is None


def test_both_letters_are_registered_for_the_checks() -> None:
    assert [template.id for template in VENDOR_LETTER_TEMPLATES] == [MESSAGE, REQUEST]
    assert all(TEMPLATES[template.id] is template for template in VENDOR_LETTER_TEMPLATES)
    assert [template.article for template in VENDOR_LETTER_TEMPLATES] == ["art:5", "art:6"]


# --- The message ---------------------------------------------------------------------------------

MESSAGE_KEYS = ["recipient", "tool", "checked", "finding", "facts", "request", "sender"]
MESSAGE_TEXT = {
    EN: {
        "title": "Message to the vendor: a prohibited practice",
        "checked": "We checked the tool against the EU AI Act as it applies on 27 September 2026 "
        "(the amended text, CELEX 02024R1689-20260727).",
        "finding": "The check found that the tool falls under a practice prohibited by "
        "Art. 5(1)(f) of the AI Act.",
        "request": "Please confirm in writing whether you agree with this finding, and tell us "
        "if any of the facts it rests on is wrong. If the finding holds, the AI Act prohibits "
        "placing the tool on the market, putting it into service and using it for this "
        "practice, so we ask you to stop supplying it to us for this use.",
        "headings": [
            "To",
            "The tool",
            "Our check",
            "What it found",
            "The facts it rests on",
            "What we ask of you",
            "From",
        ],
    },
    DE: {
        "title": "Nachricht an den Anbieter: eine verbotene Praktik",
        "checked": "Wir haben das Tool anhand der KI-Verordnung geprüft, wie sie am "
        "27. September 2026 gilt (geänderte Fassung, CELEX 02024R1689-20260727).",
        "finding": "Nach der Prüfung fällt das Tool unter eine nach Art. 5 Abs. 1 Buchst. f der "
        "KI-Verordnung verbotene Praktik.",
        "request": "Bitte bestätigen Sie uns schriftlich, ob Sie diesem Ergebnis zustimmen, und "
        "teilen Sie uns mit, falls eine der Tatsachen, auf denen es beruht, nicht zutrifft. "
        "Trifft das Ergebnis zu, verbietet die KI-Verordnung, das Tool für diese Praktik in "
        "Verkehr zu bringen, in Betrieb zu nehmen und zu verwenden. Wir bitten Sie daher, es uns "
        "für diesen Zweck nicht weiter bereitzustellen.",
        "headings": [
            "An",
            "Das Tool",
            "Unsere Prüfung",
            "Was sie ergeben hat",
            "Die Tatsachen, auf denen sie beruht",
            "Worum wir Sie bitten",
            "Absender",
        ],
    },
}


@pytest.mark.parametrize("language", [EN, DE])
def test_the_message_states_the_point_quoted_the_facts_and_the_date(language: Language) -> None:
    document = draft_vendor_letter(prohibited_result(), {}, language)
    texts = MESSAGE_TEXT[language]
    assert document.template == MESSAGE
    assert document.title == texts["title"]
    assert _keys(document) == MESSAGE_KEYS
    assert [section.heading for section in document.sections] == texts["headings"]
    assert _section(document, "checked") == (texts["checked"],)
    assert _section(document, "finding") == (texts["finding"],)
    assert _section(document, "facts") == (SCORES_MOODS.text, FEEDS_BONUS.text)
    assert _section(document, "request") == (texts["request"],)
    finding = next(section for section in document.sections if section.key == "finding")
    assert finding.requirement == EMOTIONS
    assert EMOTIONS.quote == EMOTIONS_QUOTE


def test_the_message_quotes_the_art_5_1_point_not_a_sub_point_route_or_guideline() -> None:
    social = cite("art:5:1:c", "the evaluation or classification of natural persons")
    sub_point = cite("art:5:1:c:i", "detrimental or unfavourable treatment")
    route = cite("art:5:1a", "Paragraph 1, point (ba), shall apply")
    result = prohibited_result(prohibited_step(GUIDANCE, route, social, sub_point))
    document = draft_vendor_letter(result, {}, EN)
    finding = next(section for section in document.sections if section.key == "finding")
    assert finding.requirement == social
    assert "Art. 5(1)(c) of the AI Act" in finding.paragraphs[0]


@pytest.mark.parametrize(
    ("language", "line"),
    [
        (EN, "The check names no facts it rests on."),
        (DE, "Die Prüfung nennt keine Tatsachen, auf denen sie beruht."),
    ],
)
def test_a_result_without_deciding_facts_says_so(language: Language, line: str) -> None:
    result = prohibited_result(deciding_facts=())
    document = draft_vendor_letter(result, {}, language)
    facts = next(section for section in document.sections if section.key == "facts")
    assert (facts.provenance, facts.paragraphs) == (Provenance.TEMPLATE, (line,))
    assert all(outcome.passed for outcome in run_checks(document, result, {}, None))


@pytest.mark.parametrize(
    ("language", "text"),
    [
        (EN, "(the original text, CELEX 32024R1689)"),
        (DE, "(ursprüngliche Fassung, CELEX 32024R1689)"),
    ],
)
def test_the_original_text_is_named_with_its_own_celex(language: Language, text: str) -> None:
    result = prohibited_result(law_version=LawVersion.ORIGINAL, as_of=date(2026, 3, 2))
    document = draft_vendor_letter(result, {}, language)
    [checked] = _section(document, "checked")
    assert checked.endswith(f"{text}.")
    assert ("2 March 2026" if language is EN else "2. März 2026") in checked
    assert (document.law_version, document.as_of) == (LawVersion.ORIGINAL, date(2026, 3, 2))


# --- The request ---------------------------------------------------------------------------------

REQUEST_KEYS = ["recipient", "tool", "checked", "question", "readings", "settled_by", "request"]
REQUEST_KEYS += ["sender"]
REQUEST_TEXT = {
    EN: {
        "title": "Request to the vendor: a point the law leaves open",
        "applied": "Applied until settled: ",
        "other": "The other reading: ",
        "nothing": "The check names nothing that would settle it.",
        "request": "Please tell us how you read this point, and send us anything you hold that "
        "would settle it, such as an assessment you documented under the AI Act.",
        "headings": [
            "To",
            "The tool",
            "Our check",
            "The point the law leaves open",
            "The two readings",
            "What would settle it",
            "What we ask of you",
            "From",
        ],
    },
    DE: {
        "title": "Anfrage an den Anbieter: ein Punkt, den das Recht offenlässt",
        "applied": "Bis zur Klärung angewandt: ",
        "other": "Die andere Lesart: ",
        "nothing": "Die Prüfung nennt nichts, was den Punkt klären würde.",
        "request": "Bitte teilen Sie uns mit, wie Sie diesen Punkt beurteilen, und senden Sie uns "
        "Unterlagen, die ihn klären könnten, etwa eine Bewertung, die Sie nach der "
        "KI-Verordnung dokumentiert haben.",
        "headings": [
            "An",
            "Das Tool",
            "Unsere Prüfung",
            "Der Punkt, den das Recht offenlässt",
            "Die beiden Lesarten",
            "Was den Punkt klären würde",
            "Worum wir Sie bitten",
            "Absender",
        ],
    },
}


@pytest.mark.parametrize("language", [EN, DE])
def test_the_request_states_the_question_both_readings_and_what_would_settle_it(
    language: Language,
) -> None:
    """The ResultAmbiguous case: the vendor's Art. 6(3) assessment under Art. 6(4) among what
    would settle it."""
    result = exemption_result()
    document = draft_vendor_letter(result, {}, language)
    texts = REQUEST_TEXT[language]
    assert document.template == REQUEST
    assert document.title == texts["title"]
    assert _keys(document) == REQUEST_KEYS
    assert [section.heading for section in document.sections] == texts["headings"]
    assert _section(document, "question") == (
        "Is ranking applicants only a narrow procedural task under Art. 6(3)(a)?",
    )
    assert _section(document, "readings") == (
        texts["applied"] + "High-risk under Annex III point 4(a). Ranking applicants shapes who "
        "gets hired. If this holds, the high-risk duties apply from 2 December 2027.",
        texts["other"] + "Exempt under Art. 6(3). The ranking only sorts applications for a "
        "person to read. If this holds, the provider must document its assessment that the "
        "exemption applies before placing it on the market, and register it (Art. 6(4), "
        "49(2)).",
    )
    assert _section(document, "settled_by") == (
        "Final Commission guidelines on high-risk classification (still a draft, 19 May 2026)",
        "The provider's own Art. 6(3) assessment, documented under Art. 6(4), if it made one",
    )
    assert _section(document, "request") == (texts["request"],)
    assert _section(document, "checked") == (MESSAGE_TEXT[language]["checked"],)


@pytest.mark.parametrize("language", [EN, DE])
def test_untitled_readings_and_nothing_to_settle_it(language: Language) -> None:
    document = draft_vendor_letter(ambiguous_result(), {}, language)
    texts = REQUEST_TEXT[language]
    assert _section(document, "readings") == (
        texts["applied"] + "Stricter reading. Yes, the stricter reading applies",
        texts["other"] + "Lenient reading. No, the lenient reading applies",
    )
    assert _section(document, "settled_by") == (texts["nothing"],)


def test_the_request_asks_about_the_first_open_question_in_check_order() -> None:
    first = ambiguous(StepName.SCOPE)
    steps = [first.model_dump(), *exemption_result().model_dump()["steps"][1:]]
    result = ClassificationResult.model_validate(
        {**exemption_result().model_dump(), "steps": steps}
    )
    document = draft_vendor_letter(result, {}, EN)
    assert _section(document, "question") == ("Does the law settle this point?",)


# --- Both letters: the DRAFT label, the notice and the names to fill in -------------------------

LETTER_RESULTS = [prohibited_result(), exemption_result()]


@pytest.mark.parametrize("result", LETTER_RESULTS, ids=["message", "request"])
@pytest.mark.parametrize("language", [EN, DE])
def test_names_and_addresses_are_to_fill_in_until_answered(
    result: ClassificationResult, language: Language
) -> None:
    document = draft_vendor_letter(result, {}, language)
    assert document.label == "DRAFT"
    assert document.disclaimer == DISCLAIMER[language]
    assert (document.unanswered, document.status) == (3, DraftStatus.NEEDS_ANSWERS)
    to_fill = [section for section in document.sections if not section.paragraphs]
    assert [section.key for section in to_fill] == ["recipient", "tool", "sender"]
    assert all(section.status is SectionStatus.QUESTIONS for section in to_fill)
    assert [section.question_keys for section in to_fill] == [
        ("vendor",),
        ("tool_name",),
        ("sender",),
    ]


@pytest.mark.parametrize("result", LETTER_RESULTS, ids=["message", "request"])
def test_the_answers_are_written_in_word_for_word(result: ClassificationResult) -> None:
    document = draft_vendor_letter(result, ANSWERS, EN)
    assert (document.unanswered, document.status) == (0, DraftStatus.READY_TO_REVIEW)
    assert _section(document, "recipient") == (ANSWERS["vendor"],)
    assert _section(document, "tool") == (ANSWERS["tool_name"],)
    assert _section(document, "sender") == (ANSWERS["sender"],)


def test_an_answer_to_a_question_the_letter_does_not_ask_is_refused() -> None:
    with pytest.raises(UnknownQuestionError):
        draft_vendor_letter(prohibited_result(), {"overseers": "Jana Berg"}, EN)


def test_the_questions_have_german_twins() -> None:
    template = TEMPLATES[MESSAGE]
    assert [question.text[DE] for question in template.questions] == [
        "Welches Unternehmen liefert das Tool? Nennen Sie den Namen und die Anschrift, an die "
        "Sie schreiben.",
        "Wie heißt das Tool?",
        "Wer sendet das Schreiben? Nennen Sie Ihren Namen, Ihre Funktion sowie Name und "
        "Anschrift Ihres Unternehmens.",
    ]
    assert TEMPLATES[REQUEST].questions == template.questions


# --- P8a's three checks --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "result",
    [*LETTER_RESULTS, ambiguous_result()],
    ids=["message", "request", "plain_request"],
)
@pytest.mark.parametrize("language", [EN, DE])
@pytest.mark.parametrize("answers", [{}, ANSWERS], ids=["unanswered", "answered"])
def test_a_fresh_letter_passes_all_three_checks(
    result: ClassificationResult, language: Language, answers: dict[str, str]
) -> None:
    document = draft_vendor_letter(result, answers, language)
    outcomes = run_checks(document, result, answers, None)
    assert [outcome.check for outcome in outcomes] == list(CheckName)
    assert all(outcome.passed for outcome in outcomes), outcomes


@pytest.mark.parametrize(
    ("result", "key"),
    [(prohibited_result(), "facts"), (exemption_result(), "settled_by")],
    ids=["message", "request"],
)
def test_nothing_invented_fails_on_an_injected_fact(result: ClassificationResult, key: str) -> None:
    document = draft_vendor_letter(result, {}, EN)
    injected = edit_section(
        document, key, lambda section: changed(section, paragraphs=(*section.paragraphs, INJECTED))
    )
    outcome = check_nothing_invented(injected, result, {}, None)
    assert not outcome.passed
    assert outcome.problems == (f"section {key!r} holds content the result doesn't give",)
    facts = check_facts_match(injected, result)
    assert not facts.passed
    assert INJECTED not in " ".join(facts.problems)


def test_nothing_invented_fails_on_a_swapped_quote() -> None:
    result = prohibited_result()
    document = draft_vendor_letter(result, {}, EN)
    other = cite("art:5:1:a", "subliminal techniques beyond a person's consciousness")
    swapped = edit_section(document, "finding", lambda section: changed(section, requirement=other))
    outcome = check_nothing_invented(swapped, result, {}, None)
    assert outcome.problems == ("section 'finding' quotes a requirement the template doesn't",)
    facts = check_facts_match(swapped, result)
    assert facts.problems == (
        "section 'finding': the quote is not the result's citation of the Art. 5 point",
    )


def _facts_problems(document: DraftDocument, result: ClassificationResult) -> tuple[str, ...]:
    outcome = check_facts_match(document, result)
    assert not outcome.passed
    return outcome.problems


def test_the_facts_check_finds_another_date_and_text() -> None:
    result = prohibited_result()
    other = prohibited_result(law_version=LawVersion.ORIGINAL, as_of=date(2026, 3, 2))
    stale = draft_document(TEMPLATES[MESSAGE], other, {}, EN)
    rewritten = DraftDocument.model_validate(
        {**stale.model_dump(), "law_version": result.law_version, "as_of": result.as_of}
    )
    assert _facts_problems(rewritten, result) == (
        "section 'checked': the date checked is not the result's",
        "section 'checked': the text checked against is not the result's",
    )


def test_the_facts_check_finds_another_art_5_point_named() -> None:
    result = prohibited_result()
    document = draft_vendor_letter(result, {}, EN)
    renamed = edit_section(
        document,
        "finding",
        lambda section: changed(
            section, paragraphs=(section.paragraphs[0].replace("5(1)(f)", "5(1)(a)"),)
        ),
    )
    assert _facts_problems(renamed, result) == (
        "section 'finding': the Art. 5 point named is not the one the result cites",
    )


def test_the_facts_check_finds_a_dropped_or_reordered_fact() -> None:
    result = prohibited_result()
    document = draft_vendor_letter(result, {}, EN)
    dropped = edit_section(
        document, "facts", lambda section: changed(section, paragraphs=section.paragraphs[:1])
    )
    assert _facts_problems(dropped, result) == (
        "section 'facts': it leaves out item 2 of the result's deciding facts",
    )
    reordered = edit_section(
        document, "facts", lambda section: changed(section, paragraphs=section.paragraphs[::-1])
    )
    assert _facts_problems(reordered, result) == (
        "section 'facts': it doesn't keep the result's order of deciding facts",
    )


def test_the_facts_check_finds_a_swapped_reading_mark() -> None:
    result = exemption_result()
    document = draft_vendor_letter(result, {}, EN)
    swapped = edit_section(
        document, "readings", lambda section: changed(section, paragraphs=section.paragraphs[::-1])
    )
    assert _facts_problems(swapped, result) == (
        "section 'readings': reading 1 is not marked as the result marks it",
        "section 'readings': reading 1 is not the result's",
        "section 'readings': reading 2 is not marked as the result marks it",
        "section 'readings': reading 2 is not the result's",
    )


def test_the_facts_check_finds_another_open_question() -> None:
    result = exemption_result()
    document = draft_vendor_letter(result, {}, EN)
    asked = edit_section(
        document, "question", lambda section: changed(section, paragraphs=("Is it lawful?",))
    )
    assert _facts_problems(asked, result) == (
        "section 'question': paragraph 1 is not one of the result's open question",
        "section 'question': it leaves out item 1 of the result's open question",
    )


def test_the_facts_check_refuses_a_message_for_a_result_that_is_not_prohibited() -> None:
    document = draft_vendor_letter(prohibited_result(), {}, EN)
    other = worked_example_result()
    rewritten = DraftDocument.model_validate(
        {**document.model_dump(), "as_of": other.as_of, "law_version": other.law_version}
    )
    problems = _facts_problems(rewritten, other)
    assert (
        "section 'finding': the result is not a decided prohibited one citing an Art. 5(1) point"
        in problems
    )


# --- The DoD's recordings (replayed in test_vendor_letters_recorded.py) ----------------------


@pytest.mark.parametrize(
    ("cassette_dir", "cassette"),
    [(PROHIBITED_DIR, PROHIBITED_CASSETTE), (AMBIGUOUS_DIR, AMBIGUOUS_CASSETTE)],
    ids=["prohibited", "ambiguous"],
)
def test_the_recordings_are_committed(cassette_dir: Path, cassette: str) -> None:
    """The replays below skip without their recordings; this fails instead."""
    assert all(path.is_file() for path in recording_files(cassette_dir, cassette))
