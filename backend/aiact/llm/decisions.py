"""OpenRouter's Decisions API, for decision models such as TypeSafe's Jev.

A decision model doesn't chat: it takes some state and named typed questions and returns an
answer with probabilities per question (`POST /api/alpha/decisions`; OpenRouter docs, API
reference > alphadecisions). `typesafe/jev-1.13` refuses chat completions and works only here
(decision 005). Only `choice` questions are supported so far. Every request sends the same
privacy routing as the chat and embedding clients.
"""

from collections.abc import Mapping
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aiact.llm.routing import APP_TITLE, provider_preferences, require_api_key
from aiact.settings import Settings, get_settings

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_TIMEOUT_SECONDS = 60.0


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


class ChoiceAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["choice"]
    choice: str
    confidence: float | None = None
    probabilities: Mapping[str, float] = Field(default_factory=dict)


class DecisionsUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class DecisionsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str | None = None
    model: str
    provider: str | None = None
    answers: Mapping[str, ChoiceAnswer]
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
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        http: httpx.Client | None = None,
    ) -> None:
        """Raises `LLMConfigError` when the API key is not set."""
        settings = settings or get_settings()
        self.model = model
        self._headers = {
            "Authorization": f"Bearer {require_api_key(settings).get_secret_value()}",
            "X-Title": APP_TITLE,
        }
        self._http = http or httpx.Client(timeout=timeout)

    def choose(self, state: str, questions: Mapping[str, ChoiceQuestion]) -> DecisionsResponse:
        """Ask every question about `state`; each answer's choice is one of its criteria keys.

        Raises `DecisionsError` for an HTTP error (nothing spent) or an unusable answer (with
        the cost the response reported).
        """
        body = {
            "model": self.model,
            "state": state,
            "questions": {name: question.model_dump() for name, question in questions.items()},
            "provider": provider_preferences(),
        }
        try:
            response = self._http.post(DECISIONS_URL, json=body, headers=self._headers)
        except httpx.HTTPError as exc:
            raise DecisionsError(f"decisions request failed: {type(exc).__name__}") from exc
        if response.is_error:
            raise DecisionsError(f"decisions request failed with HTTP {response.status_code}")
        return _parse(response.content, questions)


def _parse(content: bytes, questions: Mapping[str, ChoiceQuestion]) -> DecisionsResponse:
    try:
        parsed = DecisionsResponse.model_validate_json(content)
    except ValidationError as exc:
        message = f"unexpected decisions response: {exc.error_count()} errors"
        raise _unusable(content, message) from exc
    for name, question in questions.items():
        answer = parsed.answers.get(name)
        if answer is None or answer.choice not in question.criteria:
            usage = parsed.usage
            raise DecisionsError(f"question {name!r} has no valid choice", usage.cost, usage.tokens)
    return parsed


def _unusable(content: bytes, message: str) -> DecisionsError:
    """An error that still carries the cost, if the response reported one."""
    try:
        usage = _Billed.model_validate_json(content).usage
    except ValidationError:
        return DecisionsError(message)
    return DecisionsError(message, usage.cost, usage.tokens)
