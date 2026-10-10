"""Structured output helpers shared by every caller that asks a chat model for JSON (V3, E2).

The model fills a JSON Schema built from a Pydantic model, and the reply is validated against
the same model. Validation errors are described by location and message only, so a user's
description quoted back in an error never reaches a log or an exception. A reply the provider's
content filter stopped is told apart from a broken one (`parse_reply`, decision 029), and goes
once to a second pinned model when the caller has one (`ChatRoute`, decision 033).
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from openrouter.errors import NoResponseError, OpenRouterError, ResponseValidationError
from pydantic import BaseModel, JsonValue, ValidationError

logger = logging.getLogger(__name__)

CONTENT_FILTER = "content_filter"
"""The `finish_reason` a provider sends when its content filter blocked the request or the
answer (OpenRouter passes it on; LangChain puts it in `response_metadata`)."""
TRANSIENT_STATUSES = frozenset({408, 429})
"""The 4xx statuses worth a refusal's step: a timeout and a rate limit. Every 5xx is too."""
SERVER_ERROR = 500
TRANSIENT_FAILURES: tuple[type[Exception], ...] = (
    NoResponseError,
    ResponseValidationError,
    httpx.TransportError,
    ValueError,
)
"""Failures transient whatever their status: no response or a transport error, and a reply that
doesn't fit (`ValidationError`, the SDK's `ResponseValidationError`) or that carries the
provider's error (ChatOpenRouter's plain `ValueError`)."""


def is_transient_failure(exc: Exception) -> bool:
    """Whether the second call's failure is transient (decision 033): one of
    `TRANSIENT_FAILURES`, or an HTTP error with status 408, 429 or 5xx, whichever SDK class
    carries it (the SDK types those statuses only for a JSON body; a gateway's HTML 502 or any
    504 comes as `OpenRouterDefaultError`). Any other 4xx (a mistyped model or provider, a
    schema the provider rejects) is a config or request error, and still fails the run."""
    if isinstance(exc, TRANSIENT_FAILURES):
        return True
    if isinstance(exc, OpenRouterError):
        return exc.status_code in TRANSIENT_STATUSES or exc.status_code >= SERVER_ERROR
    return False


class ProviderRefusalError(RuntimeError):
    """The provider's content filter stopped the call and no usable answer came back (decision
    029), or the second model's call failed transiently after a refusal (decision 033). Never a
    broken output: the caller reports that the input needs a person's review."""


def all_required(schema: JsonValue) -> JsonValue:
    """`schema` with every object's properties listed as required, as OpenAI-style structured
    output demands (Azure rejects a schema whose optional fields, like `about`, aren't listed).
    Optional fields stay nullable, so the model sends null for them."""
    if isinstance(schema, list):
        return [all_required(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    updated = {key: all_required(value) for key, value in schema.items()}
    properties = schema.get("properties")
    if isinstance(properties, dict):
        updated["required"] = list(properties)
    return updated


def json_schema_format(name: str, model: type[BaseModel]) -> dict[str, object]:
    """The `response_format` that asks for JSON matching `model`."""
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "schema": all_required(model.model_json_schema())},
    }


def describe_validation_error(exc: ValidationError) -> str:
    """The validation errors by location and message, without the input values they quote."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'answer'}: {error['msg']}"
        for error in exc.errors()
    )


def parse_reply[M: BaseModel](reply: BaseMessage, model: type[M]) -> M:
    """The reply as `model`. An answer that parses is used whatever the finish reason (a
    `content_filter` reply can still carry one). Raises `ProviderRefusalError` when the content
    filter stopped the call and nothing parses, and `ValidationError` for any other reply that
    doesn't fit."""
    try:
        return model.model_validate_json(reply.text)
    except ValidationError:
        if reply.response_metadata.get("finish_reason") == CONTENT_FILTER:
            raise ProviderRefusalError("the provider's content filter refused the call") from None
        raise


@dataclass(frozen=True)
class ChatRoute:
    """A node's model, and the second pinned model its refused requests go to (decision 033)."""

    chat: BaseChatModel
    refusal_chat: BaseChatModel | None = None
    """None: no second call, so a refusal reaches the caller at once (the smoke harness, whose
    probes make one call each, decision 004; tests)."""

    def ask[M: BaseModel](
        self,
        messages: Sequence[BaseMessage],
        response_format: Mapping[str, object],
        model: type[M],
    ) -> M:
        """The answer as `model` (`parse_reply`). A provider refusal sends the same request once
        to `refusal_chat`, whose reply is read the same way; only a refusal does, so an answer
        that parses (even under `content_filter`), a broken reply or a transport error never
        reaches the second model. Raises `ProviderRefusalError` when both refuse (or there is no
        second model), and also when the second call fails transiently (`is_transient_failure`),
        because the route must never end worse than no route (decision 033); a 4xx config or
        request error of the second call still raises. Raises `ValidationError` when the first
        model's answer doesn't fit."""
        try:
            return parse_reply(self._invoke(self.chat, messages, response_format), model)
        except ProviderRefusalError:
            if self.refusal_chat is None:
                raise
        return self._ask_second(self.refusal_chat, messages, response_format, model)

    def _ask_second[M: BaseModel](
        self,
        chat: BaseChatModel,
        messages: Sequence[BaseMessage],
        response_format: Mapping[str, object],
        model: type[M],
    ) -> M:
        """The second model's answer; a transient failure of its call (`is_transient_failure`)
        is a refusal, logged by its type only (never the reply or the request, which quote the
        description)."""
        try:
            return parse_reply(self._invoke(chat, messages, response_format), model)
        except ProviderRefusalError:
            logger.warning("refusal route: the second model refused too")
            raise
        except Exception as exc:
            if not is_transient_failure(exc):
                raise
            kind = type(exc).__name__
            logger.warning("refusal route: the second model failed (%s)", kind)
            raise ProviderRefusalError(
                f"the second model failed ({kind}) after the provider refused"
            ) from None

    @staticmethod
    def _invoke(
        chat: BaseChatModel, messages: Sequence[BaseMessage], response_format: Mapping[str, object]
    ) -> BaseMessage:
        return chat.invoke(list(messages), response_format=dict(response_format))
