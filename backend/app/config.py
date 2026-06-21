"""Application configuration — loaded from environment variables via pydantic-settings."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Agent Factory.

    All values load from environment variables or .env file.
    Prefix AGENT_FACTORY_ is used for all custom env vars.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Mode flags ──────────────────────────────────────────────
    dev_mode: bool = Field(
        default=False,
        validation_alias="AGENT_FACTORY_DEV",
        description="Use SQLite instead of PostgreSQL (AGENT_FACTORY_DEV=1).",
    )

    mock_mode: bool = Field(
        default=False,
        validation_alias="AGENT_FACTORY_MOCK",
        description="Use MockProvider instead of DeepSeek (AGENT_FACTORY_MOCK=1).",
    )

    # ── Database ────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/agentfactory"
    )
    """Async database URL. Defaults to local PostgreSQL."""

    @property
    def resolved_database_url(self) -> str:
        """Return the effective database URL.

        When dev_mode is True, use SQLite instead of PostgreSQL.
        """
        if self.dev_mode:
            return "sqlite+aiosqlite:///agentfactory.db"
        return self.database_url

    # ── DeepSeek ────────────────────────────────────────────────
    deepseek_api_key: str = ""
    """DeepSeek API key (required for non-mock mode)."""

    deepseek_base_url: str = "https://api.deepseek.com/v1"
    """DeepSeek API base URL."""

    deepseek_model: str = "deepseek-chat"
    """Default model for chat completions."""

    # ── JWT Auth ────────────────────────────────────────────────
    jwt_secret: str = "change-me-in-production"
    """Secret key for JWT token signing. CHANGE IN PRODUCTION."""

    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ── CORS ────────────────────────────────────────────────────
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    """Allowed CORS origins for the frontend dev server."""

    # ── Run Configuration ───────────────────────────────────────
    runs_directory: str = "runs"
    """Directory where per-run working directories and artifacts are stored."""

    default_budget_limit_usd: float = 0.0
    """Default budget limit per run in USD (0 = unlimited)."""

    # ── HITL ────────────────────────────────────────────────────
    hitl_enabled_default: bool = True
    """Default HITL (Human-In-The-Loop) setting for new runs."""

    # ── Retry Budgets ───────────────────────────────────────────
    spec_design_max_retries: int = 1
    develop_verify_max_loops: int = 2
    develop_review_max_loops: int = 2


# Singleton instance
settings = Settings()
