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

DEFAULT_QUERY_INSTRUCTION = (
    "Given a description of an AI system or a question about the EU AI Act, "
    "retrieve the article, Annex point or recital of the AI Act that governs it"
)
"""Qwen3's query-side task text (`EMBEDDING_QUERY_INSTRUCTION`): the "governs it" text chosen in
decision 003 for Q&A and MCP searches."""

DEFAULT_SEARCH_MAX_DISTANCE = 0.30
"""`SEARCH_MAX_DISTANCE`, calibrated in X1b (decision 003, run bc6031fc): a hit at similarity
0.70 or more. Every answerable Q&A question's best hit is at 0.747 or more, and provision recall
in the top 5 stays at its uncut value (0.851) from 0.30 on, while 7 of 9 unanswerable questions,
13 of 14 off-topic strings and 5 of 6 questions on another act's article fall below it."""

DEFAULT_MIN_KEYWORD_IDF = 24.0
"""`SEARCH_MIN_KEYWORD_IDF`, calibrated in X1b (decision 003, run bc6031fc): above the best
keyword hit of every unanswerable question and off-topic string (at most 21.3), so keywords alone
never make them found; it lets 6 long Annex descriptions whose best hit is under 0.70 count as
found. The summed IDF grows with the query's length, so a long off-topic text could pass it."""


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
    langsmith_endpoint: str | None = None
    """The LangSmith API the traces go to and are read from; an EU-region account needs
    https://eu.api.smith.langchain.com. Unset or empty: the SDK's default (the US region)."""

    # Model ids (OpenRouter slugs; confirmed by stories X2 and X3)
    engine_model: str | None = None
    engine_provider: str | None = None
    judge_model: str | None = None
    judge_backup_model: str | None = None
    # The second-model label filter (B9): Claude Haiku 4.5 on its EU zero-retention endpoint
    # (decision 005), pinned with fallbacks off; override both together.
    label_filter_model: str = "anthropic/claude-haiku-4.5"
    label_filter_provider: str = "google-vertex/europe"
    # Refused requests (decision 033): a request the engine provider's content filter refuses
    # goes once to this second model, pinned to its provider with fallbacks off.
    refusal_model: str | None = None
    refusal_provider: str | None = None
    # RAGAS (V6): Gemini 3.1 Flash-Lite on its EU zero-retention endpoint (decision 005), the
    # only model ids with a default; override both together, since the provider is pinned.
    ragas_model: str = "google/gemini-3.1-flash-lite"
    ragas_provider: str = "google-vertex/eu"
    embedding_model: str | None = None
    embedding_provider: str | None = None
    embedding_dimensions: int = 1536
    # The task text put before every search query (documents get none). Changing it changes every
    # query vector: re-record tests/recordings/db/test_search_ai_act/ (decision 003).
    embedding_query_instruction: str = Field(default=DEFAULT_QUERY_INSTRUCTION, min_length=1)

    # Search: the meaning arm's cosine-distance cut-off for Q&A and MCP (C8); None = no cut-off.
    # The engine searches without one. Calibrated in X1b (decision 003).
    search_max_distance: float | None = Field(default=DEFAULT_SEARCH_MAX_DISTANCE, ge=0.0, le=2.0)
    # The summed keyword IDF from which a keyword-only hit still counts as found (C8, X1b).
    search_min_keyword_idf: float = Field(default=DEFAULT_MIN_KEYWORD_IDF, ge=0.0)

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
    # Questions (P7): each one is a model call, cheaper than a classification.
    rate_limit_qa: int = Field(default=20, ge=1)
    # Word and PDF files: rendering one costs up to seconds of CPU, so few per client address
    # per minute, and few at once, each in one of this many worker processes (one more is refused
    # at once, 503). A render past the time limit is stopped and refused (413).
    rate_limit_exports: int = Field(default=10, ge=1)
    export_max_concurrent: int = Field(default=2, ge=1)
    export_timeout_seconds: float = Field(default=10.0, gt=0)
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
