from pathlib import Path

import pytest

from aiact.settings import BACKEND_DIR, DEFAULT_DATA_DIR, Settings

MODEL_ID_FIELDS = (
    "engine_model",
    "judge_model",
    "judge_backup_model",
    "label_filter_model",
    "ragas_model",
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
    for field in MODEL_ID_FIELDS:
        monkeypatch.delenv(field.upper(), raising=False)
    monkeypatch.delenv("EMBEDDING_DIMENSIONS", raising=False)
    settings = Settings(_env_file=BACKEND_DIR / ".env.example")  # pyright: ignore[reportCallIssue]
    for field in MODEL_ID_FIELDS:
        assert getattr(settings, field) is None, field
    assert settings.embedding_dimensions == 1536


def test_relative_data_dir_resolves_against_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIACT_DATA_DIR", "../data")
    monkeypatch.chdir(BACKEND_DIR / "tests")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.aiact_data_dir == BACKEND_DIR.parent / "data"
