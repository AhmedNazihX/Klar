"""The judge for the checks that need judgement (INIT > Evaluation > Judge; story V4).

Four checks, each a yes/no question about a claim and the text it rests on, "yes" always meaning
the check passes:
- citation support: the cited legal text supports the claim;
- evidence tag: a fact tagged "stated" really is in the description;
- Q&A support: the cited sources support the answer;
- invented content: a drafted document adds no fact the user didn't supply.

Jev (`JUDGE_MODEL`, a TypeSafe decision model through OpenRouter's Decisions API, never
`typesafe/jev-router`, which can forward to the engine model; decision 005) answers first with the
probability of yes. When that probability lies within `margin` of 0.5 the item is unsure and goes
to the backup LLM judge (`JUDGE_BACKUP_MODEL` on its pinned EU endpoint `JUDGE_BACKUP_PROVIDER`,
fallbacks off, one attempt), which answers yes or no with a written reason. The engine (OpenAI),
Jev (TypeSafe) and the backup (Anthropic) come from three companies, so the checks are
independent (INIT > Tech stack). Both judges read the same question and criteria.

The margin is validated on the hand-labelled cases in `eval/judge_validation/`
(`aiact.eval.judge_validation`); decision 006 records the measured choice.

Jev has no EU endpoint (decision 006), so the judge must only ever read benchmark material: the
validation cases, the Act's text and the engine's answers to benchmark cases, never a user's
description. No module outside `aiact.eval` imports it, the CLI that runs the benchmark aside; a
test imports every other module in a fresh interpreter and holds that.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import Field

from aiact.llm import (
    DecisionsClient,
    DecisionsError,
    LLMConfigError,
    NoulCriteria,
    NoulQuestion,
    chat_model,
)
from aiact.llm.chat import invoke_structured
from aiact.llm.structured import json_schema_format
from aiact.schemas import Language
from aiact.schemas.base import ContractModel
from aiact.settings import Settings, get_settings

logger = logging.getLogger(__name__)

UNSURE_MARGIN = 0.1
"""Jev's answer is unsure, and goes to the backup judge, when its probability of yes lies within
this distance of 0.5 (here: strictly between 0.4 and 0.6). Chosen by the user from the validation
run's margin table (decision 006, 2026-10-13)."""
YES_AT = 0.5
"""Jev's probability of yes from which its answer is yes."""

JEV_ROUTER = "typesafe/jev-router"
"""Forwards to other models, the engine model among them (decision 005); never the judge."""
QUESTION_ID = "holds"
MAX_OUTPUT_TOKENS = 600
"""Bounds the backup judge's answer: a verdict and a reason of one or two sentences."""
PROMPT_TOKENS_BOUND = 3_000
"""The instructions and the longest validation case, in tokens, rounded up at three characters a
token; a test holds the committed cases to it."""
JEV_USD_PER_MTOK = 0.042
"""Jev's input price per million tokens; its output is free (OpenRouter listing, 2026-10-13)."""
PRICED_BACKUP_MODEL = "anthropic/claude-haiku-5.5"
"""The backup model the prices below belong to; no estimate is made for another one."""
BACKUP_INPUT_USD_PER_MTOK = 0.11
BACKUP_OUTPUT_USD_PER_MTOK = 0.55
"""Claude Haiku 5.5 on google-vertex/europe (OpenRouter listing, 2026-10-13). Haiku 4.5 there
costs ten times as much: estimates made with these prices are only valid for Haiku 5.5."""
JEV_CALL_ESTIMATE_USD = PROMPT_TOKENS_BOUND * JEV_USD_PER_MTOK / 1_000_000
BACKUP_CALL_ESTIMATE_USD = (
    PROMPT_TOKENS_BOUND * BACKUP_INPUT_USD_PER_MTOK + MAX_OUTPUT_TOKENS * BACKUP_OUTPUT_USD_PER_MTOK
) / 1_000_000
"""The most one call can cost; charged when a failed call reports no cost, and used for
estimates and the cost cap."""


class JudgeCheck(StrEnum):
    CITATION_SUPPORT = "citation_support"
    EVIDENCE_TAG = "evidence_tag"
    QA_SUPPORT = "qa_support"
    INVENTED_CONTENT = "invented_content"


@dataclass(frozen=True)
class CheckSpec:
    """How a check is put to both judges: the names of its two texts, the question and when the
    answer is yes or no."""

    claim_name: str
    source_name: str
    question: NoulQuestion


CHECKS: Mapping[JudgeCheck, CheckSpec] = {
    JudgeCheck.CITATION_SUPPORT: CheckSpec(
        "claim",
        "cited_text",
        NoulQuestion(
            instructions=(
                "Does the cited legal text support the claim? The claim must follow from what "
                "the text itself says. A text on the same topic that doesn't say it, or that "
                "names a different actor, condition, deadline or amount, doesn't support it."
            ),
            criteria=NoulCriteria(
                true="Everything the claim states follows from the cited text.",
                false="The cited text doesn't say what the claim states, or says otherwise.",
            ),
        ),
    ),
    JudgeCheck.EVIDENCE_TAG: CheckSpec(
        "fact",
        "description",
        NoulQuestion(
            instructions=(
                "Is the fact stated in the description? It is stated when the description says "
                "it, in any words. A fact the description only makes likely, leaves open or "
                "contradicts is not stated."
            ),
            criteria=NoulCriteria(
                true="The description says this fact.",
                false="The description doesn't say it, only suggests it, or says otherwise.",
            ),
        ),
    ),
    JudgeCheck.QA_SUPPORT: CheckSpec(
        "answer",
        "sources",
        NoulQuestion(
            instructions=(
                "Do the sources support every statement in the answer to the question? A "
                "statement the sources don't contain, or one that changes their actors, "
                "conditions, dates or amounts, is not supported."
            ),
            criteria=NoulCriteria(
                true="Every statement in the answer follows from the sources.",
                false="At least one statement in the answer is not in the sources or "
                "contradicts them.",
            ),
        ),
    ),
    JudgeCheck.INVENTED_CONTENT: CheckSpec(
        "document_text",
        "supplied_facts",
        NoulQuestion(
            instructions=(
                "Does the document text keep to the supplied facts? Every fact it states about "
                "the system, the company, people, numbers, dates or measures must come from the "
                "supplied facts. General wording that states no fact is fine."
            ),
            criteria=NoulCriteria(
                true="Every fact in the document text comes from the supplied facts.",
                false="The document text adds a fact the supplied facts don't give, or "
                "contradicts them.",
            ),
        ),
    ),
}


MAX_CLAIM_CHARS = 4_000
MAX_SOURCE_CHARS = 16_000
"""Caps on what one item sends to the paid judges: a claim is a sentence, an answer or a document
passage; a source is a provision, a description or the supplied facts."""


class JudgeItem(ContractModel):
    """One thing to judge: a claim and the text it must rest on."""

    check: JudgeCheck
    language: Language
    claim: str = Field(min_length=1, max_length=MAX_CLAIM_CHARS)
    source: str = Field(min_length=1, max_length=MAX_SOURCE_CHARS)


def jev_state(item: JudgeItem) -> dict[str, str]:
    """The item as named fields, which the Decisions API prefers to one text."""
    spec = CHECKS[item.check]
    return {spec.claim_name: item.claim, spec.source_name: item.source}


class JudgeError(RuntimeError):
    """No verdict: the judge that had to answer failed. `cost_usd` and `tokens` say what the
    item spent; `is_call_failed` that the call reached no model (key, endpoint, guardrail or
    network). The message names the failure by type only, never the item's text."""

    def __init__(
        self,
        message: str,
        cost_usd: float,
        tokens: int,
        *,
        is_cost_estimated: bool = False,
        is_call_failed: bool = False,
    ) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd
        self.tokens = tokens
        self.is_cost_estimated = is_cost_estimated
        self.is_call_failed = is_call_failed


@dataclass(frozen=True)
class JevAnswer:
    p_yes: float
    cost_usd: float
    tokens: int


class JevJudge:
    """Jev's probability that the check passes. Jev has no EU endpoint: give it benchmark
    material only, never a user's description (decision 006)."""

    def __init__(self, settings: Settings | None = None, client: DecisionsClient | None = None):
        """`client` replaces the OpenRouter client (tests). Raises `LLMConfigError` when the API
        key is not set, or when `JUDGE_MODEL` is the Jev router, which can forward to the engine
        model (decision 005)."""
        settings = settings or get_settings()
        self.model = settings.judge_model
        if self.model == JEV_ROUTER:
            raise LLMConfigError(f"JUDGE_MODEL must not be {JEV_ROUTER} (decision 005)")
        self._client = client or DecisionsClient(self.model, settings=settings)

    def ask(self, item: JudgeItem) -> JevAnswer:
        """Raises `DecisionsError` (with what it spent) when no answer came back."""
        question = {QUESTION_ID: CHECKS[item.check].question}
        response = self._client.ask(jev_state(item), question)
        usage = response.usage
        return JevAnswer(response.answers[QUESTION_ID].noul, usage.cost, usage.tokens)


class BackupAnswer(ContractModel):
    """The backup judge's verdict; also the JSON schema it fills."""

    holds: bool = Field(description="true when the check passes (the answer is yes).")
    reason: str = Field(min_length=1, description="One or two sentences in English.")


BACKUP_RESPONSE_FORMAT = json_schema_format("judge_verdict", BackupAnswer)

BACKUP_INSTRUCTIONS = """\
You check the output of an assistant that classifies AI systems under the EU AI Act. Answer the \
question below about the two texts you are given, judging only from what they say; nothing will \
be looked up for you. Texts may be in English or German.

Question: {question}
Answer yes when: {yes}
Answer no when: {no}

Answer with JSON matching the schema: holds is true for yes and false for no; reason says in \
one or two English sentences what decided it.
"""


def backup_messages(item: JudgeItem) -> list[BaseMessage]:
    """The check's fixed instructions first and the item last."""
    spec = CHECKS[item.check]
    criteria = spec.question.criteria
    instructions = BACKUP_INSTRUCTIONS.format(
        question=spec.question.instructions, yes=criteria.true, no=criteria.false
    )
    texts = f"{spec.claim_name}:\n{item.claim}\n\n{spec.source_name}:\n{item.source}"
    return [SystemMessage(instructions), HumanMessage(texts)]


@dataclass(frozen=True)
class BackupVerdict:
    holds: bool
    reason: str
    cost_usd: float
    tokens: int
    is_cost_estimated: bool = False
    """No cost came back with the reply; `BACKUP_CALL_ESTIMATE_USD` was charged."""


class BackupJudge:
    """The LLM judge for unsure items: yes or no with a written reason."""

    def __init__(self, settings: Settings | None = None, chat: BaseChatModel | None = None):
        """`chat` replaces the OpenRouter model (tests). The model makes exactly one attempt per
        item (`max_retries=0`), pinned to its EU endpoint with fallbacks off (decision 005).
        Raises `LLMConfigError` when the API key is not set."""
        settings = settings or get_settings()
        self.model = settings.judge_backup_model
        self.provider = settings.judge_backup_provider
        self._chat = chat or chat_model(
            model=self.model,
            provider_order=[self.provider],
            allow_fallbacks=False,
            max_tokens=MAX_OUTPUT_TOKENS,
            max_retries=0,
            settings=settings,
        )

    def ask(self, item: JudgeItem) -> BackupVerdict:
        """Raises `JudgeError` for a failed call (charged at `BACKUP_CALL_ESTIMATE_USD`), a refusal
        or an answer that doesn't fit the schema (charged what the reply reported)."""
        reply = invoke_structured(
            self._chat,
            backup_messages(item),
            BackupAnswer,
            BACKUP_RESPONSE_FORMAT,
            BACKUP_CALL_ESTIMATE_USD,
        )
        if reply.answer is not None:
            answer = reply.answer
            return BackupVerdict(
                answer.holds, answer.reason, reply.cost_usd, reply.tokens, reply.is_cost_estimated
            )
        error = JudgeError(
            reply.error or "no answer",
            reply.cost_usd,
            reply.tokens,
            is_cost_estimated=reply.is_cost_estimated,
            is_call_failed=reply.is_call_failed,
        )
        if not reply.is_call_failed:
            raise error from None  # a broken reply's validation error quotes the reply
        logger.warning("backup judge call failed: %s", reply.error)
        raise error from reply.cause


DISTANCE_DIGITS = 6
"""The distance from 0.5 is rounded before it is compared, so a probability exactly on the band's
edge (0.7 at margin 0.2, which floats compute as 0.19999999999999996) counts as sure."""


def is_unsure(p_yes: float, margin: float) -> bool:
    """Whether Jev's probability of yes lies strictly within `margin` of 0.5, too close to stand
    alone."""
    return round(abs(p_yes - YES_AT), DISTANCE_DIGITS) < margin


def jev_holds(p_yes: float) -> bool:
    """Jev's answer: yes from `YES_AT` up."""
    return p_yes >= YES_AT


def jev_decision(p_yes: float | None, margin: float) -> bool | None:
    """Jev's answer when it decides alone (it answered and is sure at `margin`); None when the
    backup judge decides. The one rule `Judge.judge` and the validation's margin table share."""
    if p_yes is None or is_unsure(p_yes, margin):
        return None
    return jev_holds(p_yes)


def needs_backup(p_yes: float | None, margin: float) -> bool:
    """The backup judge decides when Jev gave no answer or an unsure one."""
    return jev_decision(p_yes, margin) is None


class Verdict(ContractModel):
    """The judge's answer for one item."""

    holds: bool
    decided_by: Literal["jev", "backup"]
    p_yes: float | None = Field(description="Jev's probability of yes; None when Jev failed.")
    reason: str | None = Field(description="The backup judge's reason; None when Jev decided.")
    cost_usd: float = Field(ge=0)
    tokens: int = Field(ge=0)


class Judge:
    """Jev first; the backup judge for unsure items and for items Jev couldn't answer."""

    def __init__(self, jev: JevJudge, backup: BackupJudge, margin: float = UNSURE_MARGIN) -> None:
        self._jev, self._backup, self.margin = jev, backup, margin

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "Judge":
        settings = settings or get_settings()
        return cls(JevJudge(settings), BackupJudge(settings))

    def judge(self, item: JudgeItem) -> Verdict:
        """Raises `JudgeError` when the backup judge had to answer and couldn't; the error
        carries what both calls spent."""
        p_yes, cost, tokens = self._ask_jev(item)
        decided = jev_decision(p_yes, self.margin)
        if decided is not None:
            return Verdict(
                holds=decided,
                decided_by="jev",
                p_yes=p_yes,
                reason=None,
                cost_usd=cost,
                tokens=tokens,
            )
        try:
            backup = self._backup.ask(item)
        except JudgeError as exc:
            raise JudgeError(
                str(exc),
                cost + exc.cost_usd,
                tokens + exc.tokens,
                is_cost_estimated=exc.is_cost_estimated,
                is_call_failed=exc.is_call_failed,
            ) from exc
        return Verdict(
            holds=backup.holds,
            decided_by="backup",
            p_yes=p_yes,
            reason=backup.reason,
            cost_usd=cost + backup.cost_usd,
            tokens=tokens + backup.tokens,
        )

    def _ask_jev(self, item: JudgeItem) -> tuple[float | None, float, int]:
        """Jev's probability, or None when its call failed (the backup judge then answers)."""
        try:
            answer = self._jev.ask(item)
        except DecisionsError as exc:
            logger.warning("Jev failed, the backup judge answers: %s", exc)
            return None, exc.cost_usd, exc.tokens
        return answer.p_yes, answer.cost_usd, answer.tokens
