"""Structured output helpers shared by every caller that asks a chat model for JSON (V3, E2).

The model fills a JSON Schema built from a Pydantic model, and the reply is validated against
the same model. Validation errors are described by location and message only, so a user's
description quoted back in an error never reaches a log or an exception. A reply the provider's
content filter stopped is told apart from a broken one (`parse_reply`, decision 029).
"""

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
