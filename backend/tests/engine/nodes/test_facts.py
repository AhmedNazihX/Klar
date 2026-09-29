"""The facts node (E2): quote-to-span matching, the evidence rules, key-fact questions, and
replays of five recorded engine-model answers in English and German. Every description here is
invented (the first is INIT's worked example); none comes from the benchmark."""

from datetime import date

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.engine.graph import build_graph
from aiact.engine.nodes import facts
from aiact.engine.nodes.facts import (
    ExtractedFact,
    FactExtractor,
    FactsAnswer,
    FactsOutputError,
    find_span,
    to_outcome,
)
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import EngineState, FactsOutcome
from aiact.llm import LLMConfigError
from aiact.schemas import EvidenceTag, FollowUpQuestion, Language, LawVersion
from aiact.settings import Settings

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"

WORKED_EXAMPLE = (
    "We're a 40-person logistics company. We use a tool that reads incoming job applications, "
    "scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't "
    "change it."
)

HUMAN_REVIEW = FollowUpQuestion(
    id="human_review", text="Does a person review every shortlist?", about="high_risk"
)
EU_USE = FollowUpQuestion(id="eu_use", text="Is the tool used in the EU?", about="scope")


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def engine_input(description: str, language: Language = Language.EN) -> EngineState:
    return {
        "description": description,
        "language": language,
        "law_version": LawVersion.AMENDED,
        "as_of": date(2026, 9, 29),
        "answers": {},
        "exclude_source_example_ids": (),
    }


def stated(text: str, quote: str | None) -> ExtractedFact:
    return ExtractedFact(text=text, evidence=EvidenceTag.STATED, quote=quote, question=None)


def unstated(
    text: str, evidence: EvidenceTag, question: FollowUpQuestion | None = None
) -> ExtractedFact:
    return ExtractedFact(text=text, evidence=evidence, quote=None, question=question)


def assert_stated_facts_point_into(outcome: FactsOutcome, description: str) -> None:
    """The DoD: every stated fact has a span, and the span lies inside the description."""
    for fact in outcome.facts:
        if fact.evidence is not EvidenceTag.STATED:
            continue
        span = fact.source_span
        assert span is not None
        assert 0 <= span.start < span.end <= len(description)
        assert description[span.start : span.end].strip()


# --- quote to span -------------------------------------------------------------------------------


def test_an_exact_quote_gives_its_offsets() -> None:
    span = find_span(WORKED_EXAMPLE, "scores them")
    assert span is not None
    assert WORKED_EXAMPLE[span.start : span.end] == "scores them"


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ('"didn\'t change it."', "didn't change it"),
        ("Shows HR  a ranked\nshortlist", "shows HR a ranked shortlist"),
    ],
)
def test_a_quote_matches_despite_added_marks_case_and_reflowed_spaces(
    quote: str, expected: str
) -> None:
    span = find_span(WORKED_EXAMPLE, quote)
    assert span is not None
    assert WORKED_EXAMPLE[span.start : span.end] == expected


@pytest.mark.parametrize("quote", ["ranks candidates by age", "...", ""])
def test_a_quote_that_is_not_in_the_description_has_no_span(quote: str) -> None:
    assert find_span(WORKED_EXAMPLE, quote) is None


PAYMENTS = "We process EUR payments for merchants and email offers to users."
UMLAUTS = "Über die Webcam prüft die Software Prüfungen und markiert Auffälligkeiten."


@pytest.mark.parametrize(
    ("description", "quote"),
    [
        (PAYMENTS, "AI"),  # the "ai" in "email"
        (PAYMENTS, "EU"),  # inside "EUR"
        (PAYMENTS, "mail"),
        (UMLAUTS, "ber die Webcam"),  # starts inside "Über"
        (UMLAUTS, "Prüfung"),  # ends inside "Prüfungen"
        (UMLAUTS, "Auffälligkeit"),
    ],
)
def test_a_quote_never_matches_inside_a_word(description: str, quote: str) -> None:
    assert find_span(description, quote) is None


@pytest.mark.parametrize(
    ("description", "quote", "expected"),
    [
        (PAYMENTS, "EUR", "EUR"),
        (PAYMENTS, "email", "email"),
        (PAYMENTS, "users.", "users"),
        (UMLAUTS, "über die webcam", "Über die Webcam"),
        (UMLAUTS, "Prüfungen", "Prüfungen"),
        (UMLAUTS, "markiert Auffälligkeiten.", "markiert Auffälligkeiten"),
    ],
)
def test_a_whole_word_quote_still_matches(description: str, quote: str, expected: str) -> None:
    span = find_span(description, quote)
    assert span is not None
    assert description[span.start : span.end] == expected


def test_an_invented_short_quote_is_downgraded_and_asked() -> None:
    answer = FactsAnswer(facts=(stated("It is an AI system", "AI"),), questions=())
    outcome = to_outcome(answer, PAYMENTS, Language.EN)
    assert outcome.facts[0].evidence is EvidenceTag.INFERRED
    assert [q.id for q in outcome.follow_up_questions] == ["confirm_it_is_an_ai_system"]


# --- evidence rules and questions ----------------------------------------------------------------


def test_a_stated_fact_gets_the_span_of_its_quote() -> None:
    answer = FactsAnswer(facts=(stated("Ranks applicants", "a ranked shortlist"),), questions=())
    outcome = to_outcome(answer, WORKED_EXAMPLE, Language.EN)

    (fact,) = outcome.facts
    assert fact.evidence is EvidenceTag.STATED
    assert fact.source_span is not None
    assert WORKED_EXAMPLE[fact.source_span.start : fact.source_span.end] == "a ranked shortlist"
    assert outcome.follow_up_questions == ()


@pytest.mark.parametrize("quote", ["it filters applicants by age", None])
def test_a_stated_fact_without_a_findable_quote_becomes_inferred_and_asked(
    quote: str | None,
) -> None:
    answer = FactsAnswer(facts=(stated("Filters applicants", quote),), questions=())
    outcome = to_outcome(answer, WORKED_EXAMPLE, Language.EN)

    (fact,) = outcome.facts
    assert (fact.evidence, fact.source_span) == (EvidenceTag.INFERRED, None)
    (question,) = outcome.follow_up_questions
    assert (question.id, question.text) == (
        "confirm_filters_applicants",
        "Please confirm: Filters applicants",
    )


def test_a_confirm_question_id_comes_from_the_fact_not_its_position() -> None:
    fact = unstated("Nobody reviews the ranking", EvidenceTag.INFERRED)
    alone = to_outcome(FactsAnswer(facts=(fact,), questions=()), WORKED_EXAMPLE, Language.EN)
    later = to_outcome(
        FactsAnswer(facts=(stated("Scores", "scores them"), fact), questions=()),
        WORKED_EXAMPLE,
        Language.EN,
    )
    assert alone.follow_up_questions == later.follow_up_questions
    assert alone.follow_up_questions[0].id == "confirm_nobody_reviews_the_ranking"


def test_confirm_question_ids_are_unique_within_a_reply() -> None:
    clash = FollowUpQuestion(id="confirm_used_in_the_eu", text="Is it used in the EU?")
    answer = FactsAnswer(
        facts=(
            unstated("Used in the EU", EvidenceTag.ASSUMED),
            unstated("Used in the EU.", EvidenceTag.ASSUMED),
        ),
        questions=(clash,),
    )
    outcome = to_outcome(answer, WORKED_EXAMPLE, Language.EN)
    assert [q.id for q in outcome.follow_up_questions] == [
        "confirm_used_in_the_eu",
        "confirm_used_in_the_eu_2",
        "confirm_used_in_the_eu_3",
    ]


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        (
            "Die Prüfung läuft über größere Straßen, Café",
            "confirm_die_pruefung_laeuft_ueber_groessere_strassen",
        ),
        ("Café-Kasse", "confirm_cafe_kasse"),
        ("Wird in der EU genutzt", "confirm_wird_in_der_eu_genutzt"),
        ("«…»", "confirm"),
    ],
)
def test_fact_slugs_are_ascii_snake_case(text: str, slug: str) -> None:
    assert facts.fact_slug(text) == slug


@pytest.mark.parametrize("evidence", [EvidenceTag.INFERRED, EvidenceTag.ASSUMED])
def test_an_unstated_fact_keeps_the_models_confirm_question(evidence: EvidenceTag) -> None:
    answer = FactsAnswer(facts=(unstated("Used in the EU", evidence, EU_USE),), questions=())
    outcome = to_outcome(answer, WORKED_EXAMPLE, Language.EN)
    assert outcome.facts[0].evidence is evidence
    assert outcome.follow_up_questions == (EU_USE,)


def test_the_default_confirm_question_is_in_the_asked_language() -> None:
    answer = FactsAnswer(
        facts=(unstated("Wird in der EU genutzt", EvidenceTag.ASSUMED),), questions=()
    )
    outcome = to_outcome(answer, WORKED_EXAMPLE, Language.DE)
    assert outcome.follow_up_questions[0].text == "Bitte bestätigen Sie: Wird in der EU genutzt"


def test_key_fact_questions_come_first_and_each_id_is_asked_once() -> None:
    answer = FactsAnswer(
        facts=(
            stated("Scores applications", "scores them"),
            unstated("Used in the EU", EvidenceTag.ASSUMED, EU_USE),
            unstated("Nobody reviews the ranking", EvidenceTag.INFERRED, HUMAN_REVIEW),
        ),
        questions=(HUMAN_REVIEW,),
    )
    outcome = to_outcome(answer, WORKED_EXAMPLE, Language.EN)
    assert [fact.evidence for fact in outcome.facts] == [
        EvidenceTag.STATED,
        EvidenceTag.ASSUMED,
        EvidenceTag.INFERRED,
    ]
    assert outcome.follow_up_questions == (HUMAN_REVIEW, EU_USE)


def test_a_stated_fact_drops_a_confirm_question() -> None:
    fact = ExtractedFact(
        text="Scores applications", evidence=EvidenceTag.STATED, quote="scores", question=EU_USE
    )
    outcome = to_outcome(FactsAnswer(facts=(fact,), questions=()), WORKED_EXAMPLE, Language.EN)
    assert outcome.follow_up_questions == ()


# --- the node ------------------------------------------------------------------------------------


def _fake_extractor(content: str) -> FactExtractor:
    chat = GenericFakeChatModel(messages=iter([AIMessage(content=content)]))
    return FactExtractor(_settings(engine_model=LUNA, engine_provider=LUNA_PROVIDER), chat=chat)


def test_the_node_turns_the_reply_into_facts_and_questions() -> None:
    answer = FactsAnswer(
        facts=(stated("Scores applications", "scores them"),), questions=(HUMAN_REVIEW,)
    )
    outcome = _fake_extractor(answer.model_dump_json())(engine_input(WORKED_EXAMPLE))
    assert outcome.facts[0].evidence is EvidenceTag.STATED
    assert outcome.follow_up_questions == (HUMAN_REVIEW,)


@pytest.mark.parametrize("content", ["not json", '{"facts": [{"text": "x"}], "questions": []}'])
def test_a_broken_reply_is_an_error_that_does_not_quote_the_description(content: str) -> None:
    with pytest.raises(FactsOutputError) as caught:
        _fake_extractor(content)(engine_input(WORKED_EXAMPLE))
    assert WORKED_EXAMPLE not in str(caught.value)


def test_the_extractor_is_pinned_to_the_engine_provider() -> None:
    extractor = FactExtractor(_settings(engine_model=LUNA, engine_provider=LUNA_PROVIDER))
    assert extractor._model.openrouter_provider == {  # pyright: ignore[reportAttributeAccessIssue]
        "data_collection": "deny",
        "zdr": True,
        "order": [LUNA_PROVIDER],
        "allow_fallbacks": False,
    }


def test_the_extractor_needs_a_pinned_provider() -> None:
    with pytest.raises(LLMConfigError, match="ENGINE_PROVIDER is not set"):
        FactExtractor(_settings(engine_model=LUNA))


def test_the_prompt_puts_the_instructions_first_and_the_description_last() -> None:
    messages = facts.facts_messages(WORKED_EXAMPLE, Language.DE)
    assert messages[0].content == facts.FACTS_INSTRUCTIONS
    last = str(messages[-1].content)
    assert "Language for facts and questions: de" in last
    assert last.endswith(WORKED_EXAMPLE)


def test_the_graph_runs_the_node_and_carries_its_facts_and_questions() -> None:
    answer = FactsAnswer(
        facts=(stated("Scores applications", "scores them"),), questions=(HUMAN_REVIEW,)
    )
    nodes = scripted_nodes(Script())
    graph_nodes = type(nodes)(
        facts=_fake_extractor(answer.model_dump_json()),
        checks=nodes.checks,
        finalize=nodes.finalize,
    )
    state = build_graph(graph_nodes).invoke(engine_input(WORKED_EXAMPLE))
    result = state["result"]
    assert [fact.text for fact in result.facts] == ["Scores applications"]
    assert result.follow_up_questions == (HUMAN_REVIEW,)


# --- replays of recorded answers -----------------------------------------------------------------

# Each case: the description, the answer language, and question ids the answer must include.
# The money-laundering, safety-component and emotion cases have outcome-flipping features the
# description doesn't settle, so the node has to ask about them (decision 001, product rule).

REPLAY_CASES: dict[str, tuple[str, Language, frozenset[str]]] = {
    "worked_example_en": (WORKED_EXAMPLE, Language.EN, frozenset({"human_review"})),
    "transaction_monitoring_en": (
        "Our bank runs a model that flags unusual card transactions. Our compliance analysts "
        "look at every flag and decide whether to report it to the authorities.",
        Language.EN,
        frozenset({"transaction_enrichment_profiles"}),
    ),
    "predictive_maintenance_en": (
        "We make packaging machines. A model we trained on sensor data predicts when a bearing "
        "will fail, so our service team can replace it before the machine stops.",
        Language.EN,
        frozenset({"safety_component"}),
    ),
    "exam_proctoring_de": (
        "Unsere Hochschule nutzt bei Online-Prüfungen eine gekaufte Software, die über die "
        "Webcam das Verhalten der Studierenden auswertet und auffällige Stellen für die "
        "Aufsicht markiert.",
        Language.DE,
        frozenset({"infers_emotions"}),
    ),
    "customer_chatbot_de": (
        "Wir sind ein Stadtwerk mit 300 Mitarbeitenden. Auf unserer Website beantwortet ein "
        "Chatbot Fragen zu Tarifen und Rechnungen. Wir haben ihn selbst auf Basis eines großen "
        "Sprachmodells gebaut.",
        Language.DE,
        frozenset({"eu_use"}),
    ),
}


@pytest.fixture
def engine_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@pytest.mark.vcr
@pytest.mark.parametrize("case", list(REPLAY_CASES))
def test_recorded_facts(case: str, engine_settings: Settings) -> None:
    description, language, must_ask = REPLAY_CASES[case]
    outcome = FactExtractor(engine_settings)(engine_input(description, language))

    assert any(fact.evidence is EvidenceTag.STATED for fact in outcome.facts)
    assert_stated_facts_point_into(outcome, description)
    if any(fact.evidence is not EvidenceTag.STATED for fact in outcome.facts):
        assert outcome.follow_up_questions
    assert must_ask <= {question.id for question in outcome.follow_up_questions}
