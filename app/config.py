"""Typed application configuration loaded from environment variables and `.env`.

Uses Pydantic Settings so every value is validated and typed at startup.
No credentials or secrets are hardcoded here — secrets must come from the
environment (or local `.env`, which is gitignored). See `.env.example`.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Loaded once via :func:`get_settings`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # Application metadata
    # ------------------------------------------------------------------
    app_name: str = Field(default="accord", description="Human-readable app name.")
    app_version: str = Field(default="0.1.0", description="Application version.")
    app_env: Literal["development", "staging", "production", "test"] = Field(
        default="development", description="Deployment environment."
    )
    debug: bool = Field(default=False, description="Enable debug mode.")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Root log level."
    )
    host: str = Field(default="0.0.0.0", description="Bind host.")
    port: int = Field(default=8000, description="Bind port.")

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins. Comma-separated string or JSON list in env.",
    )
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"])

    # ------------------------------------------------------------------
    # LLM provider (vendor-neutral — resolved by app.services.llm.factory)
    # ------------------------------------------------------------------
    llm_provider: Literal["tensormux", "google"] = Field(
        default="tensormux", description="LLM provider name."
    )
    llm_api_key: SecretStr | None = Field(
        default=None,
        description="Generic LLM API key fallback. Prefer provider-specific keys.",
    )
    llm_model: str | None = Field(
        default=None,
        description="Generic model override. When set, wins over provider models.",
    )
    llm_base_url: str | None = Field(
        default=None, description="Generic base-URL override (TensorMux only)."
    )
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1024, gt=0)

    # ------------------------------------------------------------------
    # TensorMux (OpenAI-compatible; default model GLM-4.7-Flash)
    # ------------------------------------------------------------------
    tensormux_api_key: SecretStr | None = Field(default=None)
    tensormux_base_url: str = Field(default="https://api.tensormux.com/v1")
    tensormux_model: str = Field(default="zai-org/GLM-4.7-Flash")

    # ------------------------------------------------------------------
    # Google (google-genai SDK; default model gemini-3.8-flash)
    # ------------------------------------------------------------------
    google_api_key: SecretStr | None = Field(default=None)
    google_model: str = Field(default="gemini-3.8-flash")

    # ------------------------------------------------------------------
    # NeatLogs (mirrors `neatlogs.init()` — see https://docs.neatlogs.com/sdk/python)
    # ------------------------------------------------------------------
    neatlogs_enabled: bool = Field(
        default=True,
        description="Gate `neatlogs.init()` locally. SDK itself exports nothing without an API key.",
    )
    neatlogs_api_key: SecretStr | None = Field(
        default=None,
        description="Maps to `neatlogs.init(api_key=...)`, else NEATLOGS_API_KEY env. Never hardcode.",
    )
    neatlogs_endpoint: str = Field(
        default="https://ingest.neatlogs.com",
        description="Maps to `neatlogs.init(endpoint=...)`. Export is normalized to {base}/v1/traces.",
    )
    neatlogs_workflow_name: str = Field(
        default="accord-server",
        description="Maps to `neatlogs.init(workflow_name=...)`. SDK defaults to script filename.",
    )
    neatlogs_capture_logs: bool = Field(
        default=False, description="Maps to `neatlogs.init(capture_logs=...)`. Opt-in LOG spans."
    )
    neatlogs_sample_rate: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Maps to `neatlogs.init(sample_rate=...)`."
    )
    neatlogs_flush_interval: float = Field(
        default=5.0, gt=0.0, description="Maps to `neatlogs.init(flush_interval=...)` seconds."
    )
    neatlogs_batch_size: int = Field(
        default=100, gt=0, description="Maps to `neatlogs.init(batch_size=...)`."
    )
    neatlogs_debug: bool = Field(
        default=False, description="Maps to `neatlogs.init(debug=...)` verbose stderr."
    )

    # ------------------------------------------------------------------
    # Execution provider
    # ------------------------------------------------------------------
    execution_provider: str = Field(
        default="local", description="Code/tool execution backend name."
    )
    execution_api_key: SecretStr | None = Field(default=None)
    execution_base_url: str | None = Field(default=None)
    execution_timeout_seconds: int = Field(default=60, gt=0)

    # ------------------------------------------------------------------
    # Database (placeholders — no live DB wired yet)
    # ------------------------------------------------------------------
    database_url: str | None = Field(
        default=None,
        description="Full database URL, e.g. postgresql+asyncpg://user:pass@host:5432/db.",
    )
    database_host: str = Field(default="localhost")
    database_port: int = Field(default=5432)
    database_name: str | None = Field(default=None)
    database_user: str | None = Field(default=None)
    database_password: SecretStr | None = Field(default=None)
    database_echo: bool = Field(default=False, description="Echo SQL statements.")

    # ------------------------------------------------------------------
    # Validators / helpers
    # ------------------------------------------------------------------
    @field_validator("cors_origins", "cors_allow_methods", "cors_allow_headers", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        """Accept comma-separated strings (from .env) as well as real lists."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                # Let pydantic parse JSON-style lists like '["a", "b"]'.
                return value
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def neatlogs_init_kwargs(self) -> dict:
        """Kwargs for `neatlogs.init(...)`. Call `load_dotenv()` before `init()`.

        Per docs: call `init()` once, before importing auto-instrumented
        libraries. `wrap()` has no such ordering rule. Omit `api_key` when
        unset — SDK creates spans but does not export.
        """
        kwargs: dict = {
            "workflow_name": self.neatlogs_workflow_name,
            "endpoint": self.neatlogs_endpoint,
            "capture_logs": self.neatlogs_capture_logs,
            "sample_rate": self.neatlogs_sample_rate,
            "flush_interval": self.neatlogs_flush_interval,
            "batch_size": self.neatlogs_batch_size,
            "debug": self.neatlogs_debug,
        }
        if self.neatlogs_api_key is not None:
            kwargs["api_key"] = self.neatlogs_api_key.get_secret_value()
        return kwargs


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance."""
    return Settings()


# Convenient module-level singleton for `from app.config import settings`.
settings = get_settings()
