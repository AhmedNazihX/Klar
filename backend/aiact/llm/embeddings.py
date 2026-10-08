"""Embeddings over OpenRouter: Qwen3-Embedding-8B, pinned to one provider, 1536 dimensions.

Stored vectors and query vectors must come from the same model, provider and dimension
count (INIT > Tech stack > Embeddings), so the provider is pinned with fallbacks off.
Qwen3 is instruction-aware: queries get a task instruction prefix (`EMBEDDING_QUERY_INSTRUCTION`),
documents don't. A model that isn't (OpenAI's) is given an empty instruction: the query goes as is.
Every vector is L2-normalised here and checked, whatever the provider returned.
"""

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass

import httpx
import openrouter
from langchain_core.embeddings import Embeddings
from openrouter.components import ProviderPreferences
from openrouter.errors import NoResponseError, OpenRouterError
from openrouter.operations import CreateEmbeddingsResponseBody, CreateEmbeddingsUsage

from aiact.llm.routing import APP_TITLE, provider_preferences, require_api_key, require_setting
from aiact.settings import Settings, get_settings

logger = logging.getLogger(__name__)

NORM_WARN_TOLERANCE = 1e-3
"""Nebius returns unit vectors; a raw length further than this from 1 is logged as a warning."""

NORM_ERROR_TOLERANCE = 0.5
"""A raw length this far from 1 means the wrong model or provider answered, so it's an error."""


class EmbeddingError(RuntimeError):
    """The provider returned something that isn't a usable vector of the expected shape."""


def format_query(text: str, instruction: str) -> str:
    """Wrap a query in Qwen3's instruction format (`Instruct: …\\nQuery:…`)."""
    return f"Instruct: {instruction}\nQuery:{text}"


def l2_normalise(vector: Sequence[float], dimensions: int) -> list[float]:
    """Return `vector` scaled to unit length, after checking its dimensions and raw length.

    The provider's own length is checked before rescaling: slightly off is logged, far off
    (or zero, NaN, infinite) raises, since rescaling would hide a wrong model or provider.
    """
    if len(vector) != dimensions:
        raise EmbeddingError(f"expected {dimensions} dimensions, got {len(vector)}")
    norm = math.sqrt(math.fsum(x * x for x in vector))
    if not math.isfinite(norm) or abs(norm - 1.0) > NORM_ERROR_TOLERANCE:
        raise EmbeddingError(
            f"provider returned a vector of length {norm}, expected about 1; "
            "check the embedding model and provider"
        )
    if abs(norm - 1.0) > NORM_WARN_TOLERANCE:
        logger.warning("provider returned a vector of length %.6f; rescaling to 1", norm)
    return [x / norm for x in vector]


@dataclass(frozen=True)
class EmbeddingBatch:
    """The unit vectors of one request, in input order, with what OpenRouter billed for it."""

    vectors: list[list[float]]
    tokens: int
    cost_usd: float
    is_cost_known: bool = True
    """False when the response carried no cost, so `cost_usd` (0) undercounts."""


class OpenRouterEmbeddings(Embeddings):
    """LangChain `Embeddings` over OpenRouter's `/embeddings` endpoint, provider pinned."""

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: str | None = None,
        dimensions: int | None = None,
        query_instruction: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Model, provider, dimensions and query instruction default to `EMBEDDING_*` settings;
        an empty `query_instruction` sends queries without one.

        Raises `LLMConfigError` when the model, the provider or the API key is not set.
        """
        settings = settings or get_settings()
        self.model = model or require_setting(settings.embedding_model, "EMBEDDING_MODEL")
        self.provider = provider or require_setting(
            settings.embedding_provider, "EMBEDDING_PROVIDER"
        )
        self.dimensions = dimensions or settings.embedding_dimensions
        self.query_instruction = (
            settings.embedding_query_instruction if query_instruction is None else query_instruction
        )
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
        return self._embed([self.query_text(text)])[0]

    def query_text(self, text: str) -> str:
        """The text sent for a search query: wrapped in the instruction, or as is without one."""
        return format_query(text, self.query_instruction) if self.query_instruction else text

    def embed_batch(self, texts: list[str]) -> EmbeddingBatch:
        """Embed corpus texts in one request and report its tokens and cost (0, and
        `is_cost_known` False, when the response gives none)."""
        if not texts:
            return EmbeddingBatch([], 0, 0.0)
        try:
            response = self._client.embeddings.generate(
                input=texts,
                model=self.model,
                dimensions=self.dimensions,
                encoding_format="float",
                provider=self._routing,
            )
        except OpenRouterError as error:
            # The type and status only: the response body may echo the request.
            raise EmbeddingError(
                f"embeddings request failed: {type(error).__name__} (HTTP {error.status_code})"
            ) from error
        except (NoResponseError, httpx.HTTPError) as error:
            raise EmbeddingError(f"embeddings request failed: {type(error).__name__}") from error
        vectors, usage = _vectors(response, expected=len(texts))
        return EmbeddingBatch(
            vectors=[l2_normalise(vector, self.dimensions) for vector in vectors],
            tokens=usage.prompt_tokens if usage is not None else 0,
            cost_usd=float(usage.cost or 0.0) if usage is not None else 0.0,
            is_cost_known=usage is not None and usage.cost is not None,
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return self.embed_batch(texts).vectors


def _vectors(
    response: object, *, expected: int
) -> tuple[list[list[float]], CreateEmbeddingsUsage | None]:
    """Pull the float vectors (in input order) and the usage out of a response."""
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
    return vectors, response.usage
