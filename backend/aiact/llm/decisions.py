"""OpenRouter's Decisions API, for decision models such as TypeSafe's Jev.

A decision model doesn't chat: it takes some state and named typed questions and returns an
answer with probabilities per question (`POST /api/alpha/decisions`; OpenRouter docs, API
reference > alphadecisions). `typesafe/jev-1.13` refuses chat completions and works only here
(decision 005). Two question types are supported: `choice` (one key of its criteria, with a
probability per key; V3's baseline) and `noul` (a yes/no question answered with the probability
of yes; V4's judge). Every request sends the same privacy routing as the chat and embedding
clients.
"""

from collections.abc import Mapping
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aiact.llm.routing import APP_TITLE, provider_preferences, require_api_key
from aiact.settings import Settings, get_settings

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_TIMEOUT_SECONDS = 60.0

type State = str | Mapping[str, str]
"""What the questions are about: a plain text, or named fields (which the API prefers)."""


class DecisionsError(RuntimeError):
    """A decisions request failed. `cost_usd` and `tokens` say what it spent (0 when unpaid)."""

    def __init__(self, message: str, cost_usd: float = 0.0, tokens: int = 0) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd
        self.tokens = tokens


class ChoiceQuestion(BaseModel):
    """Pick exactly one key of `criteria`; each value says when that key applies."""

    model_config = ConfigDict(frozen=True)

    type: Literal["choice"] = "choice"
    instructions: str = Field(min_length=1)
    criteria: Mapping[str, str] = Field(min_length=2)


class NoulCriteria(BaseModel):
    """When the answer is yes (`true`) and when it is no (`false`)."""

    model_config = ConfigDict(frozen=True)

    true: str = Field(min_length=1)
    false: str = Field(min_length=1)


class NoulQuestion(BaseModel):
    """A yes/no question; its answer is the probability of yes."""

    model_config = ConfigDict(frozen=True)

    type: Literal["noul"] = "noul"
    instructions: str = Field(min_length=1)
    criteria: NoulCriteria


class ChoiceAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["choice"]
    choice: str
    confidence: float | None = None
    probabilities: Mapping[str, float] = Field(default_factory=dict)


class NoulAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["noul"]
    noul: float = Field(ge=0.0, le=1.0)
    """The probability that the answer is yes."""


class DecisionsUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class DecisionsResponse(BaseModel):
    """The answers to `choice` questions."""

    model_config = ConfigDict(frozen=True)

    id: str | None = None
    model: str
    provider: str | None = None
    answers: Mapping[str, ChoiceAnswer]
    usage: DecisionsUsage


class NoulResponse(BaseModel):
    """The answers to `noul` questions."""

    model_config = ConfigDict(frozen=True)

    id: str | None = None
    model: str
    provider: str | None = None
    answers: Mapping[str, NoulAnswer]
    usage: DecisionsUsage


class _Billed(BaseModel):
    """Just the usage of a response, read when the rest of it doesn't validate."""

    usage: DecisionsUsage


class DecisionsClient:
    """A thread-safe client for one decision model."""

    def __init__(
        self,
        model: str,
        *,
        settings: Settings | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        """Raises `LLMConfigError` when the API key is not set."""
        settings = settings or get_settings()
        self.model = model
        self._headers = {
            "Authorization": f"Bearer {require_api_key(settings).get_secret_value()}",
            "X-Title": APP_TITLE,
        }
        self._http = http or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)

    def choose(self, state: State, questions: Mapping[str, ChoiceQuestion]) -> DecisionsResponse:
        """Ask every question about `state`; each answer's choice is one of its criteria keys.

        Raises `DecisionsError` for an HTTP error (nothing spent) or an unusable answer (with
        the cost the response reported).
        """
        parsed = _parse(self._post(state, questions), DecisionsResponse)
        for name, question in questions.items():
            answer = parsed.answers.get(name)
            if answer is None or answer.choice not in question.criteria:
                raise _invalid(name, "choice", parsed.usage)
        return parsed

    def ask(self, state: State, questions: Mapping[str, NoulQuestion]) -> NoulResponse:
        """Ask every yes/no question about `state`; each answer is the probability of yes.

        Raises `DecisionsError` for an HTTP error (nothing spent) or an unusable answer (with
        the cost the response reported).
        """
        parsed = _parse(self._post(state, questions), NoulResponse)
        missing = [name for name in questions if name not in parsed.answers]
        if missing:
            raise _invalid(missing[0], "answer", parsed.usage)
        return parsed

    def _post(
        self, state: State, questions: Mapping[str, ChoiceQuestion] | Mapping[str, NoulQuestion]
    ) -> bytes:
        body = {
            "model": self.model,
            "state": state if isinstance(state, str) else dict(state),
            "questions": {name: question.model_dump() for name, question in questions.items()},
            "provider": provider_preferences(),
        }
        try:
            response = self._http.post(DECISIONS_URL, json=body, headers=self._headers)
        except httpx.HTTPError as exc:
            raise DecisionsError(f"decisions request failed: {type(exc).__name__}") from exc
        if response.is_error:
            raise DecisionsError(f"decisions request failed with HTTP {response.status_code}")
        return response.content


def _parse[R: (DecisionsResponse, NoulResponse)](content: bytes, model: type[R]) -> R:
    try:
        return model.model_validate_json(content)
    except ValidationError as exc:
        message = f"unexpected decisions response: {exc.error_count()} errors"
        raise _unusable(content, message) from exc


def _invalid(name: str, kind: str, usage: DecisionsUsage) -> DecisionsError:
    """A question left without a valid answer; the call was still paid for."""
    return DecisionsError(f"question {name!r} has no valid {kind}", usage.cost, usage.tokens)


def _unusable(content: bytes, message: str) -> DecisionsError:
    """An error that still carries the cost, if the response reported one."""
    try:
        usage = _Billed.model_validate_json(content).usage
    except ValidationError:
        return DecisionsError(message)
    return DecisionsError(message, usage.cost, usage.tokens)
