"""What the checks share (E3, E4, E5, E7): the corpus lookup of one run, the citations built from
what the corpus returns, the follow-up question of a key fact, and the per-case blocks of their
prompts."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.engine.state import EngineState
from aiact.retrieval.provisions import Provision
from aiact.retrieval.search import SearchHit
from aiact.schemas import Citation, FollowUpQuestion, Language, LawVersion

MAX_PASSAGE_CHARS = 4000
"""Bounds one retrieved text in the prompt (a parent row holds all its children's text)."""


@dataclass(frozen=True)
class Lookup:
    """What every fetch and search of one run shares: the language, the law version and date,
    and the examples the caller excludes."""

    language: Language
    law_version: LawVersion
    as_of: date | None
    """None for the original text, which has one slice per unit (`get_provision`)."""
    exclude_source_example_ids: tuple[str, ...]


def lookup_for(state: EngineState) -> Lookup:
    law_version = state["law_version"]
    return Lookup(
        language=state["language"],
        law_version=law_version,
        as_of=None if law_version is LawVersion.ORIGINAL else state["as_of"],
        exclude_source_example_ids=tuple(state["exclude_source_example_ids"]),
    )


def provision_citation(provision: Provision) -> Citation:
    return Citation(
        provision_id=provision.provision_id,
        document_id=provision.doc_key,
        law_version=provision.law_version,
        document_status=provision.status,
        language=provision.language,
        quote=provision.text,
        english_only=provision.english_only,
    )


def guidance_citation(hit: SearchHit, language: Language) -> Citation:
    return Citation(
        provision_id=hit.provision_id,
        document_id=hit.doc_key,
        law_version=hit.law_version,
        document_status=hit.status,
        language=hit.language,
        quote=hit.text,
        english_only=hit.language is not language,
    )


def answers_section(state: EngineState) -> str:
    """The answers to earlier follow-up questions, one line each, or "-"."""
    return "\n".join(f"- {qid}: {text}" for qid, text in state["answers"].items()) or "-"


def facts_section(state: EngineState) -> str:
    """The extracted facts, numbered from 1 with their evidence tag, or "-"."""
    facts = state.get("facts", ())
    return "\n".join(f"{n}. [{f.evidence.value}] {f.text}" for n, f in enumerate(facts, 1)) or "-"


def clipped(text: str) -> str:
    """`text` cut to `MAX_PASSAGE_CHARS`, marked " […]" when cut."""
    return text if len(text) <= MAX_PASSAGE_CHARS else f"{text[:MAX_PASSAGE_CHARS]} […]"


def named_passages(numbers: Sequence[int], guidance: Sequence[SearchHit]) -> tuple[SearchHit, ...]:
    """The passages `numbers` name (numbered from 1 as the prompt shows them), in range and each
    once."""
    in_range = dict.fromkeys(n for n in numbers if 0 < n <= len(guidance))
    return tuple(guidance[n - 1] for n in in_range)


def key_question(key: KeyQuestion, language: Language) -> FollowUpQuestion:
    """The follow-up question that settles a key fact, about the provision it rests on."""
    return FollowUpQuestion(id=key.id, text=key.question[language], about=key.article)
