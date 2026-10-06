"""What the checks share (E3, E4, E5, E7, E8): the corpus lookup of one run, the citations built
from what the corpus returns, the follow-up question of a key fact, the per-case blocks of their
prompts, and the step for a reply the provider refused (decision 029)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from aiact.engine.nodes.role_texts import KeyQuestion
from aiact.engine.state import CheckOutcome, EngineState, RoleFinding
from aiact.retrieval.provisions import Provision
from aiact.retrieval.search import SearchHit
from aiact.schemas import (
    PROVIDER_REFUSAL,
    Citation,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    Status,
    StepName,
    StepResult,
)

MAX_PASSAGE_CHARS = 4000
"""Bounds one retrieved text in the prompt (a parent row holds all its children's text)."""


@dataclass(frozen=True)
class Lookup:
    """What every fetch and search of one run shares: the language, the law version and date,
    the examples the caller excludes, and whether the held-out ones are included."""

    language: Language
    law_version: LawVersion
    as_of: date | None
    """None for the original text, which has one slice per unit (`get_provision`)."""
    exclude_source_example_ids: tuple[str, ...]
    include_held_out: bool = False
    """The gap run's opt-in (V8, decision 012), passed to every `get_provision` and
    `search_ai_act` call; False hides the held-out examples."""


def lookup_for(state: EngineState) -> Lookup:
    law_version = state["law_version"]
    return Lookup(
        language=state["language"],
        law_version=law_version,
        as_of=None if law_version is LawVersion.ORIGINAL else state["as_of"],
        exclude_source_example_ids=tuple(state["exclude_source_example_ids"]),
        include_held_out=state.get("include_held_out", False),
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


def guidance_section(guidance: Sequence[SearchHit]) -> str:
    """The guideline passages as the prompt lists them: numbered from 1, each with its id and
    its text cut to `MAX_PASSAGE_CHARS`, or "-"."""
    listed = (f"{n}. [{hit.provision_id}] {clipped(hit.text)}" for n, hit in enumerate(guidance, 1))
    return "\n\n".join(listed) or "-"


def named_passages(numbers: Sequence[int], guidance: Sequence[SearchHit]) -> tuple[SearchHit, ...]:
    """The passages `numbers` name (numbered from 1 as the prompt shows them), in range and each
    once."""
    in_range = dict.fromkeys(n for n in numbers if 0 < n <= len(guidance))
    return tuple(guidance[n - 1] for n in in_range)


def key_question(key: KeyQuestion, language: Language) -> FollowUpQuestion:
    """The follow-up question that settles a key fact, about the provision it rests on."""
    return FollowUpQuestion(id=key.id, text=key.question[language], about=key.article)


# --- A provider refusal (decision 029) -----------------------------------------------------------

BLOCKED: Mapping[Language, str] = {
    Language.EN: "The model provider's content filter blocked this description, so it could not "
    "be assessed automatically.",
    Language.DE: "Der Inhaltsfilter des Modellanbieters hat diese Beschreibung blockiert, daher "
    "konnte sie nicht automatisch geprüft werden.",
}
"""The first sentence of every refused step's decision."""


def refused_check(
    name: StepName,
    language: Language,
    assumption: str,
    citations: Sequence[Citation],
    review: FollowUpQuestion,
    *,
    matched: bool = False,
    high_risk_route: HighRiskRoute | None = None,
    transparency_duties: tuple[str, ...] = (),
    role: RoleFinding | None = None,
) -> CheckOutcome:
    """The step of a check whose reply the provider's content filter refused (decision 029):
    not assessed (`BLOCKED`, then the stricter reading the check assumes), `needs_more_information`
    with the person-review question as its missing fact, so the run goes on, and the check's
    assumed findings."""
    step = StepResult(
        step=name,
        decision=f"{BLOCKED[language]} {assumption}",
        citations=tuple(citations),
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact=review,
        error=PROVIDER_REFUSAL,
    )
    return CheckOutcome(
        step=step,
        matched=matched,
        high_risk_route=high_risk_route,
        transparency_duties=transparency_duties,
        role=role,
        follow_up_questions=(review,),
    )
