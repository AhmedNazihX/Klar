from pathlib import Path

import pytest

from aiact.settings import BACKEND_DIR, DEFAULT_DATA_DIR, Settings

MODEL_ID_FIELDS = (
    "engine_model",
    "judge_model",
    "judge_backup_model",
    "label_filter_model",
    "embedding_model",
    "embedding_provider",
)


def test_defaults_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIACT_DATA_DIR", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.aiact_data_dir == DEFAULT_DATA_DIR
    assert settings.openrouter_api_key is None


def test_reads_environment_and_hides_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AIACT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "placeholder-value")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.aiact_data_dir == tmp_path
    assert settings.openrouter_api_key is not None
    assert settings.openrouter_api_key.get_secret_value() == "placeholder-value"
    assert "placeholder-value" not in repr(settings)


def test_env_example_leaves_model_ids_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in (*MODEL_ID_FIELDS, "ragas_model", "ragas_provider"):
        monkeypatch.delenv(field.upper(), raising=False)
    monkeypatch.delenv("EMBEDDING_DIMENSIONS", raising=False)
    monkeypatch.delenv("SEARCH_MAX_DISTANCE", raising=False)
    settings = Settings(_env_file=BACKEND_DIR / ".env.example")  # pyright: ignore[reportCallIssue]
    for field in MODEL_ID_FIELDS:
        assert getattr(settings, field) is None, field
    # RAGAS has a default route (decision 005), so empty keys keep it.
    assert (settings.ragas_model, settings.ragas_provider) == (
        "google/gemini-3.1-flash-lite",
        "google-vertex/eu",
    )
    assert settings.embedding_dimensions == 1536
    assert settings.search_max_distance is None  # no cut-off until X1 calibrates one


def test_relative_data_dir_resolves_against_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIACT_DATA_DIR", "../data")
    monkeypatch.chdir(BACKEND_DIR / "tests")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.aiact_data_dir == BACKEND_DIR.parent / "data"


def test_api_defaults_are_the_local_dev_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("API_HOST", "API_PORT", "CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=BACKEND_DIR / ".env.example")  # pyright: ignore[reportCallIssue]
    assert (settings.api_host, settings.api_port) == ("127.0.0.1", 8000)
    assert settings.cors_origins == ("http://localhost:5173", "http://127.0.0.1:5173")


def test_cors_origins_are_read_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://klar.example, https://www.klar.example,")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.cors_origins == ("https://klar.example", "https://www.klar.example")


@pytest.mark.parametrize("name", ["CORS_ORIGINS", "API_ALLOWED_HOSTS", "API_FORWARDED_ALLOW_IPS"])
def test_a_wildcard_origin_host_or_proxy_is_refused(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(name, "localhost,*")
    with pytest.raises(ValueError, match="wildcard"):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def test_the_api_hardening_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    names = (
        "API_ALLOWED_HOSTS",
        "API_PROXY_HEADERS",
        "API_FORWARDED_ALLOW_IPS",
        "API_DOCS",
        "API_MAX_BODY_BYTES",
        "CLASSIFY_MAX_CONCURRENT",
        "RATE_LIMIT_EXPORTS",
        "EXPORT_MAX_CONCURRENT",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=BACKEND_DIR / ".env.example")  # pyright: ignore[reportCallIssue]
    assert settings.api_allowed_hosts == ("localhost", "127.0.0.1")
    assert settings.api_proxy_headers is False
    assert settings.api_forwarded_allow_ips == ()
    assert settings.api_docs is True
    assert settings.api_max_body_bytes == 262_144
    assert settings.classify_max_concurrent == 4
    assert (settings.rate_limit_exports, settings.export_max_concurrent) == (10, 2)
