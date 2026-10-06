"""The scope node (E3): every rule with invented answers, the retrieval it does, the model call with
a fake model, and the B5b replay, which runs once its recordings exist.

The descriptions and answers here are invented, not benchmark cases. The replay reads the B5b
cases only to compare the node's outcome with their labels.
"""

from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.engine.graph import build_graph
from aiact.engine.nodes import scope as node
from aiact.engine.nodes.key_facts import Answer, KeyFact
from aiact.engine.nodes.scope import (
    CorpusLibrary,
    Definition,
    DefinitionFact,
    GuidanceFact,
    Lookup,
    ScopeAnswer,
    ScopeCheck,
    ScopeLibrary,
    ScopeOutputError,
    to_outcome,
)
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseLabel, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import replay_state, scope_matches
from aiact.retrieval.provisions import Provision
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import (
    DISCLAIMER,
    STEP_ORDER,
    DocumentStatus,
    EvidenceTag,
    Language,
    LawVersion,
    RiskClass,
    Status,
    StepName,
)
from aiact.settings import Settings
from tests.engine.nodes.corpus_recording import CorpusRecording, corpus_recording, lookup_call

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
AS_OF = date(2026, 9, 30)
TOOL = (
    "We are a 30-person accounting firm in Lyon. We use a machine-learning tool that reads "
    "scanned invoices and suggests the booking account for each line."
)


def key_fact(value: Answer = Answer.NO, evidence: EvidenceTag = EvidenceTag.ASSUMED) -> KeyFact:
    return KeyFact(answer=value, evidence=evidence, fact=f"Answer {value.value}", fact_numbers=())


def definition(
    value: Definition = Definition.YES, guidance: tuple[int, ...] = ()
) -> DefinitionFact:
    return DefinitionFact(
        answer=value,
        evidence=EvidenceTag.INFERRED,
        fact=f"AI system: {value.value}",
        fact_numbers=(),
        guidance_numbers=guidance,
    )


def excludes_technique(value: Answer = Answer.YES, passages: tuple[int, ...] = ()) -> GuidanceFact:
    return GuidanceFact(
        answer=value,
        evidence=EvidenceTag.INFERRED,
        fact=f"Guidance excludes the technique: {value.value}",
        fact_numbers=(),
        guidance_numbers=passages,
    )


def scope_answer(ai_system: DefinitionFact | None = None, **key_facts: KeyFact) -> ScopeAnswer:
    """An answer: an AI system with a (assumed) link to the Union and no exclusion, unless
    overridden."""
    values: dict[str, object] = {
        "ai_system": ai_system or definition(),
        "guidance_excludes_technique": excludes_technique(Answer.NO),
        "eu_link": key_fact(Answer.YES),
        "military_only": key_fact(),
        "research_only": key_fact(),
        "pre_market_development": key_fact(),
        "personal_use": key_fact(),
        "open_source": key_fact(),
        "open_source_exception": key_fact(),
    }
    return ScopeAnswer.model_validate({**values, **key_facts})


def state(
    language: Language = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
    description: str = TOOL,
    exclude: tuple[str, ...] = (),
) -> EngineState:
    return {
        "description": description,
        "language": language,
        "law_version": law_version,
        "as_of": AS_OF,
        "answers": {},
        "exclude_source_example_ids": exclude,
        "facts": (),
        "steps": (),
        "matches": (),
    }


def provision(provision_id: str, language: Language = Language.EN) -> Provision:
    is_guidance = provision_id.startswith("guide:")
    return Provision(
        provision_id=provision_id,
        doc_key="guide-definition" if is_guidance else "ai-act-consolidated",
        document_title="Test document",
        doc_type="guideline" if is_guidance else "law",
        law_version=None if is_guidance else LawVersion.AMENDED,
        status=DocumentStatus.FINAL if is_guidance else DocumentStatus.CONSOLIDATED,
        language=language,
        english_only=False,
        heading=None,
        text=f"Text of {provision_id}",
        valid_from=date(2026, 7, 27),
        valid_to=None,
        disclaimer=DISCLAIMER[language],
    )


def hit(provision_id: str, language: Language = Language.EN, doc_key: str = "") -> SearchHit:
    return SearchHit(
        provision_id=provision_id,
        doc_key=doc_key or provision_id.split(":")[1],
        document_title="Test guidelines",
        doc_type="guideline",
        law_version=None,
        status=DocumentStatus.FINAL,
        language=language,
        heading=None,
        text=f"Passage {provision_id}",
        valid_from=date(2025, 2, 6),
        valid_to=None,
        score=0.01,
        vector_rank=1,
        keyword_rank=None,
        similarity=0.5,
        keyword_idf=None,
    )


PASSAGES = (hit("guide:guide-definition:para:40"), hit("guide:guide-definition:para:41"))


@dataclass
class FakeLibrary:
    """Serves made-up provisions and passages, and remembers what it was asked."""

    guidance: tuple[SearchHit, ...] = PASSAGES
    lookups: list[Lookup] = field(default_factory=list)
    fetched: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        self.lookups.append(lookup)
        self.fetched.append(provision_id)
        return provision(provision_id, lookup.language)

    def definition_guidance(self, query: str, lookup: Lookup) -> tuple[SearchHit, ...]:
        self.lookups.append(lookup)
        self.queries.append(query)
        return self.guidance


def outcome_of(answer: ScopeAnswer, given: EngineState | None = None) -> CheckOutcome:
    return to_outcome(answer, given or state(), PASSAGES, FakeLibrary())


def cited(outcome: CheckOutcome) -> list[str]:
    return [citation.provision_id for citation in outcome.step.citations]


# --- The rules ----------------------------------------------------------------------------------


def test_an_ai_system_with_no_exclusion_is_in_scope() -> None:
    outcome = outcome_of(scope_answer())
    assert outcome.step.step is StepName.SCOPE
    assert outcome.matched is False
    assert outcome.step.status is Status.DECIDED
    assert cited(outcome) == ["art:3:1", "art:2:1"]
    assert outcome.follow_up_questions == ()
    assert outcome.step.decision.startswith("In scope: an AI system under Art. 3(1)")
    # The territorial fact is shown even when it is only assumed (INIT > worked example).
    assert [f.text for f in outcome.step.facts_used] == ["AI system: yes", "Answer yes"]


def test_a_system_that_is_not_an_ai_system_is_out_of_scope() -> None:
    outcome = outcome_of(scope_answer(definition(Definition.NO, guidance=(2,))))
    assert outcome.matched is True
    assert outcome.step.status is Status.DECIDED
    assert cited(outcome) == ["art:3:1", "recital:12", "guide:guide-definition:para:41"]
    assert "Art. 3(1): it is not an AI system" in outcome.step.decision


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        ("eu_link", Answer.NO, ["art:3:1", "art:2:1"]),
        ("military_only", Answer.YES, ["art:3:1", "art:2:3", "recital:24"]),
        ("research_only", Answer.YES, ["art:3:1", "art:2:6", "recital:25"]),
        ("personal_use", Answer.YES, ["art:3:1", "art:2:10"]),
        ("open_source", Answer.YES, ["art:3:1", "art:2:12", "recital:102", "recital:103"]),
    ],
)
def test_each_art_2_exclusion_takes_an_ai_system_out_of_scope(
    field_name: str, value: Answer, expected: list[str]
) -> None:
    answer = scope_answer().model_copy(update={field_name: key_fact(value, EvidenceTag.STATED)})
    outcome = outcome_of(answer)
    assert outcome.matched is True
    assert outcome.step.status is Status.DECIDED
    assert cited(outcome) == expected
    assert outcome.step.decision.startswith("Out of scope: the AI Act does not apply.")
    assert "Answer" in " ".join(f.text for f in outcome.step.facts_used)


def test_a_system_in_development_is_classified_as_planned_with_art_2_8_noted() -> None:
    """User rule 2026-09-30: Art. 2(8) exempts today's development, never the planned system."""
    in_development = key_fact(Answer.YES, EvidenceTag.STATED)
    outcome = outcome_of(scope_answer(pre_market_development=in_development))
    assert outcome.matched is False
    assert outcome.step.status is Status.DECIDED
    assert cited(outcome) == ["art:3:1", "art:2:1", "art:2:8", "recital:25"]
    assert outcome.step.decision.startswith("In scope:")
    assert outcome.step.decision.endswith("the classification is for the system as it will be "
                                          "once it is.")  # fmt: skip
    assert "Answer yes" in [f.text for f in outcome.step.facts_used]


def test_the_art_2_8_note_also_accompanies_an_out_of_scope_finding() -> None:
    answer = scope_answer(
        definition(Definition.NO), pre_market_development=key_fact(Answer.YES, EvidenceTag.STATED)
    )
    outcome = outcome_of(answer)
    assert outcome.matched is True
    assert cited(outcome) == ["art:3:1", "recital:12", "art:2:8", "recital:25"]


def test_an_unknown_development_stage_asks_nothing() -> None:
    outcome = outcome_of(scope_answer(pre_market_development=key_fact(Answer.UNKNOWN)))
    assert outcome.step.status is Status.DECIDED
    assert outcome.follow_up_questions == ()


def test_open_source_put_into_service_as_high_risk_stays_in_scope() -> None:
    answer = scope_answer(
        open_source=key_fact(Answer.YES, EvidenceTag.STATED),
        open_source_exception=key_fact(Answer.YES, EvidenceTag.INFERRED),
    )
    outcome = outcome_of(answer)
    assert outcome.matched is False
    assert outcome.step.status is Status.DECIDED
    assert "art:2:12" in cited(outcome)  # the description raised the exclusion; it doesn't apply


def test_an_exclusion_the_description_rules_out_is_cited_but_a_default_one_is_not() -> None:
    answer = scope_answer(military_only=key_fact(Answer.NO, EvidenceTag.STATED))
    outcome = outcome_of(answer)
    assert outcome.matched is False
    assert cited(outcome) == ["art:3:1", "art:2:1", "art:2:3", "recital:24"]


def test_an_open_open_source_exception_needs_more_information() -> None:
    answer = scope_answer(
        open_source=key_fact(Answer.YES, EvidenceTag.STATED),
        open_source_exception=key_fact(Answer.UNKNOWN),
    )
    outcome = outcome_of(answer)
    assert outcome.matched is False
    assert outcome.step.status is Status.NEEDS_MORE_INFORMATION
    assert outcome.step.missing_fact is not None
    assert outcome.step.missing_fact.id == "open_source_exception"
    assert [q.id for q in outcome.follow_up_questions] == ["open_source_exception"]
    assert outcome.step.decision.startswith("Working assumption: in scope")


def test_an_unknown_technique_needs_more_information_and_asks_about_it() -> None:
    outcome = outcome_of(scope_answer(definition(Definition.UNKNOWN)))
    assert outcome.matched is False
    assert outcome.step.status is Status.NEEDS_MORE_INFORMATION
    assert outcome.step.missing_fact is not None
    assert outcome.step.missing_fact.id == "ai_system"
    assert outcome.step.missing_fact.about == "art:3:1"
    assert "recital:12" in cited(outcome)
    assert all(f.text != "AI system: unknown" for f in outcome.step.facts_used)


def test_a_contested_definition_is_legally_ambiguous_with_in_scope_assumed() -> None:
    outcome = outcome_of(scope_answer(definition(Definition.CONTESTED, guidance=(1, 1, 9))))
    step = outcome.step
    assert outcome.matched is False  # the stricter reading, in scope, keeps the run going
    assert step.status is Status.LEGALLY_AMBIGUOUS
    assert step.open_question is not None
    assert step.open_question.readings[0].startswith("It is an AI system")
    # Passage 1 once; the out-of-range 9 is dropped.
    assert cited(outcome) == ["art:3:1", "recital:12", "art:2:1", "guide:guide-definition:para:40"]
    assert step.missing_fact is None
    assert "Working assumption: it is" in step.decision


@pytest.mark.parametrize("ai_system", [Definition.YES, Definition.CONTESTED])
def test_a_guideline_passage_placing_the_technique_outside_makes_the_definition_contested(
    ai_system: Definition,
) -> None:
    """User rule 2026-09-30: the model never picks a reading against a named passage."""
    answer = scope_answer(
        definition(ai_system), guidance_excludes_technique=excludes_technique(passages=(2,))
    )
    outcome = outcome_of(answer)
    step = outcome.step
    assert outcome.matched is False
    assert step.status is Status.LEGALLY_AMBIGUOUS
    assert step.open_question is not None
    stricter, lenient = step.open_question.readings
    assert "Art. 3(1) and recital 12" in stricter
    assert "(guide:guide-definition:para:41)" in lenient
    assert cited(outcome) == ["art:3:1", "recital:12", "art:2:1", "guide:guide-definition:para:41"]
    guidance = step.citations[-1]
    assert (guidance.law_version, guidance.document_status) == (None, DocumentStatus.FINAL)
    assert "Guidance excludes the technique: yes" in [f.text for f in step.facts_used]


@pytest.mark.parametrize(
    "named",
    [
        excludes_technique(Answer.NO),  # a passage that only mentions the technique
        excludes_technique(Answer.YES, passages=()),  # no passage named
        excludes_technique(Answer.YES, passages=(7,)),  # not a passage the model was given
        excludes_technique(Answer.UNKNOWN),
    ],
)
def test_without_a_named_passage_placing_it_outside_the_definition_stays_decided(
    named: GuidanceFact,
) -> None:
    outcome = outcome_of(scope_answer(guidance_excludes_technique=named))
    assert outcome.step.status is Status.DECIDED
    assert outcome.matched is False
    assert outcome.follow_up_questions == ()
    assert not any(c.provision_id.startswith("guide:") for c in outcome.step.citations)


def test_not_an_ai_system_with_a_named_passage_stays_out_of_scope() -> None:
    answer = scope_answer(
        definition(Definition.NO, guidance=(1,)),
        guidance_excludes_technique=excludes_technique(passages=(1,)),
    )
    outcome = outcome_of(answer)
    assert outcome.matched is True
    assert outcome.step.status is Status.DECIDED
    assert outcome.step.open_question is None
    assert cited(outcome) == ["art:3:1", "recital:12", "guide:guide-definition:para:40"]


def test_a_contested_definition_still_asks_the_open_facts() -> None:
    answer = scope_answer(definition(Definition.CONTESTED), personal_use=key_fact(Answer.UNKNOWN))
    outcome = outcome_of(answer)
    assert outcome.step.status is Status.LEGALLY_AMBIGUOUS
    assert [q.id for q in outcome.follow_up_questions] == ["personal_use"]
    assert "Still to confirm" in outcome.step.decision


def test_an_exclusion_settles_scope_even_when_the_definition_is_open() -> None:
    answer = scope_answer(
        definition(Definition.CONTESTED),
        research_only=key_fact(Answer.YES, EvidenceTag.STATED),
        eu_link=key_fact(Answer.UNKNOWN),
    )
    outcome = outcome_of(answer)
    assert outcome.matched is True
    assert outcome.step.status is Status.DECIDED
    assert outcome.step.missing_fact is None
    assert outcome.follow_up_questions == ()


def test_guidance_in_english_is_marked_english_only_for_a_german_request() -> None:
    outcome = outcome_of(scope_answer(definition(Definition.NO, guidance=(1,))), state(Language.DE))
    guidance = [c for c in outcome.step.citations if c.provision_id.startswith("guide:")]
    assert [c.english_only for c in guidance] == [True]
    assert guidance[0].law_version is None
    assert guidance[0].document_status is DocumentStatus.FINAL
    law = [c for c in outcome.step.citations if not c.provision_id.startswith("guide:")]
    assert {c.language for c in law} == {Language.DE}
    assert outcome.step.decision.startswith("Nicht anwendbar: Die KI-Verordnung gilt nicht.")


def test_german_questions_are_asked_in_german() -> None:
    outcome = outcome_of(scope_answer(eu_link=key_fact(Answer.UNKNOWN)), state(Language.DE))
    assert outcome.follow_up_questions[0].text.startswith("Wird das System in der EU")


def test_a_contested_definition_can_only_be_given_for_the_ai_system_question() -> None:
    with pytest.raises(ValueError, match="eu_link"):
        ScopeAnswer.model_validate(
            {
                **scope_answer().model_dump(),
                "eu_link": {**key_fact().model_dump(), "answer": "contested"},
            }
        )


# --- The graph ----------------------------------------------------------------------------------


def _run(check: CheckOutcome) -> dict[str, Any]:
    scripted = scripted_nodes(Script(checks={StepName.SCOPE: check}))
    graph = build_graph(scripted)
    return graph.invoke(
        {
            "description": TOOL,
            "language": Language.EN,
            "law_version": LawVersion.AMENDED,
            "as_of": AS_OF,
            "answers": {},
            "exclude_source_example_ids": (),
        }
    )


def test_a_decided_out_of_scope_finding_ends_the_run() -> None:
    final = _run(outcome_of(scope_answer(personal_use=key_fact(Answer.YES, EvidenceTag.STATED))))
    assert [s.step for s in final["steps"]] == [StepName.SCOPE]
    assert final["result"].risk_class is RiskClass.OUT_OF_SCOPE
    assert final["result"].role is None


def test_an_ambiguous_scope_step_runs_every_check() -> None:
    final = _run(outcome_of(scope_answer(definition(Definition.CONTESTED))))
    assert tuple(s.step for s in final["steps"]) == STEP_ORDER
    assert final["result"].status is Status.LEGALLY_AMBIGUOUS


# --- Retrieval ----------------------------------------------------------------------------------


def _fake_check(content: str, library: ScopeLibrary | None = None) -> ScopeCheck:
    chat = GenericFakeChatModel(messages=iter([AIMessage(content=content)]))
    return ScopeCheck(_settings(), chat=chat, library=library or FakeLibrary())


def _settings() -> Settings:
    values = {"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def test_the_node_reads_art_3_1_and_art_2_and_passes_the_exclusions_through() -> None:
    library = FakeLibrary()
    _fake_check(scope_answer().model_dump_json(), library)(state(exclude=("hr-ex-001",)))
    assert library.fetched[:2] == ["art:3:1", "art:2"]
    assert TOOL in library.queries[0]
    assert {lookup.exclude_source_example_ids for lookup in library.lookups} == {("hr-ex-001",)}
    assert {lookup.as_of for lookup in library.lookups} == {AS_OF}


REFUSAL_TEXT = "I'm sorry, but I cannot assist with that request."


def _filtered_check(content: str = REFUSAL_TEXT) -> ScopeCheck:
    """The node over a reply the provider's content filter stopped (decision 029)."""
    reply = AIMessage(content=content, response_metadata={"finish_reason": "content_filter"})
    chat = GenericFakeChatModel(messages=iter([reply]))
    return ScopeCheck(_settings(), chat=chat, library=FakeLibrary())


def test_a_provider_refusal_assumes_in_scope_for_a_person_to_review() -> None:
    outcome = _filtered_check()(state())
    step = outcome.step
    assert outcome.matched is False  # in scope, the stricter reading: the run goes on
    assert step.status is Status.NEEDS_MORE_INFORMATION
    assert step.error == "provider_refusal"
    assert step.missing_fact is not None
    assert step.missing_fact.id == "scope_person_review"
    assert outcome.follow_up_questions == (step.missing_fact,)
    assert [c.provision_id for c in step.citations] == ["art:3:1", "art:2"]
    assert step.decision.startswith("The model provider's content filter blocked")


def test_a_refused_scope_step_keeps_the_run_going() -> None:
    final = _run(_filtered_check()(state()))
    assert tuple(s.step for s in final["steps"]) == STEP_ORDER
    assert final["result"].not_assessed == (StepName.SCOPE,)


def test_a_scope_refusal_is_reported_in_german() -> None:
    outcome = _filtered_check()(state(language=Language.DE))
    assert outcome.step.decision.startswith("Der Inhaltsfilter des Modellanbieters")
    assert outcome.step.missing_fact is not None
    assert outcome.step.missing_fact.text.startswith("Bitte lassen Sie")


def test_a_filtered_scope_reply_with_a_usable_answer_is_used() -> None:
    outcome = _filtered_check(scope_answer().model_dump_json())(state())
    assert (outcome.step.status, outcome.step.error) == (Status.DECIDED, None)


def test_the_original_text_is_read_without_a_date() -> None:
    library = FakeLibrary()
    _fake_check(scope_answer().model_dump_json(), library)(state(law_version=LawVersion.ORIGINAL))
    assert {lookup.as_of for lookup in library.lookups} == {None}
    assert {lookup.law_version for lookup in library.lookups} == {LawVersion.ORIGINAL}


def _results(language: Language, *hits: SearchHit) -> SearchResults:
    return SearchResults(
        query="q",
        language=language,
        law_version=LawVersion.AMENDED,
        as_of=AS_OF,
        hits=hits,
        max_distance=None,
        found=bool(hits),
        disclaimer=DISCLAIMER[language],
    )


def test_guidance_search_is_limited_to_the_definition_guidelines_and_falls_back_to_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_search(query: str, language: Language, *args: object, **kwargs: Any) -> SearchResults:
        calls.append({"language": language, **kwargs})
        return _results(language) if language is Language.DE else _results(language, *PASSAGES)

    monkeypatch.setattr(node, "search_ai_act", fake_search)
    lookup = Lookup(Language.DE, LawVersion.AMENDED, AS_OF, ("hr-ex-001",))
    found = CorpusLibrary().definition_guidance("q", lookup)
    assert found == PASSAGES
    assert [call["language"] for call in calls] == [Language.DE, Language.EN]
    for call in calls:
        assert call["max_distance"] is None  # a signal for the engine, never a filter
        assert "include_held_out" not in call
        assert call["exclude_source_example_ids"] == ("hr-ex-001",)
        assert call["doc_keys"] == frozenset({"guide-definition"})  # filtered in the SQL
        assert call["limit"] == node.GUIDANCE_PASSAGES


def test_english_guidance_is_searched_once(monkeypatch: pytest.MonkeyPatch) -> None:
    languages: list[Language] = []

    def fake_search(query: str, language: Language, *args: object, **kwargs: Any) -> SearchResults:
        languages.append(language)
        return _results(language)

    monkeypatch.setattr(node, "search_ai_act", fake_search)
    lookup = Lookup(Language.EN, LawVersion.AMENDED, AS_OF, ())
    assert CorpusLibrary().definition_guidance("q", lookup) == ()
    assert languages == [Language.EN]


# --- The model call -----------------------------------------------------------------------------


def test_the_prompt_puts_instructions_and_law_first_and_the_description_last() -> None:
    law = (provision("art:3:1"), provision("art:2"))
    messages = node.scope_messages(state(), law, PASSAGES)
    assert messages[0].content == node.SCOPE_INSTRUCTIONS
    human = str(messages[-1].content)
    assert human.startswith("The AI Act (amended text):\n\n[art:3:1]")
    assert human.index("Text of art:2") < human.index("1. [guide:guide-definition:para:40]")
    assert human.endswith(TOOL)


def test_the_open_source_exception_names_art_50_and_its_categories() -> None:
    """own-b-10 (user, 2026-09-30): Art. 50's own list, not any app that shows its result."""
    bullet = node.SCOPE_INSTRUCTIONS.split("- open_source_exception")[1].split("\n- ")[0]
    flat = " ".join(bullet.split())
    assert "Art. 50" in flat
    for category in (
        "interact directly with people",
        "synthetic audio, image, video or text",
        "emotion recognition or biometric categorisation",
        "deep fakes",
        "only returns its result to its own user doesn't fall under it",
    ):
        assert category in flat


def test_the_node_is_pinned_to_the_engine_provider() -> None:
    check = ScopeCheck(_settings(), library=FakeLibrary())
    assert check._model.openrouter_provider == {  # pyright: ignore[reportAttributeAccessIssue]
        "data_collection": "deny",
        "zdr": True,
        "order": [LUNA_PROVIDER],
        "allow_fallbacks": False,
    }


@pytest.mark.parametrize("content", ["not json", '{"ai_system": {"answer": "yes"}}'])
def test_a_broken_answer_raises_without_quoting_the_description(content: str) -> None:
    with pytest.raises(ScopeOutputError) as caught:
        _fake_check(content)(state())
    assert TOOL not in str(caught.value)


# --- B5b replay: the own out-of-scope cases, once their recordings exist ------------------------

SCOPE_CASES_DIR = CASES_DIR / CaseSet.OWN.value / "b"
RECORD_COMMAND = "uv run pytest tests/engine/nodes/test_scope.py -k b5b --record-mode=once"


def _scope_cases() -> list[BenchmarkCase]:
    """The B5b cases (every YAML file under `own/b/`), or none while the folder doesn't exist."""
    paths = sorted(SCOPE_CASES_DIR.rglob("*.yaml")) if SCOPE_CASES_DIR.is_dir() else []
    return [case for path in paths for case in load_yaml_file(path)]


class RecordedScopeLibrary:
    """A `ScopeLibrary` over the replay's `CorpusRecording`."""

    def __init__(self, recording: CorpusRecording[ScopeLibrary]) -> None:
        self._recording = recording

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        return self._recording.provision(
            provision_id, lookup, lambda live: live.provision(provision_id, lookup)
        )

    def definition_guidance(self, query: str, lookup: Lookup) -> tuple[SearchHit, ...]:
        call = {"definition_guidance": query, **lookup_call(lookup)}
        return self._recording.hits(call, lambda live: live.definition_guidance(query, lookup))


B5B_CASES = _scope_cases()

KNOWN_GAPS: dict[str, str] = {
    "own-b-05-regression-loan-scorecard": (
        "the model resolves guide-definition para 42 to the label's reading A (para 42 concerns "
        "optimisation, not scoring) instead of flagging the definition as contested; class "
        "correct, status decided instead of legally_ambiguous (user, 2026-09-30)"
    ),
}
"""Recorded cases whose scope outcome differs from the label, with the reason; each fails when
it starts matching, so the entry is removed."""


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    B5B_CASES or [pytest.param(None, marks=pytest.mark.skip(reason="B5b cases not merged yet"))],
    ids=lambda case: case.id if isinstance(case, BenchmarkCase) else "no-cases",
)
def test_b5b_case_replay(
    case: BenchmarkCase,
    luna_settings: Settings,
    record_mode: str,
    vcr_cassette_dir: str,
    default_cassette_name: str,
) -> None:
    """Each B5b case's scope outcome against its label. Replays the model reply from
    `recordings/engine/nodes/test_scope/test_b5b_case_replay[<id>].yaml` and the corpus from
    the `.corpus.json` next to it; record both with `RECORD_COMMAND` (needs the loaded corpus
    and a real key)."""
    label = case.label
    assert isinstance(label, CaseLabel)
    with corpus_recording(
        vcr_cassette_dir,
        default_cassette_name,
        record_mode,
        RECORD_COMMAND,
        lambda: nullcontext(CorpusLibrary()),
    ) as recording:
        library = RecordedScopeLibrary(recording)
        outcome = ScopeCheck(luna_settings, library=library)(replay_state(case, AS_OF))
    matches = scope_matches(outcome, case)
    gap = KNOWN_GAPS.get(case.id)
    if gap is not None:
        if matches:
            pytest.fail(f"{case.id} now matches its label; remove it from KNOWN_GAPS")
        pytest.xfail(gap)
    assert matches, (outcome.matched, outcome.step.status, cited(outcome), outcome.step.decision)
