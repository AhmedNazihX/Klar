"""P7: `answer_question` with a fake search and a scripted model. A question about compliance, or
one the corpus doesn't cover, never reaches the model; an answer cites only sources it was given;
a question about a result is answered with that result's own citations."""

import json
from datetime import date
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import Field

from aiact.llm.structured import ChatRoute
from aiact.qa import AnswerKind, QaAnswer, answer_question, shown_text
from aiact.qa.answer import REPLY_FORMAT, prompt, source_text
from aiact.qa.models import ModelReply
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import (
    DISCLAIMER_DE,
    DISCLAIMER_EN,
    ClassificationResult,
    DocumentStatus,
    Language,
    LawVersion,
)
from tests.schemas.worked_example import DOCUMENT_ID, worked_example_result

TODAY = date(2026, 10, 10)

OUTSIDE_EN = (
    "That's outside what I can answer. I cover the AI Act and the Commission's guidance on it, "
    "and they don't answer this question."
)
OUTSIDE_DE = (
    "Das kann ich nicht beantworten. Ich behandle die KI-Verordnung und die Leitlinien der "
    "Kommission dazu, und diese Texte beantworten die Frage nicht."
)
COMPLIANCE_EN = (
    "That's outside what I can answer. I cover the AI Act and the Commission's guidance on it, "
    "and I don't say whether a company is compliant with any law.\n\n"
    "Your lawyer or compliance officer is the right person to ask."
)
COMPLIANCE_DE = (
    "Das kann ich nicht beantworten. Ich behandle die KI-Verordnung und die Leitlinien der "
    "Kommission dazu, und ich sage nicht, ob ein Unternehmen ein Gesetz einhält.\n\n"
    "Fragen Sie dazu Ihre Rechtsberatung oder Ihre Compliance-Abteilung."
)


def hit(provision_id: str, text: str, *, doc_key: str = "ai-act-consolidated") -> SearchHit:
    is_law = doc_key == "ai-act-consolidated"
    return SearchHit(
        provision_id=provision_id,
        doc_key=doc_key,
        document_title="AI Act (consolidated)" if is_law else "Guidelines",
        doc_type="law" if is_law else "guideline",
        law_version=LawVersion.AMENDED if is_law else None,
        status=DocumentStatus.CONSOLIDATED if is_law else DocumentStatus.FINAL,
        language=Language.EN,
        heading=None,
        text=text,
        valid_from=date(2024, 8, 1),
        valid_to=None,
        score=0.05,
        vector_rank=1,
        keyword_rank=None,
        similarity=0.8,
        keyword_idf=None,
    )


ART_3_4 = hit("art:3:4", "'deployer' means a natural or legal person ... using an AI system.")
ART_25_1 = hit(
    "art:25:1", "Any distributor, importer, deployer ... shall be considered a provider."
)
GUIDE = hit("sec:2", "The definition guidelines on deployers.", doc_key="guide-definition")
DEFAULT_HITS = (ART_3_4, ART_25_1, GUIDE)


class FakeSearch:
    """Answers like `search_ai_act`, noting each call."""

    def __init__(self, hits: tuple[SearchHit, ...] = DEFAULT_HITS, *, found: bool = True) -> None:
        self.hits = hits
        self.found = found
        self.calls: list[tuple[str, Language, LawVersion, date | None]] = []

    def __call__(
        self, query: str, language: Language, law_version: LawVersion, as_of: date | None
    ) -> SearchResults:
        self.calls.append((query, language, law_version, as_of))
        return SearchResults(
            query=query,
            language=language,
            law_version=law_version,
            as_of=None if law_version is LawVersion.ORIGINAL else as_of or TODAY,
            hits=self.hits,
            max_distance=0.3,
            found=self.found,
            disclaimer=DISCLAIMER_EN,
        )


class RecordingChat(GenericFakeChatModel):
    """A scripted model that notes each request: its messages and call options."""

    seen: list[tuple[list[BaseMessage], dict[str, object]]] = Field(default_factory=list)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen.append((messages, kwargs))
        return super()._generate(messages, stop, run_manager, **kwargs)


def model(kind: str = "answered", answer: str = "", cited: tuple[int, ...] = ()) -> RecordingChat:
    reply = json.dumps({"kind": kind, "answer": answer, "cited": list(cited)})
    return RecordingChat(messages=iter([AIMessage(content=reply)]))


def ask(
    question: str,
    chat: RecordingChat,
    search: FakeSearch | None = None,
    *,
    language: Language = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
    result: ClassificationResult | None = None,
) -> QaAnswer:
    return answer_question(
        question,
        language,
        law_version=law_version,
        result=result,
        search=search or FakeSearch(),
        route=ChatRoute(chat),
    )


# --- Compliance and the corpus' edge: fixed answers, no model call -------------------------------


@pytest.mark.parametrize(
    ("question", "language", "text", "disclaimer"),
    [
        ("Are we GDPR compliant?", Language.EN, COMPLIANCE_EN, DISCLAIMER_EN),
        ("Sind wir mit unserem Chatbot konform?", Language.DE, COMPLIANCE_DE, DISCLAIMER_DE),
    ],
)
def test_a_compliance_question_gets_the_fixed_answer_without_search_or_model(
    question: str, language: Language, text: str, disclaimer: str
) -> None:
    chat, search = model(), FakeSearch()
    answer = ask(question, chat, search, language=language)
    assert (answer.kind, answer.answer, answer.citations) == (AnswerKind.COMPLIANCE, text, ())
    assert answer.disclaimer == disclaimer
    assert (answer.law_version, answer.language) == (LawVersion.AMENDED, language)
    assert answer.as_of is not None
    assert search.calls == [] and chat.seen == []


def test_a_compliance_question_under_the_original_text_has_no_date() -> None:
    answer = ask("Are we compliant?", model(), law_version=LawVersion.ORIGINAL)
    assert (answer.law_version, answer.as_of) == (LawVersion.ORIGINAL, None)


@pytest.mark.parametrize(
    ("language", "text"), [(Language.EN, OUTSIDE_EN), (Language.DE, OUTSIDE_DE)]
)
def test_nothing_relevant_found_gets_the_outside_answer_without_a_model_call(
    language: Language, text: str
) -> None:
    """C8: when `found` is False the weak hits are never cited, and the model isn't asked."""
    chat, search = model(), FakeSearch(found=False)
    answer = ask("How do I reset my laptop password?", chat, search, language=language)
    assert (answer.kind, answer.answer, answer.citations) == (AnswerKind.OUTSIDE_CORPUS, text, ())
    assert answer.as_of == TODAY
    assert len(search.calls) == 1 and chat.seen == []


def test_no_hits_at_all_gets_the_outside_answer() -> None:
    chat = model()
    answer = ask("Anything?", chat, FakeSearch(hits=()))
    assert answer.kind is AnswerKind.OUTSIDE_CORPUS and chat.seen == []


# --- Answers ------------------------------------------------------------------------------------


def test_an_answer_cites_the_sources_it_names_in_the_order_named() -> None:
    chat = model(answer="A deployer uses an AI system for work.", cited=(2, 1, 2, 9))
    answer = ask("What counts as a deployer?", chat)
    assert answer.kind is AnswerKind.ANSWERED
    assert answer.answer == "A deployer uses an AI system for work."
    # Each cited once, in the order cited; a number outside the sources is dropped.
    assert [c.provision_id for c in answer.citations] == ["art:25:1", "art:3:4"]
    first = answer.citations[1]
    assert (first.document_id, first.quote, first.law_version) == (
        "ai-act-consolidated",
        ART_3_4.text,
        LawVersion.AMENDED,
    )
    assert first.document_status is DocumentStatus.CONSOLIDATED
    assert (answer.disclaimer, answer.as_of) == (DISCLAIMER_EN, TODAY)


def test_a_guideline_cited_keeps_its_document_and_no_law_version() -> None:
    answer = ask("Deployers?", model(answer="See the guidelines.", cited=(3,)))
    (citation,) = answer.citations
    assert (citation.document_id, citation.provision_id, citation.law_version) == (
        "guide-definition",
        "sec:2",
        None,
    )
    assert citation.document_status is DocumentStatus.FINAL


@pytest.mark.parametrize(
    ("kind", "text"),
    [("outside_corpus", OUTSIDE_EN), ("compliance", COMPLIANCE_EN)],
)
def test_a_model_that_doesnt_answer_gets_the_fixed_answer(kind: str, text: str) -> None:
    """A question close in topic (the DSA, the Product Liability Directive) passes the search's
    cut-off; the model then finds the sources don't answer it. Its own words are never shown."""
    chat = model(kind=kind, answer="Under the DSA, every year.", cited=(1,))
    answer = ask("How often must a very large platform assess its risks?", chat)
    assert (answer.kind.value, answer.answer, answer.citations) == (kind, text, ())


@pytest.mark.parametrize(
    ("answer_text", "cited"), [("An answer.", ()), ("An answer.", (0, 4)), ("  ", (1,))]
)
def test_an_answer_without_a_source_it_was_given_or_without_text_isnt_shown(
    answer_text: str, cited: tuple[int, ...]
) -> None:
    answer = ask("What counts as a deployer?", model(answer=answer_text, cited=cited))
    assert (answer.kind, answer.answer, answer.citations) == (
        AnswerKind.OUTSIDE_CORPUS,
        OUTSIDE_EN,
        (),
    )


def test_the_question_is_searched_in_its_language_and_law_version_on_today() -> None:
    search = FakeSearch()
    ask("Was ist ein Betreiber?", model(answer="Ein Betreiber ...", cited=(1,)), search,
        language=Language.DE, law_version=LawVersion.ORIGINAL)  # fmt: skip
    assert search.calls == [("Was ist ein Betreiber?", Language.DE, LawVersion.ORIGINAL, None)]


def test_a_german_answer_carries_the_german_notice() -> None:
    answer = ask("Was ist ein Betreiber?", model(answer="Ein Betreiber ...", cited=(1,)),
                 language=Language.DE)  # fmt: skip
    assert (answer.language, answer.disclaimer) == (Language.DE, DISCLAIMER_DE)


def test_the_model_gets_the_numbered_sources_the_instructions_and_the_reply_format() -> None:
    chat = model(answer="An answer.", cited=(1,))
    ask("What counts as a deployer?", chat, language=Language.DE)
    ((messages, options),) = chat.seen
    system, human = (message.text for message in messages)
    assert "in German" in system
    assert '"compliance"' in system and '"outside_corpus"' in system
    assert "Klar never says whether anyone complies" in system
    assert "The user asks about a classification result" not in system
    assert human == (
        "Sources:\n"
        f"[1] [art:3:4] AI Act (consolidated)\n{ART_3_4.text}\n\n"
        f"[2] [art:25:1] AI Act (consolidated)\n{ART_25_1.text}\n\n"
        f"[3] [sec:2] Guidelines\n{GUIDE.text}\n\n"
        "Question: What counts as a deployer?"
    )
    assert options["response_format"] == REPLY_FORMAT


def test_the_reply_format_asks_for_kind_answer_and_cited_numbers() -> None:
    schema = REPLY_FORMAT["json_schema"]
    assert isinstance(schema, dict) and schema["name"] == "qa_answer"
    body = schema["schema"]
    assert body["required"] == ["kind", "answer", "cited"]
    assert body["additionalProperties"] is False


def test_a_source_reads_like_v6s_context() -> None:
    """V6 measures faithfulness on contexts written `[id] title / heading / text`
    (`ragas_metrics.context_text`); the product words its sources the same way."""
    assert source_text("art:50:1", "AI Act", "Article 50", "Text.") == (
        "[art:50:1] AI Act\nArticle 50\nText."
    )
    assert source_text("art:50:1", "AI Act", None, "Text.") == "[art:50:1] AI Act\nText."


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (ModelReply(kind=AnswerKind.ANSWERED, answer=" Yes. ", cited=(1,)), "Yes."),
        (ModelReply(kind=AnswerKind.ANSWERED, answer="Yes.", cited=(3,)), OUTSIDE_EN),
        (ModelReply(kind=AnswerKind.OUTSIDE_CORPUS, answer="", cited=()), OUTSIDE_EN),
        (ModelReply(kind=AnswerKind.COMPLIANCE, answer="", cited=()), COMPLIANCE_EN),
    ],
)
def test_the_shown_text_is_the_answer_or_the_fixed_one(reply: ModelReply, expected: str) -> None:
    assert shown_text(reply, 2, Language.EN) == expected


# --- A question about a result (DoD) --------------------------------------------------------------


def test_a_question_about_a_result_is_answered_with_that_results_citations() -> None:
    result = worked_example_result()
    result_citations = {
        (c.document_id, c.provision_id): c for step in result.steps for c in step.citations
    }
    count = len(result_citations)
    chat = model(answer="Yes: you must inform the people it screens.", cited=(1, 2))
    answer = ask("Do we have to tell applicants that AI was used?", chat, result=result)

    assert answer.kind is AnswerKind.ANSWERED
    assert answer.citations == tuple(list(result_citations.values())[:2])
    assert all(c.document_id == DOCUMENT_ID for c in answer.citations)
    # The result's citations come first, each once; the hits follow without repeating them.
    ((messages, _),) = chat.seen
    human = messages[1].text
    first_id = next(iter(result_citations))[1]
    assert f"[1] [{first_id}] {DOCUMENT_ID}\n" in human
    assert f"[{count + 1}] [art:3:4]" in human
    assert "The user asks about a classification result" in messages[0].text


def test_a_question_about_a_result_shows_the_model_its_class_role_and_steps() -> None:
    chat = model(answer="An answer.", cited=(1,))
    ask("Why is it high-risk?", chat, result=worked_example_result())
    human = chat.seen[0][0][1].text
    assert human.startswith(
        "The result asked about (the AI Act as amended by the Digital Omnibus):\n"
        "- Class: high_risk\n- Role: deployer\n- Status: decided\n- Annex point: annex:III:4:a\n"
    )
    for step in worked_example_result().steps:
        assert f"- {step.step.value}: {step.decision}" in human


def test_a_question_about_a_result_reads_the_results_law_version_and_date() -> None:
    result = worked_example_result()
    search = FakeSearch()
    answer = ask("Why?", model(answer="Because.", cited=(1,)), search, result=result,
                 law_version=LawVersion.ORIGINAL)  # fmt: skip
    assert search.calls == [("Why?", Language.EN, LawVersion.AMENDED, result.as_of)]
    assert (answer.law_version, answer.as_of) == (LawVersion.AMENDED, result.as_of)


def test_a_question_about_an_original_text_result_reads_the_original_text() -> None:
    result = worked_example_result().model_copy(update={"law_version": LawVersion.ORIGINAL})
    search = FakeSearch()
    answer = ask("Why?", model(answer="Because.", cited=(1,)), search, result=result)
    assert search.calls == [("Why?", Language.EN, LawVersion.ORIGINAL, None)]
    assert (answer.law_version, answer.as_of) == (LawVersion.ORIGINAL, None)


def test_a_question_about_a_result_is_answered_from_its_citations_when_search_finds_nothing() -> (
    None
):
    chat = model(answer="Because of Annex III.", cited=(1,))
    answer = ask("Why?", chat, FakeSearch(found=False), result=worked_example_result())
    assert answer.kind is AnswerKind.ANSWERED and len(chat.seen) == 1
    human = chat.seen[0][0][1].text
    assert "[art:3:4]" not in human  # weak hits are never put before the model


def test_a_compliance_question_about_a_result_is_still_refused() -> None:
    chat = model()
    answer = ask("Is our tool compliant now?", chat, result=worked_example_result())
    assert answer.kind is AnswerKind.COMPLIANCE and chat.seen == []


def test_the_prompt_without_a_result_has_no_result_block() -> None:
    _, human = prompt("Q?", Language.EN, ["[a] T\nx"])
    assert human.text == "Sources:\n[1] [a] T\nx\n\nQuestion: Q?"
