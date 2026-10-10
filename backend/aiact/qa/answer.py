"""`answer_question`: a question about the AI Act, or about one result, answered from the
corpus with the provisions it rests on (P7; INIT > Scope, Q&A about results).

In order, each step able to end it:
1. A question asking whether someone complies ("Are we compliant?", `scope`) gets the fixed
   compliance answer: no search, no model call.
2. The question is searched as V6 measures it (`search_ai_act`, the top `QA_TOP_K` hits, the
   `SEARCH_MAX_DISTANCE` cut-off, provisions named by number pinned; held-out examples never).
   Hits count only when `SearchResults.found` is True (C8); weak hits are never shown.
3. A question about a result also gets the result's own citations, first, so its answer cites
   what the result cites (DoD). The posted result is only checked against the contract (decision
   031), so each citation is quoted again from the corpus by its document, provision, law version
   and language (`ResultQuotes`); one the corpus doesn't have is dropped, and the posted quote is
   never put before the model or returned. Its class, role, Annex point and each step's decision
   go into the prompt, each decision and the whole block capped in length.
4. Nothing to answer from: the fixed outside-the-corpus answer, without a model call.
5. Otherwise the engine model answers from the numbered sources alone (`generate`), on the
   refusal route (decision 033). It may still find the sources don't answer (another law close in
   topic) or that the question is about compliance; either way the answer is the fixed one, never
   the model's words. An answer citing no source it was given is not shown either: every answer
   rests on at least one provision. A question both models refuse gets the fixed refused answer;
   any other failure of the model call is a `ModelCallError`.

The sources are numbered in the prompt and the model cites numbers, so a guideline section and
an article with the same id can't be confused. The model is told to keep the numbers out of its
text, and any it leaves there are taken out (`without_source_numbers`): they would not match the
citations shown. Each cited source comes back as a `Citation` with its corpus text.
"""

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

import httpx
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from openrouter.errors import NoResponseError, OpenRouterError, ResponseValidationError

from aiact.llm.structured import ChatRoute, ProviderRefusalError, json_schema_format
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
from aiact.retrieval.provisions import PROVISION_ID_RE
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import (
    DISCLAIMER,
    Citation,
    ClassificationResult,
    Language,
    LawVersion,
)

logger = logging.getLogger(__name__)

QA_TOP_K = 5
"""Hits per question, as V6 measures them (`ragas_metrics.DEFAULT_TOP_K`)."""
MAX_RESULT_CITATIONS = 12
"""The most of a result's citations put before the model: a result cites about six to ten."""
MAX_DECISION_CHARS = 600
"""The most of one step's decision put before the model: an engine decision is one to three
sentences (the worked example's longest is under 100 characters)."""
MAX_RESULT_BLOCK_CHARS = 3000
"""The most of a result's lines put before the model; steps past it are left out. A posted
result is bounded only by the body limit and the contract (decision 031), and six steps of
`MAX_DECISION_CHARS` would pass this; the worked example's block is under 600 characters."""
TRUNCATED = "…"
REPLY_FORMAT = json_schema_format("qa_answer", ModelReply)
MODEL_FAILURES: tuple[type[Exception], ...] = (
    ValueError,
    OpenRouterError,
    NoResponseError,
    ResponseValidationError,
    httpx.HTTPError,
)
"""What the model call raises when it fails: a reply that doesn't fit (`ValidationError`, a
`ValueError`), the provider's error (ChatOpenRouter raises it as a plain `ValueError`, the SDK as
`OpenRouterError`), no response, or the transport's error."""
_NUMBERS = r"\d+(?:\s*(?:[,;\u2013-]|and|und)\s*\d+)*"
"""One number, or several each after a comma, a semicolon, a dash (en or hyphen), "and" or "und"."""
_MARKER = rf"(?:\[\s*{_NUMBERS}\s*\]|\(\s*(?:sources?|quellen?)\s*{_NUMBERS}\s*\.?\s*\))"
SOURCE_NUMBERS = re.compile(rf"^{_MARKER}[ \t]*|[ \t]*{_MARKER}", re.IGNORECASE | re.MULTILINE)
"""A reference to the prompt's numbered sources left in the answer's text, in the two forms that
can't be a legal reference: numbers in square brackets ("[1]", "[1, 2]") and numbers named as
sources ("(Sources 6-8.)", "(Quelle 3)"). Numbers in plain parentheses always stay ("Article
6 (2, 3)", "Annex III (1\u20138)"): the prompt tells the model not to write them. Only the spaces
and tabs next to a marker go with it, so line and paragraph breaks stay."""
LAW_TEXT_NAMES = {
    LawVersion.AMENDED: "the AI Act as amended by the Digital Omnibus",
    LawVersion.ORIGINAL: "the original AI Act of 2024",
}
"""The text a result was checked against, as its block in the prompt names it."""

Searcher = Callable[[str, Language, LawVersion, date | None], SearchResults]
"""Searches the corpus for a question: (question, language, law version, as_of)."""
ResultQuotes = Callable[[Sequence[Citation], LawVersion, date | None], tuple[Citation, ...]]
"""Quotes a posted result's citations again from the corpus, read under the result's law version
on its date (None for the original text): each one the corpus has, by its document, provision,
law version and language, with the corpus's text; the others are dropped."""


class ModelCallError(RuntimeError):
    """The model call failed (`MODEL_FAILURES`; a refusal is the refused answer instead). It
    carries the failure's type only, never the reply or the request."""


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
    quotes: ResultQuotes | None = None,
) -> QaAnswer:
    """The answer to `question` in `language` (see the module docstring). A question about a
    `result` is read under the result's law version and date, its citations quoted again by
    `quotes` (which it needs: ValueError without). Raises what the search raises, and
    `ModelCallError` when the model call fails."""
    if result is not None and quotes is None:
        raise ValueError("a question about a result needs the corpus's quotes")
    version, as_of = _reading(law_version, result)
    if is_compliance_question(question):
        return not_answered(AnswerKind.COMPLIANCE, language, version, _shown_date(version, as_of))
    found = search(question, language, version, as_of)
    hits = found.hits if found.found else ()
    quoted = quotes(_result_citations(result), version, as_of) if quotes and result else ()
    sources = _sources(quoted, hits)
    if not sources:
        return not_answered(AnswerKind.OUTSIDE_CORPUS, language, version, found.as_of)
    about = _result_block(result, quoted) if result is not None else None
    try:
        reply = generate(question, language, [source.text for source in sources], route, about)
    except ProviderRefusalError:
        return not_answered(AnswerKind.REFUSED, language, version, found.as_of)
    except MODEL_FAILURES as exc:
        logger.error("question model call failed: %s", type(exc).__name__)
        raise ModelCallError(type(exc).__name__) from None
    return _answer(reply, sources, language, version, found.as_of)


def generate(
    question: str,
    language: Language,
    sources: Sequence[str],
    route: ChatRoute,
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
    if not cited or not without_source_numbers(reply.answer, source_count):
        return AnswerKind.OUTSIDE_CORPUS, ()
    return AnswerKind.ANSWERED, cited


def shown_text(reply: ModelReply, source_count: int, language: Language) -> str:
    """The answer's text as the user is shown it: the model's answer without source numbers, or
    the fixed one."""
    kind, _ = reply_outcome(reply, source_count)
    if kind is AnswerKind.ANSWERED:
        return without_source_numbers(reply.answer, source_count)
    return NOT_ANSWERED[kind][language]


def without_source_numbers(text: str, source_count: int) -> str:
    """`text` trimmed, with the references to numbered sources taken out (`SOURCE_NUMBERS`). A
    number in square brackets goes only when each of its numbers names one of the `source_count`
    sources: "[7]" after two sources is not a reference to them, and stays."""

    def strip(marker: re.Match[str]) -> str:
        if marker.group().lstrip().startswith("["):
            numbers = (int(number) for number in re.findall(r"\d+", marker.group()))
            if not all(1 <= number <= source_count for number in numbers):
                return marker.group()
        return ""

    return SOURCE_NUMBERS.sub(strip, text).strip()


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


def _sources(quoted: Sequence[Citation], hits: Sequence[SearchHit]) -> list[Source]:
    """The result's citations as the corpus quotes them, then the hits they don't already cite."""
    sources = [_result_source(citation) for citation in quoted]
    seen = {(source.citation.document_id, source.citation.provision_id) for source in sources}
    for hit in hits:
        if (hit.doc_key, hit.provision_id) not in seen:
            seen.add((hit.doc_key, hit.provision_id))
            sources.append(_hit_source(hit))
    return sources


def _result_citations(result: ClassificationResult | None) -> list[Citation]:
    """The result's citations, each provision once, at most `MAX_RESULT_CITATIONS`."""
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


def _result_block(result: ClassificationResult, quoted: Sequence[Citation]) -> str:
    """The result as the prompt shows it: its class, role, Annex point and status, then each
    step's decision (at most `MAX_DECISION_CHARS`) with the provisions it cites that the corpus
    quoted, until the block reaches `MAX_RESULT_BLOCK_CHARS`."""
    lines = [
        f"- Class: {result.risk_class.value if result.risk_class else 'none yet'}",
        f"- Role: {result.role.value if result.role else 'not decided'}",
        f"- Status: {result.status.value}",
    ]
    if result.annex_point and PROVISION_ID_RE.fullmatch(result.annex_point):
        lines.append(f"- Annex point: {result.annex_point}")
    known = {(citation.document_id, citation.provision_id) for citation in quoted}
    size = sum(len(line) + 1 for line in lines)
    for step in result.steps:
        line = _step_line(step.step.value, step.decision, step.citations, known)
        size += len(line) + 1
        if size > MAX_RESULT_BLOCK_CHARS:
            break
        lines.append(line)
    return RESULT_BLOCK.format(law_text=LAW_TEXT_NAMES[result.law_version], lines="\n".join(lines))


def _step_line(
    step: str, decision: str, citations: Sequence[Citation], known: set[tuple[str, str]]
) -> str:
    """One step's line: its decision, capped, and the ids of its citations the corpus quoted."""
    if len(decision) > MAX_DECISION_CHARS:
        decision = decision[: MAX_DECISION_CHARS - len(TRUNCATED)] + TRUNCATED
    ids = (c.provision_id for c in citations if (c.document_id, c.provision_id) in known)
    cited = ", ".join(dict.fromkeys(ids))
    return f"- {step}: {decision}" + (f" ({cited})" if cited else "")


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
        answer=without_source_numbers(reply.answer, len(sources)),
        citations=tuple(sources[index].citation for index in cited),
        language=language,
        law_version=version,
        as_of=as_of,
        disclaimer=DISCLAIMER[language],
    )
