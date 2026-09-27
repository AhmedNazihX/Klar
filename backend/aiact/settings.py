"""Application settings, read from the environment and `backend/.env`.

Modules read configuration only through `get_settings()`, never from `os.environ` directly.
Secrets are `SecretStr`, so they never show up in logs or reprs.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
"""The `backend/` project directory, independent of the current working directory."""

ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_DATA_DIR = BACKEND_DIR.parent / "data"


class Settings(BaseSettings):
    """Every key the app reads. `.env.example` lists the same keys with placeholder values."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    # Data: the shared legal-text folder (worktrees point this at the main checkout's data/).
    aiact_data_dir: Path = Field(default=DEFAULT_DATA_DIR)

    # Model access
    openrouter_api_key: SecretStr | None = None

    # Database
    supabase_url: str | None = None
    supabase_service_key: SecretStr | None = None
    database_url: SecretStr | None = None

    # Tracing
    langsmith_api_key: SecretStr | None = None

    # Model ids (OpenRouter slugs; confirmed by stories X2 and X3)
    engine_model: str | None = None
    judge_model: str | None = None
    judge_backup_model: str | None = None
    label_filter_model: str | None = None
    ragas_model: str | None = None
    embedding_model: str | None = None
    embedding_provider: str | None = None
    embedding_dimensions: int = 1536

    @field_validator("aiact_data_dir")
    @classmethod
    def _resolve_data_dir(cls, value: Path) -> Path:
        """Resolve a relative data dir against `backend/`, so it doesn't depend on the cwd."""
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once."""
    return Settings()
