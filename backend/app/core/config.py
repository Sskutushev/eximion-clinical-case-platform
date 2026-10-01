from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (12-factor)."""

    # Repo-root .env when run from backend/, or a local one; real env vars always win.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["local", "test", "production"] = "local"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://eximion:eximion@127.0.0.1:5433/eximion"
    )
    # Cloud Run multiplies connections by instance count: keep per-instance pool small.
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=2, ge=0, le=50)
    db_pool_timeout_seconds: int = Field(default=10, ge=1, le=120)
    # Fail fast when the database is unreachable instead of hanging a request slot.
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60)
    admin_api_key: SecretStr | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def _fail_closed_in_production(self) -> Self:
        if self.environment == "production" and not self.admin_api_key:
            raise ValueError("ADMIN_API_KEY must be set when ENVIRONMENT=production")
        return self

    @property
    def docs_enabled(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
