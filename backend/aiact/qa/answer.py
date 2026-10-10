"""`answer_question`: a question about the AI Act, or about one result, answered from the
corpus with the provisions it rests on (P7; INIT > Scope, Q&A about results).

In order, each step able to end it:
1. A question asking whether someone complies ("Are we compliant?", `scope`) gets the fixed
   compliance answer: no search, no model call.
2. The question is searched as V6 measures it (`search_ai_act`, the top `QA_TOP_K` hits, the
   `SEARCH_MAX_DISTANCE` cut-off, provisions named by number pinned; held-out examples never).
   Hits count only when `SearchResults.found` is True (C8); weak hits are never shown.
3. A question about a result also gets the result's own citations, first, so its answer cites
   what the result cites (DoD). Its class, role and each step's decision go into the prompt.
4. Nothing to answer from: the fixed outside-the-corpus answer, without a model call.
5. Otherwise the engine model answers from the numbered sources alone (`generate`). It may still
   find the sources don't answer (another law close in topic) or that the question is about
   compliance; either way the answer is the fixed one, never the model's words. An answer citing
   no source it was given is not shown either: every answer rests on at least one provision.

The sources are numbered in the prompt and the model cites numbers, so a guideline section and
an article with the same id can't be confused. Each cited source comes back as a `Citation`
with its quoted text; a result's citation as the result has it.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from aiact.llm.structured import ChatRoute, json_schema_format
from aiact.qa.models import AnswerKind, ModelReply, QaAnswer
from aiact.qa.scope import is_compliance_question
from aiact.qa.texts import (
    INSTRUCTIONS,
    LANGUAGE_NAMES,
    NOT_ANSWERED,
    QUESTION,
    RESULT_BLOCK,
    RESULT_INSTRUCTIONS,
)
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import (
    DISCLAIMER,
    Citation,
    ClassificationResult,
    Language,
    LawVersion,
)

QA_TOP_K = 5
"""Hits per question, as V6 measures them (`ragas_metrics.DEFAULT_TOP_K`)."""
MAX_RESULT_CITATIONS = 12
"""The most of a result's citations put before the model: a result cites about six to ten."""
REPLY_FORMAT = json_schema_format("qa_answer", ModelReply)
LAW_TEXT_NAMES = {
    LawVersion.AMENDED: "the AI Act as amended by the Digital Omnibus",
    LawVersion.ORIGINAL: "the original AI Act of 2024",
}
"""The text a result was checked against, as its block in the prompt names it."""

Searcher = Callable[[str, Language, LawVersion, date | None], SearchResults]
"""Searches the corpus for a question: (question, language, law version, as_of)."""


@dataclass(frozen=True)
class Source:
    """One numbered source in the prompt: the citation it becomes, and its text for the model."""

    citation: Citation
    text: str


def answer_question(
    question: str,
    language: Language,
    *,
    law_version: LawVersion = LawVersion.AMENDED,
    result: ClassificationResult | None = None,
    search: Searcher,
    route: ChatRoute,
) -> QaAnswer:
    """The answer to `question` in `language` (see the module docstring). A question about a
    `result` is read under the result's law version and date. Raises what the search and the
    model call raise (`ProviderRefusalError`, `ValidationError` for a reply that doesn't fit)."""
    version, as_of = _reading(law_version, result)
    if is_compliance_question(question):
        return not_answered(AnswerKind.COMPLIANCE, language, version, _shown_date(version, as_of))
    found = search(question, language, version, as_of)
    hits = found.hits if found.found else ()
    sources = _sources(result, hits)
    if not sources:
        return not_answered(AnswerKind.OUTSIDE_CORPUS, language, version, found.as_of)
    reply = generate(
        question,
        language,
        [source.text for source in sources],
        route,
        about_result=_result_block(result) if result is not None else None,
    )
    return _answer(reply, sources, language, version, found.as_of)


def generate(
    question: str,
    language: Language,
    sources: Sequence[str],
    route: ChatRoute,
    *,
    about_result: str | None = None,
) -> ModelReply:
    """The model's reply to `question` from `sources` alone, numbered from 1 in the order given;
    V6 calls this with its own contexts to measure faithfulness on these answers."""
    return route.ask(prompt(question, language, sources, about_result), REPLY_FORMAT, ModelReply)


def prompt(
    question: str, language: Language, sources: Sequence[str], about_result: str | None = None
) -> list[BaseMessage]:
    """The system instructions and the question with its numbered sources."""
    instructions = INSTRUCTIONS.format(language_name=LANGUAGE_NAMES[language])
    if about_result is not None:
        instructions += RESULT_INSTRUCTIONS
    numbered = "\n\n".join(f"[{number}] {text}" for number, text in enumerate(sources, start=1))
    return [
        SystemMessage(instructions),
        HumanMessage(
            QUESTION.format(result=about_result or "", sources=numbered, question=question)
        ),
    ]


def not_answered(
    kind: AnswerKind, language: Language, law_version: LawVersion, as_of: date | None
) -> QaAnswer:
    """The fixed answer for a question not answered, with no citation."""
    return QaAnswer(
        kind=kind,
        answer=NOT_ANSWERED[kind][language],
        citations=(),
        language=language,
        law_version=law_version,
        as_of=as_of,
        disclaimer=DISCLAIMER[language],
    )


def reply_outcome(reply: ModelReply, source_count: int) -> tuple[AnswerKind, tuple[int, ...]]:
    """What the user is shown for `reply`: its kind and the indexes (from 0) of the sources it
    cites, each once, in the order cited. A reply that isn't an answer cites nothing; an answer
    that is empty or cites no source it was given (of `source_count`) counts as outside the
    corpus, since every answer rests on at least one provision."""
    if reply.kind is not AnswerKind.ANSWERED:
        return reply.kind, ()
    cited = tuple(
        number - 1 for number in dict.fromkeys(reply.cited) if 1 <= number <= source_count
    )
    if not cited or not reply.answer.strip():
        return AnswerKind.OUTSIDE_CORPUS, ()
    return AnswerKind.ANSWERED, cited


def shown_text(reply: ModelReply, source_count: int, language: Language) -> str:
    """The answer's text as the user is shown it: the model's answer, or the fixed one."""
    kind, _ = reply_outcome(reply, source_count)
    if kind is AnswerKind.ANSWERED:
        return reply.answer.strip()
    return NOT_ANSWERED[kind][language]


def source_text(provision_id: str, title: str, heading: str | None, text: str) -> str:
    """A source as the model reads it: its provision id and document, then its heading and text;
    the form V6's contexts take (`ragas_metrics.context_text`), so V6 measures these answers on
    the sources as the product words them."""
    lines = [f"[{provision_id}] {title}", heading, text]
    return "\n".join(line for line in lines if line)


def _reading(
    law_version: LawVersion, result: ClassificationResult | None
) -> tuple[LawVersion, date | None]:
    """The law version and date to read: the result's own, or the version asked on today (the
    search's default); the original text has no date."""
    if result is None:
        return law_version, None
    if result.law_version is LawVersion.ORIGINAL:
        return LawVersion.ORIGINAL, None
    return LawVersion.AMENDED, result.as_of


def _shown_date(version: LawVersion, as_of: date | None) -> date | None:
    if version is LawVersion.ORIGINAL:
        return None
    return as_of or date.today()


def _sources(result: ClassificationResult | None, hits: Sequence[SearchHit]) -> list[Source]:
    """The result's citations (each provision once), then the hits it doesn't already cite."""
    sources = [_result_source(citation) for citation in _result_citations(result)]
    seen = {(source.citation.document_id, source.citation.provision_id) for source in sources}
    for hit in hits:
        if (hit.doc_key, hit.provision_id) not in seen:
            seen.add((hit.doc_key, hit.provision_id))
            sources.append(_hit_source(hit))
    return sources


def _result_citations(result: ClassificationResult | None) -> list[Citation]:
    if result is None:
        return []
    citations: dict[tuple[str, str], Citation] = {}
    for step in result.steps:
        for citation in step.citations:
            citations.setdefault((citation.document_id, citation.provision_id), citation)
    return list(citations.values())[:MAX_RESULT_CITATIONS]


def _result_source(citation: Citation) -> Source:
    text = source_text(citation.provision_id, citation.document_id, None, citation.quote)
    return Source(citation, text)


def _hit_source(hit: SearchHit) -> Source:
    citation = Citation(
        provision_id=hit.provision_id,
        document_id=hit.doc_key,
        law_version=hit.law_version,
        document_status=hit.status,
        language=hit.language,
        quote=hit.text,
    )
    return Source(
        citation, source_text(hit.provision_id, hit.document_title, hit.heading, hit.text)
    )


def _result_block(result: ClassificationResult) -> str:
    """The result as the prompt shows it: its class, role, Annex point and status, then each
    step's decision with the provisions it cites."""
    lines = [
        f"- Class: {result.risk_class.value if result.risk_class else 'none yet'}",
        f"- Role: {result.role.value if result.role else 'not decided'}",
        f"- Status: {result.status.value}",
    ]
    if result.annex_point:
        lines.append(f"- Annex point: {result.annex_point}")
    for step in result.steps:
        cited = ", ".join(dict.fromkeys(citation.provision_id for citation in step.citations))
        lines.append(f"- {step.step.value}: {step.decision}" + (f" ({cited})" if cited else ""))
    return RESULT_BLOCK.format(law_text=LAW_TEXT_NAMES[result.law_version], lines="\n".join(lines))


def _answer(
    reply: ModelReply,
    sources: Sequence[Source],
    language: Language,
    version: LawVersion,
    as_of: date | None,
) -> QaAnswer:
    """The model's reply as the answer (`reply_outcome`): its cited sources' citations, in the
    order cited, or the fixed answer."""
    kind, cited = reply_outcome(reply, len(sources))
    if kind is not AnswerKind.ANSWERED:
        return not_answered(kind, language, version, as_of)
    return QaAnswer(
        kind=kind,
        answer=reply.answer.strip(),
        citations=tuple(sources[index].citation for index in cited),
        language=language,
        law_version=version,
        as_of=as_of,
        disclaimer=DISCLAIMER[language],
    )
