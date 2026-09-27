"""OpenRouter chat and embedding clients with record/replay (F6).

All model calls in the app go through this package. Tests replay recorded HTTP responses
from `tests/recordings/` (see `tests/conftest.py`), so CI never reaches the network.
"""

from aiact.llm.chat import ModelRole, chat_model
from aiact.llm.embeddings import EmbeddingError, OpenRouterEmbeddings
from aiact.llm.routing import LLMConfigError, provider_preferences

__all__ = [
    "EmbeddingError",
    "LLMConfigError",
    "ModelRole",
    "OpenRouterEmbeddings",
    "chat_model",
    "provider_preferences",
]
