"""The facts node (E2): quote-to-span matching, the evidence rules, key-fact questions, and
replays of five recorded engine-model answers in English and German. Every description here is
invented (the first is INIT's worked example); none comes from the benchmark."""

from datetime import date
from functools import partial

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr
from vcr.errors import CannotOverwriteExistingCassetteException

from aiact.engine.graph import CheckNode, EngineGraph, EngineNodes, build_graph
from aiact.engine.nodes import facts
from aiact.engine.nodes.facts import (
    ExtractedFact,
    FactExtractor,
    FactsAnswer,
    FactsOutputError,
    find_span,
    to_outcome,
)
from aiact.engine.nodes.finalize import finalize
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseLabel, CaseSet, load_yaml_file
from aiact.llm import LLMConfigError
from aiact.llm.replies import FollowUpQuestion as ReplyQuestion
from aiact.llm.structured import json_schema_format
from aiact.schemas import (
    DESCRIPTION_QUESTION_IDS,
    STEP_ORDER,
    EvidenceTag,
    FollowUpQuestion,
    Language,
    LawVersion,
    Status,
    StepName,
)
from aiact.settings import Settings

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"

enough_answer = partial(FactsAnswer, says_what_it_decides=True, says_who_it_affects=True)
"""A facts answer for a description that says what the system decides and whom it affects."""

WORKED_EXAMPLE = (
    "We're a 40-person logistics company. We use a tool that reads incoming job applications, "
    "scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't "
    "change it."
)

HUMAN_REVIEW = ReplyQuestion(
    id="human_review", text="Does a person review every shortlist?", about="high_risk"
)
EU_USE = ReplyQuestion(id="eu_use", text="Is the tool used in the EU?", about="scope")


def asked(*questions: ReplyQuestion) -> tuple[FollowUpQuestion, ...]:
    """The model's questions as the node passes them on: answered in words, no hint."""
    return tuple(FollowUpQuestion.model_validate(q.model_dump()) for q in questions)


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def engine_input(description: str, language: Language = Language.EN) -> EngineState:
    return {
        "description": description,
        "language": language,
        "law_version": LawVersion.AMENDED,
        "as_of": date(2026, 9, 29),
        "exclude_source_example_ids": (),
    }


def stated(text: str, quote: str | None) -> ExtractedFact:
    return ExtractedFact(text=text, evidence=EvidenceTag.STATED, quote=quote, question=None)


def unstated(
    text: str, evidence: EvidenceTag, question: ReplyQuestion | None = None
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
    answer = enough_answer(facts=(stated("It is an AI system", "AI"),), questions=())
    outcome = to_outcome(answer, PAYMENTS, Language.EN)
    assert outcome.facts[0].evidence is EvidenceTag.INFERRED
    assert [q.id for q in outcome.follow_up_questions] == ["confirm_it_is_an_ai_system"]


# --- evidence rules and questions ----------------------------------------------------------------


def test_a_stated_fact_gets_the_span_of_its_quote() -> None:
    answer = enough_answer(facts=(stated("Ranks applicants", "a ranked shortlist"),), questions=())
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
    answer = enough_answer(facts=(stated("Filters applicants", quote),), questions=())
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
    alone = to_outcome(enough_answer(facts=(fact,), questions=()), WORKED_EXAMPLE, Language.EN)
    later = to_outcome(
        enough_answer(facts=(stated("Scores", "scores them"), fact), questions=()),
        WORKED_EXAMPLE,
        Language.EN,
    )
    assert alone.follow_up_questions == later.follow_up_questions
    assert alone.follow_up_questions[0].id == "confirm_nobody_reviews_the_ranking"


def test_confirm_question_ids_are_unique_within_a_reply() -> None:
    clash = ReplyQuestion(id="confirm_used_in_the_eu", text="Is it used in the EU?")
    answer = enough_answer(
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
            "confirm_die_pruefung_laeuft_ueber_groessere_strassen_cafe",
        ),
        ("Café-Kasse", "confirm_cafe_kasse"),
        ("Wird in der EU genutzt", "confirm_wird_in_der_eu_genutzt"),
        ("«…»", "confirm"),
        ("x" * 80, "confirm_" + "x" * 56),
    ],
)
def test_fact_slugs_are_ascii_snake_case(text: str, slug: str) -> None:
    assert facts.fact_slug(text) == slug


def test_fact_slugs_keep_every_word_that_fits() -> None:
    eu = facts.fact_slug("The system is used in the EU")
    workplace = facts.fact_slug("The system is used in the workplace")
    assert (eu, workplace) == (
        "confirm_the_system_is_used_in_the_eu",
        "confirm_the_system_is_used_in_the_workplace",
    )
    long_fact = "The system is used by the human resources department to rank every applicant"
    slug = facts.fact_slug(long_fact)
    assert slug == "confirm_the_system_is_used_by_the_human_resources_department_to"
    assert len(slug) <= facts.MAX_SLUG_LENGTH


def test_a_repeated_long_id_drops_whole_words_before_its_number() -> None:
    long_fact = "The system is used by the human resources department to rank every applicant"
    answer = enough_answer(
        facts=(
            unstated(long_fact, EvidenceTag.INFERRED),
            unstated(long_fact + ".", EvidenceTag.INFERRED),
        ),
        questions=(),
    )
    ids = [q.id for q in to_outcome(answer, WORKED_EXAMPLE, Language.EN).follow_up_questions]
    assert ids == [
        "confirm_the_system_is_used_by_the_human_resources_department_to",
        "confirm_the_system_is_used_by_the_human_resources_department_2",
    ]


@pytest.mark.parametrize("evidence", [EvidenceTag.INFERRED, EvidenceTag.ASSUMED])
def test_an_unstated_fact_keeps_the_models_confirm_question(evidence: EvidenceTag) -> None:
    answer = enough_answer(facts=(unstated("Used in the EU", evidence, EU_USE),), questions=())
    outcome = to_outcome(answer, WORKED_EXAMPLE, Language.EN)
    assert outcome.facts[0].evidence is evidence
    assert outcome.follow_up_questions == asked(EU_USE)


def test_the_default_confirm_question_is_in_the_asked_language() -> None:
    answer = enough_answer(
        facts=(unstated("Wird in der EU genutzt", EvidenceTag.ASSUMED),), questions=()
    )
    outcome = to_outcome(answer, WORKED_EXAMPLE, Language.DE)
    assert outcome.follow_up_questions[0].text == "Bitte bestätigen Sie: Wird in der EU genutzt"


def test_key_fact_questions_come_first_and_each_id_is_asked_once() -> None:
    answer = enough_answer(
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
    assert outcome.follow_up_questions == asked(HUMAN_REVIEW, EU_USE)


def test_a_stated_fact_drops_a_confirm_question() -> None:
    fact = ExtractedFact(
        text="Scores applications", evidence=EvidenceTag.STATED, quote="scores", question=EU_USE
    )
    outcome = to_outcome(enough_answer(facts=(fact,), questions=()), WORKED_EXAMPLE, Language.EN)
    assert outcome.follow_up_questions == ()


# --- the node ------------------------------------------------------------------------------------


def _fake_extractor(content: str) -> FactExtractor:
    chat = GenericFakeChatModel(messages=iter([AIMessage(content=content)]))
    return FactExtractor(_settings(engine_model=LUNA, engine_provider=LUNA_PROVIDER), chat=chat)


def test_the_node_turns_the_reply_into_facts_and_questions() -> None:
    answer = enough_answer(
        facts=(stated("Scores applications", "scores them"),), questions=(HUMAN_REVIEW,)
    )
    outcome = _fake_extractor(answer.model_dump_json())(engine_input(WORKED_EXAMPLE))
    assert outcome.facts[0].evidence is EvidenceTag.STATED
    assert outcome.follow_up_questions == asked(HUMAN_REVIEW)


@pytest.mark.parametrize("content", ["not json", '{"facts": [{"text": "x"}], "questions": []}'])
def test_a_broken_reply_is_an_error_that_does_not_quote_the_description(content: str) -> None:
    with pytest.raises(FactsOutputError) as caught:
        _fake_extractor(content)(engine_input(WORKED_EXAMPLE))
    assert WORKED_EXAMPLE not in str(caught.value)


def _filtered_extractor(content: str) -> FactExtractor:
    """The node over a reply the provider's content filter stopped (decision 029)."""
    reply = AIMessage(content=content, response_metadata={"finish_reason": "content_filter"})
    chat = GenericFakeChatModel(messages=iter([reply]))
    return FactExtractor(_settings(engine_model=LUNA, engine_provider=LUNA_PROVIDER), chat=chat)


@pytest.mark.parametrize(
    ("language", "start"),
    [(Language.EN, "The model provider's content filter"), (Language.DE, "Der Inhaltsfilter")],
)
def test_a_provider_refusal_gives_no_facts_and_asks_for_a_person_to_review(
    language: Language, start: str
) -> None:
    refusal = "I'm sorry, but I cannot assist with that request."
    outcome = _filtered_extractor(refusal)(engine_input(WORKED_EXAMPLE, language))
    assert outcome.facts == ()
    assert [q.id for q in outcome.follow_up_questions] == ["facts_person_review"]
    assert outcome.follow_up_questions[0].text.startswith(start)


def test_a_filtered_reply_with_usable_facts_is_used() -> None:
    usable = enough_answer(facts=(stated("Scores applications", "scores them"),), questions=())
    outcome = _filtered_extractor(usable.model_dump_json())(engine_input(WORKED_EXAMPLE))
    assert [fact.text for fact in outcome.facts] == ["Scores applications"]


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
    answer = enough_answer(
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
    assert result.follow_up_questions == asked(HUMAN_REVIEW)


# --- replays of recorded answers -----------------------------------------------------------------

# Each case: the description, the answer language, and the questions the answer must include,
# as question id -> a word its text must contain (lowercase). The money-laundering,
# safety-component and exam-proctoring cases have outcome-flipping conditions the description
# doesn't settle, so the node has to ask about them (decisions 001 and 015).

REPLAY_CASES: dict[str, tuple[str, Language, dict[str, str]]] = {
    "worked_example_en": (WORKED_EXAMPLE, Language.EN, {"human_review": "review"}),
    "transaction_monitoring_en": (
        "Our bank runs a model that flags unusual card transactions. Our compliance analysts "
        "look at every flag and decide whether to report it to the authorities.",
        Language.EN,
        {"creditworthiness": "credit"},
    ),
    "predictive_maintenance_en": (
        "We make packaging machines. A model we trained on sensor data predicts when a bearing "
        "will fail, so our service team can replace it before the machine stops.",
        Language.EN,
        {"safety_component": "safety"},
    ),
    "exam_proctoring_de": (
        "Unsere Hochschule nutzt bei Online-Prüfungen eine gekaufte Software, die über die "
        "Webcam das Verhalten der Studierenden auswertet und auffällige Stellen für die "
        "Aufsicht markiert.",
        Language.DE,
        {"infers_emotions": "emotion"},
    ),
    "customer_chatbot_de": (
        "Wir sind ein Stadtwerk mit 300 Mitarbeitenden. Auf unserer Website beantwortet ein "
        "Chatbot Fragen zu Tarifen und Rechnungen. Wir haben ihn selbst auf Basis eines großen "
        "Sprachmodells gebaut.",
        Language.DE,
        {"eu_link": "eu"},
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

    assert not outcome.needs_description
    assert any(fact.evidence is EvidenceTag.STATED for fact in outcome.facts)
    assert_stated_facts_point_into(outcome, description)
    if any(fact.evidence is not EvidenceTag.STATED for fact in outcome.facts):
        assert outcome.follow_up_questions
    asked = {question.id: question.text.lower() for question in outcome.follow_up_questions}
    for question_id, keyword in must_ask.items():
        assert keyword in asked.get(question_id, ""), question_id


# --- a description too thin to start (E13) -------------------------------------------------------

THIN = "We use AI for HR."
"""INIT's "AI for HR" line (decision 026 item 10): no word on what the tool decides or whom it
affects."""
THIN_DE = "Wir nutzen KI im Personalbereich."


def thin_answer(decides: bool, affects: bool) -> FactsAnswer:
    fact = unstated("The company uses AI in HR.", EvidenceTag.INFERRED, HUMAN_REVIEW)
    return FactsAnswer(
        facts=(fact,),
        says_what_it_decides=decides,
        says_who_it_affects=affects,
        questions=(EU_USE,),
    )


@pytest.mark.parametrize(("decides", "affects"), [(False, True), (True, False), (False, False)])
def test_a_description_missing_what_it_decides_or_whom_it_affects_is_thin(
    decides: bool, affects: bool
) -> None:
    outcome = to_outcome(thin_answer(decides, affects), THIN, Language.EN)
    assert outcome.needs_description
    assert [q.id for q in outcome.follow_up_questions] == [
        "what_it_decides",
        "who_it_affects",
        "bought_or_built",
    ]
    assert [f.text for f in outcome.facts] == ["The company uses AI in HR."]


def test_a_description_that_says_both_is_not_thin() -> None:
    outcome = to_outcome(thin_answer(True, True), WORKED_EXAMPLE, Language.EN)
    assert not outcome.needs_description
    assert [q.id for q in outcome.follow_up_questions] == ["eu_use", "human_review"]


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (
            Language.EN,
            [
                (
                    "What does it decide or suggest?",
                    "For example: it ranks applicants, answers staff questions, plans shifts.",
                ),
                ("Who does it affect?", "For example: applicants, your staff, customers."),
                (
                    "Did you buy it or build it?",
                    "And whether you changed it or put your own name on it.",
                ),
            ],
        ),
        (
            Language.DE,
            [
                (
                    "Was entscheidet es oder was schlägt es vor?",
                    "Zum Beispiel: Es reiht Bewerbungen, beantwortet Fragen von Beschäftigten, "
                    "plant Schichten.",
                ),
                ("Wen betrifft es?", "Zum Beispiel: Bewerbende, Ihre Beschäftigten, Kundschaft."),
                (
                    "Haben Sie es gekauft oder selbst entwickelt?",
                    "Und ob Sie es verändert oder Ihren eigenen Namen daraufgesetzt haben.",
                ),
            ],
        ),
    ],
)
def test_the_description_questions_are_worded_as_the_artboard(
    language: Language, expected: list[tuple[str, str]]
) -> None:
    questions = facts.description_questions(language)
    assert [(q.text, q.hint) for q in questions] == expected
    assert all(q.options == () and q.if_yes is None for q in questions)


def test_the_answer_schema_asks_the_model_both_flags() -> None:
    schema = FactsAnswer.model_json_schema()
    assert {"says_what_it_decides", "says_who_it_affects"} <= set(schema["required"])
    assert json_schema_format("facts_answer", FactsAnswer) == facts.FACTS_RESPONSE_FORMAT


def _no_check(name: StepName) -> CheckNode:
    def fail(_state: EngineState) -> CheckOutcome:
        raise AssertionError(f"the {name.value} check ran on a thin description")

    return fail


def _thin_graph(extractor: FactExtractor) -> EngineGraph:
    """The facts node and the real finalize; every check fails the test if it runs."""
    nodes = EngineNodes(
        facts=extractor,
        checks={name: _no_check(name) for name in STEP_ORDER},
        finalize=finalize,
    )
    return build_graph(nodes)


def test_the_graph_ends_a_thin_run_before_the_checks() -> None:
    extractor = _fake_extractor(thin_answer(False, False).model_dump_json())
    result = _thin_graph(extractor).invoke(engine_input(THIN))["result"]
    assert result.steps == ()
    assert result.risk_class is None
    assert [q.id for q in result.follow_up_questions] == list(DESCRIPTION_QUESTION_IDS)


THIN_REPLAYS: dict[str, tuple[str, Language]] = {
    "ai_for_hr_en": (THIN, Language.EN),
    "ki_im_personalbereich_de": (THIN_DE, Language.DE),
}


@pytest.mark.vcr
@pytest.mark.parametrize("case", list(THIN_REPLAYS))
def test_recorded_thin_description_asks_for_a_description(
    case: str, engine_settings: Settings
) -> None:
    """The DoD replay: "We use AI for HR." ends before the checks with the three questions and
    no class."""
    description, language = THIN_REPLAYS[case]
    result = _thin_graph(FactExtractor(engine_settings)).invoke(
        engine_input(description, language)
    )["result"]

    assert result.needs_description
    assert result.steps == ()
    assert result.risk_class is None
    assert result.status is Status.NEEDS_MORE_INFORMATION
    assert result.follow_up_questions == facts.description_questions(language)


OWN_CASES_DIR = CASES_DIR / CaseSet.OWN.value
OWN_CASES = [
    case for path in sorted(OWN_CASES_DIR.rglob("*.yaml")) for case in load_yaml_file(path)
]
"""Every own case. A thin-description case (its label expects no class) must come back thin;
every other one is replayed by a check node, so it must not."""
CHECK_CATEGORIES = frozenset("abcde")
"""The own categories the check nodes replay (`own-<category>-…`)."""


def expects_description(case: BenchmarkCase) -> bool:
    return isinstance(case.label, CaseLabel) and case.label.expects_description


def test_the_own_cases_cover_every_check_category_in_both_languages() -> None:
    described = [case for case in OWN_CASES if not expects_description(case)]
    assert {case.id.split("-")[1] for case in described} == CHECK_CATEGORIES
    assert {case.language for case in described} == {Language.EN, Language.DE}


def test_the_own_cases_hold_the_three_approved_thin_descriptions() -> None:
    thin = {case.id: case for case in OWN_CASES if expects_description(case)}
    assert sorted(thin) == [
        "own-t-01-ai-for-hr",
        "own-t-02-sales-team-ai-tool",
        "own-t-03-ki-im-kundenservice",
    ]
    assert [case.language for case in thin.values()] == [Language.EN, Language.EN, Language.DE]
    assert all("thin-description" in case.tags for case in thin.values())
    assert all(case.label_citation == () for case in thin.values())


PENDING_RECORDING = frozenset({"own-e-04-loader-crane-tip-guard", "own-e-07-grinder-burst-kit"})
"""Own cases B10c rewrote; the orchestrator records them after review and drops them here."""


RECORDING_PENDING = pytest.mark.xfail(
    strict=True,
    raises=CannotOverwriteExistingCassetteException,
    reason="recording pending: B10c rewrote this case's description",
)


@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            case, id=case.id, marks=RECORDING_PENDING if case.id in PENDING_RECORDING else ()
        )
        for case in OWN_CASES
    ],
)
def test_recorded_own_case_is_flagged_as_its_label_expects(
    case: BenchmarkCase, engine_settings: Settings
) -> None:
    outcome = FactExtractor(engine_settings)(engine_input(case.description, case.language))
    assert outcome.needs_description is expects_description(case)
