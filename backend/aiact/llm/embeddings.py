"""Embeddings over OpenRouter: Qwen3-Embedding-8B, pinned to one provider, 1536 dimensions.

Stored vectors and query vectors must come from the same model, provider and dimension
count (INIT > Tech stack > Embeddings), so the provider is pinned with fallbacks off.
Qwen3 is instruction-aware: queries get a task instruction prefix, documents don't.
Every vector is L2-normalised here and checked, whatever the provider returned.
"""

import logging
import math
from collections.abc import Sequence

import openrouter
from langchain_core.embeddings import Embeddings
from openrouter.components import ProviderPreferences
from openrouter.operations import CreateEmbeddingsResponseBody

from aiact.llm.routing import APP_TITLE, provider_preferences, require_api_key, require_setting
from aiact.settings import Settings, get_settings

logger = logging.getLogger(__name__)

DEFAULT_QUERY_INSTRUCTION = (
    "Given a description of an AI system or a question about the EU AI Act, "
    "retrieve the provisions of the AI Act that apply"
)
"""Placeholder task text; story X1 fixes the exact wording on the Annex-matching set."""

NORM_TOLERANCE = 1e-6
"""How far a normalised vector's length may be from 1 before it counts as broken."""


class EmbeddingError(RuntimeError):
    """The provider returned something that isn't a usable vector of the expected shape."""


def format_query(text: str, instruction: str) -> str:
    """Wrap a query in Qwen3's instruction format (`Instruct: …\\nQuery:…`)."""
    return f"Instruct: {instruction}\nQuery:{text}"


def l2_normalise(vector: Sequence[float], dimensions: int) -> list[float]:
    """Return `vector` scaled to unit length, after checking its dimension count."""
    if len(vector) != dimensions:
        raise EmbeddingError(f"expected {dimensions} dimensions, got {len(vector)}")
    norm = math.sqrt(math.fsum(x * x for x in vector))
    if norm == 0.0 or not math.isfinite(norm):
        raise EmbeddingError(f"vector has no usable length (norm={norm})")
    unit = [x / norm for x in vector]
    unit_norm = math.sqrt(math.fsum(x * x for x in unit))
    if abs(unit_norm - 1.0) > NORM_TOLERANCE:
        raise EmbeddingError(f"normalised vector has length {unit_norm}")
    return unit


class OpenRouterEmbeddings(Embeddings):
    """LangChain `Embeddings` over OpenRouter's `/embeddings` endpoint, provider pinned."""

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: str | None = None,
        dimensions: int | None = None,
        query_instruction: str = DEFAULT_QUERY_INSTRUCTION,
        settings: Settings | None = None,
    ) -> None:
        """Model, provider and dimensions default to `EMBEDDING_*` settings.

        Raises `LLMConfigError` when the model, the provider or the API key is not set.
        """
        settings = settings or get_settings()
        self.model = model or require_setting(settings.embedding_model, "EMBEDDING_MODEL")
        self.provider = provider or require_setting(
            settings.embedding_provider, "EMBEDDING_PROVIDER"
        )
        self.dimensions = dimensions or settings.embedding_dimensions
        self.query_instruction = query_instruction
        self._routing = ProviderPreferences.model_validate(
            provider_preferences([self.provider], allow_fallbacks=False)
        )
        self._client = openrouter.OpenRouter(
            api_key=require_api_key(settings).get_secret_value(),
            x_open_router_title=APP_TITLE,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed corpus texts as they are (no instruction), in one request."""
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query with the task instruction prefix."""
        return self._embed([format_query(text, self.query_instruction)])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.generate(
            input=texts,
            model=self.model,
            dimensions=self.dimensions,
            encoding_format="float",
            provider=self._routing,
        )
        vectors = _vectors(response, expected=len(texts))
        return [l2_normalise(vector, self.dimensions) for vector in vectors]


def _vectors(response: object, *, expected: int) -> list[list[float]]:
    """Pull the float vectors out of a response, in input order."""
    if not isinstance(response, CreateEmbeddingsResponseBody):
        raise EmbeddingError(f"unexpected embeddings response type {type(response).__name__}")
    if len(response.data) != expected:
        raise EmbeddingError(f"expected {expected} vectors, got {len(response.data)}")
    if response.usage is not None:
        logger.info(
            "embedded %d texts: %s tokens, cost %s",
            expected,
            response.usage.prompt_tokens,
            response.usage.cost,
        )
    ordered = sorted(response.data, key=lambda item: item.index or 0)
    vectors: list[list[float]] = []
    for item in ordered:
        if isinstance(item.embedding, str):
            raise EmbeddingError("got a base64 embedding; expected floats")
        vectors.append(item.embedding)
    return vectors
