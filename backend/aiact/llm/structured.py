"""Structured output helpers shared by every caller that asks a chat model for JSON (V3, E2).

The model fills a JSON Schema built from a Pydantic model, and the reply is validated against
the same model. Validation errors are described by location and message only, so a user's
description quoted back in an error never reaches a log or an exception. A reply the provider's
content filter stopped is told apart from a broken one (`parse_reply`, decision 029), and goes
once to a second pinned model when the caller has one (`ChatRoute`, decision 033).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, JsonValue, ValidationError

CONTENT_FILTER = "content_filter"
"""The `finish_reason` a provider sends when its content filter blocked the request or the
answer (OpenRouter passes it on; LangChain puts it in `response_metadata`)."""


class ProviderRefusalError(RuntimeError):
    """The provider's content filter stopped the call and no usable answer came back (decision
    029). Never a broken output: the caller reports that the input needs a person's review."""


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
        second model), and `ValidationError` when the answer that came back doesn't fit."""
        try:
            return parse_reply(self._invoke(self.chat, messages, response_format), model)
        except ProviderRefusalError:
            if self.refusal_chat is None:
                raise
        reply = self._invoke(self.refusal_chat, messages, response_format)
        return parse_reply(reply, model)

    @staticmethod
    def _invoke(
        chat: BaseChatModel, messages: Sequence[BaseMessage], response_format: Mapping[str, object]
    ) -> BaseMessage:
        return chat.invoke(list(messages), response_format=dict(response_format))
