"""The transparency node (E6): Art. 50 applied to invented answers (each duty and its exceptions,
uncertain answers, the Art. 111(4) grace period), the retrieval it runs, the model call with a
fake model, and the B5a replays, which run once their recordings exist.

The unit-test descriptions and answers are invented, not benchmark cases. The replays read the
own cases from `eval/cases/own/a/` and replay recorded model answers; the corpus answers the
recording run saw are stored next to each cassette (`<cassette>.corpus.json`).
"""

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from typing import cast

import psycopg
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.db import connect
from aiact.engine.graph import EngineNodes, build_graph
from aiact.engine.nodes import guideline_retrieval as retrieval
from aiact.engine.nodes import prohibited_texts
from aiact.engine.nodes import transparency as node
from aiact.engine.nodes import transparency_texts as texts
from aiact.engine.nodes.common import Lookup
from aiact.engine.nodes.guideline_retrieval import (
    GuidelineCorpus,
    GuidelineLibrary,
    Retrieved,
    retrieve,
)
from aiact.engine.nodes.high_risk_texts import ANNEX_I_QUESTIONS, PROFILING
from aiact.engine.nodes.key_facts import Answer, Settled
from aiact.engine.nodes.transparency import (
    TransparencyCheck,
    TransparencyOutputError,
    to_outcome,
)
from aiact.engine.nodes.transparency_duties import (
    MAX_TEXT_CHARS,
    DutyAnswer,
    MarketTiming,
    TransparencyAnswer,
)
from aiact.engine.scripted import Script, no_match, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import replay_state, transparency_matches
from aiact.llm import LLMConfigError, OpenRouterEmbeddings
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import (
    DISCLAIMER,
    DocumentStatus,
    EvidenceTag,
    Fact,
    HighRiskRoute,
    Language,
    LawVersion,
    OpenQuestion,
    RiskClass,
    SourceSpan,
    Status,
    StepName,
)
from aiact.settings import Settings
from tests.engine.built_corpus import unresolved_citations
from tests.engine.nodes.corpus_recording import RecordedGuidelineLibrary, corpus_recording

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
AS_OF = date(2026, 9, 30)
AFTER_DEADLINE = date(2026, 12, 2)
TOOL = "We run a garden centre. A tool on our website answers questions about plants."
EXCLUDED = ("tr-ex-900",)
OPEN_EDITING = OpenQuestion(
    question="Is a change of tone standard editing?",
    readings=("No: the outputs must be marked.", "Yes: no marking is needed."),
)
GUIDE_HITS = ("guide:guide-art50:para:010", "guide:guide-art50:para:020")


# --- Fakes ---------------------------------------------------------------------------------------


def provision(pid: str, language: Language = Language.EN) -> Provision:
    return Provision(
        provision_id=pid,
        doc_key="ai-act-consolidated",
        document_title="AI Act (consolidated)",
        doc_type="law",
        law_version=LawVersion.AMENDED,
        status=DocumentStatus.CONSOLIDATED,
        language=language,
        english_only=False,
        heading="Article 50 — Transparency obligations",
        text=f"Text of {pid}.",
        valid_from=date(2026, 7, 27),
        valid_to=None,
        disclaimer=DISCLAIMER[language],
    )


def hit(pid: str, language: Language = Language.EN) -> SearchHit:
    return SearchHit(
        provision_id=pid,
        doc_key="guide-art50",
        document_title="Guidelines on the transparency obligations under Article 50",
        doc_type="guideline",
        law_version=None,
        status=DocumentStatus.FINAL,
        language=language,
        heading="A heading",
        text=f"Text of {pid}.",
        valid_from=date(2026, 5, 1),
        valid_to=None,
        score=0.03,
        vector_rank=1,
        keyword_rank=None,
        similarity=0.6,
        keyword_idf=None,
    )


class FakeLibrary:
    """A `GuidelineLibrary` that records every call: any provision has a text except those in
    `missing`, and the guidance found in a language is `guidance[language]`."""

    def __init__(
        self,
        guidance: Mapping[Language, Sequence[str]] | None = None,
        missing: frozenset[str] = frozenset(),
    ) -> None:
        self.lookups: list[tuple[str, Lookup]] = []
        self.searches: list[tuple[str, Lookup, Language]] = []
        self._guidance = guidance if guidance is not None else {Language.EN: GUIDE_HITS}
        self._missing = missing

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        self.lookups.append((provision_id, lookup))
        if provision_id in self._missing:
            raise ProvisionNotFoundError(provision_id)
        return provision(provision_id, lookup.language)

    def guidance(self, query: str, lookup: Lookup, *, language: Language) -> tuple[SearchHit, ...]:
        self.searches.append((query, lookup, language))
        return tuple(hit(pid, language) for pid in self._guidance.get(language, ()))


def state(
    as_of: date = AS_OF,
    language: Language = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
    exclude: tuple[str, ...] = (),
    facts: tuple[Fact, ...] = (),
) -> EngineState:
    return {
        "description": TOOL,
        "language": language,
        "law_version": law_version,
        "as_of": as_of,
        "answers": {},
        "exclude_source_example_ids": exclude,
        "facts": facts,
        "steps": (),
    }


# --- Answers -------------------------------------------------------------------------------------


def duty(
    covered: Answer = Answer.NO, exception: Answer = Answer.NO, fact: str = "A reading."
) -> DutyAnswer:
    """One duty's answer, settled in law."""
    return DutyAnswer(
        covered=covered,
        exception=exception,
        settled_in_law=Settled.YES,
        open_question=None,
        evidence=EvidenceTag.INFERRED,
        fact=fact,
        fact_numbers=(),
    )


APPLIES = duty(Answer.YES, fact="It applies.")


def unsettled(given: DutyAnswer, question: OpenQuestion | None = OPEN_EDITING) -> DutyAnswer:
    """`given` with the law leaving it open, on `question`."""
    return given.model_copy(update={"settled_in_law": Settled.NO, "open_question": question})


DUTY_PARTS = tuple(
    name
    for name in TransparencyAnswer.model_fields
    if name not in ("market_timing", "guidance_numbers")
)


def answer(
    timing: MarketTiming = MarketTiming.LATER,
    guidance: tuple[int, ...] = (),
    /,
    **parts: DutyAnswer,
) -> TransparencyAnswer:
    """The whole answer: the duties given, every other one not raised."""
    fields = {name: parts.get(name, duty()) for name in DUTY_PARTS}
    return TransparencyAnswer.model_validate(
        {**fields, "market_timing": timing, "guidance_numbers": guidance}
    )


def outcome(
    given: TransparencyAnswer,
    at: EngineState | None = None,
    library: GuidelineLibrary | None = None,
) -> CheckOutcome:
    run = at or state()
    library = library or FakeLibrary()
    return to_outcome(given, run, retrieve(run, library, node.SOURCE.article), library)


def cited(result: CheckOutcome) -> list[str]:
    return [citation.provision_id for citation in result.step.citations]


# --- Applying Art. 50 ----------------------------------------------------------------------------


def test_no_duty_raised_is_decided_with_no_duties_citing_art_50() -> None:
    result = outcome(answer())
    assert result.transparency_duties == ()
    assert result.step.status is Status.DECIDED
    assert result.step.decision == "No transparency duty under Art. 50 applies."
    assert cited(result) == ["art:50"]


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        ("interaction", "art:50:1"),
        ("synthetic_content", "art:50:2"),
        ("emotion_biometric", "art:50:3"),
        ("deep_fake", "art:50:4"),
        ("public_interest_text", "art:50:4"),
    ],
)
def test_each_duty_that_applies_is_listed_and_cited(part: str, expected: str) -> None:
    result = outcome(answer(**{part: APPLIES}))
    assert result.transparency_duties == (expected,)
    assert result.step.status is Status.DECIDED
    assert cited(result) == [expected]
    assert result.step.decision.startswith(
        f"Transparency duties apply under Art. 50({expected[-1]})"
    )
    assert "It applies." in result.step.decision


def test_the_duties_stack_in_the_order_of_art_50_each_once() -> None:
    result = outcome(
        answer(
            public_interest_text=APPLIES,
            deep_fake=APPLIES,
            synthetic_content=APPLIES,
            interaction=APPLIES,
        )
    )
    assert result.transparency_duties == ("art:50:1", "art:50:2", "art:50:4")
    assert cited(result) == ["art:50:1", "art:50:2", "art:50:4"]
    assert result.step.decision.count("It applies.") == 1


def test_an_exception_rules_a_duty_out_and_is_named() -> None:
    obvious = duty(Answer.YES, Answer.YES, fact="Only trained staff use it, so it is obvious.")
    result = outcome(answer(interaction=obvious, synthetic_content=APPLIES))
    assert result.transparency_duties == ("art:50:2",)
    assert "Considered Art. 50(1): Only trained staff use it, so it is obvious." in (
        result.step.decision
    )
    assert cited(result) == ["art:50:1", "art:50:2"]


def test_a_paragraph_listed_through_one_part_is_not_also_considered() -> None:
    """Art. 50(4) has two parts: a deep fake listed and its text part ruled out name 50(4) once."""
    reviewed = duty(Answer.YES, Answer.YES, fact="An editor reviews every text.")
    result = outcome(answer(deep_fake=APPLIES, public_interest_text=reviewed))
    assert result.transparency_duties == ("art:50:4",)
    assert "Considered" not in result.step.decision
    assert "An editor reviews every text." not in result.step.decision
    assert cited(result) == ["art:50:4"]


def test_every_duty_ruled_out_leaves_none_and_says_why() -> None:
    edits = duty(Answer.YES, Answer.YES, fact="It only corrects spelling.")
    result = outcome(answer(synthetic_content=edits))
    assert result.transparency_duties == ()
    assert result.step.status is Status.DECIDED
    assert result.step.decision == (
        "No transparency duty under Art. 50 applies. Considered Art. 50(2): It only corrects "
        "spelling."
    )
    assert cited(result) == ["art:50:2"]


def test_an_open_fact_lists_the_duty_as_assumed_and_asks_it() -> None:
    unreviewed = duty(Answer.YES, Answer.UNKNOWN)
    result = outcome(answer(public_interest_text=unreviewed))
    assert result.transparency_duties == ("art:50:4",)
    step = result.step
    assert step.status is Status.NEEDS_MORE_INFORMATION
    assert step.missing_fact is not None
    assert step.missing_fact.id == "editorial_control"
    assert step.missing_fact.about == "art:50:4"
    assert result.follow_up_questions == (step.missing_fact,)
    assert "Art. 50(4) is assumed until this is answered: Does a person review" in step.decision


def test_an_unknown_coverage_is_asked_before_the_exception() -> None:
    result = outcome(answer(interaction=duty(Answer.UNKNOWN, Answer.UNKNOWN)))
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "interacts_directly"
    assert result.transparency_duties == ("art:50:1",)


def test_every_open_fact_is_a_follow_up_question_each_once() -> None:
    result = outcome(
        answer(
            emotion_biometric=duty(Answer.YES, Answer.UNKNOWN),
            deep_fake=duty(Answer.YES, Answer.UNKNOWN),
            interaction=duty(Answer.UNKNOWN),
        )
    )
    assert [q.id for q in result.follow_up_questions] == [
        "interacts_directly",
        "authorised_for_law_enforcement",
    ]
    assert result.transparency_duties == ("art:50:1", "art:50:3", "art:50:4")


def test_a_duty_the_law_leaves_open_is_ambiguous_with_the_duty_listed() -> None:
    rewrite = unsettled(duty(Answer.YES, Answer.YES, fact="It rewrites the tone."))
    result = outcome(answer(synthetic_content=rewrite))
    assert result.transparency_duties == ("art:50:2",)
    step = result.step
    assert step.status is Status.LEGALLY_AMBIGUOUS
    assert step.open_question == OPEN_EDITING
    assert step.missing_fact is None
    assert "Art. 50(2) is assumed pending legal review: Is a change of tone standard editing?" in (
        step.decision
    )


def test_an_open_duty_without_its_question_gets_the_fixed_one() -> None:
    result = outcome(answer(synthetic_content=unsettled(APPLIES, question=None)))
    assert result.step.open_question == OpenQuestion(
        question="Do the Act and guidance settle whether Art. 50(2) applies to this system?",
        readings=("Art. 50(2) applies.", "Art. 50(2) does not apply."),
    )


def test_an_open_flag_on_a_duty_not_raised_changes_nothing() -> None:
    result = outcome(answer(deep_fake=unsettled(duty())))
    assert result.step.status is Status.DECIDED
    assert result.transparency_duties == ()


def test_an_open_duty_beats_an_open_fact_but_both_are_listed_and_asked() -> None:
    result = outcome(
        answer(
            synthetic_content=unsettled(APPLIES),
            interaction=duty(Answer.YES, Answer.UNKNOWN),
        )
    )
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    assert result.transparency_duties == ("art:50:1", "art:50:2")
    assert [q.id for q in result.follow_up_questions] == ["interaction_obvious"]


# --- The grace period (Art. 111(4)) -------------------------------------------------------------


MARKS = {"synthetic_content": APPLIES}


def test_marking_placed_on_the_market_before_august_2026_is_due_by_2_december() -> None:
    result = outcome(answer(MarketTiming.PLACED_BEFORE, **MARKS))
    assert result.transparency_duties == ("art:50:2",)
    assert result.step.status is Status.DECIDED
    assert cited(result) == ["art:50:2", "art:111:4"]
    assert result.step.decision.endswith(
        "The system was placed on the market before 2 August 2026, so its outputs must be marked "
        "under Art. 50(2) by 2 December 2026 (Art. 111(4))."
    )


def test_the_grace_period_is_given_in_german() -> None:
    result = outcome(answer(MarketTiming.PLACED_BEFORE, **MARKS), state(language=Language.DE))
    assert "bis zum 2. Dezember 2026 nach Art. 50 Abs. 2 gekennzeichnet" in result.step.decision
    assert result.step.decision.startswith("Transparenzpflichten bestehen nach Art. 50 Abs. 2.")


def test_a_system_launched_from_august_2026_gets_no_grace_period() -> None:
    result = outcome(answer(MarketTiming.LATER, **MARKS))
    assert cited(result) == ["art:50:2"]
    assert "111" not in result.step.decision


def test_the_grace_period_is_not_given_once_it_has_ended() -> None:
    result = outcome(answer(MarketTiming.PLACED_BEFORE, **MARKS), state(as_of=AFTER_DEADLINE))
    assert cited(result) == ["art:50:2"]
    assert "111" not in result.step.decision


def test_the_grace_period_concerns_only_the_marking_duty() -> None:
    result = outcome(answer(MarketTiming.PLACED_BEFORE, interaction=APPLIES))
    assert cited(result) == ["art:50:1"]
    assert "111" not in result.step.decision


def test_a_system_only_put_into_service_before_august_follows_the_acts_wording() -> None:
    result = outcome(answer(MarketTiming.IN_SERVICE_BEFORE, **MARKS))
    assert result.step.status is Status.DECIDED
    assert cited(result) == ["art:50:2", "art:111:4"]
    decision = result.step.decision
    assert "on the Act's wording marking under Art. 50(2) applies now" in decision
    assert "guidelines also extend that period to systems put into service" in decision


def test_an_unknown_launch_date_is_asked_without_holding_up_the_step() -> None:
    result = outcome(answer(MarketTiming.UNKNOWN, **MARKS))
    assert result.step.status is Status.DECIDED
    assert [q.id for q in result.follow_up_questions] == ["first_placed_on_market"]
    assert "If the system was placed on the market before 2 August 2026" in result.step.decision
    assert cited(result) == ["art:50:2", "art:111:4"]


def test_the_original_text_has_no_grace_period() -> None:
    run = state(law_version=LawVersion.ORIGINAL)
    result = outcome(answer(MarketTiming.PLACED_BEFORE, **MARKS), run)
    assert cited(result) == ["art:50:2"]


def test_a_text_without_art_111_4_gives_no_grace_period() -> None:
    library = FakeLibrary(missing=frozenset({"art:111:4"}))
    result = outcome(answer(MarketTiming.PLACED_BEFORE, **MARKS), library=library)
    assert cited(result) == ["art:50:2"]
    assert "111" not in result.step.decision


# --- Facts and guidance ------------------------------------------------------------------------


def test_the_answers_facts_and_guidance_are_cited() -> None:
    stated = Fact(
        text="Customers chat with it.",
        evidence=EvidenceTag.STATED,
        source_span=SourceSpan(start=0, end=5),
    )
    chats = APPLIES.model_copy(update={"evidence": EvidenceTag.STATED, "fact_numbers": (1,)})
    result = outcome(answer(MarketTiming.LATER, (2, 7), interaction=chats), state(facts=(stated,)))
    assert result.step.facts_used == (stated,)
    assert cited(result) == ["art:50:1", GUIDE_HITS[1]]


def test_english_guidance_for_a_german_case_is_marked_english_only() -> None:
    result = outcome(
        answer(MarketTiming.LATER, (1,), interaction=APPLIES), state(language=Language.DE)
    )
    guidance = result.step.citations[-1]
    assert guidance.provision_id == GUIDE_HITS[0]
    assert guidance.english_only


def test_german_questions_are_asked_in_german() -> None:
    result = outcome(answer(interaction=duty(Answer.UNKNOWN)), state(language=Language.DE))
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.text.startswith("Interagieren Menschen direkt")
    assert "Bis zur Antwort auf diese Frage wird Art. 50 Abs. 1 angenommen" in (
        result.step.decision
    )


# --- Retrieval ----------------------------------------------------------------------------------


def test_art_50_is_always_fetched_and_the_exclusions_reach_every_search() -> None:
    library = FakeLibrary()
    found = retrieve(state(language=Language.DE, exclude=EXCLUDED), library, node.SOURCE.article)
    assert found.article.provision_id == "art:50"
    assert library.lookups == [("art:50", Lookup(Language.DE, LawVersion.AMENDED, AS_OF, EXCLUDED))]
    assert [language for *_, language in library.searches] == [Language.DE, Language.EN]
    for query, lookup, _ in library.searches:
        assert query == TOOL
        assert lookup.exclude_source_example_ids == EXCLUDED
    assert [h.provision_id for h in found.guidance] == list(GUIDE_HITS)


def test_german_guidance_found_in_german_is_not_searched_again() -> None:
    library = FakeLibrary(guidance={Language.DE: GUIDE_HITS[:1]})
    found = retrieve(state(language=Language.DE), library, node.SOURCE.article)
    assert len(library.searches) == 1
    assert found.guidance[0].language is Language.DE


class FakeEmbedder:
    model = "fake"
    dimensions = 3

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 0.0, 1.0]


def test_the_corpus_limits_the_search_to_the_art_50_guidelines_without_a_cut_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, object]] = []

    def spy(
        query: str, language: Language, law_version: LawVersion, as_of: date, **kwargs: object
    ) -> SearchResults:
        seen.append(kwargs)
        return SearchResults(
            query=query,
            language=language,
            law_version=law_version,
            as_of=as_of,
            hits=(),
            max_distance=None,
            found=False,
            disclaimer=DISCLAIMER[language],
        )

    monkeypatch.setattr(retrieval, "search_ai_act", spy)
    connection, embedder = cast(psycopg.Connection, object()), FakeEmbedder()
    lookup = Lookup(Language.EN, LawVersion.AMENDED, AS_OF, EXCLUDED)
    corpus = GuidelineCorpus(connection, embedder, node.SOURCE)
    corpus.guidance("query", lookup, language=Language.EN)
    assert node.SOURCE.article == "art:50"
    assert frozenset({"guide-art50"}) == node.SOURCE.doc_keys
    assert node.SOURCE.passages == 8
    assert seen == [
        {
            "doc_keys": node.SOURCE.doc_keys,
            "exclude_source_example_ids": EXCLUDED,
            "include_held_out": False,
            "max_distance": None,
            "limit": node.SOURCE.passages,
            "embedder": embedder,
            "connection": connection,
        }
    ]


def test_provision_lookups_use_the_steps_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[object, ...]] = []

    def spy(
        provision_id: str, *args: object, connection: object, include_held_out: bool
    ) -> Provision:
        seen.append((provision_id, *args, connection))
        return provision(provision_id)

    monkeypatch.setattr(retrieval, "get_provision", spy)
    connection = cast(psycopg.Connection, object())
    library = GuidelineCorpus(connection, FakeEmbedder(), node.SOURCE)
    library.provision("art:50", Lookup(Language.DE, LawVersion.AMENDED, AS_OF, ()))
    assert seen == [("art:50", Language.DE, LawVersion.AMENDED, AS_OF, connection)]


# --- The model call -----------------------------------------------------------------------------


def _settings(**values: object) -> Settings:
    pinned = {"engine_model": LUNA, "engine_provider": LUNA_PROVIDER, **values}
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **pinned)  # pyright: ignore[reportCallIssue]


def _fake_chat(given: TransparencyAnswer | str) -> GenericFakeChatModel:
    content = given if isinstance(given, str) else given.model_dump_json()
    return GenericFakeChatModel(messages=iter([AIMessage(content=content)]))


def _retrieved() -> Retrieved:
    return retrieve(state(), FakeLibrary(), node.SOURCE.article)


def test_the_prompt_puts_instructions_and_art_50_first_and_the_description_last() -> None:
    messages = node.transparency_messages(state(), _retrieved())
    assert messages[0].content == node.TRANSPARENCY_INSTRUCTIONS
    human = messages[1].content
    assert isinstance(human, str)
    assert human.startswith("The AI Act, Article 50 (amended text):\n\nText of art:50.")
    assert human.index("Text of art:50.") < human.index(f"1. [{GUIDE_HITS[0]}]")
    assert human.endswith(f"Description:\n{TOOL}")


def test_the_prompt_leaves_dates_to_the_application() -> None:
    """The model never sees `as_of`, so the prefix stays the same for every date."""
    early = node.transparency_messages(state(), _retrieved())
    late = node.transparency_messages(state(as_of=AFTER_DEADLINE), _retrieved())
    assert early == late


def _run(check: TransparencyCheck, script: Script | None = None) -> EngineState:
    scripted = scripted_nodes(script or Script())
    checks = {**scripted.checks, StepName.TRANSPARENCY: check}
    graph = build_graph(
        EngineNodes(facts=scripted.facts, checks=checks, finalize=scripted.finalize)
    )
    given: EngineState = {
        "description": TOOL,
        "language": Language.EN,
        "law_version": LawVersion.AMENDED,
        "as_of": AS_OF,
        "answers": {},
        "exclude_source_example_ids": (),
    }
    return cast(EngineState, graph.invoke(given))


def test_the_duties_reach_the_state_whatever_class_the_other_checks_find() -> None:
    """They stack: a high-risk run keeps its Art. 50 duties for the role step."""
    high_risk = CheckOutcome(
        step=no_match(StepName.HIGH_RISK).step, high_risk_route=HighRiskRoute.ANNEX_III
    )
    script = Script(checks={StepName.HIGH_RISK: high_risk}, risk_class=RiskClass.HIGH_RISK)
    check = TransparencyCheck(
        _settings(), chat=_fake_chat(answer(interaction=APPLIES)), library=FakeLibrary()
    )
    final = _run(check, script)
    assert final.get("high_risk_route") is HighRiskRoute.ANNEX_III
    assert final.get("transparency_duties") == ("art:50:1",)


def test_no_duty_leaves_the_state_without_duties() -> None:
    check = TransparencyCheck(_settings(), chat=_fake_chat(answer()), library=FakeLibrary())
    final = _run(check)
    assert "transparency_duties" not in final
    assert [s.step for s in final.get("steps", ())][-2] is StepName.TRANSPARENCY


REFUSAL_TEXT = "I'm sorry, but I cannot assist with that request."


def _filtered(content: str) -> GenericFakeChatModel:
    """A reply the provider's content filter stopped, as recorded for E4's refused cases."""
    reply = AIMessage(content=content, response_metadata={"finish_reason": "content_filter"})
    return GenericFakeChatModel(messages=iter([reply]))


def test_a_provider_refusal_assumes_every_duty_for_a_person_to_review() -> None:
    """Decision 029: not a broken output; every Art. 50 duty assumed, Art. 50 cited."""
    library = FakeLibrary()
    check = TransparencyCheck(_settings(), chat=_filtered(REFUSAL_TEXT), library=library)
    result = check(state())
    assert result.transparency_duties == ("art:50:1", "art:50:2", "art:50:3", "art:50:4")
    step = result.step
    assert step.status is Status.NEEDS_MORE_INFORMATION
    assert step.error == "provider_refusal"
    assert step.missing_fact is not None
    assert step.missing_fact.id == "transparency_person_review"
    assert result.follow_up_questions == (step.missing_fact,)
    assert cited(result) == ["art:50"]
    assert step.decision.startswith("The model provider's content filter blocked")


def test_a_refusal_is_reported_in_german() -> None:
    check = TransparencyCheck(_settings(), chat=_filtered(REFUSAL_TEXT), library=FakeLibrary())
    result = check(state(language=Language.DE))
    assert result.step.decision.startswith("Der Inhaltsfilter des Modellanbieters")
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.text.startswith("Bitte lassen Sie")


def test_a_filtered_reply_with_a_usable_answer_is_used() -> None:
    usable = answer(interaction=APPLIES).model_dump_json()
    check = TransparencyCheck(_settings(), chat=_filtered(usable), library=FakeLibrary())
    result = check(state())
    assert result.step.status is Status.DECIDED
    assert result.step.error is None
    assert result.transparency_duties == ("art:50:1",)


LONG = "x" * (MAX_TEXT_CHARS + 1)


@pytest.mark.parametrize(
    "too_long",
    [
        {"fact": LONG},
        {
            "settled_in_law": Settled.NO,
            "open_question": OpenQuestion(question=LONG, readings=("Applies.", "Not.")),
        },
        {
            "settled_in_law": Settled.NO,
            "open_question": OpenQuestion(question="Open?", readings=("Applies.", LONG)),
        },
    ],
)
def test_a_text_longer_than_the_cap_is_a_broken_output(too_long: dict[str, object]) -> None:
    """Prose a description smuggles into a fact or an open question never reaches the step."""
    long_part = APPLIES.model_construct(**{**dict(APPLIES), **too_long})
    reply = json.dumps(
        {**answer().model_dump(mode="json"), "interaction": long_part.model_dump(mode="json")}
    )
    check = TransparencyCheck(_settings(), chat=_fake_chat(reply), library=FakeLibrary())
    with pytest.raises(TransparencyOutputError, match=f"longer than {MAX_TEXT_CHARS}") as raised:
        check(state())
    assert LONG not in str(raised.value)


def test_a_text_at_the_cap_is_accepted() -> None:
    at_cap = APPLIES.model_copy(update={"fact": "x" * MAX_TEXT_CHARS})
    assert DutyAnswer.model_validate(at_cap.model_dump()).fact == at_cap.fact


def test_a_reply_that_does_not_fit_the_schema_is_a_broken_output() -> None:
    reply = '{"interaction": {"fact": "SECRET-VALUE-7731"}}'
    check = TransparencyCheck(_settings(), chat=_fake_chat(reply), library=FakeLibrary())
    with pytest.raises(TransparencyOutputError, match="doesn't fit the schema") as raised:
        check(state())
    assert "SECRET-VALUE-7731" not in str(raised.value)


def test_the_output_cap_leaves_room_for_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: dict[str, object] = {}

    def spy(**kwargs: object) -> BaseChatModel:
        asked.update(kwargs)
        return _fake_chat(answer())

    monkeypatch.setattr(node, "engine_chat_model", spy)
    TransparencyCheck(_settings(), library=FakeLibrary())
    assert asked["max_tokens"] == 4000


def test_the_engine_model_must_be_pinned() -> None:
    with pytest.raises(LLMConfigError, match="ENGINE_PROVIDER"):
        TransparencyCheck(_settings(engine_provider=None))


def _definitions() -> dict[str, dict[str, object]]:
    spec = node.TRANSPARENCY_RESPONSE_FORMAT["json_schema"]
    assert isinstance(spec, dict)
    return spec["schema"]["$defs"]


def test_the_response_format_requires_every_field() -> None:
    spec = node.TRANSPARENCY_RESPONSE_FORMAT["json_schema"]
    assert isinstance(spec, dict)
    assert spec["schema"]["required"] == list(TransparencyAnswer.model_fields)
    for definition in _definitions().values():
        if "properties" in definition:
            assert definition["required"] == list(cast(dict[str, object], definition["properties"]))


def test_each_duty_answers_its_legal_openness_right_after_its_facts() -> None:
    """Strict structured output fills fields in order, so `settled_in_law` and `open_question`
    follow the key facts and come before the summary."""
    assert _definitions()["DutyAnswer"]["required"] == [
        "covered",
        "exception",
        "settled_in_law",
        "open_question",
        "evidence",
        "fact",
        "fact_numbers",
    ]


def test_follow_up_ids_do_not_collide_with_other_checks() -> None:
    """Finalize merges every check's questions by id, so an Art. 50 id must be its own."""

    def ids(module: object) -> list[str]:
        return [value.id for value in vars(module).values() if hasattr(value, "question")]

    ours = ids(texts)
    assert len(ours) == len(set(ours))
    theirs = {*ids(prohibited_texts), *(q.id for q in (*ANNEX_I_QUESTIONS, PROFILING))}
    assert not theirs & set(ours)


# --- The matcher ---------------------------------------------------------------------------------


def _case(**fields: object) -> BenchmarkCase:
    base: dict[str, object] = {
        "id": "own-a-90-invented",
        "set_name": "own",
        "language": "en",
        "description": TOOL,
        "label": {"risk_class": "limited_risk", "role": "provider"},
        "label_citation": ["art:50:1"],
        "tags": ["obligation:art:50:1"],
    }
    return BenchmarkCase.model_validate({**base, **fields})


def test_the_matcher_needs_the_role_s_own_duties_exactly() -> None:
    case = _case()
    assert transparency_matches(outcome(answer(interaction=APPLIES)), case)
    assert not transparency_matches(outcome(answer(synthetic_content=APPLIES)), case)
    both = outcome(answer(interaction=APPLIES, synthetic_content=APPLIES))
    assert not transparency_matches(both, case)
    assert transparency_matches(outcome(answer(interaction=APPLIES, deep_fake=APPLIES)), case)


def test_the_matcher_lets_a_deployer_case_list_the_providers_duties() -> None:
    """Rule 2: a deployer whose tool marks its outputs is limited_risk without a duty of its own."""
    case = _case(label={"risk_class": "limited_risk", "role": "deployer"}, tags=[])
    assert transparency_matches(outcome(answer(synthetic_content=APPLIES)), case)
    assert not transparency_matches(outcome(answer()), case)
    marked_and_fake = outcome(answer(synthetic_content=APPLIES, deep_fake=APPLIES))
    assert not transparency_matches(marked_and_fake, case)


def test_the_matcher_needs_no_duty_for_minimal_risk() -> None:
    case = _case(label={"risk_class": "minimal_risk", "role": "provider"}, tags=[])
    assert transparency_matches(outcome(answer()), case)
    assert not transparency_matches(outcome(answer(interaction=APPLIES)), case)


def test_the_matcher_needs_the_labels_status() -> None:
    case = _case(
        label={"risk_class": "limited_risk", "status": "legally_ambiguous", "role": "provider"},
        tags=["obligation:art:50:2"],
        notes="Open question: is a tone rewrite standard editing? Reading 1: yes. Reading 2: no.",
    )
    assert transparency_matches(outcome(answer(synthetic_content=unsettled(APPLIES))), case)
    assert not transparency_matches(outcome(answer(synthetic_content=APPLIES)), case)


def test_the_matcher_fails_a_minimal_deployer_case_listing_the_tools_marking() -> None:
    case = _case(label={"risk_class": "minimal_risk", "role": "deployer"}, tags=[])
    assert not transparency_matches(outcome(answer(synthetic_content=APPLIES)), case)


def test_the_matcher_needs_every_tagged_duty_listed_even_another_roles() -> None:
    case = _case(
        label={"risk_class": "limited_risk", "role": "deployer"}, tags=["obligation:art:50:1"]
    )
    assert transparency_matches(outcome(answer(interaction=APPLIES)), case)
    assert not transparency_matches(outcome(answer(synthetic_content=APPLIES)), case)


def test_the_matcher_fails_an_ambiguous_step_against_a_decided_label() -> None:
    case = _case(tags=["obligation:art:50:2"])
    assert transparency_matches(outcome(answer(synthetic_content=APPLIES)), case)
    assert not transparency_matches(outcome(answer(synthetic_content=unsettled(APPLIES))), case)


@pytest.mark.parametrize("timing", [MarketTiming.UNKNOWN, MarketTiming.IN_SERVICE_BEFORE])
def test_the_matcher_needs_the_grace_period_given_outright(timing: MarketTiming) -> None:
    """An unread launch date or a system only put into service cites Art. 111(4) too, but
    doesn't give the grace period."""
    grace = _case(tags=["obligation:art:50:2", "timing:art111_4_grace"])
    unsure = outcome(answer(timing, **MARKS))
    assert "art:111:4" in cited(unsure)
    assert not transparency_matches(unsure, grace)


def test_the_matcher_reads_the_grace_period_in_german() -> None:
    grace = _case(language="de", tags=["obligation:art:50:2", "timing:art111_4_grace"])
    given = outcome(answer(MarketTiming.PLACED_BEFORE, **MARKS), state(language=Language.DE))
    assert transparency_matches(given, grace)


def test_the_matcher_checks_the_grace_period_both_ways() -> None:
    marking = ["obligation:art:50:2"]
    grace = _case(tags=[*marking, "timing:art111_4_grace"])
    no_grace = _case(tags=[*marking, "timing:art111_4_no_grace"])
    before = outcome(answer(MarketTiming.PLACED_BEFORE, **MARKS))
    later = outcome(answer(MarketTiming.LATER, **MARKS))
    assert transparency_matches(before, grace)
    assert not transparency_matches(later, grace)
    assert transparency_matches(later, no_grace)
    assert not transparency_matches(before, no_grace)


# --- B5a replays: the own category-a cases, once their recordings exist -----------------------
#
# Record (live model and embedding calls, and the local corpus) with `RECORD_COMMAND`.

B5A_CASES_DIR = CASES_DIR / CaseSet.OWN.value / "a"
RECORD_COMMAND = "uv run pytest tests/engine/nodes/test_transparency.py -k b5a --record-mode=once"


def _b5a_cases() -> list[BenchmarkCase]:
    paths = sorted(B5A_CASES_DIR.rglob("*.yaml")) if B5A_CASES_DIR.is_dir() else []
    return [case for path in paths for case in load_yaml_file(path)]


B5A_CASES = _b5a_cases()

KNOWN_GAPS: dict[str, str] = {}
"""Recorded cases whose Art. 50 outcome differs from the label, with the reason; each fails when
it starts matching, so the entry is removed."""


def test_the_replays_include_cases_on_each_side_of_the_grace_period() -> None:
    """The story's grace period: some cases were placed on the market before 2 August 2026 and
    some after, all judged before the 2 December 2026 deadline."""
    tagged = {tag for case in B5A_CASES for tag in case.tags}
    assert {"timing:art111_4_grace", "timing:art111_4_no_grace"} <= tagged
    assert all(case.as_of is not None and case.as_of < AFTER_DEADLINE for case in B5A_CASES)
    assert replay_state(B5A_CASES[0], AS_OF)["as_of"] == B5A_CASES[0].as_of


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@contextmanager
def _live_corpus(settings: Settings) -> Iterator[GuidelineCorpus]:
    with connect() as connection:
        yield GuidelineCorpus(connection, OpenRouterEmbeddings(settings=settings), node.SOURCE)


@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    B5A_CASES or [pytest.param(None, marks=pytest.mark.skip(reason="no B5a cases"))],
    ids=lambda case: case.id if isinstance(case, BenchmarkCase) else "no-cases",
)
def test_b5a_case_replay(
    case: BenchmarkCase,
    luna_settings: Settings,
    record_mode: str,
    vcr_cassette_dir: str,
    default_cassette_name: str,
) -> None:
    """Each B5a case's Art. 50 outcome against its label, at the case's own date (`as_of`)."""
    with corpus_recording(
        vcr_cassette_dir,
        default_cassette_name,
        record_mode,
        RECORD_COMMAND,
        lambda: _live_corpus(luna_settings),
    ) as recording:
        check = TransparencyCheck(luna_settings, library=RecordedGuidelineLibrary(recording))
        run_state = replay_state(case, AS_OF)
        result = check(run_state)
    assert not unresolved_citations(result.step, run_state)
    matches = transparency_matches(result, case)
    gap = KNOWN_GAPS.get(case.id)
    if gap is not None:
        if matches:
            pytest.fail(f"{case.id} now matches its label; remove it from KNOWN_GAPS")
        pytest.xfail(gap)
    step = result.step
    assert matches, (result.transparency_duties, step.status, cited(result), step.decision)
