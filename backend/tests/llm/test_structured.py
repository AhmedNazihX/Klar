"""`parse_reply`: a reply the provider's content filter stopped is a refusal, not a broken output
(decision 029); an answer that parses is used whatever the finish reason."""

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel, ValidationError

from aiact.llm.structured import CONTENT_FILTER, ProviderRefusalError, parse_reply


class Small(BaseModel):
    value: int


REFUSAL = "I'm sorry, but I cannot assist with that request."


def reply(content: str, finish_reason: str | None) -> AIMessage:
    metadata = {"finish_reason": finish_reason} if finish_reason else {}
    return AIMessage(content=content, response_metadata=metadata)


def test_a_filtered_reply_without_an_answer_is_a_refusal() -> None:
    with pytest.raises(ProviderRefusalError) as raised:
        parse_reply(reply(REFUSAL, CONTENT_FILTER), Small)
    assert REFUSAL not in str(raised.value)


def test_a_filtered_reply_with_an_answer_is_used() -> None:
    assert parse_reply(reply('{"value": 3}', CONTENT_FILTER), Small) == Small(value=3)


@pytest.mark.parametrize("finish_reason", ["stop", "length", None])
def test_any_other_reply_that_does_not_fit_is_a_validation_error(finish_reason: str | None) -> None:
    with pytest.raises(ValidationError):
        parse_reply(reply(REFUSAL, finish_reason), Small)
