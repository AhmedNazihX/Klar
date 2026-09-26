from pathlib import Path

import pytest

from aiact.settings import DEFAULT_DATA_DIR, Settings


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
