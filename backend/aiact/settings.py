"""Application settings, read from the environment and `backend/.env`.

Modules read configuration only through `get_settings()`, never from `os.environ` directly.
Secrets are `SecretStr`, so they never show up in logs or reprs.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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

    # Tracing: LangSmith traces each classification when the key is set (E10). Outside
    # development they carry metadata only: no description, prompt or answer (INIT > Tech stack).
    aiact_env: Literal["development", "production"] = "production"
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "aiact"

    # Model ids (OpenRouter slugs; confirmed by stories X2 and X3)
    engine_model: str | None = None
    engine_provider: str | None = None
    judge_model: str | None = None
    judge_backup_model: str | None = None
    label_filter_model: str | None = None
    # RAGAS (V6): Gemini 3.1 Flash-Lite on its EU zero-retention endpoint (decision 005), the
    # only model ids with a default; override both together, since the provider is pinned.
    ragas_model: str = "google/gemini-3.1-flash-lite"
    ragas_provider: str = "google-vertex/eu"
    embedding_model: str | None = None
    embedding_provider: str | None = None
    embedding_dimensions: int = 1536

    # Search: the meaning arm's cosine-distance cut-off for Q&A and MCP (C8); None = no cut-off.
    # Left unset until X1 calibrates it.
    search_max_distance: float | None = Field(default=None, ge=0.0, le=2.0)

    # API (P1): where `aiact api serve` listens, and the browser origins allowed to call it
    # (comma-separated in the environment). The defaults are the Vite dev server's origin
    # (frontend/vite.config.ts) and the port the frontend's VITE_API_URL fallback names.
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: Annotated[tuple[str, ...], NoDecode] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    # The Host headers the API answers (against DNS rebinding), comma-separated.
    api_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = ("localhost", "127.0.0.1")
    # Client addresses come from X-Forwarded-For only behind a proxy the deployment names (S3).
    api_proxy_headers: bool = False
    # The proxies trusted for X-Forwarded-For: explicit IPs or CIDRs, comma-separated, never "*".
    api_forwarded_allow_ips: Annotated[tuple[str, ...], NoDecode] = ()
    # The interactive docs (/docs, /redoc, /openapi.json); S3 turns them off when deployed.
    api_docs: bool = True
    # The largest request body read: the biggest classification (20,000 characters and 40
    # answers of 1,000, 60,000 in all) in three-byte UTF-8, with room for its JSON.
    api_max_body_bytes: int = Field(default=262_144, ge=1_024)
    # Requests per client address per minute: classifications cost model calls, lookups don't.
    rate_limit_classify: int = Field(default=5, ge=1)
    rate_limit_lookups: int = Field(default=120, ge=1)
    # Word and PDF files: rendering one costs up to seconds of CPU, so few per client address
    # per minute, and few at once in this process (one more is refused at once, 503).
    rate_limit_exports: int = Field(default=10, ge=1)
    export_max_concurrent: int = Field(default=2, ge=1)
    # Classifications running at once in this process; one more is refused at once (503).
    classify_max_concurrent: int = Field(default=4, ge=1)

    @field_validator("cors_origins", "api_allowed_hosts", "api_forwarded_allow_ips", mode="before")
    @classmethod
    def _split_list(cls, value: object) -> object:
        """`A,B` from the environment as a tuple; a wildcard is refused, so no deployment can
        open the API to every site, host or forwarding peer by accident."""
        if isinstance(value, str):
            value = tuple(item.strip() for item in value.split(",") if item.strip())
        if isinstance(value, tuple | list) and "*" in value:
            raise ValueError("list the origins, hosts or proxies; a wildcard is not allowed")
        return value

    @field_validator("aiact_data_dir")
    @classmethod
    def _resolve_data_dir(cls, value: Path) -> Path:
        """Resolve a relative data dir against `backend/`, so it doesn't depend on the cwd."""
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once."""
    return Settings()
