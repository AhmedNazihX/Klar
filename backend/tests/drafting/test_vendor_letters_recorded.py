"""P28's DoD: each vendor letter in English and German, drafted from a recorded result (see
`recorded_results.py`), passes P8a's three checks, holds the result's own facts, quotes the Act
from the corpus in the letter's language (decision 031), and fails the nothing-invented check
once a fact is injected. Replay only: no model, database or network (the corpus is the one built
from `data/parsed/`)."""

import pytest

from aiact.drafting import DraftDocument, DraftStatus, check_nothing_invented, quoted_points
from aiact.schemas import (
    DISCLAIMER,
    ClassificationResult,
    Language,
    RiskClass,
    Status,
    StepName,
)
from aiact.settings import Settings
from tests.drafting.builders import changed, edit_section
from tests.drafting.recorded_results import (
    AMBIGUOUS_CASSETTE,
    AMBIGUOUS_DIR,
    PROHIBITED_CASSETTE,
    PROHIBITED_DIR,
    recorded_ambiguous_result,
    recorded_prohibited_result,
)
from tests.drafting.vendor_builders import corpus_quotes, letter, letter_checks

INJECTED = "The vendor has already admitted the tool breaks the law."
CHECKED = {
    Language.EN: "We checked the tool against the EU AI Act as it applies on 30 September 2026 "
    "(the amended text, CELEX 02024R1689-20260727).",
    Language.DE: "Wir haben das Tool anhand der KI-Verordnung geprüft, wie sie am "
    "30. September 2026 gilt (geänderte Fassung, CELEX 02024R1689-20260727).",
}
FINDING = {
    Language.EN: "The check found that the tool falls under a practice prohibited by "
    "Art. 5(1)(f) of the AI Act.",
    Language.DE: "Nach der Prüfung fällt das Tool unter eine nach Art. 5 Abs. 1 Buchst. f der "
    "KI-Verordnung verbotene Praktik.",
}
QUOTE_START = {
    Language.EN: "the placing on the market, the putting into service for this specific purpose",
    Language.DE: "das Inverkehrbringen, die Inbetriebnahme für diesen spezifischen Zweck",
}
"""Art. 5(1)(f) as the corpus words it: an English letter quotes the English Act."""
APPLIED = {Language.EN: "Applied until settled: ", Language.DE: "Bis zur Klärung angewandt: "}
OTHER = {Language.EN: "The other reading: ", Language.DE: "Die andere Lesart: "}


@pytest.fixture
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def default_cassette_name(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def replay_settings(openrouter_settings: Settings, record_mode: str) -> Settings:
    if record_mode != "none":
        pytest.skip("replay only: record the node tests' replays instead")
    return openrouter_settings


def _section(document: DraftDocument, key: str) -> tuple[str, ...]:
    return next(section.paragraphs for section in document.sections if section.key == key)


def _assert_a_valid_letter(
    result: ClassificationResult, language: Language, template: str
) -> DraftDocument:
    """The letter in `language`: DRAFT, with the notice, its names to fill in, every check
    passed, and an injected fact caught by the nothing-invented check."""
    document = letter(result, {}, language)
    assert document.template == template
    assert (document.label, document.disclaimer) == ("DRAFT", DISCLAIMER[language])
    assert (document.unanswered, document.status) == (3, DraftStatus.NEEDS_ANSWERS)
    assert _section(document, "checked") == (CHECKED[language],)
    outcomes = letter_checks(document, result, {})
    assert all(outcome.passed for outcome in outcomes), outcomes
    key = "facts" if template == "vendor_message_prohibited" else "readings"
    injected = edit_section(
        document, key, lambda section: changed(section, paragraphs=(*section.paragraphs, INJECTED))
    )
    quotes = quoted_points(result, language, corpus_quotes())
    assert not check_nothing_invented(injected, result, {}, None, quotes).passed
    return document


@pytest.mark.vcr
@pytest.mark.parametrize(
    ("vcr_cassette_dir", "default_cassette_name"),
    [(PROHIBITED_DIR, PROHIBITED_CASSETTE)],
    indirect=True,
)
def test_the_message_on_a_recorded_prohibited_result(
    vcr_cassette_dir: str, default_cassette_name: str, replay_settings: Settings, record_mode: str
) -> None:
    """Replays `default_cassette_name` from `vcr_cassette_dir`."""
    result = recorded_prohibited_result(replay_settings, record_mode)
    assert (result.risk_class, result.status) == (RiskClass.PROHIBITED, Status.DECIDED)
    [step] = [step for step in result.steps if step.step is StepName.PROHIBITED]
    [point] = [c for c in step.citations if c.provision_id == "art:5:1:f"]
    assert point.language is Language.DE  # the case is German
    assert result.deciding_facts
    for language in Language:
        document = _assert_a_valid_letter(result, language, "vendor_message_prohibited")
        assert document.article == "art:5"
        assert _section(document, "finding") == (FINDING[language],)
        finding = next(section for section in document.sections if section.key == "finding")
        [quote] = finding.quotes
        assert (quote.provision_id, quote.language) == ("art:5:1:f", language)
        assert quote.quote.startswith(QUOTE_START[language])
        assert _section(document, "facts") == tuple(fact.text for fact in result.deciding_facts)


@pytest.mark.vcr
@pytest.mark.parametrize(
    ("vcr_cassette_dir", "default_cassette_name"),
    [(AMBIGUOUS_DIR, AMBIGUOUS_CASSETTE)],
    indirect=True,
)
def test_the_request_on_a_recorded_ambiguous_result(
    vcr_cassette_dir: str, default_cassette_name: str, replay_settings: Settings, record_mode: str
) -> None:
    """Replays `default_cassette_name` from `vcr_cassette_dir`."""
    result = recorded_ambiguous_result(replay_settings, record_mode)
    assert result.status is Status.LEGALLY_AMBIGUOUS
    [step] = [step for step in result.steps if step.open_question]
    question = step.open_question
    assert question is not None
    stricter, lenient = question.readings
    for language in Language:
        document = _assert_a_valid_letter(result, language, "vendor_request_ambiguous")
        assert document.article == "art:6"
        assert _section(document, "question") == (question.question,)
        applied, other = _section(document, "readings")
        assert applied.startswith(f"{APPLIED[language]}High-risk under Art. 6(1). ")
        assert other.startswith(f"{OTHER[language]}Art. 6(1) not met. ")
        assert stricter.explanation in applied and lenient.explanation in other
        assert _section(document, "settled_by") == tuple(item.text for item in question.settled_by)
        assert _section(document, "settled_by")[0].startswith(
            "Final Commission guidelines on high-risk classification (still a draft"
        )
