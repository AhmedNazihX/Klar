"""What every engine node builds without a `chat` (decisions 005, 033): the engine model and the
refusal model, each pinned to its EU endpoint with fallbacks off and given the node's output cap."""

from langchain_openrouter import ChatOpenRouter

from aiact.llm.structured import ChatRoute

ENGINE = ("openai/gpt-6-luna-20260922", "azure/eu")
REFUSAL = ("google/gemini-3.1-flash-lite", "google-vertex/eu")
"""Decision 033's second model and endpoint, written out rather than read from the settings."""


def assert_pinned_route(route: object, max_tokens: int) -> None:
    """`route` (a node's `_route`) holds Luna on azure/eu and Gemini on google-vertex/eu, both
    zero-retention, no training, no fallbacks, at `max_tokens`."""
    assert isinstance(route, ChatRoute)
    for chat, (model, provider) in ((route.chat, ENGINE), (route.refusal_chat, REFUSAL)):
        assert isinstance(chat, ChatOpenRouter)
        assert chat.model_name == model
        assert chat.max_tokens == max_tokens
        assert chat.openrouter_provider == {
            "data_collection": "deny",
            "zdr": True,
            "order": [provider],
            "allow_fallbacks": False,
        }
