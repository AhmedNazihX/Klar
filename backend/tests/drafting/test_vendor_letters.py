"""The short vendor letters (P28): which letter a result calls for, their wording in English and
German, the Art. 5(1) points quoted from the corpus and never from the result (decision 031),
the names and addresses left to fill in, and P8a's three checks on them. The quotes come from
the corpus built from `data/parsed/` (`vendor_builders.corpus_quotes`). The DoD's recorded
results are in `test_vendor_letters_recorded.py`."""

from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from aiact.drafting import (
    TEMPLATES,
    VENDOR_LETTER_TEMPLATES,
    CheckName,
    DraftDocument,
    DraftSection,
    DraftStatus,
    NoVendorLetterError,
    Provenance,
    SectionStatus,
    UnknownPointError,
    UnknownQuestionError,
    check_facts_match,
    check_nothing_invented,
    draft_document,
    draft_vendor_letter,
    quoted_points,
    vendor_letter_for,
)
from aiact.drafting.vendor_letters import fills
from aiact.drafting.vendor_letters.quotes import MAX_POINTS
from aiact.engine.nodes import prohibited_practices
from aiact.schemas import (
    DISCLAIMER,
    Citation,
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
    corpus_quotes,
    exemption_result,
    letter,
    letter_checks,
    prohibited_result,
    prohibited_step,
)
from tests.schemas.builders import ambiguous, rebuild, steps_with
from tests.schemas.worked_example import cite, worked_example_result

EN, DE = Language.EN, Language.DE
AMENDED = LawVersion.AMENDED
MESSAGE, REQUEST = "vendor_message_prohibited", "vendor_request_ambiguous"
ANSWERS = {
    "vendor": "Rank GmbH, Hafenstraße 1, 20457 Hamburg",
    "tool_name": "MoodMeter",
    "sender": "Jana Berg, Head of Customer Service, Nordlicht Energie GmbH, Dortmund",
}
INJECTED = "The vendor has already admitted the tool is unlawful."
FORGED = "FORGED: the Act allows this tool expressly"
AS_OF = prohibited_result().as_of
DECEMBER = date(2026, 12, 10)
"""After 2 December 2026, when points (ba) and (bb) apply."""
SOCIAL = cite("art:5:1:c", "the evaluation or classification of natural persons")


def _section(document: DraftDocument, key: str) -> tuple[str, ...]:
    return _part(document, key).paragraphs


def _part(document: DraftDocument, key: str) -> DraftSection:
    return next(section for section in document.sections if section.key == key)


def _keys(document: DraftDocument) -> list[str]:
    return [section.key for section in document.sections]


def _corpus(
    *points: str, language: Language = EN, version: LawVersion = AMENDED, on: date | None = AS_OF
) -> tuple[Citation, ...]:
    """The points as the corpus quotes them."""
    return corpus_quotes()(points, language, version, on)


def _quotes(result: ClassificationResult, language: Language = EN) -> tuple[Citation, ...]:
    return quoted_points(result, language, corpus_quotes())


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


def _open_at(step: StepName) -> ClassificationResult:
    """The worked example with the question of law left open at `step`."""
    is_prohibited = step is StepName.PROHIBITED
    risk = {"risk_class": RiskClass.PROHIBITED} if is_prohibited else {}
    steps = steps_with(ambiguous(step))
    return rebuild(worked_example_result(), status=Status.LEGALLY_AMBIGUOUS, steps=steps, **risk)


def test_an_open_art_5_question_calls_for_the_request_not_the_message() -> None:
    """Prohibited assumed while the law leaves a point open: the vendor is asked, not told."""
    template = vendor_letter_for(_open_at(StepName.PROHIBITED))
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
CORPUS_5_1_F = {
    EN: "the placing on the market, the putting into service for this specific purpose, or the "
    "use of AI systems to infer emotions of a natural person in the areas of workplace and "
    "education institutions, except where the use of the AI system is intended to be put in "
    "place or into the market for medical or safety reasons;",
    DE: "das Inverkehrbringen, die Inbetriebnahme für diesen spezifischen Zweck oder die "
    "Verwendung von KI-Systemen zur Ableitung von Emotionen einer natürlichen Person am "
    "Arbeitsplatz und in Bildungseinrichtungen, es sei denn, die Verwendung des KI-Systems "
    "soll aus medizinischen Gründen oder Sicherheitsgründen eingeführt oder auf den Markt "
    "gebracht werden;",
}
"""Art. 5(1)(f) in the consolidated text, as `data/parsed/` holds it."""


@pytest.mark.parametrize("language", [EN, DE])
def test_the_message_states_the_point_quoted_the_facts_and_the_date(language: Language) -> None:
    document = letter(prohibited_result(), {}, language)
    texts = MESSAGE_TEXT[language]
    assert document.template == MESSAGE
    assert (document.title, document.article) == (texts["title"], "art:5")
    assert _keys(document) == MESSAGE_KEYS
    assert [section.heading for section in document.sections] == texts["headings"]
    assert _section(document, "checked") == (texts["checked"],)
    assert _section(document, "finding") == (texts["finding"],)
    assert _section(document, "facts") == (SCORES_MOODS.text, FEEDS_BONUS.text)
    assert _section(document, "request") == (texts["request"],)
    [quote] = _part(document, "finding").quotes
    assert (quote.provision_id, quote.document_id) == ("art:5:1:f", "ai-act-consolidated")
    assert (quote.language, quote.law_version, quote.quote) == (
        language,
        AMENDED,
        CORPUS_5_1_F[language],
    )
    assert _part(document, "finding").requirement is None


@pytest.mark.parametrize("language", [EN, DE])
def test_a_forged_quote_in_the_result_is_replaced_by_the_acts_text(language: Language) -> None:
    """Decision 031: the posted result's quote is never the letter's; the corpus's is."""
    forged = EMOTIONS.model_copy(update={"quote": FORGED})
    result = prohibited_result(prohibited_step(forged, GUIDANCE))
    document = letter(result, {}, language)
    [quote] = _part(document, "finding").quotes
    assert quote.quote == CORPUS_5_1_F[language]
    assert FORGED not in document.model_dump_json()
    assert all(outcome.passed for outcome in letter_checks(document, result, {}))


@pytest.mark.parametrize(
    "point", ["art:5:1:zz", "art:5:1:i"], ids=["not_a_letter_of_the_list", "after_h"]
)
def test_a_point_the_act_does_not_have_is_refused(point: str) -> None:
    result = prohibited_result(prohibited_step(EMOTIONS, cite(point, FORGED)))
    assert vendor_letter_for(result) is not None  # the result claims a decided Art. 5(1) point
    with pytest.raises(UnknownPointError):
        quoted_points(result, EN, corpus_quotes())


@pytest.mark.parametrize("point", ["art:5:1:ba", "art:5:1:bb"])
def test_an_omnibus_point_under_the_original_text_is_refused(point: str) -> None:
    """The original text has no (ba) or (bb), whatever the date."""
    step = prohibited_step(cite(point, FORGED))
    result = prohibited_result(step, law_version=LawVersion.ORIGINAL, as_of=DECEMBER)
    with pytest.raises(UnknownPointError):
        quoted_points(result, EN, corpus_quotes())


def _never(
    provision_ids: Sequence[str], language: Language, law_version: LawVersion, as_of: date | None
) -> tuple[Citation, ...]:
    raise AssertionError("no lookup expected")


def test_more_points_than_art_5_1_lists_are_refused_before_any_lookup() -> None:
    letters = "abcdefghjkl"
    assert (MAX_POINTS, len(letters)) == (10, 11)
    step = prohibited_step(*(cite(f"art:5:1:{letter}", FORGED) for letter in letters))
    with pytest.raises(UnknownPointError):
        quoted_points(prohibited_result(step), EN, _never)


def test_a_result_that_is_not_prohibited_is_quoted_without_a_lookup() -> None:
    assert quoted_points(exemption_result(), EN, _never) == ()


TWO_POINTS = {
    EN: "The check found that the tool falls under a practice prohibited by Art. 5(1)(c) and "
    "Art. 5(1)(f) of the AI Act.",
    DE: "Nach der Prüfung fällt das Tool unter eine nach Art. 5 Abs. 1 Buchst. c und Art. 5 "
    "Abs. 1 Buchst. f der KI-Verordnung verbotene Praktik.",
}


@pytest.mark.parametrize("language", [EN, DE])
def test_every_deciding_point_is_named_and_quoted(language: Language) -> None:
    result = prohibited_result(prohibited_step(SOCIAL, GUIDANCE, EMOTIONS))
    document = letter(result, {}, language)
    assert _section(document, "finding") == (TWO_POINTS[language],)
    assert _part(document, "finding").quotes == _corpus("art:5:1:c", "art:5:1:f", language=language)
    assert all(outcome.passed for outcome in letter_checks(document, result, {}))


def test_three_points_are_listed_with_commas() -> None:
    manipulation = cite("art:5:1:a", "subliminal techniques")
    result = prohibited_result(prohibited_step(manipulation, SOCIAL, EMOTIONS))
    [finding] = _section(letter(result, {}, EN), "finding")
    assert "by Art. 5(1)(a), Art. 5(1)(c) and Art. 5(1)(f) of the AI Act." in finding


def test_the_message_quotes_the_art_5_1_point_not_a_sub_point_route_or_guideline() -> None:
    sub_point = cite("art:5:1:c:i", "detrimental or unfavourable treatment")
    route = cite("art:5:1a", "Paragraph 1, point (ba), shall apply")
    result = prohibited_result(prohibited_step(GUIDANCE, route, SOCIAL, sub_point))
    document = letter(result, {}, EN)
    assert _part(document, "finding").quotes == _corpus("art:5:1:c")
    assert "Art. 5(1)(c) of the AI Act" in _section(document, "finding")[0]


@pytest.mark.parametrize("point", ["art:5:1:ba", "art:5:1:bb"])
def test_a_point_that_applies_only_later_is_not_named_until_its_date(point: str) -> None:
    """Art. 113(a): (ba) and (bb) apply from 2 December 2026; before, the step cites them after
    its deciding point, as practices that will apply."""
    step = prohibited_step(EMOTIONS, cite(point, FORGED), GUIDANCE)
    before = prohibited_result(step, as_of=date(2026, 12, 1))
    document = letter(before, {}, EN)
    assert _part(document, "finding").quotes == _corpus("art:5:1:f", on=date(2026, 12, 1))
    assert "Art. 5(1)(f) of the AI Act" in _section(document, "finding")[0]
    after = prohibited_result(step, as_of=date(2026, 12, 2))
    quotes = _part(letter(after, {}, EN), "finding").quotes
    assert [quote.provision_id for quote in quotes] == ["art:5:1:f", point]
    assert quotes[1].changed_by_omnibus  # the Omnibus inserted it, as the validator marks it


def test_a_result_deciding_only_on_a_later_point_calls_for_no_message() -> None:
    step = prohibited_step(cite("art:5:1:ba", FORGED))
    assert vendor_letter_for(prohibited_result(step, as_of=date(2026, 12, 1))) is None


def test_the_later_points_dates_are_the_engines() -> None:
    assert {
        "art:5:1:ba": date(2026, 12, 2),
        "art:5:1:bb": date(2026, 12, 2),
    } == fills.LATER_POINTS
    assert date(2026, 12, 2) == prohibited_practices.DECEMBER_PROHIBITIONS_APPLY_FROM
    assert fills.PROHIBITIONS_APPLY_FROM == prohibited_practices.PROHIBITIONS_APPLY_FROM
    assert date(2025, 2, 2) == fills.PROHIBITIONS_APPLY_FROM


def test_an_english_letter_on_a_german_result_quotes_the_english_act() -> None:
    german = EMOTIONS.model_copy(update={"language": DE, "quote": CORPUS_5_1_F[DE]})
    result = prohibited_result(prohibited_step(german, GUIDANCE))
    [quote] = _part(letter(result, {}, EN), "finding").quotes
    assert (quote.language, quote.quote) == (EN, CORPUS_5_1_F[EN])


@pytest.mark.parametrize(
    ("language", "line"),
    [
        (EN, "The check names no facts it rests on."),
        (DE, "Die Prüfung nennt keine Tatsachen, auf denen sie beruht."),
    ],
)
def test_a_result_without_deciding_facts_says_so(language: Language, line: str) -> None:
    result = prohibited_result(deciding_facts=())
    document = letter(result, {}, language)
    facts = _part(document, "facts")
    assert (facts.provenance, facts.paragraphs) == (Provenance.TEMPLATE, (line,))
    assert all(outcome.passed for outcome in letter_checks(document, result, {}))


@pytest.mark.parametrize(
    ("language", "text"),
    [
        (EN, "(the original text, CELEX 32024R1689)"),
        (DE, "(ursprüngliche Fassung, CELEX 32024R1689)"),
    ],
)
def test_the_original_text_is_named_with_its_own_celex(language: Language, text: str) -> None:
    result = prohibited_result(law_version=LawVersion.ORIGINAL, as_of=date(2026, 3, 2))
    document = letter(result, {}, language)
    [checked] = _section(document, "checked")
    assert checked.endswith(f"{text}.")
    assert ("2 March 2026" if language is EN else "2. März 2026") in checked
    assert (document.law_version, document.as_of) == (LawVersion.ORIGINAL, date(2026, 3, 2))
    [quote] = _part(document, "finding").quotes
    assert (quote.document_id, quote.law_version) == ("ai-act", LawVersion.ORIGINAL)
    assert all(outcome.passed for outcome in letter_checks(document, result, {}))


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
    document = letter(result, {}, language)
    texts = REQUEST_TEXT[language]
    assert document.template == REQUEST
    assert (document.title, document.article) == (texts["title"], "art:6")
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
    assert all(not section.quotes for section in document.sections)


@pytest.mark.parametrize("language", [EN, DE])
def test_untitled_readings_and_nothing_to_settle_it(language: Language) -> None:
    document = letter(ambiguous_result(), {}, language)
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
    document = letter(result, {}, EN)
    assert _section(document, "question") == ("Does the law settle this point?",)
    assert document.article == "art:3"


@pytest.mark.parametrize(
    ("step", "article"),
    [
        (StepName.SCOPE, "art:3"),
        (StepName.PROHIBITED, "art:5"),
        (StepName.HIGH_RISK, "art:6"),
        (StepName.TRANSPARENCY, "art:50"),
        (StepName.ROLE_OBLIGATIONS, "art:25"),
    ],
)
def test_the_request_is_about_the_article_of_the_open_question(
    step: StepName, article: str
) -> None:
    result = _open_at(step)
    document = letter(result, {}, EN)
    assert (document.template, document.article) == (REQUEST, article)
    assert all(outcome.passed for outcome in letter_checks(document, result, {}))


def test_the_facts_check_finds_a_request_about_another_article() -> None:
    result = _open_at(StepName.TRANSPARENCY)
    document = letter(result, {}, EN)
    moved = DraftDocument.model_validate({**document.model_dump(), "article": "art:6"})
    assert _facts_problems(moved, result) == ("the duty art:6 is not the template's art:50",)


# --- Both letters: the DRAFT label, the notice and the names to fill in -------------------------

LETTER_RESULTS = [prohibited_result(), exemption_result()]


@pytest.mark.parametrize("result", LETTER_RESULTS, ids=["message", "request"])
@pytest.mark.parametrize("language", [EN, DE])
def test_names_and_addresses_are_to_fill_in_until_answered(
    result: ClassificationResult, language: Language
) -> None:
    document = letter(result, {}, language)
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
    document = letter(result, ANSWERS, EN)
    assert (document.unanswered, document.status) == (0, DraftStatus.READY_TO_REVIEW)
    assert _section(document, "recipient") == (ANSWERS["vendor"],)
    assert _section(document, "tool") == (ANSWERS["tool_name"],)
    assert _section(document, "sender") == (ANSWERS["sender"],)


def test_an_answer_to_a_question_the_letter_does_not_ask_is_refused() -> None:
    with pytest.raises(UnknownQuestionError):
        letter(prohibited_result(), {"overseers": "Jana Berg"}, EN)


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
    document = letter(result, answers, language)
    outcomes = letter_checks(document, result, answers)
    assert [outcome.check for outcome in outcomes] == list(CheckName)
    assert all(outcome.passed for outcome in outcomes), outcomes


@pytest.mark.parametrize(
    ("result", "key"),
    [(prohibited_result(), "facts"), (exemption_result(), "settled_by")],
    ids=["message", "request"],
)
def test_nothing_invented_fails_on_an_injected_fact(result: ClassificationResult, key: str) -> None:
    document = letter(result, {}, EN)
    injected = edit_section(
        document, key, lambda section: changed(section, paragraphs=(*section.paragraphs, INJECTED))
    )
    outcome = check_nothing_invented(injected, result, {}, None, _quotes(result))
    assert not outcome.passed
    assert outcome.problems == (f"section {key!r} holds content the result doesn't give",)
    facts = check_facts_match(injected, result)
    assert not facts.passed
    assert INJECTED not in " ".join(facts.problems)


def test_nothing_invented_fails_on_a_quote_that_is_not_the_corpus_text() -> None:
    result = prohibited_result()
    document = letter(result, {}, EN)
    [quote] = _part(document, "finding").quotes
    forged = (quote.model_copy(update={"quote": FORGED}),)
    swapped = edit_section(document, "finding", lambda section: changed(section, quotes=forged))
    outcome = check_nothing_invented(swapped, result, {}, None, _quotes(result))
    assert outcome.problems == ("section 'finding' quotes a text the corpus doesn't give",)
    assert check_facts_match(swapped, result).passed  # the right point, from the right text


def test_nothing_invented_fails_on_a_requirement_or_a_quote_where_none_belongs() -> None:
    result = prohibited_result()
    document = letter(result, {}, EN)
    [quote] = _part(document, "finding").quotes
    required = edit_section(document, "finding", lambda s: changed(s, requirement=quote))
    quoting = edit_section(document, "request", lambda s: changed(s, quotes=(quote,)))
    quotes = _quotes(result)
    assert check_nothing_invented(required, result, {}, None, quotes).problems == (
        "section 'finding' quotes a requirement the template doesn't",
    )
    assert check_nothing_invented(quoting, result, {}, None, quotes).problems == (
        "section 'request' quotes a requirement the template doesn't",
    )


def _facts_problems(document: DraftDocument, result: ClassificationResult) -> tuple[str, ...]:
    outcome = check_facts_match(document, result)
    assert not outcome.passed
    return outcome.problems


def test_the_facts_check_finds_another_date_and_text() -> None:
    result = prohibited_result()
    other = prohibited_result(law_version=LawVersion.ORIGINAL, as_of=date(2026, 3, 2))
    stale = draft_document(TEMPLATES[MESSAGE], other, {}, EN, quotes=_quotes(result))
    rewritten = DraftDocument.model_validate(
        {**stale.model_dump(), "law_version": result.law_version, "as_of": result.as_of}
    )
    assert _facts_problems(rewritten, result) == (
        "section 'checked': the date checked is not the result's",
        "section 'checked': the text checked against is not the result's",
    )


def test_the_facts_check_finds_another_art_5_point_named() -> None:
    result = prohibited_result()
    document = letter(result, {}, EN)
    renamed = edit_section(
        document,
        "finding",
        lambda section: changed(
            section, paragraphs=(section.paragraphs[0].replace("5(1)(f)", "5(1)(a)"),)
        ),
    )
    assert _facts_problems(renamed, result) == (
        "section 'finding': the Art. 5 points named are not the ones the result decided on",
    )


@pytest.mark.parametrize("language", [EN, DE])
def test_the_facts_check_finds_a_deciding_point_left_out(language: Language) -> None:
    result = prohibited_result(prohibited_step(SOCIAL, EMOTIONS))
    document = letter(result, {}, language)
    one = letter(prohibited_result(), {}, language)
    dropped = edit_section(
        document, "finding", lambda section: changed(section, paragraphs=_section(one, "finding"))
    )
    assert _facts_problems(dropped, result) == (
        "section 'finding': the Art. 5 points named are not the ones the result decided on",
    )
    unquoted = edit_section(
        document, "finding", lambda section: changed(section, quotes=section.quotes[1:])
    )
    assert _facts_problems(unquoted, result) == (
        "section 'finding': the quotes are not the points named, from the text checked against",
    )


def test_the_facts_check_finds_a_quote_from_another_text_or_language() -> None:
    result = prohibited_result()
    document = letter(result, {}, EN)
    original = _corpus("art:5:1:f", version=LawVersion.ORIGINAL, on=None)
    other_text = edit_section(document, "finding", lambda s: changed(s, quotes=original))
    assert _facts_problems(other_text, result) == (
        "section 'finding': the quotes are not the points named, from the text checked against",
    )
    german = edit_section(
        document, "finding", lambda s: changed(s, quotes=_corpus("art:5:1:f", language=DE))
    )
    assert _facts_problems(german, result) == (
        "section 'finding': a quote is not in the letter's language",
    )


def test_the_facts_check_finds_a_dropped_or_reordered_fact() -> None:
    result = prohibited_result()
    document = letter(result, {}, EN)
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
    document = letter(result, {}, EN)
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
    document = letter(result, {}, EN)
    asked = edit_section(
        document, "question", lambda section: changed(section, paragraphs=("Is it lawful?",))
    )
    assert _facts_problems(asked, result) == (
        "section 'question': paragraph 1 is not one of the result's open question",
        "section 'question': it leaves out item 1 of the result's open question",
    )


def test_the_facts_check_refuses_a_message_for_a_result_that_is_not_prohibited() -> None:
    document = letter(prohibited_result(), {}, EN)
    other = worked_example_result()
    rewritten = DraftDocument.model_validate(
        {**document.model_dump(), "as_of": other.as_of, "law_version": other.law_version}
    )
    problems = _facts_problems(rewritten, other)
    assert (
        "section 'finding': the result is not a decided prohibited one citing an Art. 5(1) point"
        in problems
    )


def test_the_builders_quote_is_not_the_corpus_text() -> None:
    """The fixture differs from the corpus on what the quote tests assert."""
    assert CORPUS_5_1_F[EN] != EMOTIONS_QUOTE


# --- The DoD's recordings (replayed in test_vendor_letters_recorded.py) ----------------------


@pytest.mark.parametrize(
    ("cassette_dir", "cassette"),
    [(PROHIBITED_DIR, PROHIBITED_CASSETTE), (AMBIGUOUS_DIR, AMBIGUOUS_CASSETTE)],
    ids=["prohibited", "ambiguous"],
)
def test_the_recordings_are_committed(cassette_dir: Path, cassette: str) -> None:
    """The replays below skip without their recordings; this fails instead."""
    assert all(path.is_file() for path in recording_files(cassette_dir, cassette))
