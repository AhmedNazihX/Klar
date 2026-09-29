"""The baselines the engine is measured against (INIT > Evaluation > Baselines).

- `baseline_luna`: the engine model (`ENGINE_MODEL`) answering in a single prompt, with no
  retrieval and no staged checks. It requires `ENGINE_PROVIDER` and is always pinned to that
  endpoint with fallbacks off (decision 005). It returns one JSON answer: class, status, role,
  Annex point, Art. 50 duties and a short reason.
- `baseline_jev`: TypeSafe's Jev decision model choosing the class directly, through OpenRouter's
  Decisions API (decision 005: `typesafe/jev-1.13`, never `typesafe/jev-router`, which can
  forward to Luna). Jev answers choice questions with probabilities, so it only ever gives a
  decided answer and names no Annex point.

Both answers become a `ClassificationResult` with the steps the contract needs for that class.
The step the class rests on carries the answer; the other steps say they weren't checked
separately. Neither baseline extracts facts or cites provisions, so citation metrics don't
apply to them. Both are asked about the AI Act as amended, as the engine is; without retrieval
the Luna baseline answers from what the model remembers.
"""

from datetime import date

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import Field, ValidationError

from aiact.eval.runner import (
    Classification,
    ClassifierFailedError,
    ClassifierInfo,
    ClassifierInput,
)
from aiact.llm import ChoiceQuestion, DecisionsClient, DecisionsError, chat_model
from aiact.llm.routing import require_setting
from aiact.llm.structured import describe_validation_error, json_schema_format
from aiact.schemas import (
    DISCLAIMER,
    STEP_ORDER,
    ClassificationResult,
    FollowUpQuestion,
    Language,
    LawVersion,
    OpenQuestion,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.base import ContractModel
from aiact.schemas.result import SCOPE_ONLY, UP_TO_ART_5, derived_status
from aiact.settings import Settings, get_settings

JEV_MODEL = "typesafe/jev-1.13"
MAX_OUTPUT_TOKENS = 4000
"""Bounds a runaway answer; one classification used about 1,900 output tokens (decision 005)."""

DECIDING_STEP: dict[RiskClass, StepName] = {
    RiskClass.OUT_OF_SCOPE: StepName.SCOPE,
    RiskClass.PROHIBITED: StepName.PROHIBITED,
    RiskClass.HIGH_RISK: StepName.HIGH_RISK,
    RiskClass.LIMITED_RISK: StepName.TRANSPARENCY,
    RiskClass.MINIMAL_RISK: StepName.TRANSPARENCY,
}
"""The step a baseline's class rests on: where the staged engine would have settled it."""

CLASSES_WITH_DUTIES = frozenset({RiskClass.LIMITED_RISK, RiskClass.HIGH_RISK})
"""The classes a result may list Art. 50 duties for."""


class BaselineAnswer(ContractModel):
    """A baseline's whole answer; also the JSON schema the Luna baseline must fill.

    Enum fields carry no description: strict structured output rejects keywords next to a
    `$ref`. `LUNA_INSTRUCTIONS` explains every field instead."""

    risk_class: RiskClass
    status: Status
    role: Role
    annex_point: str | None = Field(
        description="For a high_risk system, the Annex point, for example annex:III:4:a."
    )
    transparency_duties: tuple[str, ...] = Field(
        description="The Art. 50 paragraphs that apply, for example art:50:1."
    )
    reason: str = Field(min_length=1, description="One or two sentences.")
    missing_fact: FollowUpQuestion | None = Field(
        description="Required when status is needs_more_information: the question to ask."
    )
    open_question: OpenQuestion | None = Field(
        description="Required when status is legally_ambiguous: the question and both readings."
    )


class BaselineOutputError(ValueError):
    """A baseline's answer doesn't fit the result contract (a broken output)."""


def to_result(answer: BaselineAnswer, language: Language, label: str) -> ClassificationResult:
    """The contract result for `answer`; fields that don't apply to its class are dropped.

    The Annex point is kept only for high_risk. Art. 50 duties are kept only for limited_risk
    and high_risk (Art. 50 applies alongside Chapter III); for out_of_scope, prohibited and
    minimal_risk they contradict the class and are dropped. (`jev_answer` is stricter: its duty
    question is always answered, so it keeps the duty for limited_risk only.)

    Raises `BaselineOutputError` when the answer can't be a valid result (for example an
    uncertain out_of_scope, or limited_risk without an Art. 50 duty).
    """
    names = _step_names(answer)
    deciding = DECIDING_STEP[answer.risk_class]
    try:
        steps = tuple(_step(name, answer, label, is_deciding=name is deciding) for name in names)
        has_role = StepName.ROLE_OBLIGATIONS in names
        return ClassificationResult(
            facts=(),
            steps=steps,
            risk_class=answer.risk_class,
            status=derived_status(steps),
            role=answer.role if has_role else None,
            annex_point=answer.annex_point if answer.risk_class is RiskClass.HIGH_RISK else None,
            transparency_duties=(
                answer.transparency_duties if answer.risk_class in CLASSES_WITH_DUTIES else ()
            ),
            law_version=LawVersion.AMENDED,
            as_of=date.today(),
            disclaimer=DISCLAIMER[language],
            follow_up_questions=tuple(step.missing_fact for step in steps if step.missing_fact),
        )
    except ValidationError as exc:
        raise BaselineOutputError(_describe(exc)) from exc


def _step_names(answer: BaselineAnswer) -> tuple[StepName, ...]:
    if answer.risk_class is RiskClass.OUT_OF_SCOPE:
        return SCOPE_ONLY
    if answer.risk_class is RiskClass.PROHIBITED and answer.status is Status.DECIDED:
        return UP_TO_ART_5
    return STEP_ORDER


def _step(name: StepName, answer: BaselineAnswer, label: str, *, is_deciding: bool) -> StepResult:
    if name is StepName.ROLE_OBLIGATIONS:
        return StepResult(step=name, decision=f"{label}: role {answer.role.value}")
    if not is_deciding:
        return StepResult(step=name, decision=f"{label}: not checked separately")
    status = answer.status
    return StepResult(
        step=name,
        decision=f"{label}: {answer.risk_class.value}. {answer.reason}",
        status=status,
        missing_fact=answer.missing_fact if status is Status.NEEDS_MORE_INFORMATION else None,
        open_question=answer.open_question if status is Status.LEGALLY_AMBIGUOUS else None,
    )


def _describe(exc: ValidationError) -> str:
    return f"answer doesn't fit the result contract: {describe_validation_error(exc)}"


# --- Luna without retrieval or staged checks ----------------------------------------------------

LUNA_LABEL = "Single-prompt baseline"

LUNA_INSTRUCTIONS = """\
You classify an AI system under the EU AI Act (Regulation (EU) 2024/1689, as amended by the \
Digital Omnibus), using only the description you are given. Nothing will be looked up for you.

Check in this order and stop at the first class that applies:
1. Scope: is it an AI system (Art. 3(1)) within the Act's scope (Art. 2)? If not: out_of_scope.
2. Prohibited practices (Art. 5): prohibited.
3. High-risk (Art. 6 with Annex I or Annex III, including the Art. 6(3) exception): high_risk.
4. Transparency duties (Art. 50): limited_risk.
5. Otherwise: minimal_risk.

Answer with JSON matching the schema:
- risk_class: the class.
- status: "decided" when the description settles the class; "needs_more_information" when a \
fact that is missing would change it (give missing_fact: an id in snake_case and the question \
to ask); "legally_ambiguous" when the law itself doesn't settle it (give open_question: the \
question and exactly two readings, stricter first). When uncertain, risk_class is the stricter \
reading. out_of_scope is always "decided".
- role: provider, deployer, importer or distributor, for the company describing the system.
- annex_point: for high_risk under Annex III or Annex I, the point, for example "annex:III:4:a"; \
otherwise null.
- transparency_duties: the Art. 50 paragraphs that apply, for example ["art:50:1"]; at least \
one for limited_risk.
- reason: one or two sentences, in the language asked for.
"""


LUNA_RESPONSE_FORMAT = json_schema_format("baseline_answer", BaselineAnswer)


def luna_messages(request: ClassifierInput) -> list[BaseMessage]:
    """The fixed instructions first and the description last, so the prefix is cached (005)."""
    return [
        SystemMessage(LUNA_INSTRUCTIONS),
        HumanMessage(
            f"Language for reason and questions: {request.language.value}\n\n"
            f"Description:\n{request.description}"
        ),
    ]


class LunaBaseline:
    """The engine model in one prompt, no retrieval, no staged checks (`baseline_luna`)."""

    def __init__(self, settings: Settings | None = None, chat: BaseChatModel | None = None) -> None:
        """`chat` replaces the OpenRouter model (tests). Raises `LLMConfigError` when
        `ENGINE_MODEL`, `ENGINE_PROVIDER` or the API key is not set: the model is always pinned
        to its EU endpoint with fallbacks off (decision 005), so descriptions stay in the EU."""
        settings = settings or get_settings()
        model_id = require_setting(settings.engine_model, "ENGINE_MODEL")
        provider = require_setting(settings.engine_provider, "ENGINE_PROVIDER")
        self._model = chat or chat_model(
            model=model_id,
            provider_order=[provider],
            allow_fallbacks=False,
            max_tokens=MAX_OUTPUT_TOKENS,
            settings=settings,
        )
        self.info = ClassifierInfo(model=model_id, provider=provider)

    def classify(self, request: ClassifierInput) -> Classification:
        reply = self._model.invoke(luna_messages(request), response_format=LUNA_RESPONSE_FORMAT)
        cost_usd, tokens = _chat_usage(reply)
        try:
            answer = BaselineAnswer.model_validate_json(reply.text)
        except ValidationError as exc:
            cause = BaselineOutputError(_describe(exc))
            raise ClassifierFailedError(cost_usd, tokens, cause) from exc
        try:
            result = to_result(answer, request.language, LUNA_LABEL)
        except BaselineOutputError as exc:
            raise ClassifierFailedError(cost_usd, tokens, exc) from exc
        return Classification(result=result, cost_usd=cost_usd, tokens=tokens)


def _chat_usage(reply: AIMessage) -> tuple[float, int]:
    """What a chat call cost (OpenRouter's `usage.cost`) and how many tokens it used."""
    cost = reply.response_metadata.get("cost")
    tokens = reply.usage_metadata["total_tokens"] if reply.usage_metadata else 0
    return (float(cost) if isinstance(cost, int | float) else 0.0), tokens


# --- Jev classifying directly -------------------------------------------------------------------

JEV_LABEL = "Jev baseline"

ACT = "the EU AI Act (Regulation (EU) 2024/1689, as amended by the Digital Omnibus)"

JEV_QUESTIONS: dict[str, ChoiceQuestion] = {
    "risk_class": ChoiceQuestion(
        instructions=(
            f"Which risk class does the described AI system have under {ACT}? Check in this "
            "order and pick the first that applies: scope, prohibited practices, high-risk, "
            "transparency duties."
        ),
        criteria={
            RiskClass.OUT_OF_SCOPE: "Not an AI system under Art. 3(1), or outside the Act's "
            "scope under Art. 2 (for example military use, or research only).",
            RiskClass.PROHIBITED: "A prohibited AI practice under Art. 5.",
            RiskClass.HIGH_RISK: "High-risk under Art. 6: a safety component or product under "
            "Annex I, or a use listed in Annex III that the Art. 6(3) exception doesn't cover.",
            RiskClass.LIMITED_RISK: "Not high-risk, but an Art. 50 transparency duty applies "
            "(interacts with people, generates synthetic content, emotion recognition or "
            "biometric categorisation, deep fakes).",
            RiskClass.MINIMAL_RISK: "An AI system in scope to which none of the above applies.",
        },
    ),
    "role": ChoiceQuestion(
        instructions=f"Which role does the company describing the system have under {ACT}?",
        criteria={
            Role.PROVIDER: "Develops the system, or has it developed, and places it on the "
            "market or puts it into service under its own name (Art. 3(3)).",
            Role.DEPLOYER: "Uses a system someone else provides, under its own authority "
            "(Art. 3(4)).",
            Role.IMPORTER: "Established in the EU and places on the market a system bearing the "
            "name of a provider established outside the EU (Art. 3(6)).",
            Role.DISTRIBUTOR: "Makes a system available on the EU market without being its "
            "provider or importer (Art. 3(7)).",
        },
    ),
    "transparency_duty": ChoiceQuestion(
        instructions=f"Which Art. 50 transparency duty of {ACT} fits the system best?",
        criteria={
            "art_50_1": "Art. 50(1): the system interacts directly with people.",
            "art_50_2": "Art. 50(2): the system generates synthetic audio, image, video or text.",
            "art_50_3": "Art. 50(3): emotion recognition or biometric categorisation.",
            "art_50_4": "Art. 50(4): deep fakes, or generated text published to inform the "
            "public on matters of public interest.",
        },
    ),
}
"""Criteria keys are the answer values; `transparency_duty` keys map to `art:50:<n>`."""


def jev_answer(risk_class: str, role: str, duty: str, confidence: float | None) -> BaselineAnswer:
    """Jev's three choices as a decided answer; the confidence goes into the reason. The Art. 50
    duty is kept only for limited_risk, the one class that is defined by it."""
    shown = "unknown" if confidence is None else f"{confidence:.2f}"
    chosen_class = RiskClass(risk_class)
    is_limited = chosen_class is RiskClass.LIMITED_RISK
    return BaselineAnswer(
        risk_class=chosen_class,
        status=Status.DECIDED,
        role=Role(role),
        annex_point=None,
        transparency_duties=(duty.replace("_", ":"),) if is_limited else (),
        reason=f"Jev's choice, confidence {shown}.",
        missing_fact=None,
        open_question=None,
    )


class JevBaseline:
    """Jev choosing the class directly from the description (`baseline_jev`)."""

    info = ClassifierInfo(model=JEV_MODEL)

    def __init__(self, client: DecisionsClient | None = None) -> None:
        """Raises `LLMConfigError` when the API key is not set."""
        self._client = client or DecisionsClient(JEV_MODEL)

    def classify(self, request: ClassifierInput) -> Classification:
        try:
            response = self._client.choose(request.description, JEV_QUESTIONS)
        except DecisionsError as exc:
            if exc.cost_usd > 0:
                raise ClassifierFailedError(exc.cost_usd, exc.tokens, exc) from exc
            raise
        cost_usd, tokens = response.usage.cost, response.usage.tokens
        answers = response.answers
        risk = answers["risk_class"]
        answer = jev_answer(
            risk.choice,
            answers["role"].choice,
            answers["transparency_duty"].choice,
            risk.confidence,
        )
        try:
            result = to_result(answer, request.language, JEV_LABEL)
        except BaselineOutputError as exc:
            raise ClassifierFailedError(cost_usd, tokens, exc) from exc
        return Classification(result=result, cost_usd=cost_usd, tokens=tokens)
