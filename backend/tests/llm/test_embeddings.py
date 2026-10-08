import math
from collections.abc import Callable
from types import SimpleNamespace

import httpx
import pytest
from openrouter.errors import NoResponseError, OpenRouterError
from openrouter.operations import CreateEmbeddingsResponseBody
from pydantic import SecretStr

from aiact.llm import EmbeddingError, LLMConfigError, OpenRouterEmbeddings
from aiact.llm.embeddings import format_query, l2_normalise
from aiact.settings import Settings, get_settings

MODEL = "qwen/qwen3-embedding-8b"
PROVIDER = "nebius"
DIMENSIONS = 1536
TEXTS = [
    "Providers of high-risk AI systems shall establish a risk management system.",
    "Anbieter von KI-Systemen mit hohem Risiko richten ein Risikomanagementsystem ein.",
]


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def _client(settings: Settings) -> OpenRouterEmbeddings:
    return OpenRouterEmbeddings(
        model=MODEL, provider=PROVIDER, dimensions=DIMENSIONS, settings=settings
    )


def test_unit_vector_passes_without_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    assert l2_normalise([0.6, 0.8], 2) == pytest.approx([0.6, 0.8])
    assert caplog.records == []


def test_slightly_off_length_is_rescaled_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    # Length 1.01: past the warning tolerance, well inside the error bound.
    unit = l2_normalise([0.606, 0.808], 2)
    assert math.fsum(x * x for x in unit) == pytest.approx(1.0)
    assert [r.levelname for r in caplog.records] == ["WARNING"]
    assert "length 1.01" in caplog.text


def test_normalise_rejects_wrong_dimensions() -> None:
    with pytest.raises(EmbeddingError, match="expected 3 dimensions, got 2"):
        l2_normalise([0.6, 0.8], 3)


@pytest.mark.parametrize(
    "vector", [[3.0, 4.0], [0.2, 0.3], [0.0, 0.0], [math.nan, 1.0], [math.inf, 1.0]]
)
def test_far_off_length_points_to_wrong_model_or_provider(vector: list[float]) -> None:
    with pytest.raises(EmbeddingError, match="check the embedding model and provider"):
        l2_normalise(vector, 2)


def test_query_gets_the_qwen3_instruction_format() -> None:
    assert format_query("chatbot for HR", "Find provisions") == (
        "Instruct: Find provisions\nQuery:chatbot for HR"
    )


def test_embed_query_sends_the_configured_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenRouterEmbeddings(
        model=MODEL, provider=PROVIDER, query_instruction="Find provisions", settings=_settings()
    )
    sent: list[list[str]] = []

    def fake_embed(texts: list[str]) -> list[list[float]]:
        sent.append(texts)
        return [[1.0]]

    monkeypatch.setattr(client, "_embed", fake_embed)
    client.embed_query("chatbot for HR")
    assert sent == [["Instruct: Find provisions\nQuery:chatbot for HR"]]


def test_the_query_instruction_defaults_to_the_setting() -> None:
    default = OpenRouterEmbeddings(model=MODEL, provider=PROVIDER, settings=_settings())
    assert default.query_instruction == (
        "Given a description of an AI system or a question about the EU AI Act, "
        "retrieve the provisions of the AI Act that apply"
    )
    configured = OpenRouterEmbeddings(
        model=MODEL,
        provider=PROVIDER,
        settings=_settings(embedding_query_instruction="Match the Annex III point"),
    )
    assert configured.query_text("chatbot") == "Instruct: Match the Annex III point\nQuery:chatbot"


def test_an_empty_instruction_sends_the_query_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """For a model that isn't instruction-aware (OpenAI's comparison arm)."""
    client = OpenRouterEmbeddings(
        model=MODEL, provider=PROVIDER, query_instruction="", settings=_settings()
    )
    sent: list[list[str]] = []

    def fake_embed(texts: list[str]) -> list[list[float]]:
        sent.append(texts)
        return [[1.0]]

    monkeypatch.setattr(client, "_embed", fake_embed)
    client.embed_query("chatbot for HR")
    assert sent == [["chatbot for HR"]]


def test_settings_supply_model_provider_and_dimensions() -> None:
    client = OpenRouterEmbeddings(
        settings=_settings(embedding_model=MODEL, embedding_provider=PROVIDER)
    )
    assert (client.model, client.provider, client.dimensions) == (MODEL, PROVIDER, 1536)


@pytest.mark.parametrize(
    ("values", "missing"),
    [
        ({"embedding_provider": PROVIDER}, "EMBEDDING_MODEL"),
        ({"embedding_model": MODEL}, "EMBEDDING_PROVIDER"),
    ],
)
def test_unset_embedding_setting_is_a_config_error(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, object], missing: str
) -> None:
    monkeypatch.delenv(missing, raising=False)
    with pytest.raises(LLMConfigError, match=f"{missing} is not set"):
        OpenRouterEmbeddings(settings=_settings(**values))


def _assert_embeddings_roundtrip(settings: Settings) -> None:
    vectors = _client(settings).embed_documents(TEXTS)
    assert len(vectors) == len(TEXTS)
    for vector in vectors:
        assert len(vector) == DIMENSIONS
        assert math.fsum(x * x for x in vector) == pytest.approx(1.0, abs=1e-6)
    similarity = math.fsum(a * b for a, b in zip(*vectors, strict=True))
    # The English and German sentences say the same thing, so they should sit close.
    assert 0.5 < similarity < 1.0


@pytest.mark.vcr
def test_embeddings_roundtrip(openrouter_settings: Settings) -> None:
    _assert_embeddings_roundtrip(openrouter_settings)


@pytest.mark.live
def test_embeddings_roundtrip_live() -> None:
    _assert_embeddings_roundtrip(get_settings())


@pytest.mark.vcr
@pytest.mark.default_cassette("test_embeddings_roundtrip.yaml")
def test_embed_batch_reports_tokens_and_cost(openrouter_settings: Settings) -> None:
    batch = _client(openrouter_settings).embed_batch(TEXTS)
    assert len(batch.vectors) == len(TEXTS)
    assert (batch.tokens, batch.cost_usd) == (40, pytest.approx(4e-7))
    assert batch.is_cost_known


UNIT = [1.0] + [0.0] * (DIMENSIONS - 1)


@pytest.mark.parametrize("usage", [None, {"prompt_tokens": 7, "total_tokens": 7}])
def test_a_batch_without_its_cost_says_so(
    monkeypatch: pytest.MonkeyPatch, usage: dict[str, int] | None
) -> None:
    client = _client(_settings())
    body = {
        "data": [{"embedding": UNIT, "index": 0, "object": "embedding"}],
        "model": "m",
        "object": "list",
        "usage": usage,
    }
    response = CreateEmbeddingsResponseBody.model_validate(body)
    fake_sdk = SimpleNamespace(embeddings=SimpleNamespace(generate=lambda **_: response))
    monkeypatch.setattr(client, "_client", fake_sdk)
    batch = client.embed_batch(TEXTS[:1])
    assert (batch.cost_usd, batch.is_cost_known) == (0.0, False)


def _http_error() -> Exception:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/embeddings")
    response = httpx.Response(402, text="Insufficient credits for: the input text", request=request)
    return OpenRouterError("Insufficient credits for: the input text", response)


@pytest.mark.parametrize(
    ("make_error", "expected"),
    [(_http_error, r"OpenRouterError \(HTTP 402\)"), (NoResponseError, "NoResponseError")],
)
def test_sdk_errors_become_embedding_errors(
    monkeypatch: pytest.MonkeyPatch, make_error: Callable[[], Exception], expected: str
) -> None:
    client = _client(_settings())
    raised = make_error()

    def fail(**_: object) -> None:
        raise raised

    fake_sdk = SimpleNamespace(embeddings=SimpleNamespace(generate=fail))
    monkeypatch.setattr(client, "_client", fake_sdk)
    with pytest.raises(EmbeddingError, match=expected) as info:
        client.embed_batch(TEXTS)
    assert info.value.__cause__ is raised
    assert "input text" not in str(info.value)
